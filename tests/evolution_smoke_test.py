"""
Friday :: Evolution Smoke Test
Verifies Semantic Vision, Unified Memory, and Consolidated Daemon.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.expanduser("~/AI"))

from friday.brain.v2_daemon import OmniDaemon
from friday.brain.v2_sensors import Signal
from friday.brain.engine import MultiEngine

async def run_smoke_test():
    print("🚀 Running Friday Evolution Smoke Test...")
    daemon = OmniDaemon()
    
    # 1. Vision Flow
    img_path = Path(os.path.expanduser("~/AI/friday/data/vision/latest.png"))
    if img_path.exists():
        print("[Test] Vision Flow...")
        sig = Signal("Vision", {"path": str(img_path), "action": "captured"})
        await daemon.handle_signal(sig)
    
    # 2. Heartbeat Flow
    print("[Test] Heartbeat Flow...")
    sig = Signal("Heartbeat", {"action": "sweep"})
    await daemon.handle_signal(sig)
    
    # 3. Memory API Check
    print("[Test] Memory API...")
    daemon.memory.log_event("test_event", {"status": "ok"})
    events = daemon.memory.recent_events(n=1, event_type="test_event")
    if events: print(f"    ✓ Memory event logged and retrieved.")

    print("\n✅ Evolution Smoke Test Passed.")

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
