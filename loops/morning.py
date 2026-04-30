"""
Friday :: Morning Loop
Fires at 06:00. Runs the daily briefing, adds Friday's commentary, pushes to Telegram.
"""
from __future__ import annotations
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.expanduser("~"))

from friday.actions import nexus, comms
from friday.brain.engine import MultiEngine
from friday.brain.memory import Memory
from friday.brain.personality import system_prompt


def morning_briefing() -> str:
    """Generate Friday's morning message — briefing + commentary + priorities."""
    now = datetime.now()
    is_sunday = now.weekday() == 6

    if is_sunday:
        return (f"*Good morning, Bhargav.* It's Sunday {now.strftime('%d %b')}.\n\n"
                "_Rest day. Non-negotiable._\n\n"
                "No briefing. No trading alerts. No content cadence. "
                "Recharge. Friday will see you Monday 6 AM.")

    # Base briefing from existing script
    base = nexus.run_daily_briefing(telegram=False)

    # Friday's own layer: top-3 priorities from memory + snapshot
    snap = nexus.snapshot()
    eng = MultiEngine()
    mem = Memory()

    prompt = f"""It's {now.strftime('%A, %d %B %Y')} at {now.strftime('%H:%M')}.

Empire snapshot:
- Agency clients: {snap['agency']['clients'].get('active', 0)} active / {snap['agency']['clients'].get('total', 0)} total
- Leads: {snap['agency']['leads'].get('total', 0)} ({snap['agency']['leads'].get('with_phone', 0)} with phone)
- CRM: {snap['agency']['crm']}
- Trading regime: {snap['trading'].get('regime', 'no data') if isinstance(snap['trading'], dict) else 'no data'}

Write Friday's morning commentary for Bhargav — 3-5 lines max.
- What matters TODAY (not next week)
- One specific action he should do FIRST this morning
- If the numbers are off, call it out
- Zero fluff. No greetings. No sign-off. Just signal."""

    commentary, _ = eng.ask(system_prompt(task_hint="morning commentary"), prompt, force="ollama")

    day_name = now.strftime("%A")
    header = f"*🧠 Friday :: {day_name} {now.strftime('%d %b')}*"
    msg = f"{header}\n\n{commentary.strip()}\n\n---\n{base}"

    mem.log_event("morning_briefing", {"day": day_name})
    return msg


def run() -> None:
    msg = morning_briefing()
    print(msg)
    comms.telegram_push(msg)
    comms.log_to_file("morning", msg[:1000])


if __name__ == "__main__":
    run()
