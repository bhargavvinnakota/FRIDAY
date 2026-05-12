"""
Friday :: Briefing Skill
Wraps morning/evening loops as skill operations so the autonomy engine
can dispatch them uniformly with all other capabilities.
"""
from __future__ import annotations
from datetime import datetime

from .registry import Skill, Operation, SkillResult


class BriefingSkill(Skill):
    name = "briefing"
    description = "Ship morning briefing + evening debrief via autonomy engine."

    def _register_operations(self) -> None:
        self.register_op(Operation("run_morning", "Ship the 06:00 morning briefing.",
                                   fn=self.op_run_morning, risk="medium"))
        self.register_op(Operation("run_evening", "Ship the 22:00 evening debrief.",
                                   fn=self.op_run_evening, risk="medium"))
        self.register_op(Operation("run_ad_hoc", "Ship an ad-hoc briefing (now).",
                                   fn=self.op_run_ad_hoc, risk="medium"))

    def op_run_morning(self, **_) -> SkillResult:
        try:
            from friday.loops import morning as m
            m.run()
            from friday.brain.memory import Memory
            Memory().log_event("briefing_shipped", {"kind": "morning",
                                                    "ts": datetime.now().isoformat()})
            return SkillResult(ok=True, data={"kind": "morning", "shipped": True})
        except Exception as e:
            return SkillResult(ok=False, error=str(e))

    def op_run_evening(self, **_) -> SkillResult:
        try:
            from friday.loops import evening as e_loop
            e_loop.run()
            from friday.brain.memory import Memory
            Memory().log_event("briefing_shipped", {"kind": "evening",
                                                    "ts": datetime.now().isoformat()})
            return SkillResult(ok=True, data={"kind": "evening", "shipped": True})
        except Exception as e:
            return SkillResult(ok=False, error=str(e))

    def op_run_ad_hoc(self, **_) -> SkillResult:
        try:
            from friday.actions import nexus, comms
            from friday.skills.connector_center import ConnectorCenterSkill
            snap = nexus.snapshot()
            connector_status = ConnectorCenterSkill().op_status().data or {}
            lines = [f"🤖 *Friday ad-hoc briefing* {datetime.now().strftime('%H:%M')}",
                     f"Empire status: {snap.get('empire', {}).get('status', '?')}"]
            if connector_status:
                lines.append(
                    f"Connector readiness: {connector_status.get('readiness_score', '?')}% "
                    f"(verified {connector_status.get('verified_connected_score', '?')}%)"
                )
                if connector_status.get("action_needed"):
                    broken = connector_status["action_needed"][0]
                    lines.append(f"Connector blocker: {broken.get('id', '?')} needs reconnect")
            for engine, data in snap.items():
                if isinstance(data, dict):
                    lines.append(f"- {engine}: {list(data.keys())[:3]}")
            comms.telegram_push("\n".join(lines)[:3900], silent=True)
            return SkillResult(ok=True, data=snap)
        except Exception as e:
            return SkillResult(ok=False, error=str(e))
