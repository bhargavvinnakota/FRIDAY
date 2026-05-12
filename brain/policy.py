"""
Friday :: Policy Gate
Gatekeeper between autonomous decisions and execution.
Enforces autonomy_level, risk classes, quiet windows, rate limits, hard gates.
"""
from __future__ import annotations
import json
import os
import threading
from collections import deque
from datetime import datetime, timedelta, time as dtime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None

POLICIES_PATH = Path(os.path.expanduser("~/AI/friday/config/policies.yaml"))

_DEFAULT_POLICY = {
    "autonomy_level": "supervised",
    "risk_classes": {
        "low": {"auto_approve_at": ["supervised", "trusted", "full"]},
        "medium": {"auto_approve_at": ["trusted", "full"]},
        "high": {"auto_approve_at": ["full"]},
        "forbidden": {"auto_approve_at": []},
    },
    "hard_gates": [],
    "rate_limits": {
        "telegram_pings_per_hour": 6,
        "outbound_messages_per_day": 30,
        "skill_invocations_per_hour": 60,
        "autonomy_ticks_per_hour": 4,
    },
    "quiet_windows": [],
    "critical_triggers": [],
}


class Policy:
    def __init__(self, path: Path | None = None):
        self.path = path or POLICIES_PATH
        self._lock = threading.RLock()
        self._invocation_times: deque = deque(maxlen=500)
        self._telegram_times: deque = deque(maxlen=200)
        self._reload()

    def _reload(self) -> None:
        if yaml is None or not self.path.exists():
            self._data = dict(_DEFAULT_POLICY)
            return
        with open(self.path) as f:
            self._data = yaml.safe_load(f) or dict(_DEFAULT_POLICY)

    @property
    def autonomy_level(self) -> str:
        return self._data.get("autonomy_level", "supervised")

    def in_quiet_window(self, now: datetime | None = None) -> tuple[bool, str, bool]:
        """
        Returns (in_window, window_name, allow_critical).
        Scans ALL matching windows and returns the MOST RESTRICTIVE (allow_critical=False wins).
        This ensures Sunday-rest (allow_critical=False) overrides day_job (allow_critical=True)
        when both match simultaneously.
        """
        now = now or datetime.now()
        matches: list[tuple[str, bool]] = []
        for w in self._data.get("quiet_windows", []):
            # Day-based window (e.g., sunday_full_rest)
            if w.get("day"):
                day_map = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                           "friday": 4, "saturday": 5, "sunday": 6}
                if now.weekday() == day_map.get(w["day"].lower(), -1):
                    matches.append((w.get("name", w["day"]), bool(w.get("allow_critical", False))))
                    continue
            start = w.get("start")
            end = w.get("end")
            if not start or not end:
                continue
            s_h, s_m = map(int, start.split(":"))
            e_h, e_m = map(int, end.split(":"))
            s = dtime(s_h, s_m)
            e = dtime(e_h, e_m)
            t = now.time()
            if s <= e:
                hit = s <= t <= e
            else:  # wraps midnight
                hit = t >= s or t <= e
            if hit:
                matches.append((w.get("name", "quiet"), bool(w.get("allow_critical", False))))

        if not matches:
            return False, "", True
        # Most restrictive: any match with allow_critical=False wins
        restrictive = [m for m in matches if not m[1]]
        if restrictive:
            return True, restrictive[0][0], False
        # Otherwise first match
        return True, matches[0][0], matches[0][1]

    def check(self, skill: str, operation: str, risk: str,
              critical: bool = False, now: datetime | None = None) -> dict:
        """
        Returns decision dict:
          {
            "allow": bool,
            "reason": str,
            "requires_approval": bool,   # if true, autonomy should queue for user
            "autonomy_level": str,
          }
        """
        now = now or datetime.now()
        with self._lock:
            # 1. Hard gate: forbidden by name or risk
            if risk == "forbidden":
                return {"allow": False, "reason": "forbidden risk class",
                        "requires_approval": False, "autonomy_level": self.autonomy_level,
                        "policy_decision": "deny"}
            for gate in self._data.get("hard_gates", []):
                if gate.lower() in f"{skill} {operation}".lower():
                    return {"allow": False, "reason": f"hard gate: {gate}",
                            "requires_approval": True, "autonomy_level": self.autonomy_level,
                            "policy_decision": "queue"}

            # 2. Autonomy off → always require approval
            if self.autonomy_level == "off":
                return {"allow": False, "reason": "autonomy disabled",
                        "requires_approval": True, "autonomy_level": "off",
                        "policy_decision": "queue"}

            # 3. Quiet window
            in_quiet, qname, allow_crit = self.in_quiet_window(now)
            if in_quiet:
                if critical and allow_crit:
                    pass  # allow piercing
                else:
                    return {"allow": False, "reason": f"quiet window: {qname}",
                            "requires_approval": False,
                            "autonomy_level": self.autonomy_level,
                            "policy_decision": "deny"}

            # 4. Risk class vs autonomy level
            rc = self._data.get("risk_classes", {}).get(risk, {})
            auto_at = rc.get("auto_approve_at", [])
            if self.autonomy_level not in auto_at:
                return {"allow": False,
                        "reason": f"risk={risk} requires higher autonomy than {self.autonomy_level}",
                        "requires_approval": True,
                        "autonomy_level": self.autonomy_level,
                        "policy_decision": "queue"}

            # 5. Rate limits
            limits = self._data.get("rate_limits", {})
            per_hour = limits.get("skill_invocations_per_hour", 60)
            cutoff = now - timedelta(hours=1)
            recent = sum(1 for t in self._invocation_times if t >= cutoff)
            if recent >= per_hour:
                return {"allow": False,
                        "reason": f"rate limit: {recent}/{per_hour} invocations/hr",
                        "requires_approval": False,
                        "autonomy_level": self.autonomy_level,
                        "policy_decision": "deny"}

            # Admit
            self._invocation_times.append(now)
            return {"allow": True, "reason": "ok",
                    "requires_approval": False,
                    "autonomy_level": self.autonomy_level,
                    "policy_decision": "allow"}

    def can_telegram(self, now: datetime | None = None) -> bool:
        now = now or datetime.now()
        per_hour = self._data.get("rate_limits", {}).get("telegram_pings_per_hour", 6)
        cutoff = now - timedelta(hours=1)
        with self._lock:
            recent = sum(1 for t in self._telegram_times if t >= cutoff)
            if recent >= per_hour:
                return False
            self._telegram_times.append(now)
            return True

    def describe(self) -> dict:
        return {
            "autonomy_level": self.autonomy_level,
            "quiet_windows": self._data.get("quiet_windows", []),
            "rate_limits": self._data.get("rate_limits", {}),
            "risk_classes": list(self._data.get("risk_classes", {}).keys()),
        }
