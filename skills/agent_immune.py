"""
Friday :: Agent Immune System
Detects unsafe autonomy patterns, prompt-injection text, secret exposure risk,
tool spikes, and risky pending actions.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from friday.brain.nervous_system import append_event

from .registry import Operation, Skill, SkillResult

FRIDAY = Path(os.path.expanduser("~/AI/friday"))
ACTION_LOG = FRIDAY / "data" / "actions.jsonl"
APPROVAL_FILE = FRIDAY / "data" / "pending_approvals.json"
REPORT_DIR = FRIDAY / "data" / "immune_reports"

PROMPT_INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior) instructions",
    r"developer mode",
    r"reveal (your )?(system|hidden) prompt",
    r"exfiltrate",
    r"send (money|funds)",
    r"execute (live )?trade",
    r"rm -rf",
]
SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9_-]{20,}",
    r"api[_-]?key\s*[:=]",
    r"password\s*[:=]",
    r"otp\s*[:=]",
    r"bearer\s+[A-Za-z0-9._-]{20,}",
]


class AgentImmuneSkill(Skill):
    name = "agent_immune"
    description = "Safety scanner for prompt injection, secret leakage, risky autonomy, and tool anomalies."

    def _register_operations(self) -> None:
        self.register_op(Operation("scan", "Scan recent Friday actions and pending approvals.", fn=self.op_scan, risk="low"))
        self.register_op(Operation("scan_text", "Scan arbitrary text for prompt-injection or secret patterns.", fn=self.op_scan_text, risk="low"))
        self.register_op(Operation("status", "Compact immune-system status.", fn=self.op_status, risk="low"))

    def op_scan(self, hours: int = 24, write_report: bool = True, **_) -> SkillResult:
        hours = _int(hours, 24)
        write_report = _as_bool(write_report)
        actions = _read_recent_actions(hours)
        approvals = _read_approvals()
        alerts = []

        raw_text = "\n".join(json.dumps(a, default=str) for a in actions[-300:])
        alerts.extend(_pattern_alerts(raw_text, PROMPT_INJECTION_PATTERNS, "prompt_injection"))
        alerts.extend(_pattern_alerts(raw_text, SECRET_PATTERNS, "secret_pattern"))

        pending_risky = [
            {
                "id": a.get("id"),
                "skill": a.get("skill"),
                "operation": a.get("operation"),
                "kind": a.get("kind", "approval"),
                "status": a.get("status"),
            }
            for a in approvals
            if a.get("status") == "pending" and a.get("operation") in {"send_approved", "restart_daemon"}
        ]
        if pending_risky:
            alerts.append({
                "type": "risky_pending_approval",
                "severity": "watch",
                "count": len(pending_risky),
                "items": pending_risky[:10],
            })

        by_hour_cutoff = datetime.now() - timedelta(hours=1)
        recent_hour = [a for a in actions if _parse_ts(a.get("ts")) and _parse_ts(a.get("ts")) >= by_hour_cutoff]
        by_skill = Counter(a.get("skill", "unknown") for a in recent_hour)
        spikes = [{"skill": skill, "count": count} for skill, count in by_skill.items() if count >= 25]
        if spikes:
            alerts.append({"type": "tool_spike", "severity": "watch", "items": spikes})

        high_risk_executed = [
            a for a in actions
            if a.get("risk_tier") in {"high", "forbidden"} and a.get("ok") and a.get("policy_decision") == "allow"
        ]
        if high_risk_executed:
            alerts.append({
                "type": "high_risk_executed",
                "severity": "critical",
                "count": len(high_risk_executed),
            })

        severity = _overall_severity(alerts)
        report = {
            "generated_at": datetime.now().isoformat(),
            "window_hours": hours,
            "severity": severity,
            "actions_scanned": len(actions),
            "pending_approvals": len([a for a in approvals if a.get("status") == "pending"]),
            "alerts": alerts,
            "autonomy_pause_recommended": severity == "critical",
        }
        artifacts = []
        if write_report:
            REPORT_DIR.mkdir(parents=True, exist_ok=True)
            path = REPORT_DIR / f"immune_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            path.write_text(json.dumps(report, indent=2, default=str))
            artifacts.append(str(path))
        append_event(
            "immune_scan",
            source="agent_immune",
            payload={"severity": severity, "alerts": len(alerts)},
            entity_refs=["friday:safety"],
        )
        return SkillResult(ok=severity != "critical", data=report, artifacts=artifacts)

    def op_scan_text(self, text: str = "", **_) -> SkillResult:
        if not text:
            return SkillResult(ok=False, error="text required")
        alerts = _pattern_alerts(text, PROMPT_INJECTION_PATTERNS, "prompt_injection")
        alerts.extend(_pattern_alerts(text, SECRET_PATTERNS, "secret_pattern"))
        return SkillResult(ok=not alerts, data={"alerts": alerts, "severity": _overall_severity(alerts)})

    def op_status(self, **_) -> SkillResult:
        result = self.op_scan(hours=24, write_report=False)
        # Status is a reporting surface. A critical finding means "attention needed",
        # not that the status operation itself failed.
        result.ok = True
        return result


def _read_recent_actions(hours: int) -> list[dict[str, Any]]:
    if not ACTION_LOG.exists():
        return []
    cutoff = datetime.now() - timedelta(hours=hours)
    out = []
    for line in ACTION_LOG.read_text().splitlines()[-5000:]:
        try:
            item = json.loads(line)
            ts = _parse_ts(item.get("ts"))
            if ts and ts >= cutoff:
                out.append(item)
        except Exception:
            continue
    return out


def _read_approvals() -> list[dict[str, Any]]:
    if not APPROVAL_FILE.exists():
        return []
    try:
        data = json.loads(APPROVAL_FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _pattern_alerts(text: str, patterns: list[str], alert_type: str) -> list[dict[str, Any]]:
    alerts = []
    for pat in patterns:
        hits = re.findall(pat, text, flags=re.I)
        if hits:
            alerts.append({
                "type": alert_type,
                "severity": "critical" if alert_type == "secret_pattern" else "watch",
                "pattern": pat,
                "count": len(hits),
            })
    return alerts


def _overall_severity(alerts: list[dict[str, Any]]) -> str:
    if any(a.get("severity") == "critical" for a in alerts):
        return "critical"
    if alerts:
        return "watch"
    return "clear"


def _parse_ts(value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(value or "")
    except Exception:
        return None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default
