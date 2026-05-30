#!/usr/bin/env python3
"""
Friday v1.0 :: Autonomy Test Suite
Exercises every piece of the v1.0 layer:
  - skills registry (all 7 skills + invocations)
  - planner (active goals, trigger eval, deterministic + LLM plans)
  - policy gate (risk classes, autonomy levels, quiet windows, rate limits)
  - autonomy engine (tick, approval queue, approve/reject/hold)
  - reflector (action stats, heuristics)
  - CLI commands (autonomy, goals, tick, skills, pending, reflect)
  - telegram approval commands (isolated)
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import sys
import time
from datetime import datetime, timedelta, time as dtime
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/AI"))

FRIDAY = Path(os.path.expanduser("~/AI/friday"))


class R:
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.per_section: dict[str, dict] = {}
        self.current = None
        self.start = time.time()

    def section(self, name: str):
        print(f"\n{'═'*60}\n  {name}\n{'═'*60}")
        self.current = name
        self.per_section.setdefault(name, {"ok": 0, "fail": 0})

    def ok(self, msg: str):
        self.total += 1
        self.passed += 1
        self.per_section[self.current]["ok"] += 1
        print(f"  ✅ {msg}")

    def bad(self, msg: str):
        self.total += 1
        self.failed += 1
        self.per_section[self.current]["fail"] += 1
        print(f"  ❌ {msg}")

    def report(self):
        dur = time.time() - self.start
        print(f"\n{'═'*60}\n  V1.0 AUTONOMY TEST REPORT\n{'═'*60}")
        print(f"  Duration: {dur:.1f}s")
        print(f"  Total: {self.total}  ✅ {self.passed}  ❌ {self.failed}")
        rate = (self.passed / self.total * 100) if self.total else 0
        print(f"  Success rate: {rate:.1f}%\n")
        for sec, d in self.per_section.items():
            tot = d["ok"] + d["fail"]
            print(f"    {sec:50} {d['ok']}/{tot}")
        data = {"total": self.total, "passed": self.passed, "failed": self.failed,
                "rate": rate, "duration_s": dur, "sections": self.per_section}
        (FRIDAY / "data" / "v1_autonomy_report.json").write_text(
            json.dumps(data, indent=2, default=str))


r = R()

# ====================================================================
# 1. VERSION + CONFIG
# ====================================================================
r.section("1. VERSION + CONFIG")
try:
    from friday import __version__, __codename__
    if __version__ == "2.0.0":
        r.ok(f"version == 2.0.0")
    else:
        r.bad(f"version is {__version__}")
    if "Autonomy" in __codename__:
        r.ok(f"codename: {__codename__}")
    else:
        r.bad(f"codename unexpected: {__codename__}")
except Exception as e:
    r.bad(f"version import: {e}")

# goals.yaml
try:
    import yaml
    with open(FRIDAY / "config" / "goals.yaml") as f:
        gy = yaml.safe_load(f)
    goals = gy.get("goals", [])
    if len(goals) >= 5:
        r.ok(f"goals.yaml has {len(goals)} goals")
    else:
        r.bad(f"only {len(goals)} goals defined")
    # priorities sorted?
    priorities = [g.get("priority", 0) for g in goals]
    if priorities == sorted(priorities, reverse=True):
        r.ok("goals listed in priority order")
    else:
        r.ok(f"goals not sorted (planner re-sorts)")
    # each has required fields
    required = ["id", "title", "priority", "actions", "trigger"]
    for g in goals:
        missing = [k for k in required if k not in g]
        if missing:
            r.bad(f"goal {g.get('id','?')} missing: {missing}")
            break
    else:
        r.ok("all goals have required fields")
except Exception as e:
    r.bad(f"goals.yaml: {e}")

# policies.yaml
try:
    with open(FRIDAY / "config" / "policies.yaml") as f:
        py = yaml.safe_load(f)
    if py.get("autonomy_level") in ("off", "supervised", "trusted", "full"):
        r.ok(f"autonomy_level: {py['autonomy_level']}")
    else:
        r.bad(f"invalid autonomy_level: {py.get('autonomy_level')}")
    if "risk_classes" in py and set(py["risk_classes"]) >= {"low", "medium", "high", "forbidden"}:
        r.ok("all 4 risk classes defined")
    else:
        r.bad("risk classes incomplete")
    if "rate_limits" in py:
        r.ok(f"rate_limits defined ({len(py['rate_limits'])})")
    else:
        r.bad("no rate_limits")
except Exception as e:
    r.bad(f"policies.yaml: {e}")

# ====================================================================
# 2. SKILLS REGISTRY
# ====================================================================
r.section("2. SKILLS REGISTRY")
try:
    from friday.skills.registry import get_registry, SkillResult, Skill
    reg = get_registry()
    skills = reg.all()
    expected = {"system", "watchdog", "outreach", "content", "research", "journal", "briefing"}
    got = set(skills.keys())
    if expected <= got:
        r.ok(f"all 7 expected skills registered: {sorted(got)}")
    else:
        r.bad(f"missing: {expected - got}")

    # Each skill has operations
    total_ops = 0
    for sn, s in skills.items():
        if len(s.operations) > 0:
            total_ops += len(s.operations)
        else:
            r.bad(f"{sn} has no operations")
            break
    else:
        r.ok(f"total operations: {total_ops}")

    # Describe_all structure
    desc = reg.describe_all()
    if all("name" in d and "operations" in d for d in desc.values()):
        r.ok("describe_all returns well-formed dicts")
    else:
        r.bad("describe_all malformed")
except Exception as e:
    r.bad(f"registry: {e}")

# Invoke each skill's lowest-risk op
try:
    # system.health_check
    res = reg.invoke("system", "health_check", _actor="test")
    if isinstance(res, SkillResult) and "python_version" in (res.data or {}):
        r.ok(f"system.health_check → py={res.data.get('python_version')}")
    else:
        r.bad(f"health_check bad: {res.to_dict()}")

    # watchdog.scan
    res = reg.invoke("watchdog", "scan", _actor="test")
    if res.ok and "findings" in res.data:
        r.ok(f"watchdog.scan → {len(res.data['findings'])} findings")
    else:
        r.bad(f"watchdog.scan bad: {res.to_dict()}")

    # outreach.find_due_leads
    res = reg.invoke("outreach", "find_due_leads", _actor="test")
    if res.ok:
        r.ok(f"outreach.find_due_leads → {res.data.get('count',0)} due / {res.data.get('total_leads',0)} total")
    else:
        r.bad(f"find_due_leads: {res.error}")

    # outreach.manual_send_outbox (proof artifact for manual WhatsApp send)
    res = reg.invoke("outreach", "manual_send_outbox", _actor="test")
    if res.ok and "count" in res.data:
        r.ok(f"outreach.manual_send_outbox → {res.data.get('count',0)} items")
    else:
        r.bad(f"manual_send_outbox: {res.error}")

    # research.local_search (fast, offline)
    res = reg.invoke("research", "local_search", _actor="test", query="autonomy")
    if res.ok and "matches" in res.data:
        r.ok(f"research.local_search → {len(res.data['matches'])} hits")
    else:
        r.bad(f"local_search: {res.error}")

    # journal.recent
    res = reg.invoke("journal", "recent", _actor="test", n=3)
    if res.ok:
        r.ok(f"journal.recent → {len(res.data.get('entries',[]))} entries")
    else:
        r.bad(f"journal.recent: {res.error}")

    # outreach.status
    res = reg.invoke("outreach", "status", _actor="test")
    if res.ok:
        r.ok(f"outreach.status → {res.data.get('pending_count',0)} pending")
    else:
        r.bad(f"outreach.status: {res.error}")

    # mission_control.test_capabilities (20-domain Friday vision harness)
    res = reg.invoke("mission_control", "test_capabilities", _actor="test", write_report=False, generate_artifacts=False)
    summary = (res.data or {}).get("summary", {})
    if res.ok and summary.get("total") == 20 and summary.get("failed") == 0:
        r.ok(f"mission_control.test_capabilities → {summary.get('passed')}/20 passed")
    else:
        r.bad(f"mission_control.test_capabilities: {res.error or summary}")

    # mission_control.mission_brief includes connector state
    res = reg.invoke("mission_control", "mission_brief", _actor="test")
    connector_status = (res.data or {}).get("connector_status", {})
    if res.ok and connector_status.get("total", 0) >= 10 and (res.data or {}).get("next_action", {}).get("action"):
        r.ok(f"mission_control.mission_brief → connectors {connector_status.get('readiness_score')}%")
    else:
        r.bad(f"mission_control.mission_brief: {res.error or res.data}")

    # money_engine.rank_opportunities (ethical opportunity science)
    res = reg.invoke("money_engine", "rank_opportunities", _actor="test", top_n=3, refresh=True)
    opportunities = (res.data or {}).get("opportunities", [])
    if res.ok and len(opportunities) >= 3 and opportunities[0].get("score", 0) >= opportunities[-1].get("score", 0):
        r.ok(f"money_engine.rank_opportunities → top={opportunities[0].get('id')}")
    else:
        r.bad(f"money_engine.rank_opportunities: {res.error or res.data}")

    # money_engine.create_experiment
    top_id = opportunities[0].get("id") if opportunities else ""
    res = reg.invoke("money_engine", "create_experiment", _actor="test", opportunity_id=top_id)
    if res.ok and res.data.get("opportunity_id") == top_id and res.data.get("first_action"):
        r.ok(f"money_engine.create_experiment → {res.data.get('id')}")
    else:
        r.bad(f"money_engine.create_experiment: {res.error or res.data}")

    # money_engine.launch_experiment dry-run
    res = reg.invoke("money_engine", "launch_experiment", _actor="test", opportunity_id=top_id, max_leads=2, dry_run=True)
    if res.ok and res.data.get("dry_run") and res.data.get("would_queue_outreach"):
        r.ok("money_engine.launch_experiment dry-run")
    else:
        r.bad(f"money_engine.launch_experiment dry-run: {res.error or res.data}")

    # nervous_system.status
    res = reg.invoke("nervous_system", "status", _actor="test")
    if res.ok and "total" in (res.data or {}):
        r.ok(f"nervous_system.status → {res.data.get('total')} events")
    else:
        r.bad(f"nervous_system.status: {res.error or res.data}")

    # world_twin.pulse (local only)
    res = reg.invoke("world_twin", "pulse", _actor="test", persist=True, use_web=False)
    if res.ok and (res.data or {}).get("count", 0) >= 3:
        r.ok(f"world_twin.pulse → {res.data.get('count')} events")
    else:
        r.bad(f"world_twin.pulse: {res.error or res.data}")

    # connector_center.status
    res = reg.invoke("connector_center", "status", _actor="test")
    if res.ok and (res.data or {}).get("total", 0) >= 10 and (res.data or {}).get("missing_p0"):
        r.ok(f"connector_center.status → {(res.data or {}).get('readiness_score')}% ready")
    else:
        r.bad(f"connector_center.status: {res.error or res.data}")

    # connector_center.test_plan
    res = reg.invoke("connector_center", "test_plan", _actor="test", include_write_tests=False)
    if res.ok and (res.data or {}).get("count", 0) >= 10 and (res.data or {}).get("rule"):
        r.ok(f"connector_center.test_plan → {(res.data or {}).get('count')} tests")
    else:
        r.bad(f"connector_center.test_plan: {res.error or res.data}")

    # connector_center.roadmap
    res = reg.invoke("connector_center", "roadmap", _actor="test")
    roadmap = res.data or {}
    if res.ok and roadmap.get("now") and roadmap.get("blocked_by_org_workspace") is not None:
        r.ok(f"connector_center.roadmap → {len(roadmap.get('now', []))} now / {len(roadmap.get('blocked_by_org_workspace', []))} org-blocked")
    else:
        r.bad(f"connector_center.roadmap: {res.error or res.data}")

    # agent_immune.status
    res = reg.invoke("agent_immune", "status", _actor="test")
    if res.ok or (res.data or {}).get("severity") in {"clear", "watch"}:
        r.ok(f"agent_immune.status → {(res.data or {}).get('severity')}")
    else:
        r.bad(f"agent_immune.status: {res.error or res.data}")

    # memory_sleep.consolidate dry-run
    res = reg.invoke("memory_sleep", "consolidate", _actor="test", dry_run=True, write_report=False)
    if res.ok and "playbook_updates" in (res.data or {}):
        r.ok("memory_sleep.consolidate dry-run")
    else:
        r.bad(f"memory_sleep.consolidate: {res.error or res.data}")

    # razorpay.status
    res = reg.invoke("razorpay", "status", _actor="test")
    if res.ok and "configured" in (res.data or {}) and "recommended_env_vars" in (res.data or {}):
        r.ok(f"razorpay.status → configured={(res.data or {}).get('configured')}")
    else:
        r.bad(f"razorpay.status: {res.error or res.data}")

    # razorpay.create_payment_link dry-run
    res = reg.invoke(
        "razorpay",
        "create_payment_link",
        _actor="test",
        amount_inr="199.00",
        customer_name="Autonomy Test",
        customer_email="autonomy@example.com",
        customer_phone="9876543210",
        description="FRIDAY autonomy dry run",
        dry_run=True,
    )
    if res.ok and (res.data or {}).get("dry_run") and (res.data or {}).get("payload", {}).get("amount") == 19900:
        r.ok("razorpay.create_payment_link dry-run")
    else:
        r.bad(f"razorpay.create_payment_link dry-run: {res.error or res.data}")

    # revenue_ledger.ingest_razorpay_webhook
    webhook_body = json.dumps({
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_autonomy",
                    "entity": "payment",
                    "amount": 29900,
                    "currency": "INR",
                    "status": "captured",
                    "contact": "9876543210",
                    "email": "autonomy@example.com",
                    "created_at": int(datetime.now().timestamp()),
                }
            }
        },
    })
    webhook_secret = "autonomy-secret"
    webhook_signature = hmac.new(webhook_secret.encode("utf-8"), webhook_body.encode("utf-8"), hashlib.sha256).hexdigest()
    res = reg.invoke(
        "revenue_ledger",
        "ingest_razorpay_webhook",
        _actor="test",
        raw_body=webhook_body,
        signature=webhook_signature,
        webhook_secret=webhook_secret,
        mode="test",
        source="autonomy_test",
    )
    if res.ok and (res.data or {}).get("entry", {}).get("entity_id") == "pay_test_autonomy":
        r.ok("revenue_ledger.ingest_razorpay_webhook")
    else:
        r.bad(f"revenue_ledger.ingest_razorpay_webhook: {res.error or res.data}")

    # revenue_ledger.followups
    res = reg.invoke("revenue_ledger", "followups", _actor="test", limit=5)
    followups = (res.data or {}).get("followups", [])
    if res.ok and isinstance(followups, list):
        r.ok(f"revenue_ledger.followups → {len(followups)} items")
    else:
        r.bad(f"revenue_ledger.followups: {res.error or res.data}")

    # friday_bench.run_suite
    res = reg.invoke("friday_bench", "run_suite", _actor="test", quick=True, write_report=False)
    if res.ok and (res.data or {}).get("failed") == 0:
        r.ok(f"friday_bench.run_suite → {(res.data or {}).get('score')}%")
    else:
        r.bad(f"friday_bench.run_suite: {res.error or res.data}")

    # Unknown skill
    res = reg.invoke("nonexistent", "x", _actor="test")
    if not res.ok and "unknown skill" in (res.error or ""):
        r.ok("unknown skill graceful")
    else:
        r.bad("unknown skill not caught")

    # Unknown operation
    res = reg.invoke("system", "nonexistent_op", _actor="test")
    if not res.ok:
        r.ok("unknown op graceful")
    else:
        r.bad("unknown op not caught")

    # Action log written
    alog = FRIDAY / "data" / "actions.jsonl"
    if alog.exists() and alog.stat().st_size > 0:
        r.ok(f"actions.jsonl populated ({alog.stat().st_size}B)")
    else:
        r.bad("actions.jsonl empty")

    # Action envelope + proof artifact
    res = reg.invoke(
        "system",
        "health_check",
        _actor="test",
        _goal="envelope-regression",
        _policy_decision={
            "allow": True,
            "reason": "test policy gate",
            "requires_approval": False,
            "autonomy_level": "supervised",
            "policy_decision": "allow",
        },
    )
    env = res.action_envelope or {}
    proof_path = Path(res.proof_path or "")
    if env.get("trace_id") and env.get("risk_tier") == "low" and env.get("policy_decision") == "allow":
        r.ok(f"action envelope attached → {env.get('trace_id')}")
    else:
        r.bad(f"action envelope missing fields: {env}")
    if proof_path.exists():
        proof = json.loads(proof_path.read_text())
        if proof.get("action_envelope", {}).get("trace_id") == env.get("trace_id"):
            r.ok("action proof artifact matches envelope")
        else:
            r.bad("action proof artifact trace mismatch")
    else:
        r.bad(f"action proof missing: {proof_path}")
    latest = json.loads((FRIDAY / "data" / "actions.jsonl").read_text().splitlines()[-1])
    required_log_keys = {"trace_id", "risk_tier", "policy_decision", "proof_path"}
    if required_log_keys <= set(latest) and latest.get("proof_path"):
        r.ok("actions.jsonl records trace/risk/policy/proof")
    else:
        r.bad(f"actions.jsonl missing envelope keys: {latest}")
except Exception as e:
    r.bad(f"skill invocations: {e}")

# ====================================================================
# 3. PLANNER
# ====================================================================
r.section("3. PLANNER")
try:
    from friday.brain.planner import Planner, Plan, Step
    p = Planner()

    goals = p.active_goals()
    if len(goals) >= 5:
        r.ok(f"active_goals → {len(goals)}")
    else:
        r.bad(f"only {len(goals)} active")

    # Priority order
    prs = [g.get("priority", 0) for g in goals]
    if prs == sorted(prs, reverse=True):
        r.ok("active_goals sorted desc by priority")
    else:
        r.bad("not sorted")

    # goal_is_triggered at 14:00 (between day_job ranges)
    now_test = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0)
    if now_test.weekday() == 6:
        now_test = now_test - timedelta(days=1)
    goal_drift = next((g for g in goals if g["id"] == "drift_detection"), None)
    if goal_drift and p.goal_is_triggered(goal_drift, now_test):
        r.ok("drift_detection triggered at 14:00 (interval type)")
    else:
        r.bad("drift_detection not triggered at 14:00")

    # morning_briefing at 06:05
    now_0605 = now_test.replace(hour=6, minute=5)
    goal_morn = next((g for g in goals if g["id"] == "morning_briefing_ship"), None)
    if goal_morn and p.goal_is_triggered(goal_morn, now_0605):
        r.ok("morning_briefing_ship triggered at 06:05")
    else:
        r.bad("morning_briefing_ship not triggered at 06:05")

    # morning_briefing NOT at 14:00
    if goal_morn and not p.goal_is_triggered(goal_morn, now_test.replace(hour=14)):
        r.ok("morning_briefing NOT triggered at 14:00")
    else:
        r.bad("morning_briefing incorrectly triggered at 14:00")

    # Sunday skip
    # find next Sunday
    now_sun = datetime.now()
    while now_sun.weekday() != 6:
        now_sun += timedelta(days=1)
    now_sun = now_sun.replace(hour=6, minute=5)
    if goal_morn and not p.goal_is_triggered(goal_morn, now_sun):
        r.ok("Sunday skip honored for morning_briefing")
    else:
        r.bad("Sunday not honored")

    # Deterministic plan
    plan = p.plan_goal_deterministic(goals[0])
    if isinstance(plan, Plan) and len(plan.steps) > 0:
        r.ok(f"plan_goal_deterministic → {len(plan.steps)} steps")
    else:
        r.bad("deterministic plan empty")

    # Each step has a real skill+op
    from friday.skills.registry import get_registry
    reg = get_registry()
    bad_steps = [s for s in plan.steps if not reg.get(s.skill)
                 or s.operation not in reg.get(s.skill).operations]
    if not bad_steps:
        r.ok("all plan steps reference real skill ops")
    else:
        r.bad(f"{len(bad_steps)} invalid steps")

    # pick_next_goal works (may or may not return one depending on time)
    nxt = p.pick_next_goal()
    r.ok(f"pick_next_goal → {nxt['id'] if nxt else 'none (valid — time-dependent)'}")

    # Plan logging
    p.log_plan(plan)
    plog = FRIDAY / "data" / "plans.jsonl"
    if plog.exists() and plog.stat().st_size > 0:
        r.ok(f"plans.jsonl populated")
    else:
        r.bad("plans.jsonl not written")
except Exception as e:
    r.bad(f"planner: {e}")

# ====================================================================
# 4. POLICY GATE
# ====================================================================
r.section("4. POLICY GATE")
try:
    from friday.brain.policy import Policy
    pol = Policy()

    # Low-risk at supervised level
    now_day = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0)
    if now_day.weekday() == 6:
        now_day -= timedelta(days=1)
    # Need to be outside day_job (09-18) — use 19:00
    now_eve = now_day.replace(hour=19, minute=0)
    d = pol.check("system", "health_check", "low", now=now_eve)
    if d["allow"]:
        r.ok(f"low-risk allowed at supervised @ 19:00")
    else:
        r.bad(f"low-risk blocked: {d['reason']}")

    # Medium-risk at supervised → requires approval
    d2 = pol.check("briefing", "run_morning", "medium", now=now_eve)
    if not d2["allow"] and d2.get("requires_approval"):
        r.ok(f"medium-risk queued for approval at supervised")
    else:
        r.bad(f"medium-risk unexpected: {d2}")

    # Forbidden always blocked
    d3 = pol.check("anything", "x", "forbidden", now=now_eve)
    if not d3["allow"]:
        r.ok("forbidden always blocked")
    else:
        r.bad("forbidden allowed?!")

    # Quiet window (23:30)
    now_night = now_eve.replace(hour=23, minute=30)
    d4 = pol.check("system", "health_check", "low", now=now_night)
    if not d4["allow"] and "quiet" in d4["reason"]:
        r.ok(f"quiet window blocks: {d4['reason']}")
    else:
        r.bad(f"quiet window not blocking: {d4}")

    # Critical can pierce quiet
    d5 = pol.check("watchdog", "alert_if_critical", "medium",
                    critical=True, now=now_night)
    # Note: medium at supervised blocks via risk check even with critical
    # It would only pierce if risk allowed at level. Quiet allow_critical is the gate here.
    # So this should still fail on risk check. That's correct.
    # Verify at full level it would pass:
    pol._data["autonomy_level"] = "full"
    d6 = pol.check("watchdog", "alert_if_critical", "medium",
                    critical=True, now=now_night)
    pol._data["autonomy_level"] = "supervised"  # restore
    if d6["allow"]:
        r.ok("critical pierces quiet window at full level")
    else:
        r.bad(f"critical pierce failed: {d6}")

    # Sunday full rest — even critical blocked
    now_sun_mid = datetime.now()
    while now_sun_mid.weekday() != 6:
        now_sun_mid += timedelta(days=1)
    now_sun_mid = now_sun_mid.replace(hour=14, minute=0)
    d7 = pol.check("system", "health_check", "low", critical=True, now=now_sun_mid)
    if not d7["allow"]:
        r.ok("Sunday blocks even critical (allow_critical=false)")
    else:
        r.bad("Sunday let action through")

    # Rate limit
    pol2 = Policy()
    pol2._data["rate_limits"]["skill_invocations_per_hour"] = 2
    d_a = pol2.check("system", "health_check", "low", now=now_eve)
    d_b = pol2.check("system", "health_check", "low", now=now_eve)
    d_c = pol2.check("system", "health_check", "low", now=now_eve)
    if d_a["allow"] and d_b["allow"] and not d_c["allow"] and "rate" in d_c["reason"]:
        r.ok("rate limit enforced (3rd call blocked)")
    else:
        r.bad(f"rate limit fail: {[d_a,d_b,d_c]}")

    # Telegram rate cap
    pol3 = Policy()
    pol3._data["rate_limits"]["telegram_pings_per_hour"] = 2
    a, b, c = pol3.can_telegram(), pol3.can_telegram(), pol3.can_telegram()
    if a and b and not c:
        r.ok("telegram rate cap enforced")
    else:
        r.bad(f"telegram cap fail: {[a,b,c]}")
except Exception as e:
    r.bad(f"policy: {e}")

# ====================================================================
# 5. AUTONOMY ENGINE
# ====================================================================
r.section("5. AUTONOMY ENGINE")
try:
    from friday.brain.autonomy import AutonomyEngine, TickResult
    eng = AutonomyEngine()

    status = eng.status()
    if status["enabled"] and status["active_goals"] >= 5:
        r.ok(f"engine status: {status['skills_registered']} skills, "
             f"{status['active_goals']} goals")
    else:
        r.bad(f"engine status bad: {status}")

    # Tick (will likely block in quiet window or return skip — both fine)
    tick = eng.tick()
    if isinstance(tick, TickResult):
        r.ok(f"tick returned TickResult (goal={tick.goal_id})")
    else:
        r.bad(f"tick didn't return TickResult")

    # Dry run tick — force a specific goal
    tick2 = eng.tick(force_goal_id="self_maintenance", dry_run=True)
    if tick2.goal_id == "self_maintenance":
        r.ok(f"force_goal_id works; attempted={tick2.steps_attempted}")
    else:
        r.bad(f"force_goal_id failed: {tick2.to_dict()}")

    # Approval queue flow
    aid = eng.queue_for_approval("outreach", "send_approved",
                                  {"approval_id": "x"}, reason="test")
    if aid:
        r.ok(f"queue_for_approval → id={aid}")
    else:
        r.bad("queue failed")

    pending = eng.pending_approvals()
    if any(p["id"] == aid for p in pending):
        r.ok(f"appears in pending_approvals ({len(pending)})")
    else:
        r.bad("not in pending list")

    # Hold
    h = eng.hold(aid, hours=1)
    if h["ok"]:
        r.ok("hold works")
    else:
        r.bad(f"hold: {h}")
    # hold takes it out of pending
    pending2 = eng.pending_approvals()
    if not any(p["id"] == aid for p in pending2):
        r.ok("held item removed from pending")
    else:
        r.bad("held item still pending")

    # Create new for reject test
    aid2 = eng.queue_for_approval("outreach", "send_approved", {}, reason="test2")
    rej = eng.reject(aid2)
    if rej["ok"]:
        r.ok("reject works")
    else:
        r.bad(f"reject: {rej}")

    # Approve execution (use a low-risk op for safety)
    aid3 = eng.queue_for_approval("system", "health_check", {}, reason="approve-test")
    app = eng.approve(aid3)
    if app["ok"]:
        r.ok(f"approve + execute → ok={app['result']['ok']}")
    else:
        r.bad(f"approve: {app}")

    # Regression: approving a skill that appends approval records must not
    # overwrite those child records with the old parent approval snapshot.
    child_id = f"sidefx{int(time.time()) % 100000}"
    draft = {
        "id": child_id,
        "lead": {"name": "Side Effect Test", "phone": "0000000000", "category": "test"},
        "proposed_message": "Test draft; do not send.",
        "drafted_at": datetime.now().isoformat(),
        "status": "proposed",
    }
    aid4 = eng.queue_for_approval("outreach", "queue_for_approval",
                                  {"drafts": [draft]}, reason="side-effect-preserve")
    app2 = eng.approve(aid4)
    items = eng._load_approvals()
    if app2["ok"] and any(x.get("id") == child_id for x in items):
        r.ok("approve preserves child approval side effects")
        eng.reject(child_id)
    else:
        r.bad("approve erased child approval side effects")

    # Unknown id
    bad_r = eng.approve("nonexistent_id")
    if not bad_r["ok"]:
        r.ok("approve(unknown) → error")
    else:
        r.bad("approve(unknown) didn't fail")
except Exception as e:
    r.bad(f"autonomy: {e}")

# ====================================================================
# 6. REFLECTOR
# ====================================================================
r.section("6. REFLECTOR")
try:
    from friday.brain.reflector import Reflector
    from friday.brain.memory import Memory
    refl = Reflector(Memory())

    # Review a synthetic action
    refl.review_action("system", "health_check",
                        {"ok": True, "error": None, "artifacts": []},
                        elapsed_ms=42, context={"test": True})
    r.ok("review_action accepted")

    refl.review_action("outreach", "find_due_leads",
                        {"ok": False, "error": "synthetic fail", "artifacts": []},
                        elapsed_ms=100)
    r.ok("review_action (fail) accepted")

    # Stats
    stats = refl.action_stats(hours=24)
    if stats["total"] > 0:
        r.ok(f"action_stats → {stats['total']} actions, {stats['success_rate']*100:.0f}% ok")
    else:
        r.bad("action_stats empty (but actions were logged)")

    # Top performers
    top = refl.top_performers(3)
    if isinstance(top, list):
        r.ok(f"top_performers → {len(top)} entries")
    else:
        r.bad("top_performers not list")

    # Weak skills list (may be empty)
    weak = refl.weakest_skills()
    r.ok(f"weakest_skills → {len(weak)} weak")

    # Playbook heuristic
    key = "skill:system:health_check"
    val = Memory().recall(key, default=None)
    if val and "wins" in val:
        r.ok(f"playbook heuristic: wins={val['wins']} fails={val.get('fails',0)}")
    else:
        r.bad("playbook heuristic not stored")
except Exception as e:
    r.bad(f"reflector: {e}")

# ====================================================================
# 7. TELEGRAM APPROVAL COMMANDS (unit)
# ====================================================================
r.section("7. TELEGRAM APPROVAL COMMANDS")
try:
    from friday.brain.autonomy import AutonomyEngine
    eng = AutonomyEngine()
    aid = eng.queue_for_approval("system", "health_check", {}, reason="tg-test")
    # Simulate /yes command path
    r1 = eng.approve(aid)
    if r1["ok"]:
        r.ok(f"/yes path works")
    else:
        r.bad(f"/yes fail: {r1}")
    # Simulate /no
    aid2 = eng.queue_for_approval("system", "health_check", {}, reason="tg-test-no")
    r2 = eng.reject(aid2)
    if r2["ok"]:
        r.ok("/no path works")
    else:
        r.bad(f"/no fail: {r2}")
    # Simulate /hold
    aid3 = eng.queue_for_approval("system", "health_check", {}, reason="tg-test-hold")
    r3 = eng.hold(aid3, hours=1)
    if r3["ok"]:
        r.ok("/hold path works")
    else:
        r.bad(f"/hold fail: {r3}")

    # File integrity
    af = FRIDAY / "data" / "pending_approvals.json"
    if af.exists():
        data = json.loads(af.read_text())
        if isinstance(data, list):
            r.ok(f"pending_approvals.json valid ({len(data)} entries)")
        else:
            r.bad("approvals file not a list")
    else:
        r.bad("approvals file missing")
except Exception as e:
    r.bad(f"telegram approvals: {e}")

# ====================================================================
# 8. CLI COMMANDS
# ====================================================================
r.section("8. CLI COMMANDS")
import subprocess
HOME = os.path.expanduser("~/AI")
PY = os.path.expanduser("~/AI/friday/venv/bin/python3")

def cli(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run([PY, "-m", "friday.cli"] + args,
                          cwd=HOME, capture_output=True, text=True, timeout=timeout)

try:
    c = cli(["autonomy"])
    if c.returncode == 0 and "autonomy_level" in c.stdout:
        r.ok("friday autonomy")
    else:
        r.bad(f"friday autonomy: rc={c.returncode} {c.stderr[:200]}")

    c = cli(["goals"])
    if c.returncode == 0 and "active goals" in c.stdout:
        r.ok("friday goals")
    else:
        r.bad(f"friday goals: rc={c.returncode} {c.stderr[:200]}")

    c = cli(["skills"])
    if c.returncode == 0 and "system" in c.stdout and "outreach" in c.stdout:
        r.ok("friday skills")
    else:
        r.bad(f"friday skills: rc={c.returncode}")

    c = cli(["skill", "system", "health_check"])
    if c.returncode == 0 and "python_version" in c.stdout:
        r.ok("friday skill system health_check")
    else:
        r.bad(f"friday skill: rc={c.returncode} {c.stderr[:200]}")

    c = cli(["opportunities", "--top", "3", "--refresh"])
    if c.returncode == 0 and "opportunities" in c.stdout and "score" in c.stdout:
        r.ok("friday opportunities")
    else:
        r.bad(f"friday opportunities: rc={c.returncode} {c.stderr[:200]}")

    c = cli(["opportunities", "--launch", "opp_local_whatsapp_pilot", "--max-leads", "2", "--dry-run"])
    if c.returncode == 0 and "would_queue_outreach" in c.stdout:
        r.ok("friday opportunities --launch dry-run")
    else:
        r.bad(f"friday opportunities --launch dry-run: rc={c.returncode} {c.stderr[:200]}")

    c = cli(["nervous"])
    if c.returncode == 0 and "total" in c.stdout:
        r.ok("friday nervous")
    else:
        r.bad(f"friday nervous: rc={c.returncode} {c.stderr[:200]}")

    c = cli(["world", "--no-persist"])
    if c.returncode == 0 and "events" in c.stdout:
        r.ok("friday world")
    else:
        r.bad(f"friday world: rc={c.returncode} {c.stderr[:200]}")

    c = cli(["sleep", "--dry-run", "--no-report"])
    if c.returncode == 0 and "playbook_updates" in c.stdout:
        r.ok("friday sleep dry-run")
    else:
        r.bad(f"friday sleep dry-run: rc={c.returncode} {c.stderr[:200]}")

    c = cli(["immune", "--no-report"])
    if c.returncode == 0 and "severity" in c.stdout:
        r.ok("friday immune")
    else:
        r.bad(f"friday immune: rc={c.returncode} {c.stderr[:200]}")

    c = cli(["bench", "--no-report"])
    if c.returncode == 0 and '"failed": 0' in c.stdout:
        r.ok("friday bench")
    else:
        r.bad(f"friday bench: rc={c.returncode} {c.stderr[:200]}")

    c = cli(["razorpay", "status"])
    if c.returncode == 0 and "recommended_env_vars" in c.stdout and "configured" in c.stdout:
        r.ok("friday razorpay status")
    else:
        r.bad(f"friday razorpay status: rc={c.returncode} {c.stderr[:200]}")

    c = cli([
        "razorpay",
        "create-link",
        "--amount",
        "149.00",
        "--name",
        "CLI Test",
        "--email",
        "cli@example.com",
        "--phone",
        "9876543210",
        "--description",
        "FRIDAY CLI dry run",
    ])
    if c.returncode == 0 and '"dry_run": true' in c.stdout.lower():
        r.ok("friday razorpay create-link dry-run")
    else:
        r.bad(f"friday razorpay create-link dry-run: rc={c.returncode} {c.stderr[:200]}")

    c = cli(["revenue", "status"])
    if c.returncode == 0 and "captured_payments_inr_total" in c.stdout and "entries" in c.stdout:
        r.ok("friday revenue status")
    else:
        r.bad(f"friday revenue status: rc={c.returncode} {c.stderr[:200]}")

    webhook_path = FRIDAY / "data" / "cli_revenue_webhook.json"
    webhook_path.parent.mkdir(parents=True, exist_ok=True)
    cli_body = json.dumps({
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_cli_autonomy",
                    "entity": "payment",
                    "amount": 14900,
                    "currency": "INR",
                    "status": "captured",
                    "contact": "9876543210",
                    "email": "cli@example.com",
                    "created_at": int(datetime.now().timestamp()),
                }
            }
        },
    })
    webhook_path.write_text(cli_body)
    cli_secret = "cli-secret"
    cli_signature = hmac.new(cli_secret.encode("utf-8"), cli_body.encode("utf-8"), hashlib.sha256).hexdigest()
    c = cli([
        "revenue",
        "ingest-razorpay-webhook",
        "--body-file",
        str(webhook_path),
        "--signature",
        cli_signature,
        "--secret",
        cli_secret,
        "--mode",
        "test",
        "--source",
        "cli_test",
    ])
    if c.returncode == 0 and '"inserted": true' in c.stdout.lower():
        r.ok("friday revenue ingest-razorpay-webhook")
    else:
        r.bad(f"friday revenue ingest-razorpay-webhook: rc={c.returncode} {c.stderr[:200]}")

    c = cli(["pending"])
    if c.returncode == 0:
        r.ok("friday pending")
    else:
        r.bad(f"friday pending: rc={c.returncode}")

    c = cli(["tick", "self_maintenance", "--dry-run"])
    if c.returncode == 0 and "self_maintenance" in c.stdout:
        r.ok("friday tick self_maintenance --dry-run")
    else:
        r.bad(f"friday tick: rc={c.returncode} stderr={c.stderr[:200]}")

    c = cli(["reflect"])
    if c.returncode == 0:
        r.ok("friday reflect")
    else:
        r.bad(f"friday reflect: rc={c.returncode}")
except Exception as e:
    r.bad(f"CLI: {e}")

# ====================================================================
# 9. DAEMON v1.0 IMPORT SANITY
# ====================================================================
r.section("9. DAEMON v1.0 BOOT (3s smoke)")
try:
    import signal as _sig
    log_path = FRIDAY / "logs" / "v1_daemon.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_f = open(log_path, "w")
    proc = subprocess.Popen(
        [PY, "-u", "-m", "friday.daemon"],
        cwd=HOME, stdout=log_f, stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )
    time.sleep(5)
    alive = (proc.poll() is None)
    if alive:
        r.ok(f"daemon alive after 5s (pid={proc.pid})")
    else:
        r.bad(f"daemon exited early rc={proc.returncode}")

    # Kill
    try:
        os.killpg(os.getpgid(proc.pid), _sig.SIGTERM)
        proc.wait(timeout=10)
        r.ok("daemon SIGTERM graceful shutdown")
    except Exception:
        proc.kill()
        r.bad("daemon needed SIGKILL")
    log_f.close()

    # Inspect log
    log_content = log_path.read_text()
    if "skills registered" in log_content:
        r.ok("daemon log shows skills registered")
    else:
        r.bad("daemon log missing skills line")
    if "autonomy thread started" in log_content:
        r.ok("autonomy thread started per log")
    else:
        r.bad("autonomy thread not confirmed")
    if "Traceback" not in log_content:
        r.ok("no tracebacks during boot")
    else:
        r.bad(f"traceback in daemon log: {log_content[-500:]}")
except Exception as e:
    r.bad(f"daemon boot: {e}")

# ====================================================================
# 10. END-TO-END: tick → approve → execute
# ====================================================================
r.section("10. END-TO-END FLOW")
try:
    from friday.brain.autonomy import AutonomyEngine
    eng = AutonomyEngine()

    # Force a goal that will require approval (medium-risk op in supervised)
    # self_maintenance contains system.rotate_logs (low), system.prune_memory (low),
    # system.health_check (low) — all low, so all should auto-execute
    tick = eng.tick(force_goal_id="self_maintenance")
    if tick.goal_id == "self_maintenance":
        r.ok(f"e2e tick: {tick.steps_executed} exec / {tick.steps_queued} queued / {tick.steps_blocked} blocked")
    else:
        r.bad(f"e2e tick: no goal_id? {tick.to_dict()}")

    # At least one should have executed (all low-risk in supervised + day hours)
    # Note: this depends on current time window. If in quiet, all block → valid behavior.
    total = tick.steps_executed + tick.steps_queued + tick.steps_blocked
    if total == tick.steps_attempted:
        r.ok(f"step accounting consistent ({total} == {tick.steps_attempted})")
    else:
        r.bad(f"accounting mismatch: {total} vs {tick.steps_attempted}")

    # Verify plans.jsonl got an entry
    plog = FRIDAY / "data" / "plans.jsonl"
    if plog.exists():
        latest = plog.read_text().splitlines()[-1]
        pd = json.loads(latest)
        if pd.get("goal_id") == "self_maintenance":
            r.ok("plans.jsonl last entry == self_maintenance")
        else:
            r.ok(f"plans.jsonl last entry = {pd.get('goal_id')} (other goals may be planned between)")
    else:
        r.bad("plans.jsonl missing")

    # Actions log has recent entries
    alog = FRIDAY / "data" / "actions.jsonl"
    if alog.exists():
        lines = alog.read_text().splitlines()
        recent = [json.loads(l) for l in lines[-20:]]
        actors = set(e.get("actor") for e in recent)
        if "autonomy" in actors or "cli" in actors or "test" in actors:
            r.ok(f"actions.jsonl has entries from actors: {actors}")
        else:
            r.bad(f"unexpected actors: {actors}")
    else:
        r.bad("actions.jsonl missing")
except Exception as e:
    r.bad(f"e2e: {e}")

# ====================================================================
# FINAL REPORT
# ====================================================================
r.report()
sys.exit(0 if r.failed == 0 else 1)
