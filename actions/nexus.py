"""
Friday :: Nexus Integration Layer
Hooks into Bhargav's existing infrastructure:
  - Trading bot state (brain_state.json, portfolio.json)
  - Agency (clients registry, leads.csv, crm_tracker.csv)
  - Empire dashboard (:5055)
  - AuditMind (:8000)
  - Content generator, scorecard, deploy_bot, daily_briefing
"""
from __future__ import annotations
import csv
import json
import os
import subprocess
import urllib.request
from pathlib import Path

from friday.paths import NEXUS_ROOT


HOME = Path(os.path.expanduser("~"))


# ------------------ Trading ------------------
def trading_state() -> dict:
    p = NEXUS_ROOT / "trading-bot" / "brain_state.json"
    if not p.exists():
        return {"status": "no_data", "message": f"brain_state.json not found at {p}"}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception as e:
        return {"status": "error", "error": str(e)}


def portfolio_state() -> dict:
    p = NEXUS_ROOT / "trading-bot" / "portfolio.json"
    if not p.exists():
        return {"status": "no_data", "message": f"portfolio.json not found at {p}"}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ------------------ Agency ------------------
def agency_clients() -> dict:
    p = HOME / "agency" / "clients" / "clients_registry.json"
    if not p.exists():
        return {"total": 0, "active": 0, "clients": []}
    try:
        with open(p) as f:
            data = json.load(f)
        clients = data if isinstance(data, list) else data.get("clients", [])
        active = [c for c in clients if c.get("status") == "active"]
        return {"total": len(clients), "active": len(active), "clients": clients}
    except Exception:
        return {"total": 0, "active": 0, "clients": []}


def leads_summary() -> dict:
    p = HOME / "agency" / "outreach" / "leads.csv"
    if not p.exists():
        return {"total": 0, "with_phone": 0}
    total = 0
    with_phone = 0
    try:
        with open(p) as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += 1
                phone = (row.get("phone") or "").strip()
                if phone and phone.lower() not in ("", "none", "n/a"):
                    with_phone += 1
        return {"total": total, "with_phone": with_phone}
    except Exception:
        return {"total": 0, "with_phone": 0}


def crm_summary() -> dict:
    p = HOME / "agency" / "outreach" / "crm_tracker.csv"
    if not p.exists():
        return {"total_outreach": 0, "replied": 0, "qualified": 0, "closed": 0}
    counters = {"total_outreach": 0, "replied": 0, "qualified": 0, "closed": 0}
    try:
        with open(p) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not any((v or "").strip() for v in row.values()):
                    continue
                counters["total_outreach"] += 1
                stage = (row.get("stage") or row.get("Status") or row.get("Response") or "").lower()
                if stage == "sent_stub":
                    stage = "manual_sent"
                if stage in ("replied", "qualified", "closed"):
                    counters[stage] = counters.get(stage, 0) + 1
    except Exception:
        pass
    return counters


# ------------------ Empire Dashboard ------------------
def empire_status(url: str = "http://localhost:5055/api/status") -> dict:
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            return json.loads(r.read())
    except Exception:
        return {"status": "offline", "hint": f"start with: python3 {NEXUS_ROOT / 'command-center' / 'empire_dashboard.py'}"}


# ------------------ AuditMind ------------------
def auditmind_status(url: str = "http://localhost:8000/dashboard") -> dict:
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            return json.loads(r.read())
    except Exception:
        return {"status": "offline"}


# ------------------ Unified Snapshot ------------------
def snapshot() -> dict:
    """One-shot view of the entire empire. Friday's primary sensor sweep."""
    return {
        "trading": trading_state(),
        "portfolio": portfolio_state(),
        "agency": {
            "clients": agency_clients(),
            "leads": leads_summary(),
            "crm": crm_summary(),
        },
        "empire": empire_status(),
        "auditmind": auditmind_status(),
    }


# ------------------ Scorecard Log ------------------
def log_scorecard(metric: str, value) -> dict:
    """Append to ~/agency/content/scorecards.json (used by weekly_scorecard.py)."""
    p = HOME / "agency" / "content" / "scorecards.json"
    from datetime import datetime
    week = datetime.now().isocalendar().week
    entry = {metric: value, "ts": datetime.now().isoformat(), "week": week}
    data = []
    if p.exists():
        try:
            with open(p) as f:
                data = json.load(f)
        except Exception:
            data = []
    data.append(entry)
    with open(p, "w") as f:
        json.dump(data, f, indent=2)
    return {"ok": True, "entry": entry}


# ------------------ Run Daily Briefing ------------------
def run_daily_briefing(telegram: bool = False) -> str:
    script = NEXUS_ROOT / "command-center" / "daily_briefing.py"
    if not script.exists():
        return "[daily_briefing.py not found]"
    cmd = ["python3", str(script)]
    if telegram:
        cmd.append("--telegram")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return r.stdout or r.stderr or "[empty]"
    except Exception as e:
        return f"[error: {e}]"


if __name__ == "__main__":
    import json as _j
    print(_j.dumps(snapshot(), indent=2, default=str)[:2000])
