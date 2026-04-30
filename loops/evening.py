"""
Friday :: Evening Loop
Fires at 22:00. Asks Bhargav for scorecard numbers, logs them, produces debrief.
For v0.1: pushes a prompt with the day's auto-detected stats + asks for confirmation.
"""
from __future__ import annotations
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~"))

from friday.actions import nexus, comms
from friday.brain.engine import MultiEngine
from friday.brain.memory import Memory
from friday.brain.personality import system_prompt


def evening_debrief() -> str:
    now = datetime.now()
    is_sunday = now.weekday() == 6
    if is_sunday:
        return ("*Good night, Bhargav.* Sunday log skipped. "
                "New week starts tomorrow. 6 AM.")

    snap = nexus.snapshot()
    crm = snap["agency"]["crm"]
    clients = snap["agency"]["clients"]

    # What happened today?
    mem = Memory()
    events_today = [e for e in mem.recent_events(n=200)
                    if e["ts"].startswith(now.strftime("%Y-%m-%d"))]

    prompt = f"""It's {now.strftime('%A %d %b %Y')} 22:00. End of day.

TODAY'S STATE:
- Active clients: {clients.get('active', 0)}
- Total outreach this week: {crm.get('total_outreach', 0)}
- Replied: {crm.get('replied', 0)}
- Friday events today: {len(events_today)}

Write a 4-line debrief for Bhargav:
1. One-line verdict on today (win / grind / drift)
2. One number that matters
3. Tomorrow's ONE priority
4. Reminder: log your scorecard tonight: `python3 ~/agency/content/weekly_scorecard.py add`

Dry, direct, honest."""

    eng = MultiEngine()
    debrief, _ = eng.ask(system_prompt(task_hint="evening debrief"), prompt, force="ollama")

    header = "*🌙 Friday :: Debrief*"
    msg = f"{header}\n\n{debrief.strip()}"
    mem.log_event("evening_debrief", {"day": now.strftime("%Y-%m-%d")})
    return msg


def run() -> None:
    msg = evening_debrief()
    print(msg)
    comms.telegram_push(msg)
    comms.log_to_file("evening", msg[:1000])


if __name__ == "__main__":
    run()
