import asyncio
import os
import sys
from pathlib import Path
sys.path.insert(0, os.path.expanduser("~/AI"))

from friday.brain.v2_sensors import SensorSuite, FileSensor

async def test_proactive_trigger():
    print("--- INITIATING NERVOUS SYSTEM TEST ---")
    trigger_file = Path("/tmp/friday_signal.txt")
    if trigger_file.exists(): trigger_file.unlink()
    
    suite = SensorSuite()
    suite.add_sensor(FileSensor(name="TradingWatchdog", path=trigger_file, trigger_phrase="PANIC", interval=0.1))
    
    # Callback to verify signal reception
    received = asyncio.Event()
    
    async def handle_signal(signal):
        print(f"✅ Handler Received Signal: {signal.data}")
        received.set()

    # Start Sensors and Listener
    sensor_task = asyncio.create_task(suite.start())
    listener_task = asyncio.create_task(suite.listen(handle_signal))
    
    # Wait for sensors to spin up
    await asyncio.sleep(0.5)
    
    # Trigger the event
    print("Writing PANIC signal to file...")
    with open(trigger_file, "w") as f:
        f.write("PANIC: Drawdown at 10%")
        
    try:
        await asyncio.wait_for(received.wait(), timeout=2.0)
        print("✅ SUCCESS: Real-time signal propagation verified.")
    except asyncio.TimeoutError:
        print("❌ FAILURE: Signal lost in transit.")
    
    # Cleanup
    sensor_task.cancel()
    listener_task.cancel()

if __name__ == "__main__":
    asyncio.run(test_proactive_trigger())
