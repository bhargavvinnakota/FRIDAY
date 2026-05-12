"""
Friday :: Autonomy Engine
The heart of v1.0. Every tick:

  1. Ask the planner for the next triggered goal.
  2. Expand it into a plan (deterministic from goals.yaml).
  3. For each step: policy-check, execute (or queue for approval), reflect.
  4. Log everything. Log it all.

A tick is a finite, bounded unit of work (max_actions_per_tick steps).
Runs forever under loops/autonomy_loop.py → daemon.py.
"""
from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None

from friday.brain.memory import Memory
from friday.brain.action_envelope import build_action_envelope, write_action_proof
from friday.brain.planner import Planner, Plan, Step
from friday.brain.policy import Policy
from friday.brain.reflector import Reflector
from friday.skills.registry import get_registry, SkillResult

FRIDAY = Path(os.path.expanduser("~/AI/friday"))
CFG_PATH = FRIDAY / "config" / "friday.yaml"
APPROVAL_FILE = FRIDAY / "data" / "pending_approvals.json"


def _load_autonomy_cfg() -> dict:
    if yaml is None or not CFG_PATH.exists():
        return {}
    with open(CFG_PATH) as f:
        return (yaml.safe_load(f) or {}).get("autonomy", {})


@dataclass
class TickResult:
    goal_id: str | None = None
    goal_title: str = ""
    steps_attempted: int = 0
    steps_executed: int = 0
    steps_queued: int = 0
    steps_blocked: int = 0
    outcomes: list[dict] = field(default_factory=list)
    skipped_reason: str | None = None
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict:
        return {
            "goal_id": self.goal_id,
            "goal_title": self.goal_title,
            "steps_attempted": self.steps_attempted,
            "steps_executed": self.steps_executed,
            "steps_queued": self.steps_queued,
            "steps_blocked": self.steps_blocked,
            "outcomes": self.outcomes,
            "skipped_reason": self.skipped_reason,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class AutonomyEngine:
    def __init__(self,
                 planner: Planner | None = None,
                 policy: Policy | None = None,
                 reflector: Reflector | None = None,
                 memory: Memory | None = None):
        self.planner = planner or Planner()
        self.policy = policy or Policy()
        self.memory = memory or Memory()
        self.reflector = reflector or Reflector(self.memory)
        self.registry = get_registry()
        cfg = _load_autonomy_cfg()
        self.enabled = cfg.get("enabled", True)
        self.max_actions = cfg.get("max_actions_per_tick", 3)
        self.tick_minutes = cfg.get("tick_interval_minutes", 15)

    # --------- approvals ---------
    def _load_approvals(self) -> list[dict]:
        if not APPROVAL_FILE.exists():
            return []
        try:
            return json.loads(APPROVAL_FILE.read_text())
        except Exception:
            return []

    def _save_approvals(self, items: list[dict]) -> None:
        APPROVAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        APPROVAL_FILE.write_text(json.dumps(items, indent=2, default=str))

    def queue_for_approval(self, skill: str, operation: str, kwargs: dict,
                           reason: str, goal: str | None = None,
                           policy_decision: dict | None = None,
                           trace_id: str | None = None) -> str:
        import uuid
        aid = uuid.uuid4().hex[:8]
        proof: dict[str, Any] = {}
        try:
            skill_obj = self.registry.get(skill)
            op = skill_obj.operations.get(operation) if skill_obj else None
            risk = op.risk if op else "unknown"
            decision = policy_decision or {
                "allow": False,
                "requires_approval": True,
                "reason": reason,
                "autonomy_level": self.policy.autonomy_level,
                "policy_decision": "queue",
            }
            envelope = build_action_envelope(
                skill=skill,
                operation=operation,
                actor="autonomy",
                risk_tier=risk,
                args=kwargs,
                policy_decision=decision,
                goal=goal,
                approval_id=aid,
                expected_outcome="Queue action for Bhargav approval before execution.",
                rollback="Reject or hold the pending approval before execution.",
                notification="summary",
                post_action_metric="approval_status",
                trace_id=trace_id,
            )
            proof_path = write_action_proof(envelope, {
                "ok": True,
                "data": {"status": "queued", "approval_id": aid},
                "artifacts": [],
                "followup": [],
            })
            proof = {
                "action_envelope": envelope.to_dict(),
                "proof_path": proof_path,
                "trace_id": envelope.trace_id,
                "risk_tier": envelope.risk_tier,
                "policy_decision": envelope.policy_decision,
            }
        except Exception as e:
            proof = {"proof_error": f"{type(e).__name__}: {e}"}
        items = self._load_approvals()
        items.append({
            "id": aid,
            "skill": skill,
            "operation": operation,
            "kwargs": kwargs,
            "reason": reason,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            **proof,
        })
        self._save_approvals(items)
        return aid

    def approve(self, aid: str) -> dict:
        """
        Approve + execute. Returns {ok, action_ok, result, id}.
        - ok:        whether the approval was found and executed (approval-layer success)
        - action_ok: whether the underlying skill operation succeeded
        These are independent: approving a system.health_check can succeed (ok=True)
        even if the health_check reports an unhealthy disk (action_ok=False).
        """
        items = self._load_approvals()
        for it in items:
            if it["id"] == aid and it["status"] == "pending":
                it["status"] = "approved"
                it["approved_at"] = datetime.now().isoformat()
                self._save_approvals(items)
                # Execute now
                action_envelope = it.get("action_envelope") or {}
                result = self.registry.invoke(it["skill"], it["operation"],
                                              _actor="user_approved",
                                              _approval_id=aid,
                                              _goal=action_envelope.get("goal"),
                                              _policy_decision={
                                                  "allow": True,
                                                  "reason": f"user approved {aid}",
                                                  "requires_approval": False,
                                                  "autonomy_level": self.policy.autonomy_level,
                                                  "policy_decision": "allow",
                                              },
                                              **it.get("kwargs", {}))
                # Reload before writing the execution result. Some approved
                # operations, especially outreach.queue_for_approval, append
                # new approval records as their main side effect. Saving the
                # old in-memory snapshot here would silently erase those new
                # records and make Friday "act" without leaving usable work.
                latest = self._load_approvals()
                for latest_item in latest:
                    if latest_item.get("id") == aid:
                        if latest_item.get("status") == "approved":
                            latest_item["status"] = "executed"
                        else:
                            latest_item["execution_status"] = "executed"
                        latest_item["result"] = result.to_dict()
                        break
                else:
                    it["status"] = "executed"
                    it["result"] = result.to_dict()
                    latest.append(it)
                self._save_approvals(latest)
                return {"ok": True, "action_ok": result.ok,
                        "result": result.to_dict(), "id": aid}
        return {"ok": False, "error": f"no pending approval with id={aid}"}

    def reject(self, aid: str) -> dict:
        items = self._load_approvals()
        for it in items:
            if it["id"] == aid and it["status"] == "pending":
                it["status"] = "rejected"
                it["rejected_at"] = datetime.now().isoformat()
                self._save_approvals(items)
                return {"ok": True, "id": aid}
        return {"ok": False, "error": f"no pending approval with id={aid}"}

    def hold(self, aid: str, hours: int = 1) -> dict:
        items = self._load_approvals()
        for it in items:
            if it["id"] == aid:
                it["status"] = "held"
                it["hold_until"] = (datetime.now().timestamp() + hours * 3600)
                self._save_approvals(items)
                return {"ok": True, "id": aid, "until": it["hold_until"]}
        return {"ok": False, "error": f"no approval with id={aid}"}

    def pending_approvals(self) -> list[dict]:
        return [a for a in self._load_approvals() if a.get("status") == "pending"]

    # --------- tick ---------
    def tick(self, force_goal_id: str | None = None,
             dry_run: bool = False) -> TickResult:
        now = datetime.now()
        result = TickResult(started_at=now.isoformat())

        if not self.enabled and not force_goal_id:
            result.skipped_reason = "autonomy disabled in config"
            result.finished_at = datetime.now().isoformat()
            return result

        # Pick goal
        if force_goal_id:
            data = self.planner.load_goals()
            goal = next((g for g in data.get("goals", []) if g.get("id") == force_goal_id), None)
        else:
            goal = self.planner.pick_next_goal(now)

        if not goal:
            result.skipped_reason = "no triggered goal"
            result.finished_at = datetime.now().isoformat()
            return result

        result.goal_id = goal.get("id")
        result.goal_title = goal.get("title", "")

        # Build plan
        plan = self.planner.plan_goal_deterministic(goal)
        self.planner.log_plan(plan)

        # Execute up to max_actions steps
        context: dict[str, Any] = {}
        for step in plan.steps[:self.max_actions]:
            result.steps_attempted += 1
            outcome = self._execute_step(step, goal, dry_run=dry_run, context=context)
            result.outcomes.append(outcome)
            if outcome.get("data"):
                context.update(outcome["data"])
            if outcome["status"] == "executed":
                result.steps_executed += 1
            elif outcome["status"] == "queued":
                result.steps_queued += 1
            elif outcome["status"] == "blocked":
                result.steps_blocked += 1

        # Log tick
        self.memory.log_event("autonomy_tick", {
            "goal_id": result.goal_id,
            "executed": result.steps_executed,
            "queued": result.steps_queued,
            "blocked": result.steps_blocked,
        })
        result.finished_at = datetime.now().isoformat()
        return result

    def _execute_step(self, step: Step, goal: dict, dry_run: bool = False,
                      context: dict[str, Any] | None = None) -> dict:
        skill = self.registry.get(step.skill)
        op = skill.operations.get(step.operation) if skill else None
        if not op:
            return {"status": "blocked", "skill": step.skill, "operation": step.operation,
                    "reason": "skill/op not found"}
        risk = op.risk
        critical = goal.get("priority", 0) >= 90
        kwargs = dict(step.kwargs)
        context = context or {}
        if step.skill == "outreach" and step.operation == "draft_next_touch":
            kwargs.setdefault("leads", context.get("due"))
        elif step.skill == "outreach" and step.operation == "queue_for_approval":
            kwargs.setdefault("drafts", context.get("drafts"))

        decision = self.policy.check(step.skill, step.operation, risk, critical=critical)
        if not decision["allow"]:
            if decision.get("requires_approval"):
                aid = self.queue_for_approval(
                    step.skill, step.operation, kwargs,
                    reason=f"goal={goal.get('id')} · {decision['reason']}",
                    goal=goal.get("id"),
                    policy_decision=decision,
                )
                return {"status": "queued", "skill": step.skill, "operation": step.operation,
                        "approval_id": aid, "reason": decision["reason"]}
            return {"status": "blocked", "skill": step.skill, "operation": step.operation,
                    "reason": decision["reason"]}

        if dry_run:
            return {"status": "dry_run", "skill": step.skill, "operation": step.operation,
                    "kwargs": kwargs}

        t0 = time.time()
        res = self.registry.invoke(step.skill, step.operation, _actor="autonomy",
                                   _goal=goal.get("id"),
                                   _policy_decision=decision,
                                   _expected_outcome=f"Advance goal {goal.get('id')} via {step.skill}.{step.operation}",
                                   **kwargs)
        elapsed_ms = int((time.time() - t0) * 1000)
        self.reflector.review_action(step.skill, step.operation, res.to_dict(),
                                     elapsed_ms, context={"goal": goal.get("id")})
        return {"status": "executed", "skill": step.skill, "operation": step.operation,
                "ok": res.ok, "error": res.error, "elapsed_ms": elapsed_ms,
                "artifacts_count": len(res.artifacts), "data": res.data or {}}

    # --------- introspection ---------
    def status(self) -> dict:
        goals = self.planner.active_goals()
        next_goal = self.planner.pick_next_goal()
        return {
            "enabled": self.enabled,
            "autonomy_level": self.policy.autonomy_level,
            "active_goals": len(goals),
            "next_goal": next_goal.get("id") if next_goal else None,
            "next_goal_title": next_goal.get("title") if next_goal else None,
            "pending_approvals": len(self.pending_approvals()),
            "tick_interval_minutes": self.tick_minutes,
            "max_actions_per_tick": self.max_actions,
            "skills_registered": len(self.registry.all()),
            "skills": list(self.registry.all().keys()),
        }
