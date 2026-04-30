#!/usr/bin/env python3
"""
Friday :: 24/7 Daemon (v1.0)
Runs forever. Four concurrent threads:
  1. Telegram sense       — listen + respond + /yes /no /hold approvals
  2. Heartbeat            — hourly sensor sweep + proactive alerts
  3. Scheduler            — morning (06:00) + evening (22:00) triggers
  4. Autonomy loop        — tick-driven goal execution (15-min default)

Launch:
    python3 -m friday.daemon
Or via PM2:
    pm2 start ~/AI/friday/daemon.py --interpreter python3 --name friday
    pm2 save
"""
from __future__ import annotations
import os
import sys
import signal
import threading
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~"))

from friday.actions import comms
from friday.brain.memory import Memory


STOP = threading.Event()
FRIDAY = Path(os.path.expanduser("~/AI/friday"))
RESTART_MARKER = FRIDAY / "data" / "restart.requested"


def telegram_worker():
    try:
        from friday.senses.telegram_in import run_forever
        run_forever()
    except Exception as e:
        print(f"[telegram worker crashed] {e}")


def heartbeat_worker(interval_minutes: int = 60):
    from friday.loops.heartbeat import sweep
    mem = Memory()
    while not STOP.is_set():
        try:
            findings = sweep(mem)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 💓 alerts: {findings.get('alerts', [])}")
        except Exception as e:
            print(f"[heartbeat error] {e}")
        for _ in range(interval_minutes * 60):
            if STOP.is_set():
                return
            time.sleep(1)


def scheduler_worker():
    """Fires morning (06:00) and evening (22:00) every day. (Autonomy loop
    ALSO schedules these via goals.yaml — but scheduler here is a reliability
    belt-and-braces in case autonomy is disabled.)"""
    from friday.loops import morning as morning_loop
    from friday.loops import evening as evening_loop

    last_morning = None
    last_evening = None

    while not STOP.is_set():
        now = datetime.now()
        today = now.date()
        if now.hour == 6 and now.minute < 10 and last_morning != today:
            try:
                print("⏰ Morning loop firing...")
                morning_loop.run()
                last_morning = today
            except Exception as e:
                print(f"[morning error] {e}")
        if now.hour == 22 and now.minute < 10 and last_evening != today:
            try:
                print("⏰ Evening loop firing...")
                evening_loop.run()
                last_evening = today
            except Exception as e:
                print(f"[evening error] {e}")
        time.sleep(60)


def autonomy_worker():
    try:
        from friday.loops import autonomy_loop
        autonomy_loop.run(stop_event=STOP)
    except Exception as e:
        print(f"[autonomy worker crashed] {e}")


def restart_watcher():
    """If a skill writes ~/AI/friday/data/restart.requested, shut down cleanly
    so PM2/supervisor restarts us."""
    while not STOP.is_set():
        if RESTART_MARKER.exists():
            print("🔁 restart requested — shutting down cleanly")
            RESTART_MARKER.unlink(missing_ok=True)
            STOP.set()
            break
        time.sleep(5)


def graceful_shutdown(signum, frame):
    print("\n╔════════════════════════════╗")
    print("║  Friday :: shutting down   ║")
    print("╚════════════════════════════╝")
    STOP.set()
    try:
        comms.telegram_push("_Friday going offline._", silent=True)
    except Exception:
        pass
    time.sleep(2)
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    print("╔══════════════════════════════════════════════╗")
    print("║  F.R.I.D.A.Y :: DAEMON v1.0.0                ║")
    print("║  Autonomous Sovereign · 24/7 operation       ║")
    print("╚══════════════════════════════════════════════╝")
    print(f"PID: {os.getpid()}")
    print(f"Boot: {datetime.now().isoformat()}")
    print()

    # Ensure skills registry is initialized early (imports them all)
    from friday.skills.registry import get_registry
    reg = get_registry()
    print(f"  🧰 {len(reg.all())} skills registered: {', '.join(reg.all().keys())}")

    mem = Memory()
    mem.log_event("daemon_boot", {"pid": os.getpid(), "version": "1.0.0"})

    threads = [
        threading.Thread(target=telegram_worker, name="telegram", daemon=True),
        threading.Thread(target=heartbeat_worker, name="heartbeat", daemon=True, args=(60,)),
        threading.Thread(target=scheduler_worker, name="scheduler", daemon=True),
        threading.Thread(target=autonomy_worker, name="autonomy", daemon=True),
        threading.Thread(target=restart_watcher, name="restart_watcher", daemon=True),
    ]
    for t in threads:
        t.start()
        print(f"  ✓ {t.name} thread started")

    print("\nFriday is live. Ctrl-C to stop.\n")

    try:
        while not STOP.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        graceful_shutdown(None, None)


if __name__ == "__main__":
    main()
