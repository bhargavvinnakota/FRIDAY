from __future__ import annotations

from friday.brain.nervous_system import append_event, read_events, stats

from .registry import Operation, Skill, SkillResult


class NervousSystemSkill(Skill):
    name = "nervous_system"
    description = "Event-sourced nervous system: records observations, tool calls, proofs, and state changes."

    def _register_operations(self) -> None:
        self.register_op(Operation("status", "Summarize nervous-system event volume.", fn=self.op_status, risk="low"))
        self.register_op(Operation("recent", "Return recent nervous-system events.", fn=self.op_recent, risk="low"))
        self.register_op(Operation("emit", "Emit a safe internal nervous-system event.", fn=self.op_emit, risk="low"))

    def op_status(self, **_) -> SkillResult:
        return SkillResult(ok=True, data=stats())

    def op_recent(self, limit: int = 20, event_type: str = "", source: str = "", **_) -> SkillResult:
        return SkillResult(ok=True, data={
            "events": read_events(
                limit=_int(limit, 20),
                event_type=event_type or None,
                source=source or None,
            )
        })

    def op_emit(self, event_type: str = "internal_note", source: str = "friday",
                message: str = "", **_) -> SkillResult:
        event = append_event(event_type, source=source, payload={"message": message}, entity_refs=["friday"])
        return SkillResult(ok=True, data=event.to_dict())


def _int(value, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default

