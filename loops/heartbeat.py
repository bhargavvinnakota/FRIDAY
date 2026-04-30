"""
Friday :: Heartbeat Loop
Runs every N minutes. Sweeps sensor state, flags anomalies, pushes proactively.

Rules:
  - Respect quiet hours (23:00-05:30): log only, no push.
  - Respect day-job hours (09:00-18:00): only push for critical alerts.
  - Skip Sundays entirely (rest rule).
  - Never repeat the same alert within 4 hours.
"""
from __future__ import annotations
import json
import os
import sys
import time
from datetime import datetime, time as dtime
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~"))

from friday.actions import nexus, comms
from friday.brain.memory import Memory


ALERT_COOLDOWN_SECONDS = 4 * 3600  # 4 hours


def _in_quiet_hours(now: datetime) -> bool:
    t = now.time()
    # 23:00-05:30
    return t >= dtime(23, 0) or t < dtime(5, 30)


def _in_day_job(now: datetime) -> bool:
    t = now.time()
    return dtime(9, 0) <= t < dtime(18, 0)


def _is_sunday(now: datetime) -> bool:
    return now.weekday() == 6


def _recently_alerted(mem: Memory, alert_key: str) -> bool:
    for e in mem.recent_events(n=50, event_type="alert"):
        if e["data"].get("key") == alert_key:
            ts = datetime.fromisoformat(e["ts"])
            if (datetime.now() - ts).total_seconds() < ALERT_COOLDOWN_SECONDS:
                return True
    return False


def _send_alert(mem: Memory, key: str, text: str, critical: bool = False) -> None:
    now = datetime.now()
    if _is_sunday(now):
        return  # rest rule
    if _recently_alerted(mem, key):
        return

    in_quiet = _in_quiet_hours(now)
    in_day_job = _in_day_job(now)

    if in_quiet and not critical:
        comms.log_to_file("suppressed_alert", f"[{key}] {text}")
        return
    if in_day_job and not critical:
        comms.log_to_file("suppressed_alert", f"[{key}] {text}")
        return

    comms.telegram_push(f"🔔 *{key}*\n{text}", silent=not critical)
    mem.log_event("alert", {"key": key, "text": text[:300], "critical": critical})


def sweep(mem: Memory) -> dict:
    """One sensor sweep. Returns summary + fires alerts."""
    now = datetime.now()
    findings = {"ts": now.isoformat(), "alerts": []}

    # --- Agency sensor ---
    crm = nexus.crm_summary()
    leads = nexus.leads_summary()

    # Rule: if <20 outreach by Wed 6pm, flag
    if now.weekday() in (2, 3, 4) and now.hour >= 18:
        outreach = crm.get("total_outreach", 0)
        if outreach < 20:
            _send_alert(mem, "outreach_low",
                        f"Only {outreach} outreach this week. Target was 100. Ship tonight.",
                        critical=False)
            findings["alerts"].append("outreach_low")

    # --- Trading sensor ---
    tr = nexus.trading_state()
    if isinstance(tr, dict):
        positions = tr.get("open_positions", 0)
        pnl = tr.get("daily_pnl") or tr.get("pnl_today") or 0
        # Rule: intraday loss > 2% → critical
        if isinstance(pnl, (int, float)) and pnl < -2000:
            _send_alert(mem, "trading_drawdown",
                        f"Intraday P&L: ₹{pnl}. Check trading bot.",
                        critical=True)
            findings["alerts"].append("trading_drawdown")

    # --- Empire dashboard health ---
    emp = nexus.empire_status()
    if emp.get("status") == "offline":
        findings["empire"] = "offline"
        # non-critical — just log

    # --- Content cadence ---
    if now.weekday() in (0, 2, 4) and now.hour >= 12:
        # Mon/Wed/Fri after noon: has a post gone out?
        posts_archive = Path(os.path.expanduser("~/agency/content/posts_archive"))
        if posts_archive.exists():
            today = now.strftime("%Y-%m-%d")
            today_posts = [p for p in posts_archive.glob(f"{today}*")]
            if not today_posts:
                _send_alert(mem, "content_missing",
                            f"Today is a post day ({'Mon' if now.weekday()==0 else 'Wed' if now.weekday()==2 else 'Fri'}). No post archived yet.",
                            critical=False)
                findings["alerts"].append("content_missing")

    mem.log_event("heartbeat", findings)
    return findings


def run_loop(interval_minutes: int = 60) -> None:
    mem = Memory()
    print(f"💓 Friday heartbeat online (every {interval_minutes}min)")
    while True:
        try:
            findings = sweep(mem)
            print(f"[{findings['ts']}] sweep ok — alerts: {findings.get('alerts', [])}")
        except Exception as e:
            print(f"[heartbeat error] {e}")
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    # Run one sweep and exit (for testing)
    mem = Memory()
    print(json.dumps(sweep(mem), indent=2, default=str))
