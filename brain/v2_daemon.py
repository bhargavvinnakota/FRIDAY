"""
Friday V2.5 :: THE OMNI-DAEMON
The Unified Sovereign Intelligence Engine. 
Unifies V2.0 (Schema), V2.1 (Graph), V2.2 (Memory), V2.3 (Sensors).
"""
import asyncio
import signal
import logging
from pathlib import Path

# V2 Components
from .v2_sensors import SensorSuite, FileSensor, TelegramSensor
from .v2_memory import VectorMemory
from .v2_mission import MissionGraph, MissionRunnerV2_1
from .v2_orchestrator import MissionRunnerV2 # For validation
from .engine import MultiEngine
from .orchestrator import Orchestrator
from friday.skills import get_registry
from friday.actions import comms

class OmniDaemon:
    def __init__(self):
        self.engine = MultiEngine()
        self.memory = VectorMemory()
        self.skills = get_registry()
        self.sensors = SensorSuite()
        self.runner = MissionRunnerV2_1(self.engine, self.skills)
        self.orch = Orchestrator(self.engine, self.memory)
        self.active = True

    async def handle_signal(self, sig):
        """Processes signals from the Nervous System and spawns missions."""
        print(f"🧠 OMNI-DAEMON: Handling Signal from [{sig.source}]")
        
        if sig.source == "Telegram":
            text = sig.data.get("text", "")
            chat_id = sig.data.get("chat_id")
            user = sig.data.get("user", "User")
            
            print(f"   📥 Processing Msg from {user}: {text[:50]}...")
            
            # Send immediate feedback to user
            comms.telegram_push("_Thinking..._", chat_id=chat_id, silent=True)
            
            try:
                # Use Orchestrator to respond. 
                # Orchestrator might be slow, so we run it in a thread.
                print(f"   -> Invoking Orchestrator for: {text[:30]}")
                res = await asyncio.to_thread(self.orch.respond, text, use_tools=True)
                reply = res.get("reply", "I'm sorry, I couldn't process that.")
                
                print(f"   -> Sending response to Telegram (len={len(reply)})")
                comms.telegram_push(reply, chat_id=chat_id)
            except Exception as e:
                error_msg = f"❌ Orchestrator Error: {type(e).__name__}: {e}"
                print(f"   {error_msg}")
                comms.telegram_push(error_msg, chat_id=chat_id)
            return

        if sig.source == "Vision":
            path = sig.data.get("path")
            print(f"   👁️ Vision Signal: Analyzing {path}...")
            try:
                # Trigger a vision analysis
                vision_skill = self.skills.get("vision")
                if vision_skill:
                    res = await asyncio.to_thread(vision_skill.invoke, "analyze_frame", path=path)
                    if res.ok:
                        analysis = res.data.get("analysis", "")
                        print(f"   ✅ Screen Analysis: {analysis[:100]}...")
                        # Store in memory
                        self.memory.add(f"Visual context at {sig.ts}: {analysis}")
                        # Update HUD
                        from .state_relay import update_hud_state
                        update_hud_state(status="ACTIVE", friday_output=f"Vision: {analysis[:50]}...")
                    else:
                        print(f"   ❌ Vision Analysis Failed: {res.error}")
            except Exception as e:
                print(f"   ⚠️ Vision Processing Error: {e}")
            return

        if sig.source == "Heartbeat":
            print(f"   💓 Heartbeat Signal: Running system sweep...")
            try:
                from friday.loops.heartbeat import sweep
                await asyncio.to_thread(sweep, self.memory)
            except Exception as e:
                print(f"   ⚠️ Heartbeat Error: {e}")
            return

        if sig.source == "Scheduler":
            loop_type = sig.data.get("loop")
            print(f"   ⏰ Scheduler Signal: Running {loop_type} loop...")
            try:
                if loop_type == "morning":
                    from friday.loops.morning import run as run_morning
                    await asyncio.to_thread(run_morning)
                elif loop_type == "evening":
                    from friday.loops.evening import run as run_evening
                    await asyncio.to_thread(run_evening)
            except Exception as e:
                print(f"   ⚠️ Scheduler Error: {e}")
            return

        if sig.source == "RestartWatcher":
            print("🔁 Restart requested via signal. Shutting down OmniDaemon...")
            await self.shutdown()
            # Remove the marker file
            try:
                Path("/Users/bhargav/AI/friday/data/restart.requested").unlink(missing_ok=True)
            except: pass
            return

        if sig.source == "AppSwitch":
            app = sig.data.get("app")
            print(f"   🍎 OS Signal: User switched to {app}.")
            self.memory.add(f"User switched active application to {app}.", category="os_event")
            return

        if sig.source.startswith("OS:"):
            msg = sig.data.get("message")
            print(f"   📜 OS Signal [{sig.source}]: {msg[:100]}...")
            # We don't save every log message, only if it looks critical
            if any(k in msg.lower() for k in ["fail", "crash", "error", "denied"]):
                self.memory.add(f"System Log Alert from {sig.source}: {msg}", category="system_alert")
            return

        # 1. Semantic Context Retrieval
        content = sig.data.get("content", "")
        print(f"   🔍 Signal Content: {content[:100]}...")
        context = self.memory.search(content, limit=3)
        print(f"   ✅ Semantic Context: {len(context)} facts retrieved.")

    async def shutdown(self):
        print("Omni-Daemon Shutting Down...")
        self.active = False

    async def run(self):
        print("--- FRIDAY V2 OMNI-DAEMON ONLINE ---")
        logging.info("Starting OmniDaemon...")
        
        try:
            # Configure Sensors
            if comms.telegram_direct_enabled():
                logging.info("Initializing TelegramSensor...")
                self.sensors.add_sensor(TelegramSensor())
            else:
                logging.info("Skipping TelegramSensor: OpenClaw owns Telegram.")
            
            logging.info("Initializing VisionSensor...")
            from .v2_sensors import VisionSensor
            self.sensors.add_sensor(VisionSensor(interval=15.0))

            logging.info("Initializing Heartbeat and Scheduler Sensors...")
            from .v2_sensors import HeartbeatSensor, SchedulerSensor, LogSensor, NativeEventSensor
            self.sensors.add_sensor(HeartbeatSensor(interval_minutes=60))
            self.sensors.add_sensor(SchedulerSensor())
            self.sensors.add_sensor(LogSensor())
            self.sensors.add_sensor(NativeEventSensor())

            logging.info("Initializing RestartWatcher Sensor...")
            self.sensors.add_sensor(FileSensor(
                name="RestartWatcher",
                path=Path("/Users/bhargav/AI/friday/data/restart.requested"),
                trigger_phrase="", # Any change/existence triggers
                interval=5.0
            ))
            
            logging.info("Initializing FileSensor for TradingAlert...")
            self.sensors.add_sensor(FileSensor(
                name="TradingAlert", 
                path=Path("/Users/bhargav/AI/friday/data/trading_signal.txt"),
                trigger_phrase="CRITICAL"
            ))

            # Start the Nervous System and the Signal Listener
            logging.info("Spawning sensor and listener tasks...")
            tasks = [
                asyncio.create_task(self.sensors.start()),
                asyncio.create_task(self.sensors.listen(self.handle_signal))
            ]
            
            print("OmniDaemon Tasks Spawned. Event loop running.")
            await asyncio.gather(*tasks)
        except Exception as e:
            print(f"OMNI-DAEMON CRITICAL ERROR: {e}")
            logging.error(f"OmniDaemon Error: {e}", exc_info=True)
        finally:
            await self.shutdown()

if __name__ == "__main__":
    daemon = OmniDaemon()
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        pass
