"""
Friday :: Mission Orchestrator
Long-running goal pursuit. The v2.0 core.

A Mission is:
  - A goal (user intent)
  - A plan (decomposed by Planner)
  - An execution state (which steps done, which pending, artifacts)
  - A verification pass (Critic on risky outputs)
  - A final report (Synthesizer)

Missions persist to disk — survive daemon restarts.
Missions can checkpoint and resume.
Missions can be paused, cancelled, or have their plan amended mid-flight.
"""
from __future__ import annotations
import json
import os
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .engine import MultiEngine
from .memory import Memory
from .agents import Researcher, Planner, Critic, Synthesizer

FRIDAY = Path(os.path.expanduser("~/AI/friday"))
MISSIONS_DIR = FRIDAY / "data" / "missions"
MISSIONS_DIR.mkdir(parents=True, exist_ok=True)

_LOCK = threading.RLock()


@dataclass
class Step:
    id: int
    name: str
    skill: str
    operation: str
    depends_on: list[int] = field(default_factory=list)
    args: dict = field(default_factory=dict)
    expected_output: str = ""
    status: str = "pending"    # pending | running | done | failed | skipped
    result: Any = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


@dataclass
class Mission:
    id: str
    goal: str
    created_at: str
    status: str = "planning"   # planning | running | blocked | done | failed | cancelled
    risk: str = "medium"
    est_duration_minutes: int = 30
    plan_reasoning: str = ""
    steps: list[Step] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    final_report: str = ""
    created_by: str = "bhargav"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Mission":
        d = dict(d)
        steps = [Step(**s) for s in d.pop("steps", [])]
        return cls(**d, steps=steps)

    def path(self) -> Path:
        return MISSIONS_DIR / f"{self.id}.json"

    def save(self) -> None:
        with _LOCK:
            with open(self.path(), "w") as f:
                json.dump(self.to_dict(), f, indent=2, default=str)


def new_mission(goal: str, created_by: str = "bhargav") -> Mission:
    mid = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    m = Mission(id=mid, goal=goal, created_at=datetime.now().isoformat(), created_by=created_by)
    m.save()
    return m


def load_mission(mission_id: str) -> Mission | None:
    path = MISSIONS_DIR / f"{mission_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return Mission.from_dict(json.load(f))


def list_missions(status: str | None = None, limit: int = 20) -> list[Mission]:
    out = []
    for p in sorted(MISSIONS_DIR.glob("*.json"), reverse=True)[:limit * 2]:
        try:
            with open(p) as f:
                m = Mission.from_dict(json.load(f))
            if status is None or m.status == status:
                out.append(m)
            if len(out) >= limit:
                break
        except Exception:
            continue
    return out


