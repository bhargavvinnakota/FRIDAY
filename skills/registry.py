"""
Friday :: Skills Registry
Base classes for the capability layer.

Design principles:
  - Every skill declares its operations, risk class, and input schema.
  - The autonomy engine invokes skills *only* through this registry.
  - Risk class → policy.yaml → approval gate. No skill can bypass.
  - Every invocation is logged to actions.jsonl for auditability.
"""
from __future__ import annotations
import json
import os
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal

Risk = Literal["low", "medium", "high", "forbidden"]


@dataclass
class SkillResult:
    ok: bool
    data: Any = None
    error: str | None = None
    artifacts: list[str] = field(default_factory=list)   # file paths produced
    followup: list[dict] = field(default_factory=list)   # proposed next actions

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "data": self.data,
            "error": self.error,
            "artifacts": self.artifacts,
            "followup": self.followup,
        }


@dataclass
class Operation:
    name: str
    description: str
    fn: Callable[..., SkillResult]
    risk: Risk = "low"
    requires_confirm: bool = False
    input_schema: dict = field(default_factory=dict)   # {"field": "description"}


class Skill:
    """
    Base class for all skills. Subclass and register operations with @op.

    Lifecycle per invocation:
      1. autonomy.propose() picks a skill+op based on goal
      2. policy.check() gates on risk class and autonomy level
      3. skill.invoke(op, **kwargs) executes
      4. action.jsonl gets a line; reflector may review outcome
    """
    name: str = "abstract"
    description: str = ""

    def __init__(self):
        self.operations: dict[str, Operation] = {}
        self._register_operations()

    def _register_operations(self) -> None:
        """Override in subclasses to register operations."""
        pass

    def register_op(self, op: Operation) -> None:
        self.operations[op.name] = op

    def describe(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "operations": {
                opn: {
                    "description": o.description,
                    "risk": o.risk,
                    "requires_confirm": o.requires_confirm,
                    "input_schema": o.input_schema,
                }
                for opn, o in self.operations.items()
            },
        }

    def invoke(self, op_name: str, **kwargs) -> SkillResult:
        op = self.operations.get(op_name)
        if not op:
            return SkillResult(ok=False, error=f"unknown operation '{op_name}' on skill '{self.name}'")
        try:
            result = op.fn(**kwargs)
            if not isinstance(result, SkillResult):
                # Allow ops to return plain dicts for convenience
                result = SkillResult(ok=True, data=result)
            return result
        except Exception as e:
            return SkillResult(ok=False, error=f"{type(e).__name__}: {e}")


class SkillRegistry:
    """Global registry. Singleton pattern via get_registry()."""

    def __init__(self, action_log_path: str | Path | None = None):
        self._skills: dict[str, Skill] = {}
        self._lock = threading.RLock()
        self.action_log_path = Path(action_log_path) if action_log_path else Path(
            os.path.expanduser("~/AI/friday/data/actions.jsonl")
        )
        self.action_log_path.parent.mkdir(parents=True, exist_ok=True)

    def register(self, skill: Skill) -> None:
        with self._lock:
            self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        with self._lock:
            return self._skills.get(name)

    def all(self) -> dict[str, Skill]:
        with self._lock:
            return dict(self._skills)

    def describe_all(self) -> dict[str, dict]:
        with self._lock:
            return {name: s.describe() for name, s in self._skills.items()}

    def invoke(self, skill_name: str, op_name: str, _actor: str = "autonomy",
               **kwargs) -> SkillResult:
        """Invoke a skill operation. Logs before+after to action log."""
        skill = self.get(skill_name)
        if not skill:
            result = SkillResult(ok=False, error=f"unknown skill '{skill_name}'")
            self._log(skill_name, op_name, kwargs, result, _actor, risk="unknown")
            return result

        op = skill.operations.get(op_name)
        risk = op.risk if op else "unknown"

        result = skill.invoke(op_name, **kwargs)
        self._log(skill_name, op_name, kwargs, result, _actor, risk)
        return result

    def _log(self, skill: str, op: str, args: dict, result: SkillResult,
             actor: str, risk: str) -> None:
        try:
            with self._lock:
                with open(self.action_log_path, "a") as f:
                    f.write(json.dumps({
                        "ts": datetime.now().isoformat(),
                        "actor": actor,
                        "skill": skill,
                        "operation": op,
                        "risk": risk,
                        "args": _safe_args(args),
                        "ok": result.ok,
                        "error": result.error,
                        "artifacts": result.artifacts,
                        "has_followup": bool(result.followup),
                    }, default=str) + "\n")
        except Exception:
            pass  # never let logging break execution


def _safe_args(args: dict) -> dict:
    """Strip non-serializable values; truncate large strings."""
    out = {}
    for k, v in args.items():
        try:
            if isinstance(v, str):
                out[k] = v[:200]
            elif isinstance(v, (int, float, bool, type(None))):
                out[k] = v
            elif isinstance(v, (list, dict)):
                s = json.dumps(v, default=str)
                out[k] = s[:200] if len(s) > 200 else v
            else:
                out[k] = str(type(v).__name__)
        except Exception:
            out[k] = "<unserializable>"
    return out


# Singleton
_REGISTRY: SkillRegistry | None = None
_REG_LOCK = threading.Lock()


def get_registry() -> SkillRegistry:
    global _REGISTRY
    with _REG_LOCK:
        if _REGISTRY is None:
            _REGISTRY = SkillRegistry()
            # Dynamically load all skills from the current directory
            import importlib
            import inspect
            import pkgutil
            from . import registry
            
            # 1. Load built-ins first for stability
            # (Keeping explicit imports for core skills to avoid circular dependencies)
            from . import system, watchdog, outreach, content, research, journal, briefing, intelligence, computer, empire, builder, swarm, broker, oracle, mac, omni_learner, self_refactor
            _REGISTRY.register(system.SystemSkill())
            _REGISTRY.register(watchdog.WatchdogSkill())
            _REGISTRY.register(outreach.OutreachSkill())
            _REGISTRY.register(content.ContentSkill())
            _REGISTRY.register(research.ResearchSkill())
            _REGISTRY.register(journal.JournalSkill())
            _REGISTRY.register(briefing.BriefingSkill())
            _REGISTRY.register(intelligence.IntelligenceSkill())
            _REGISTRY.register(computer.ComputerSkill())
            _REGISTRY.register(empire.EmpireSkill())
            _REGISTRY.register(builder.BuilderSkill())
            _REGISTRY.register(swarm.SwarmSkill())
            _REGISTRY.register(broker.BrokerSkill())
            _REGISTRY.register(oracle.OracleSkill())
            _REGISTRY.register(mac.MacSkill())
            _REGISTRY.register(omni_learner.OmniLearnerSkill())
            _REGISTRY.register(self_refactor.SelfRefactorSkill())

            # 2. Discover and load all 'auto_*' skills
            skills_dir = Path(__file__).parent
            for loader, module_name, is_pkg in pkgutil.iter_modules([str(skills_dir)]):
                if module_name.startswith("auto_"):
                    try:
                        module = importlib.import_module(f".{module_name}", package="friday.skills")
                        for name, obj in inspect.getmembers(module):
                            if inspect.isclass(obj) and issubclass(obj, registry.Skill) and obj is not registry.Skill:
                                _REGISTRY.register(obj())
                                # print(f"[Registry] Dynamically loaded: {module_name}.{name}")
                    except Exception as e:
                        print(f"[Registry] Failed to load {module_name}: {e}")
                        
        return _REGISTRY
