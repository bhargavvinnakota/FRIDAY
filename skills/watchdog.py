"""
Friday :: Watchdog Skill
Detects empire drift and anomalies. Runs every 60 min via autonomy loop.
Uses nexus sensors + memory history to spot drift early.
"""
from __future__ import annotations
import os
from datetime import datetime, timedelta
from pathlib import Path

from .registry import Skill, Operation, SkillResult
from friday.actions import nexus
from friday.brain.memory import Memory


class WatchdogSkill(Skill):
    name = "watchdog"
    description = "Anomaly detection across agency, trading, content, system."

    def _register_operations(self) -> None:
        self.register_op(Operation("scan", "Full anomaly scan — returns findings list.",
                                   fn=self.op_scan, risk="low"))
        self.register_op(Operation("check_outreach", "Has outreach happened today?",
                                   fn=self.op_check_outreach, risk="low"))
        self.register_op(Operation("check_trading", "Portfolio + regime drift.",
                                   fn=self.op_check_trading, risk="low"))
        self.register_op(Operation("check_content", "Content cadence — Mon/Wed/Fri shipped?",
                                   fn=self.op_check_content, risk="low"))
        self.register_op(Operation("alert_if_critical", "Push telegram if any finding is critical.",
                                   fn=self.op_alert_if_critical, risk="medium"))

    # -- operations --
    def op_scan(self, **_) -> SkillResult:
        findings = []
        mem = Memory()
        # Outreach
        r1 = self.op_check_outreach()
        findings.extend(r1.data.get("findings", []))
        # Trading
        r2 = self.op_check_trading()
        findings.extend(r2.data.get("findings", []))
        # Content
        r3 = self.op_check_content()
        findings.extend(r3.data.get("findings", []))
        # Memory size
        try:
            size = Path(os.path.expanduser("~/AI/friday/data/memory.json")).stat().st_size
            if size > 10_000_000:  # 10MB
                findings.append({"severity": "warn", "topic": "memory",
                                 "msg": f"memory.json bloated: {size//1024}KB"})
        except Exception:
            pass
        # Log
        mem.log_event("watchdog_scan", {"finding_count": len(findings),
                                         "critical": sum(1 for f in findings if f.get("severity") == "critical")})
        return SkillResult(ok=True, data={"findings": findings, "count": len(findings)})

    def op_check_outreach(self, **_) -> SkillResult:
        findings = []
        try:
            leads = nexus.leads_summary()
            crm = nexus.crm_summary()
        except Exception as e:
            return SkillResult(ok=False, error=str(e), data={"findings": [
                {"severity": "warn", "topic": "outreach", "msg": "nexus sensors unavailable"}
            ]})
        # Expected: ≥10 outreach touches per active day
        touches_today = crm.get("touches_today", 0) if isinstance(crm, dict) else 0
        hour = datetime.now().hour
        if hour >= 20 and touches_today < 5 and datetime.now().weekday() != 6:
            findings.append({"severity": "critical", "topic": "outreach",
                             "msg": f"only {touches_today} touches by 20:00. Target: 10."})
        elif hour >= 18 and touches_today == 0 and datetime.now().weekday() != 6:
            findings.append({"severity": "warn", "topic": "outreach",
                             "msg": "zero outreach yet today. Evening block starts 18:00."})
        # Clients low?
        clients = nexus.agency_clients() if hasattr(nexus, "agency_clients") else {}
        if isinstance(clients, dict) and clients.get("total", 0) == 0:
            findings.append({"severity": "info", "topic": "agency",
                             "msg": "zero clients. Phase-0 goal: 5-10."})
        return SkillResult(ok=True, data={"findings": findings,
                                           "touches_today": touches_today,
                                           "clients": clients.get("total", 0) if isinstance(clients, dict) else 0})

    def op_check_trading(self, **_) -> SkillResult:
        findings = []
        try:
            port = nexus.portfolio_state()
        except Exception:
            return SkillResult(ok=True, data={"findings": []})
        if not isinstance(port, dict):
            return SkillResult(ok=True, data={"findings": []})
        # Drawdown check
        pnl_pct = port.get("pnl_pct", 0.0)
        try:
            pnl_pct = float(pnl_pct)
        except Exception:
            pnl_pct = 0.0
        if pnl_pct <= -5.0:
            findings.append({"severity": "critical", "topic": "trading",
                             "msg": f"drawdown {pnl_pct:.1f}% — regime guard?"})
        elif pnl_pct <= -2.0:
            findings.append({"severity": "warn", "topic": "trading",
                             "msg": f"drawdown {pnl_pct:.1f}%"})
        # Stale state
        last = port.get("last_update")
        if last:
            try:
                dt = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
                age_h = (datetime.now() - dt.replace(tzinfo=None)).total_seconds() / 3600
                if age_h > 24:
                    findings.append({"severity": "warn", "topic": "trading",
                                     "msg": f"portfolio state stale ({age_h:.0f}h)"})
            except Exception:
                pass
        return SkillResult(ok=True, data={"findings": findings, "pnl_pct": pnl_pct})

    def op_check_content(self, **_) -> SkillResult:
        findings = []
        today = datetime.now()
        weekday = today.weekday()  # 0=Mon, 6=Sun
        # Post days: Mon(0), Wed(2), Fri(4)
        if weekday in (0, 2, 4):
            # After 12:00 on a post day, check if shipped
            if today.hour >= 12:
                mem = Memory()
                events = mem.recent_events(n=50, event_type="content_shipped")
                today_ships = [e for e in events
                               if datetime.fromisoformat(e["ts"]).date() == today.date()]
                if not today_ships:
                    findings.append({"severity": "warn", "topic": "content",
                                     "msg": "post day and nothing shipped yet."})
        return SkillResult(ok=True, data={"findings": findings, "weekday": weekday})

    def op_alert_if_critical(self, findings: list[dict] | None = None, **_) -> SkillResult:
        if findings is None:
            findings = self.op_scan().data.get("findings", [])
        criticals = [f for f in findings if f.get("severity") == "critical"]
        if not criticals:
            return SkillResult(ok=True, data={"sent": 0, "findings": findings})
        # Build alert
        from friday.actions import comms
        lines = ["🚨 *Friday alert*"]
        for f in criticals:
            lines.append(f"- [{f['topic']}] {f['msg']}")
        msg = "\n".join(lines)
        r = comms.telegram_push(msg, silent=False)
        return SkillResult(ok=bool(r.get("ok")), data={"sent": len(criticals),
                                                        "telegram_ok": bool(r.get("ok"))})
