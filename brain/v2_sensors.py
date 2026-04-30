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