class MissionRunner:
    """
    Executes a mission step-by-step. Respects dependencies. Stops on failure
    unless the step is marked non-critical.

    Can be invoked:
      - Synchronously: run(mission) — blocks until done/failed
      - Asynchronously: spawn(mission) — returns immediately, runs in thread
    """

    def __init__(self, engine: MultiEngine, memory: Memory,
                 skill_registry=None):
        self.engine = engine
        self.memory = memory
        if skill_registry is None:
            from friday.skills import get_registry
            skill_registry = get_registry()
        self.skills = skill_registry
        self.researcher = Researcher(engine)
        self.planner = Planner(engine)
        self.critic = Critic(engine)
        self.synthesizer = Synthesizer(engine)

    # ---- Plan ----
    def plan(self, mission: Mission) -> bool:
        """Ask Planner to decompose the goal. Populates mission.steps."""
        skills_desc = self.skills.describe_all() if self.skills else {}
        # Also expose the agent-level operations as pseudo-skills
        skills_desc["researcher"] = {
            "description": "Deep web/news research on a topic. Produces cited briefing.",
            "operations": {"run": {"description": "Research a topic",
                                    "risk": "low",
                                    "input_schema": {"topic": "str", "depth": "quick|medium|deep"}}},
        }
        skills_desc["critic"] = {
            "description": "Stress-test an output for grounding, voice, safety.",
            "operations": {"run": {"description": "Critique proposed output",
                                    "risk": "low"}},
        }
        skills_desc["synthesizer"] = {
            "description": "Merge multiple inputs into one Friday-voice response.",
            "operations": {"run": {"description": "Synthesize final output",
                                    "risk": "low"}},
        }

        res = self.planner.run(mission.goal, available_skills=skills_desc)
        if not res.ok:
            mission.status = "failed"
            mission.notes.append(f"planner failed: {res.error}")
            mission.save()
            return False

        plan = res.data
        mission.risk = plan.get("risk", "medium")
        mission.est_duration_minutes = int(plan.get("est_duration_minutes", 30))
        mission.plan_reasoning = plan.get("reasoning", "")
        mission.steps = []
        for s in plan.get("steps", []):
            mission.steps.append(Step(
                id=int(s.get("id")),
                name=s.get("name", ""),
                skill=s.get("skill", ""),
                operation=s.get("operation", ""),
                depends_on=[int(x) for x in s.get("depends_on", [])],
                args=s.get("args", {}),
                expected_output=s.get("expected_output", ""),
            ))
        mission.status = "running"
        mission.save()
        return True

    # ---- Execute ----
    def run(self, mission: Mission, on_step: Callable[[Mission, Step], None] | None = None) -> Mission:
        if mission.status == "planning":
            if not self.plan(mission):
                return mission
        if mission.status not in ("running", "blocked"):
            return mission

        # Execute steps respecting dependencies
        done_ids = {s.id for s in mission.steps if s.status == "done"}
        while True:
            runnable = [s for s in mission.steps
                        if s.status == "pending" and all(d in done_ids for d in s.depends_on)]
            if not runnable:
                break
            # Run first runnable step sequentially (keeps it simple; parallel later)
            step = runnable[0]
            step.status = "running"
            step.started_at = datetime.now().isoformat()
            mission.save()
            try:
                result = self._execute_step(mission, step)
                step.result = self._trim_for_persistence(result)
                step.status = "done"
                done_ids.add(step.id)
            except Exception as e:
                step.status = "failed"
                step.error = f"{type(e).__name__}: {e}"
                mission.status = "failed"
                mission.notes.append(f"step {step.id} failed: {step.error}")
                step.finished_at = datetime.now().isoformat()
                mission.save()
                if on_step:
                    on_step(mission, step)
                return mission
            step.finished_at = datetime.now().isoformat()
            mission.save()
            if on_step:
                on_step(mission, step)

        # All steps done
        mission.status = "done"
        # Find final report step if exists
        report_step = next((s for s in reversed(mission.steps)
                            if s.operation in ("report", "final_report", "summarize")), None)
        if report_step and report_step.result:
            mission.final_report = str(report_step.result)[:5000]
        else:
            mission.final_report = self._auto_summary(mission)
        mission.save()
        return mission

    def spawn(self, mission: Mission) -> threading.Thread:
        """Run in a daemon thread; returns immediately."""
        t = threading.Thread(target=self.run, args=(mission,), daemon=True,
                             name=f"mission-{mission.id[:12]}")
        t.start()
        return t

    # ---- Step dispatch ----
    def _execute_step(self, mission: Mission, step: Step) -> Any:
        """Resolve arg templates + dispatch to the right capability."""
        args = self._resolve_args(step.args, mission)

        # Agent-level dispatches
        if step.skill == "researcher":
            topic = args.get("topic") or mission.goal
            depth = args.get("depth", "medium")
            r = self.researcher.run(topic=topic, depth=depth)
            if not r.ok:
                raise RuntimeError(r.error or "researcher failed")
            return r.data
        if step.skill == "critic":
            r = self.critic.run(
                proposed_output=str(args.get("proposed_output", "")),
                context=str(args.get("context", mission.goal)),
                source_material=str(args.get("source_material", "")),
            )
            if not r.ok:
                raise RuntimeError(r.error or "critic failed")
            return r.data
        if step.skill == "synthesizer":
            inputs = args.get("inputs") or self._collect_prior_results(mission, step)
            r = self.synthesizer.run(inputs=inputs, task=args.get("task", "briefing"))
            if not r.ok:
                raise RuntimeError(r.error or "synthesizer failed")
            return r.data
        if step.skill in ("confirm", "approval"):
            # Queue for user approval — doesn't block mission thread forever, marks as blocked
            mission.status = "blocked"
            mission.notes.append(f"awaiting approval at step {step.id}: {step.name}")
            raise RuntimeError("mission_blocked_awaiting_approval")
        if step.skill in ("report", "final_report"):
            inputs = self._collect_prior_results(mission, step)
            r = self.synthesizer.run(inputs=inputs,
                                      task=f"final report for mission: {mission.goal}")
            return r.data

        # Skill-registry dispatch
        if self.skills:
            result = self.skills.invoke(step.skill, step.operation, _actor=f"mission:{mission.id}",
                                        **args)
            if not getattr(result, "ok", False):
                raise RuntimeError(result.error or f"skill {step.skill}.{step.operation} failed")
            return result.data

        raise RuntimeError(f"no handler for skill={step.skill} op={step.operation}")

    # ---- helpers ----
    def _resolve_args(self, args: dict, mission: Mission) -> dict:
        """Resolve ${step_N} templates in arg values to prior step results."""
        out = {}
        for k, v in args.items():
            if isinstance(v, str) and v.startswith("${step_") and v.endswith("}"):
                try:
                    sid = int(v[len("${step_"):-1])
                    prior = next((s for s in mission.steps if s.id == sid), None)
                    out[k] = prior.result if prior and prior.result is not None else v
                except Exception:
                    out[k] = v
            else:
                out[k] = v
        return out

    def _collect_prior_results(self, mission: Mission, step: Step) -> list[dict]:
        deps = step.depends_on or [s.id for s in mission.steps if s.id < step.id and s.status == "done"]
        inputs = []
        for d in deps:
            prior = next((s for s in mission.steps if s.id == d), None)
            if prior and prior.result:
                content = prior.result
                if isinstance(content, dict):
                    content = content.get("report") or content.get("text") or json.dumps(content, default=str)[:2000]
                inputs.append({"label": prior.name or f"step_{prior.id}", "content": content})
        return inputs

    def _trim_for_persistence(self, result: Any) -> Any:
        """Keep persisted step results small enough for readable mission files."""
        try:
            s = json.dumps(result, default=str)
            if len(s) < 20_000:
                return result
            # Too big — keep a summary
            if isinstance(result, dict):
                return {k: (v if not isinstance(v, str) else v[:2000])
                        for k, v in result.items()}
            return str(result)[:5000]
        except Exception:
            return str(result)[:5000]

    def _auto_summary(self, mission: Mission) -> str:
        done = [s for s in mission.steps if s.status == "done"]
        return (f"Mission {mission.id} — {mission.goal}\n"
                f"Completed {len(done)}/{len(mission.steps)} steps. "
                f"Status: {mission.status}.")
