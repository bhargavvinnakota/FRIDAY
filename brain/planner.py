"""
Friday :: Planner
Decomposes a goal into a concrete action sequence, respecting the
skill registry's actual capabilities and policy gate constraints.

Two planning modes:
  - deterministic: goal.yaml already lists (skill, operation) pairs → expand directly
  - llm: freeform goal text → LLM drafts step list → validated against registry

Deterministic mode is the v1.0 default (reliable on small models).
LLM mode kicks in when user issues `friday focus <freeform>`.
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, time as dtime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None

from friday.skills.registry import get_registry

GOALS_PATH = Path(os.path.expanduser("~/AI/friday/config/goals.yaml"))
PLAN_LOG = Path(os.path.expanduser("~/AI/friday/data/plans.jsonl"))


@dataclass
class Step:
    skill: str
    operation: str
    kwargs: dict = field(default_factory=dict)
    rationale: str = ""

    def to_dict(self) -> dict:
        return {"skill": self.skill, "operation": self.operation,
                "kwargs": self.kwargs, "rationale": self.rationale}


@dataclass
class Plan:
    goal_id: str
    goal_title: str
    steps: list[Step] = field(default_factory=list)
    created_at: str = ""
    source: str = "deterministic"   # "deterministic" | "llm"
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "goal_id": self.goal_id,
            "goal_title": self.goal_title,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
            "source": self.source,
            "notes": self.notes,
        }


class Planner:
    def __init__(self, goals_path: Path | None = None):
        self.goals_path = goals_path or GOALS_PATH

    def load_goals(self) -> dict:
        if yaml is None or not self.goals_path.exists():
            return {"goals": []}
        with open(self.goals_path) as f:
            return yaml.safe_load(f) or {"goals": []}

    def active_goals(self) -> list[dict]:
        data = self.load_goals()
        gs = [g for g in data.get("goals", []) if g.get("active", True)]
        ad_hoc = data.get("ad_hoc_slot")
        if ad_hoc and ad_hoc.get("active"):
            gs = [ad_hoc] + gs
        gs.sort(key=lambda g: g.get("priority", 0), reverse=True)
        return gs

    def goal_is_triggered(self, goal: dict, now: datetime | None = None) -> bool:
        """Is this goal's trigger currently firing?"""
        now = now or datetime.now()
        # Sunday skip
        if now.weekday() == 6 and "sunday" in [d.lower() for d in goal.get("skip_days", [])]:
            return False
        trig = goal.get("trigger", {})
        t_type = trig.get("type")
        if t_type == "time_window":
            start = trig.get("start", "00:00")
            end = trig.get("end", "23:59")
            s_h, s_m = map(int, start.split(":"))
            e_h, e_m = map(int, end.split(":"))
            now_t = now.time()
            return dtime(s_h, s_m) <= now_t <= dtime(e_h, e_m)
        elif t_type == "interval":
            # Always eligible when the autonomy loop ticks
            return True
        elif t_type == "always":
            return True
        # Default: let autonomy decide by cadence
        return True

    def plan_goal_deterministic(self, goal: dict) -> Plan:
        """Expand goal.yaml's action list → Step list, verifying each against registry."""
        reg = get_registry()
        steps = []
        notes = []
        for action in goal.get("actions", []):
            skill_name = action.get("skill")
            op_name = action.get("operation")
            kwargs = action.get("kwargs", {})
            skill = reg.get(skill_name)
            if not skill:
                notes.append(f"⚠️  unknown skill: {skill_name}")
                continue
            if op_name not in skill.operations:
                notes.append(f"⚠️  {skill_name} has no op '{op_name}'")
                continue
            steps.append(Step(
                skill=skill_name, operation=op_name, kwargs=kwargs,
                rationale=f"declared in goal '{goal['id']}'",
            ))
        plan = Plan(
            goal_id=goal.get("id", "unknown"),
            goal_title=goal.get("title", ""),
            steps=steps,
            created_at=datetime.now().isoformat(),
            source="deterministic",
            notes="; ".join(notes),
        )
        return plan

    def plan_freeform(self, description: str, engine=None) -> Plan:
        """LLM-backed: take a freeform goal, pick skills+ops to accomplish it."""
        if engine is None:
            from friday.brain.engine import MultiEngine
            engine = MultiEngine()
        reg = get_registry()
        manifest = reg.describe_all()
        # Build a compact catalogue
        cat_lines = []
        for sn, sd in manifest.items():
            cat_lines.append(f"- {sn}: {sd['description']}")
            for opn, od in sd["operations"].items():
                args = ", ".join(od.get("input_schema", {}).keys()) or "-"
                cat_lines.append(f"    • {opn} [risk={od['risk']}] args=({args})")
        catalogue = "\n".join(cat_lines)

        prompt = (
            "You are Friday's planner. Given a goal, output a JSON array of steps.\n"
            f"Available skills:\n{catalogue}\n\n"
            f"Goal: {description}\n\n"
            "Output ONLY a JSON array like:\n"
            '[{"skill":"<name>","operation":"<op>","kwargs":{},"rationale":"<why>"}]\n'
            "Max 5 steps. Prefer low-risk operations."
        )
        try:
            raw, _ = engine.ask(
                "You output ONLY valid JSON. No prose.",
                prompt, force="ollama",
            )
            # Extract JSON array
            start = raw.find("[")
            end = raw.rfind("]")
            arr = json.loads(raw[start:end+1]) if start >= 0 and end > start else []
        except Exception as e:
            arr = []
        steps = []
        notes = []
        for item in arr[:5]:
            sn = item.get("skill")
            op = item.get("operation")
            skill = reg.get(sn)
            if not skill or op not in (skill.operations if skill else {}):
                notes.append(f"⚠️  invalid step {sn}.{op}")
                continue
            steps.append(Step(
                skill=sn, operation=op,
                kwargs=item.get("kwargs", {}),
                rationale=item.get("rationale", ""),
            ))
        return Plan(
            goal_id="ad_hoc",
            goal_title=description[:100],
            steps=steps,
            created_at=datetime.now().isoformat(),
            source="llm",
            notes="; ".join(notes),
        )

    def log_plan(self, plan: Plan) -> None:
        PLAN_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(PLAN_LOG, "a") as f:
            f.write(json.dumps(plan.to_dict(), default=str) + "\n")

    def pick_next_goal(self, now: datetime | None = None) -> dict | None:
        """Return the highest-priority triggered goal (or None)."""
        now = now or datetime.now()
        for goal in self.active_goals():
            if self.goal_is_triggered(goal, now):
                return goal
        return None
