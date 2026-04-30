"""
Friday :: Autonomy Loop
The tick driver. Runs forever — every `tick_interval_minutes`, fires the
AutonomyEngine. This is the thread that makes Friday actually do things.
"""
from __future__ import annotations
import threading
import time
from datetime import datetime

from friday.brain.autonomy import AutonomyEngine


def run(stop_event: threading.Event | None = None,
        tick_interval_seconds: int | None = None) -> None:
    """
    Blocking. Call from a daemon worker thread.
    If stop_event is set, returns gracefully.
    """
    engine = AutonomyEngine()
    interval = tick_interval_seconds or (engine.tick_minutes * 60)
    stop = stop_event or threading.Event()

    print(f"🧠 Autonomy loop online. tick={interval}s level={engine.policy.autonomy_level}")

    # Wait 30s before first tick so daemon can finish boot
    for _ in range(30):
        if stop.is_set():
            return
        time.sleep(1)

    while not stop.is_set():
        try:
            result = engine.tick()
            now = datetime.now().strftime("%H:%M:%S")
            if result.goal_id:
                print(f"[{now}] 🎯 tick: goal={result.goal_id} "
                      f"exec={result.steps_executed} queued={result.steps_queued} "
                      f"blocked={result.steps_blocked}")
            else:
                print(f"[{now}] ⏸ tick: {result.skipped_reason}")
        except Exception as e:
            print(f"[autonomy error] {e}")
        # sleep in 1s chunks for responsive shutdown
        for _ in range(interval):
            if stop.is_set():
                return
            time.sleep(1)


if __name__ == "__main__":
    run()
