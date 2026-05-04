"""
Friday V2.3 :: Async Sensor Registry (The Nervous System)
Enables real-time reactivity to system and external events.
"""
import asyncio
import os
from pathlib import Path
from datetime import datetime

class Signal:
    def __init__(self, source: str, data: dict, priority: int = 1):
        self.source = source
        self.data = data
        self.priority = priority
        self.ts = datetime.now().isoformat()

class BaseSensor:
    def __init__(self, name: str, interval: float = 1.0):
        self.name = name
        self.interval = interval
        self.active = True

    async def watch(self, queue: asyncio.Queue):
        """Override this to implement specific monitoring logic."""
        pass

class FileSensor(BaseSensor):
    """Monitors a file for specific content/triggers."""
    def __init__(self, path: Path, trigger_phrase: str, **kwargs):
        super().__init__(**kwargs)
        self.path = path
        self.trigger_phrase = trigger_phrase

    async def watch(self, queue: asyncio.Queue):
        print(f"Sensor {self.name} watching {self.path}")
        last_mtime = 0
        while self.active:
            if self.path.exists():
                mtime = self.path.stat().st_mtime
                if mtime > last_mtime:
                    last_mtime = mtime
                    with open(self.path, "r") as f:
                        content = f.read().strip()
                        if self.trigger_phrase in content:
                            await queue.put(Signal(self.name, {"content": content}, priority=3))
            await asyncio.sleep(self.interval)

class TelegramSensor(BaseSensor):
    """Monitors Telegram for incoming messages."""
    def __init__(self, **kwargs):
        super().__init__(name="Telegram", interval=1.0)
        from friday.actions import comms
        self.comms = comms
        self.offset = self._load_offset()

    def _load_offset(self) -> int | None:
        path = Path(os.path.expanduser("~/AI/friday/data/telegram_offset.txt"))
        if path.exists():
            try: return int(path.read_text().strip())
            except: return None
        return None

    def _save_offset(self, offset: int):
        try:
            path = Path(os.path.expanduser("~/AI/friday/data/telegram_offset.txt"))
            path.write_text(str(offset))
        except Exception as e:
            print(f"Error saving telegram offset: {e}")

    async def watch(self, queue: asyncio.Queue):
        print(f"📡 Sensor {self.name}: Starting Telegram Poll Loop.")
        while self.active:
            try:
                # Use a shorter timeout for the poll to keep it responsive
                updates = await asyncio.to_thread(self.comms.telegram_get_updates, offset=self.offset, timeout=5)
                
                if updates:
                    print(f"📥 Telegram Sensor: Received {len(updates)} update(s).")
                    for u in updates:
                        self.offset = u["update_id"] + 1
                        self._save_offset(self.offset)
                        msg = u.get("message") or u.get("edited_message")
                        if msg and "text" in msg:
                            text = msg["text"]
                            chat_id = str(msg["chat"]["id"])
                            print(f"   -> Msg from {chat_id}: {text[:30]}...")
                            await queue.put(Signal(self.name, {
                                "text": text,
                                "chat_id": chat_id,
                                "user": msg.get("from", {}).get("first_name", "User")
                            }, priority=5))
                # else:
                #    print("   (no new telegram updates)")
                    
            except Exception as e:
                print(f"⚠️ TelegramSensor Error: {e}")
                
            await asyncio.sleep(self.interval)

import subprocess
from pathlib import Path
from datetime import datetime

