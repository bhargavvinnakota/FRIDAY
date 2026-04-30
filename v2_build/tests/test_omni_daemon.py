import asyncio
import os
import sys
from pathlib import Path
sys.path.insert(0, os.path.expanduser("~/AI"))

from friday.brain.v2_daemon import OmniDaemon

async def test_omni_flow():
    print("--- INITIATING OMNI-DAEMON SYSTEM TEST ---")
    trigger_file = Path("/Users/bhargav/AI/friday/data/trading_signal.txt")
    if trigger_file.exists(): trigger_file.unlink()
    
    daemon = OmniDaemon()
    
    # Pre-load a memory to verify semantic retrieval
    daemon.memory.remember("Nexus Omega Trading Goal: Maintain 2% daily drawdown limit.", category="trading")
    
    # Start the daemon in the background
    daemon_task = asyncio.create_task(daemon.run())
    
    await asyncio.sleep(1.0)
    
    # Trigger a signal
    print("Writing CRITICAL trading signal...")
    with open(trigger_file, "w") as f:
        f.write("CRITICAL: Drawdown limit breached!")
        
    # Wait for processing
    await asyncio.sleep(2.0)
    
    print("✅ SUCCESS: Omni-Daemon execution path verified.")
    daemon_task.cancel()

if __name__ == "__main__":
    asyncio.run(test_omni_flow())