class VisionSensor(BaseSensor):
    """Monitors the screen for visual state changes using native macOS tools."""
    def __init__(self, interval: float = 10.0, **kwargs):
        super().__init__(name="Vision", interval=interval)
        self.output_dir = Path(os.path.expanduser("~/AI/friday/data/vision"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def watch(self, queue: asyncio.Queue):
        print(f"👁️ Sensor {self.name}: Starting Screen Capture Loop.")
        while self.active:
            try:
                # Capture screen to a temporary file
                img_path = self.output_dir / "latest.png"
                # -x: silent mode
                res = await asyncio.to_thread(subprocess.run, ["screencapture", "-x", str(img_path)], capture_output=True)
                
                if res.returncode == 0:
                    # For now, we just signal that a new frame is ready.
                    # Future iterations will include CLIP or GPT-4o analysis here.
                    await queue.put(Signal(self.name, {
                        "path": str(img_path),
                        "action": "captured"
                    }, priority=1))
                else:
                    print(f"⚠️ VisionSensor Error: {res.stderr.decode()}")
                    
            except Exception as e:
                print(f"⚠️ VisionSensor Exception: {e}")
                
            await asyncio.sleep(self.interval)

class HeartbeatSensor(BaseSensor):
    """Fires a signal every hour for system maintenance and alerts."""
    def __init__(self, interval_minutes: int = 60, **kwargs):
        super().__init__(name="Heartbeat", interval=interval_minutes * 60)

    async def watch(self, queue: asyncio.Queue):
        print(f"💓 Sensor {self.name}: Starting Heartbeat Loop ({self.interval/60}m).")
        while self.active:
            await queue.put(Signal(self.name, {"action": "sweep"}, priority=2))
            await asyncio.sleep(self.interval)

class SchedulerSensor(BaseSensor):
    """Fires signals for morning (06:00) and evening (22:00) routines."""
    def __init__(self, **kwargs):
        super().__init__(name="Scheduler", interval=60.0)

    async def watch(self, queue: asyncio.Queue):
        print(f"⏰ Sensor {self.name}: Starting Scheduler Loop.")
        last_morning = None
        last_evening = None
        while self.active:
            now = datetime.now()
            today = now.date()
            if now.hour == 6 and now.minute < 10 and last_morning != today:
                await queue.put(Signal(self.name, {"loop": "morning"}, priority=4))
                last_morning = today
            if now.hour == 22 and now.minute < 10 and last_evening != today:
                await queue.put(Signal(self.name, {"loop": "evening"}, priority=4))
                last_evening = today
            await asyncio.sleep(self.interval)

class LogSensor(BaseSensor):
    """Streams the macOS Unified Log and filters for critical system signals."""
    def __init__(self, predicate: str = "type == error OR type == fault", **kwargs):
        super().__init__(name="LogStream", interval=0.1)
        self.predicate = predicate

    async def watch(self, queue: asyncio.Queue):
        print(f"📜 Sensor {self.name}: Starting Native Log Stream.")
        cmd = ["log", "stream", "--predicate", self.predicate, "--style", "ndjson"]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        
        while self.active:
            line = await process.stdout.readline()
            if not line: break
            try:
                import json
                event = json.loads(line.decode().strip())
                await queue.put(Signal(self.source_name(event), {
                    "message": event.get("eventMessage"),
                    "process": event.get("processImagePath")
                }, priority=2))
            except: continue

    def source_name(self, event):
        proc = (event.get("processImagePath", "") or "Unknown").split("/")[-1]
        return f"OS:{proc}"

class NativeEventSensor(BaseSensor):
    """Listens for native macOS events like app launches and system sleep."""
    def __init__(self, **kwargs):
        super().__init__(name="NativeEvents", interval=1.0)

    async def watch(self, queue: asyncio.Queue):
        print(f"🍎 Sensor {self.name}: Initializing Cocoa Event Listener.")
        try:
            from AppKit import NSWorkspace
            ws = NSWorkspace.sharedWorkspace()
            
            last_app = ""
            while self.active:
                front_app = ws.frontmostApplication().localizedName()
                if front_app != last_app:
                    await queue.put(Signal("AppSwitch", {"app": front_app}, priority=3))
                    last_app = front_app
                await asyncio.sleep(self.interval)
        except Exception as e:
            print(f"⚠️ NativeEventSensor Error: {e}")

class SensorSuite:
    def __init__(self):
        self.sensors = []
        self.signal_queue = asyncio.Queue()

    def add_sensor(self, sensor: BaseSensor):
        self.sensors.append(sensor)

    async def start(self):
        """Starts all sensors in the background."""
        tasks = [sensor.watch(self.signal_queue) for sensor in self.sensors]
        return asyncio.gather(*tasks)

    async def listen(self, callback):
        """Main loop to handle signals as they arrive."""
        print("Nervous System Active. Listening for signals...")
        while True:
            signal = await self.signal_queue.get()
            print(f"Signal Received: {signal.source} @ {signal.ts}")
            await callback(signal)
            self.signal_queue.task_done()
