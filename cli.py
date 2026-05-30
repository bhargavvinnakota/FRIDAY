#!/usr/bin/env python3
"""
Friday :: Command Line Interface (v1.0)

    friday ask "<question>"       - one-shot query
    friday chat                   - interactive REPL
    friday status                 - empire snapshot
    friday briefing               - run morning briefing now
    friday debrief                - run evening debrief now
    friday heartbeat              - run one sensor sweep
    friday absorb-openclaw        - import the real OpenClaw conversational seed
    friday memory                 - inspect memory
    friday remember KEY=VALUE     - store a fact
    friday forget KEY             - delete fact
    friday test                   - smoke test all components

  v1.0 AUTONOMY:
    friday autonomy               - autonomy engine status
    friday goals                  - list active goals
    friday tick [GOAL_ID]         - run one autonomy tick
    friday plan "<freeform>"      - LLM-generate a plan
    friday skills                 - list registered skills
    friday skill SKILL OP [k=v]   - invoke a skill op directly
    friday pending                - list pending approvals
    friday approve ID             - approve a queued action
    friday reject ID              - reject a queued action
    friday reflect                - show 24h action stats + heuristics
    friday journal                - write nightly reflection now
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

# Make the active checkout importable even when it lives outside ~/AI/friday.
_CLI_ROOT = Path(os.environ.get("FRIDAY_ROOT", Path(__file__).resolve().parent)).expanduser().resolve()
if str(_CLI_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(_CLI_ROOT.parent))

from friday.brain.engine import MultiEngine
from friday.brain.memory import Memory
from friday.brain.orchestrator import Orchestrator, Tool
from friday.actions import nexus, comms, computer
from friday.paths import FRIDAY_ROOT


def cmd_ask(args):
    eng = MultiEngine()
    mem = Memory()
    orch = Orchestrator(eng, mem)
    # Tool order matters — first match wins. Agency/trading before general snapshot.
    orch.register(Tool(
        "agency_summary", "Agency clients + leads + CRM.",
        triggers=["client", "clients", "lead", "leads", "outreach", "crm", "agency", "whatsapp bot"],
        fn=lambda **kw: {"clients": nexus.agency_clients(),
                         "leads": nexus.leads_summary(),
                         "crm": nexus.crm_summary()},
    ))
    orch.register(Tool(
        "trading_state", "Trading brain state.",
        triggers=["trading", "trade", "portfolio", "p&l", "pnl", "regime", "positions", "nexus omega"],
        fn=lambda **kw: {"brain": nexus.trading_state(), "portfolio": nexus.portfolio_state()},
    ))
    orch.register(Tool(
        "empire_snapshot", "Full empire status across all engines.",
        triggers=["empire", "snapshot", "status", "overview", "all engines", "dashboard"],
        fn=lambda **kw: nexus.snapshot(),
    ))
    orch.register(Tool(
        "mission_brief", "Friday vision, capabilities, gaps, and next action.",
        triggers=[
            "vision", "mission", "capabilities", "capability", "what can you do",
            "what are you built for", "build friday", "gap", "gaps", "next action",
            "what should we build", "friday roadmap", "master plan"
        ],
        fn=lambda **kw: _mission_brief_data(),
    ))

    q = " ".join(args.query)
    result = orch.respond(q, use_tools=True, heavy=args.heavy)
    print(result["reply"])
    print(f"\n— [{result['engine']}" + (f" · {result['tool_used']}" if result["tool_used"] else "") + "]")


def cmd_chat(args):
    eng = MultiEngine()
    mem = Memory()
    orch = Orchestrator(eng, mem)
    print("Friday :: chat mode. Type 'exit' to quit.\n")
    while True:
        try:
            q = input("you > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nexit.")
            break
        if not q:
            continue
        if q.lower() in ("exit", "quit", "bye"):
            break
        result = orch.respond(q, use_tools=True)
        print(f"friday> {result['reply']}\n[{result['engine']}]\n")


def _mission_brief_data():
    from friday.skills.registry import get_registry
    res = get_registry().invoke("mission_control", "mission_brief", _actor="cli")
    if not res.ok:
        return {"error": res.error}
    return res.data


def cmd_mission(args):
    from friday.skills.registry import get_registry
    reg = get_registry()
    op_by_mode = {
        "capabilities": "capability_map",
        "gaps": "gap_report",
        "next": "next_action",
        "brief": "mission_brief",
    }
    op_name = op_by_mode.get(args.mode, "mission_brief")
    result = reg.invoke("mission_control", op_name, _actor="cli")
    print(json.dumps(result.to_dict(), indent=2, default=str))


def cmd_operate(args):
    """Run Friday's safe operator loop and emit proof artifacts."""
    from friday.skills.registry import get_registry

    reg = get_registry()
    mission = reg.invoke("mission_control", "mission_brief", _actor="operate")
    outreach_status = reg.invoke("outreach", "status", _actor="operate")
    outbox = reg.invoke("outreach", "manual_send_outbox", _actor="operate")

    summary = {
        "ok": mission.ok and outreach_status.ok and outbox.ok,
        "mission": mission.data,
        "outreach": outreach_status.data,
        "manual_send_outbox": outbox.data,
        "artifacts": (mission.artifacts or []) + (outbox.artifacts or []),
    }
    print(json.dumps(summary, indent=2, default=str))


def cmd_unlock(args):
    """Run the 20-domain capability unlock/test pass."""
    from friday.skills.registry import get_registry

    result = get_registry().invoke("mission_control", "unlock_all", _actor="cli")
    print(json.dumps(result.to_dict(), indent=2, default=str))


def cmd_opportunities(args):
    """Rank money opportunities and optionally create the next experiment."""
    from friday.skills.registry import get_registry

    reg = get_registry()
    if args.launch:
        opportunity_id = "" if args.launch == "__top__" else args.launch
        result = reg.invoke(
            "money_engine",
            "launch_experiment",
            _actor="cli",
            _goal="money-engine",
            opportunity_id=opportunity_id,
            max_leads=args.max_leads,
            dry_run=args.dry_run,
        )
    elif args.experiment:
        result = reg.invoke(
            "money_engine",
            "create_experiment",
            _actor="cli",
            _goal="money-engine",
            opportunity_id=args.experiment,
        )
    else:
        result = reg.invoke(
            "money_engine",
            "rank_opportunities",
            _actor="cli",
            _goal="money-engine",
            top_n=args.top,
            refresh=args.refresh,
        )
    print(json.dumps(result.to_dict(), indent=2, default=str))


def _invoke_json(skill: str, operation: str, actor: str = "cli", **kwargs):
    from friday.skills.registry import get_registry
    result = get_registry().invoke(skill, operation, _actor=actor, **kwargs)
    print(json.dumps(result.to_dict(), indent=2, default=str))


def _parse_note_pairs(items: list[str]) -> dict[str, str]:
    notes: dict[str, str] = {}
    for item in items or []:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        if key:
            notes[key] = value.strip()
    return notes


def cmd_nervous(args):
    if args.mode == "recent":
        _invoke_json("nervous_system", "recent", limit=args.limit, event_type=args.event_type)
    else:
        _invoke_json("nervous_system", "status")


def cmd_immune(args):
    _invoke_json("agent_immune", "scan", hours=args.hours, write_report=not args.no_report)


def cmd_sleep(args):
    if args.latest:
        _invoke_json("memory_sleep", "latest")
    else:
        _invoke_json("memory_sleep", "consolidate", dry_run=args.dry_run, write_report=not args.no_report)


def cmd_bench(args):
    if args.latest:
        _invoke_json("friday_bench", "latest")
    else:
        _invoke_json("friday_bench", "run_suite", quick=True, write_report=not args.no_report)


def cmd_world(args):
    if args.mode == "entities":
        _invoke_json("world_twin", "entities", limit=args.limit)
    elif args.mode == "status":
        _invoke_json("world_twin", "status")
    else:
        _invoke_json("world_twin", "pulse", persist=not args.no_persist, use_web=args.web)


def cmd_connectors(args):
    if args.mode == "inventory":
        _invoke_json("connector_center", "inventory", status=args.status, category=args.category)
    elif args.mode == "gaps":
        _invoke_json("connector_center", "gaps", priority=args.priority)
    elif args.mode == "roadmap":
        _invoke_json("connector_center", "roadmap")
    elif args.mode == "test-plan":
        _invoke_json("connector_center", "test_plan", include_write_tests=args.include_write_tests)
    elif args.mode == "export":
        _invoke_json("connector_center", "export_map")
    else:
        _invoke_json("connector_center", "status")


def cmd_revenue(args):
    if args.revenue_cmd == "latest":
        _invoke_json("revenue_ledger", "latest", limit=args.limit)
    elif args.revenue_cmd == "followups":
        _invoke_json("revenue_ledger", "followups", limit=args.limit)
    elif args.revenue_cmd == "sync-razorpay":
        _invoke_json(
            "revenue_ledger",
            "sync_razorpay",
            count=args.count,
            include_payments=not args.no_payments,
            include_links=not args.no_links,
            include_orders=not args.no_orders,
            include_subscriptions=args.include_subscriptions,
            mode=args.mode,
        )
    elif args.revenue_cmd == "ingest-razorpay-webhook":
        raw_body = Path(args.body_file).expanduser().read_text()
        _invoke_json(
            "revenue_ledger",
            "ingest_razorpay_webhook",
            raw_body=raw_body,
            signature=args.signature,
            webhook_secret=args.secret,
            mode=args.mode,
            source=args.source,
        )
    else:
        _invoke_json("revenue_ledger", "status", days=args.days)


def cmd_razorpay(args):
    note_map = _parse_note_pairs(getattr(args, "note", []) or [])
    if args.razorpay_cmd == "payments":
        _invoke_json(
            "razorpay",
            "fetch_payments",
            count=args.count,
            skip=args.skip,
            from_ts=args.from_ts,
            to_ts=args.to_ts,
            mode=args.mode,
        )
    elif args.razorpay_cmd == "orders":
        _invoke_json(
            "razorpay",
            "fetch_orders",
            count=args.count,
            skip=args.skip,
            from_ts=args.from_ts,
            to_ts=args.to_ts,
            mode=args.mode,
        )
    elif args.razorpay_cmd == "links":
        _invoke_json(
            "razorpay",
            "fetch_payment_links",
            count=args.count,
            skip=args.skip,
            from_ts=args.from_ts,
            to_ts=args.to_ts,
            mode=args.mode,
        )
    elif args.razorpay_cmd == "subscriptions":
        _invoke_json(
            "razorpay",
            "fetch_subscriptions",
            count=args.count,
            skip=args.skip,
            mode=args.mode,
        )
    elif args.razorpay_cmd == "create-link":
        _invoke_json(
            "razorpay",
            "create_payment_link",
            amount=args.amount,
            customer_name=args.name,
            customer_email=args.email,
            customer_phone=args.phone,
            description=args.description,
            reference_id=args.reference_id,
            accept_partial=args.accept_partial,
            first_min_partial_amount=args.first_min_partial_amount,
            expiry_minutes=args.expiry_minutes,
            notify_email=args.notify_email,
            notify_sms=args.notify_sms,
            callback_url=args.callback_url,
            callback_method=args.callback_method,
            reminder_enable=args.reminder_enable,
            upi_link=args.upi_link,
            notes=note_map,
            dry_run=not args.commit,
            mode=args.mode,
        )
    elif args.razorpay_cmd == "create-order":
        _invoke_json(
            "razorpay",
            "create_order",
            amount=args.amount,
            receipt=args.receipt,
            partial_payment=args.partial_payment,
            first_payment_min_amount=args.first_payment_min_amount,
            notes=note_map,
            dry_run=not args.commit,
            mode=args.mode,
        )
    elif args.razorpay_cmd == "create-subscription":
        _invoke_json(
            "razorpay",
            "create_subscription",
            plan_id=args.plan_id,
            total_count=args.total_count,
            quantity=args.quantity,
            customer_notify=args.customer_notify,
            start_at=args.start_at,
            expire_by=args.expire_by,
            notes=note_map,
            dry_run=not args.commit,
            mode=args.mode,
        )
    elif args.razorpay_cmd == "verify-payment":
        _invoke_json(
            "razorpay",
            "verify_payment_signature",
            order_id=args.order_id,
            payment_id=args.payment_id,
            signature=args.signature,
            mode=args.mode,
        )
    elif args.razorpay_cmd == "verify-webhook":
        raw_body = Path(args.body_file).expanduser().read_text()
        _invoke_json(
            "razorpay",
            "verify_webhook_signature",
            raw_body=raw_body,
            signature=args.signature,
            mode=args.mode,
        )
    else:
        _invoke_json("razorpay", "status", probe=args.probe, mode=args.mode)


def cmd_status(args):
    snap = nexus.snapshot()
    print(json.dumps(snap, indent=2, default=str))


def cmd_briefing(args):
    from friday.loops.morning import run as run_morning
    run_morning()


def cmd_debrief(args):
    from friday.loops.evening import run as run_evening
    run_evening()


def cmd_heartbeat(args):
    from friday.loops.heartbeat import sweep
    mem = Memory()
    findings = sweep(mem)
    print(json.dumps(findings, indent=2, default=str))


def cmd_memory(args):
    mem = Memory()
    d = mem._data
    print(f"Facts:  {len(d.get('facts', {}))}")
    print(f"Events: {len(d.get('events', []))}")
    print(f"Turns:  {len(d.get('recent_turns', []))}")
    if args.dump:
        print("\n--- FACTS ---")
        print(json.dumps(d.get("facts", {}), indent=2))
        print("\n--- LAST 10 EVENTS ---")
        print(json.dumps(d.get("events", [])[-10:], indent=2))


def cmd_absorb_openclaw(args):
    from friday.brain.openclaw_absorb import absorb_openclaw

    result = absorb_openclaw(
        state_dir=Path(os.path.expanduser(args.state_dir)),
        write_memory=not args.no_memory,
    )
    print(json.dumps(result, indent=2, default=str))


def cmd_remember(args):
    mem = Memory()
    for pair in args.pairs:
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        mem.remember(k.strip(), v.strip(), category=args.category)
        print(f"✓ stored: {k.strip()} = {v.strip()[:60]}")


def cmd_forget(args):
    mem = Memory()
    for k in args.keys:
        ok = mem.forget(k)
        print(f"{'✓' if ok else '✗'} {k}")


def cmd_test(args):
    print("╔══════════════════════════════════════╗")
    print("║  FRIDAY :: BOOT SEQUENCE             ║")
    print("╚══════════════════════════════════════╝\n")

    # 1. Memory
    print("[1/5] Memory...", end=" ")
    try:
        mem = Memory()
        mem.log_event("boot_test", {"ok": True})
        print(f"OK ({len(mem._data.get('facts', {}))} facts, {len(mem._data.get('events', []))} events)")
    except Exception as e:
        print(f"FAIL: {e}")

    # 2. Ollama
    print("[2/5] Ollama...", end=" ")
    try:
        eng = MultiEngine()
        if eng.ollama.health():
            r, u = eng.ask("You are Friday.", "Say 'online' in one word.", force="ollama")
            print(f"OK [{u}]: {r[:80]}")
        else:
            print("FAIL: ollama not responding on localhost:11434")
    except Exception as e:
        print(f"FAIL: {e}")

    # 3. Nexus sensors
    print("[3/5] Nexus sensors...", end=" ")
    try:
        snap = nexus.snapshot()
        print(f"OK (agency_clients={snap['agency']['clients'].get('total',0)}, "
              f"empire={snap['empire'].get('status','?')})")
    except Exception as e:
        print(f"FAIL: {e}")

    # 4. Telegram
    print("[4/5] Telegram...", end=" ")
    try:
        r = comms.telegram_push("Friday boot test ✓", silent=True)
        print("OK" if r.get("ok") else f"FAIL: {r.get('error')}")
    except Exception as e:
        print(f"FAIL: {e}")

    # 5. Computer
    print("[5/5] Computer...", end=" ")
    try:
        r = computer.shell(f"ls {FRIDAY_ROOT}")
        print("OK" if r["ok"] else f"FAIL: {r['stderr']}")
    except Exception as e:
        print(f"FAIL: {e}")

    print("\n✅ Boot sequence complete.")


# ======================================================================
# v1.0 Autonomy commands
# ======================================================================

def cmd_autonomy(args):
    from friday.brain.autonomy import AutonomyEngine
    st = AutonomyEngine().status()
    print(json.dumps(st, indent=2, default=str))


def cmd_goals(args):
    from friday.brain.planner import Planner
    goals = Planner().active_goals()
    print(f"{len(goals)} active goals:\n")
    for g in goals:
        trig = g.get("trigger", {})
        trigger_s = (f"{trig.get('start','?')}-{trig.get('end','?')}"
                     if trig.get("type") == "time_window"
                     else f"every {trig.get('every_minutes','?')}m"
                     if trig.get("type") == "interval"
                     else trig.get("type", "?"))
        print(f"  [{g.get('priority'):3}] {g.get('id'):30} {trigger_s:20} {g.get('title','')[:60]}")


def cmd_tick(args):
    from friday.brain.autonomy import AutonomyEngine
    eng = AutonomyEngine()
    result = eng.tick(force_goal_id=args.goal_id, dry_run=args.dry_run)
    print(json.dumps(result.to_dict(), indent=2, default=str))


def cmd_plan(args):
    from friday.brain.planner import Planner
    p = Planner()
    description = " ".join(args.description)
    plan = p.plan_freeform(description)
    p.log_plan(plan)
    print(json.dumps(plan.to_dict(), indent=2, default=str))


def cmd_skills(args):
    from friday.skills.registry import get_registry
    reg = get_registry()
    desc = reg.describe_all()
    print(f"{len(desc)} skills registered:\n")
    for sn, sd in desc.items():
        print(f"● {sn} — {sd['description']}")
        for opn, od in sd["operations"].items():
            print(f"    · {opn:30} risk={od['risk']:<8} {od['description']}")
        print()


def cmd_skill(args):
    from friday.skills.registry import get_registry
    reg = get_registry()
    kwargs = {}
    for pair in args.kwargs:
        if "=" in pair:
            k, v = pair.split("=", 1)
            kwargs[k.strip()] = v.strip()
    result = reg.invoke(args.skill, args.operation, _actor="cli", **kwargs)
    print(json.dumps(result.to_dict(), indent=2, default=str))


def cmd_pending(args):
    from friday.brain.autonomy import AutonomyEngine
    items = AutonomyEngine().pending_approvals()
    if not items:
        print("(no pending approvals)")
        return
    for it in items:
        print(f"  [{it['id']}] {it['skill']}.{it['operation']} — {it.get('reason','')[:80]}")
        print(f"           created: {it.get('created_at','')}")


def cmd_approve(args):
    from friday.brain.autonomy import AutonomyEngine
    r = AutonomyEngine().approve(args.id)
    print(json.dumps(r, indent=2, default=str))


def cmd_reject(args):
    from friday.brain.autonomy import AutonomyEngine
    r = AutonomyEngine().reject(args.id)
    print(json.dumps(r, indent=2, default=str))


def cmd_reflect(args):
    from friday.brain.reflector import Reflector
    r = Reflector()
    stats = r.action_stats(hours=24)
    top = r.top_performers(5)
    weak = r.weakest_skills()
    print(f"24h: {stats['ok']}/{stats['total']} ok ({stats['success_rate']*100:.1f}%)")
    print(f"\nTop performers:")
    for t in top:
        print(f"  {t['skill']:20} n={t['n']:3} sr={t['success_rate']*100:.0f}%")
    print(f"\nWeak skills:")
    for w in weak:
        print(f"  {w['skill']:20} n={w['n']:3} sr={w['success_rate']*100:.0f}%")
    print(f"\nBy skill ({stats['window_hours']}h):")
    for sn, d in stats["by_skill"].items():
        print(f"  {sn:20} ok={d['ok']:3} fail={d['fail']:3}")


def cmd_journal(args):
    from friday.skills.registry import get_registry
    r = get_registry().invoke("journal", "write_nightly_reflection", _actor="cli")
    print(json.dumps(r.to_dict(), indent=2, default=str))


def cmd_voice(args):
    """Launches the voice sensing loop."""
    import subprocess
    script = "voice_core.py" if args.core else "voice_live.py"
    script_path = FRIDAY_ROOT / "senses" / script
    
    if not script_path.exists():
        print(f"✗ Error: {script} not found at {script_path}")
        return

    print(f"🎙️ Launching Friday Voice ({script})...")
    try:
        # Use sys.executable to ensure we use the same python environment
        subprocess.run([sys.executable, str(script_path)], check=True)
    except KeyboardInterrupt:
        print("\nVoice mode stopped.")
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Error: Voice loop exited with code {e.returncode}")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")


def cmd_build(args):
    from friday.brain.engine import MultiEngine
    from friday.brain.memory import Memory
    from friday.brain.mission import MissionRunner, new_mission
    
    eng = MultiEngine()
    mem = Memory()
    runner = MissionRunner(eng, mem)
    
    goal = " ".join(args.goal)
    print(f"╔══════════════════════════════════════╗")
    print(f"║  FRIDAY :: MASTER BUILDER            ║")
    print(f"╚══════════════════════════════════════╝\n")
    print(f"GOAL: {goal}\n")
    
    mission = new_mission(goal)
    print("[1] Planning mission using cognitive engine... (this may take a minute)")
    if not runner.plan(mission):
        print(f"FAIL: Could not plan mission. Notes: {mission.notes}")
        return
        
    print(f"\nPLAN GENERATED ({len(mission.steps)} steps, Risk: {mission.risk}):")
    for s in mission.steps:
        print(f"  [{s.id}] {s.name} ({s.skill}.{s.operation})")
        
    print("\n[2] Executing plan autonomously...\n")
    
    def on_step_update(m, s):
        if s.status == "done":
            res_str = str(s.result)[:150].replace('\n', ' ')
            print(f"  ✓ Step {s.id} ({s.skill}.{s.operation}) complete. Output: {res_str}")
        elif s.status == "failed":
            print(f"  ✗ Step {s.id} FAILED: {s.error}")
            
    runner.run(mission, on_step=on_step_update)
    
    if mission.status == "done":
        print("\n✅ MISSION ACCOMPLISHED")
        print(f"\nFINAL REPORT:\n{mission.final_report}")
    else:
        print(f"\n❌ MISSION FAILED (Status: {mission.status})")
        print(f"Notes: {mission.notes}")


def cmd_venture(args):
    from friday.brain.agents.venture import VentureOrchestrator
    objective = " ".join(args.objective)
    orch = VentureOrchestrator(objective)
    orch.run()

def cmd_distill(args):
    from friday.skills.registry import get_registry
    reg = get_registry()
    res = reg.invoke("distillation", "export_dataset")
    if res.ok:
        print(f"✅ Distillation complete. Exported {res.data.get('exported_records')} records.")
        print(f"   Dataset saved to: {res.data.get('file')}")
    else:
        print(f"❌ Distillation failed: {res.error}")

def cmd_train(args):
    import subprocess
    script_path = FRIDAY_ROOT / "scripts" / "train_lora_mlx.py"
    if not script_path.exists():
        print(f"❌ Error: {script_path} not found.")
        return
    print(f"🚀 Launching MLX LoRA Training Pipeline...")
    subprocess.run([sys.executable, str(script_path)])

def main():
    p = argparse.ArgumentParser(prog="friday", description="F.R.I.D.A.Y. v1.0 — Bhargav's autonomous sovereign AI")
    sub = p.add_subparsers(dest="cmd")

    a = sub.add_parser("ask", help="one-shot query")
    a.add_argument("query", nargs="+")
    a.add_argument("--heavy", action="store_true", help="use heavy model (gemma3:4b / opus)")
    a.set_defaults(func=cmd_ask)

    sub.add_parser("chat", help="interactive REPL").set_defaults(func=cmd_chat)
    sub.add_parser("status", help="empire snapshot").set_defaults(func=cmd_status)
    sub.add_parser("operate", help="run Friday's safe operator loop and emit proof artifacts").set_defaults(func=cmd_operate)
    sub.add_parser("unlock", help="unlock and test all 20 Friday capability domains").set_defaults(func=cmd_unlock)
    opp = sub.add_parser("opportunities", help="rank ethical money opportunities and create experiments")
    opp.add_argument("--top", type=int, default=10)
    opp.add_argument("--refresh", action="store_true")
    opp.add_argument("--experiment", default="", help="create a reversible experiment for an opportunity id")
    opp.add_argument("--launch", nargs="?", const="__top__", default="", help="launch the first safe action for an opportunity id, or top opportunity if omitted")
    opp.add_argument("--max-leads", type=int, default=5)
    opp.add_argument("--dry-run", action="store_true")
    opp.set_defaults(func=cmd_opportunities)
    ns = sub.add_parser("nervous", help="FRIDAY nervous-system event stream")
    ns.add_argument("mode", nargs="?", choices=["status", "recent"], default="status")
    ns.add_argument("--limit", type=int, default=20)
    ns.add_argument("--event-type", default="")
    ns.set_defaults(func=cmd_nervous)
    immune = sub.add_parser("immune", help="scan for unsafe autonomy and prompt-injection signals")
    immune.add_argument("--hours", type=int, default=24)
    immune.add_argument("--no-report", action="store_true")
    immune.set_defaults(func=cmd_immune)
    sleep = sub.add_parser("sleep", help="run FRIDAY memory sleep consolidation")
    sleep.add_argument("--dry-run", action="store_true")
    sleep.add_argument("--no-report", action="store_true")
    sleep.add_argument("--latest", action="store_true")
    sleep.set_defaults(func=cmd_sleep)
    bench = sub.add_parser("bench", help="run FRIDAY-Bench")
    bench.add_argument("--no-report", action="store_true")
    bench.add_argument("--latest", action="store_true")
    bench.set_defaults(func=cmd_bench)
    world = sub.add_parser("world", help="world twin pulse/entities/status")
    world.add_argument("mode", nargs="?", choices=["pulse", "entities", "status"], default="pulse")
    world.add_argument("--web", action="store_true")
    world.add_argument("--no-persist", action="store_true")
    world.add_argument("--limit", type=int, default=20)
    world.set_defaults(func=cmd_world)
    connectors = sub.add_parser("connectors", help="connector command center status/inventory/gaps")
    connectors.add_argument("mode", nargs="?", choices=["status", "inventory", "gaps", "roadmap", "test-plan", "export"], default="status")
    connectors.add_argument("--status", default="", help="filter inventory by status")
    connectors.add_argument("--category", default="", help="filter inventory by category")
    connectors.add_argument("--priority", default="", help="filter missing connectors by priority, e.g. P0")
    connectors.add_argument("--include-write-tests", action="store_true")
    connectors.set_defaults(func=cmd_connectors)
    revenue = sub.add_parser("revenue", help="revenue ledger status, followups, and Razorpay ingestion")
    revenue.set_defaults(func=cmd_revenue, revenue_cmd="status", days=30)
    revenue_sub = revenue.add_subparsers(dest="revenue_cmd")
    rev_status = revenue_sub.add_parser("status", help="show revenue ledger summary")
    rev_status.add_argument("--days", type=int, default=30)
    rev_status.set_defaults(func=cmd_revenue)

    rev_latest = revenue_sub.add_parser("latest", help="show latest revenue ledger entries")
    rev_latest.add_argument("--limit", type=int, default=10)
    rev_latest.set_defaults(func=cmd_revenue)

    rev_followups = revenue_sub.add_parser("followups", help="show approval-aware revenue followups")
    rev_followups.add_argument("--limit", type=int, default=10)
    rev_followups.set_defaults(func=cmd_revenue)

    rev_ingest = revenue_sub.add_parser("ingest-razorpay-webhook", help="verify and ingest a Razorpay webhook body file")
    rev_ingest.add_argument("--body-file", required=True)
    rev_ingest.add_argument("--signature", required=True)
    rev_ingest.add_argument("--secret", default="", help="optional webhook secret override for local testing")
    rev_ingest.add_argument("--mode", default="", help="test or live")
    rev_ingest.add_argument("--source", default="webhook")
    rev_ingest.set_defaults(func=cmd_revenue)

    rev_sync = revenue_sub.add_parser("sync-razorpay", help="pull recent Razorpay entities into the revenue ledger")
    rev_sync.add_argument("--count", type=int, default=10)
    rev_sync.add_argument("--no-payments", action="store_true")
    rev_sync.add_argument("--no-links", action="store_true")
    rev_sync.add_argument("--no-orders", action="store_true")
    rev_sync.add_argument("--include-subscriptions", action="store_true")
    rev_sync.add_argument("--mode", default="", help="test or live")
    rev_sync.set_defaults(func=cmd_revenue)
    rz = sub.add_parser("razorpay", help="Razorpay payments rail status, dry-runs, and reads")
    rz.set_defaults(func=cmd_razorpay, razorpay_cmd="status", probe=False, mode="")
    rz_sub = rz.add_subparsers(dest="razorpay_cmd")
    rz_status = rz_sub.add_parser("status", help="show Razorpay readiness")
    rz_status.add_argument("--probe", action="store_true")
    rz_status.add_argument("--mode", default="", help="test or live")
    rz_status.set_defaults(func=cmd_razorpay)

    for name, help_text in (
        ("payments", "fetch recent payments"),
        ("orders", "fetch recent orders"),
        ("links", "fetch recent payment links"),
    ):
        subparser = rz_sub.add_parser(name, help=help_text)
        subparser.add_argument("--count", type=int, default=10)
        subparser.add_argument("--skip", type=int, default=0)
        subparser.add_argument("--from-ts", type=int, default=0)
        subparser.add_argument("--to-ts", type=int, default=0)
        subparser.add_argument("--mode", default="", help="test or live")
        subparser.set_defaults(func=cmd_razorpay)

    rz_subs = rz_sub.add_parser("subscriptions", help="fetch recent subscriptions")
    rz_subs.add_argument("--count", type=int, default=10)
    rz_subs.add_argument("--skip", type=int, default=0)
    rz_subs.add_argument("--mode", default="", help="test or live")
    rz_subs.set_defaults(func=cmd_razorpay)

    rz_link = rz_sub.add_parser("create-link", help="preview or create a payment link")
    rz_link.add_argument("--amount", required=True, help="amount in INR major units, e.g. 499.00")
    rz_link.add_argument("--name", default="")
    rz_link.add_argument("--email", default="")
    rz_link.add_argument("--phone", default="")
    rz_link.add_argument("--description", default="")
    rz_link.add_argument("--reference-id", default="")
    rz_link.add_argument("--accept-partial", action="store_true")
    rz_link.add_argument("--first-min-partial-amount", default="")
    rz_link.add_argument("--expiry-minutes", type=int, default=0)
    rz_link.add_argument("--notify-email", action="store_true")
    rz_link.add_argument("--notify-sms", action="store_true")
    rz_link.add_argument("--callback-url", default="")
    rz_link.add_argument("--callback-method", default="")
    rz_link.add_argument("--reminder-enable", action="store_true")
    rz_link.add_argument("--upi-link", action="store_true")
    rz_link.add_argument("--note", action="append", default=[], help="k=v note pair")
    rz_link.add_argument("--commit", action="store_true", help="perform the live API call instead of dry-run preview")
    rz_link.add_argument("--mode", default="", help="test or live")
    rz_link.set_defaults(func=cmd_razorpay)

    rz_order = rz_sub.add_parser("create-order", help="preview or create an order")
    rz_order.add_argument("--amount", required=True, help="amount in INR major units, e.g. 499.00")
    rz_order.add_argument("--receipt", default="")
    rz_order.add_argument("--partial-payment", action="store_true")
    rz_order.add_argument("--first-payment-min-amount", default="")
    rz_order.add_argument("--note", action="append", default=[], help="k=v note pair")
    rz_order.add_argument("--commit", action="store_true")
    rz_order.add_argument("--mode", default="", help="test or live")
    rz_order.set_defaults(func=cmd_razorpay)

    rz_sub_create = rz_sub.add_parser("create-subscription", help="preview or create a subscription")
    rz_sub_create.add_argument("--plan-id", required=True)
    rz_sub_create.add_argument("--total-count", required=True, type=int)
    rz_sub_create.add_argument("--quantity", type=int, default=1)
    rz_sub_create.add_argument("--customer-notify", action="store_true")
    rz_sub_create.add_argument("--start-at", type=int, default=0)
    rz_sub_create.add_argument("--expire-by", type=int, default=0)
    rz_sub_create.add_argument("--note", action="append", default=[], help="k=v note pair")
    rz_sub_create.add_argument("--commit", action="store_true")
    rz_sub_create.add_argument("--mode", default="", help="test or live")
    rz_sub_create.set_defaults(func=cmd_razorpay)

    rz_verify_payment = rz_sub.add_parser("verify-payment", help="verify checkout signature")
    rz_verify_payment.add_argument("--order-id", required=True)
    rz_verify_payment.add_argument("--payment-id", required=True)
    rz_verify_payment.add_argument("--signature", required=True)
    rz_verify_payment.add_argument("--mode", default="", help="test or live")
    rz_verify_payment.set_defaults(func=cmd_razorpay)

    rz_verify_webhook = rz_sub.add_parser("verify-webhook", help="verify webhook signature from a body file")
    rz_verify_webhook.add_argument("--body-file", required=True)
    rz_verify_webhook.add_argument("--signature", required=True)
    rz_verify_webhook.add_argument("--mode", default="", help="test or live")
    rz_verify_webhook.set_defaults(func=cmd_razorpay)
    ms = sub.add_parser("mission", help="Friday vision, capabilities, gaps, and next action")
    ms.add_argument("mode", nargs="?", choices=["brief", "capabilities", "gaps", "next"], default="brief")
    ms.set_defaults(func=cmd_mission)
    sub.add_parser("briefing", help="run morning briefing").set_defaults(func=cmd_briefing)
    sub.add_parser("debrief", help="run evening debrief").set_defaults(func=cmd_debrief)
    sub.add_parser("heartbeat", help="run one sensor sweep").set_defaults(func=cmd_heartbeat)

    ao = sub.add_parser("absorb-openclaw", help="import the substantive OpenClaw prompts and replies")
    ao.add_argument("--state-dir", default="~/.openclaw")
    ao.add_argument("--no-memory", action="store_true", help="skip writing distilled facts into Friday memory")
    ao.set_defaults(func=cmd_absorb_openclaw)

    m = sub.add_parser("memory", help="inspect memory")
    m.add_argument("--dump", action="store_true")
    m.set_defaults(func=cmd_memory)

    r = sub.add_parser("remember", help="store a fact (KEY=VALUE)")
    r.add_argument("pairs", nargs="+")
    r.add_argument("--category", default="general")
    r.set_defaults(func=cmd_remember)

    f = sub.add_parser("forget", help="delete facts")
    f.add_argument("keys", nargs="+")
    f.set_defaults(func=cmd_forget)

    sub.add_parser("test", help="smoke test all components").set_defaults(func=cmd_test)

    v = sub.add_parser("voice", help="launch voice mode")
    v.add_argument("--core", action="store_true", help="use legendary voice-core (RAM-only)")
    v.set_defaults(func=lambda args: cmd_voice(args))

    # -------- v1.0 autonomy --------
    sub.add_parser("autonomy", help="autonomy engine status").set_defaults(func=cmd_autonomy)
    sub.add_parser("goals", help="list active goals").set_defaults(func=cmd_goals)

    tk = sub.add_parser("tick", help="run one autonomy tick")
    tk.add_argument("goal_id", nargs="?", default=None)
    tk.add_argument("--dry-run", action="store_true")
    tk.set_defaults(func=cmd_tick)

    pl = sub.add_parser("plan", help="LLM-generate a plan from freeform description")
    pl.add_argument("description", nargs="+")
    pl.set_defaults(func=cmd_plan)

    sub.add_parser("skills", help="list registered skills").set_defaults(func=cmd_skills)

    sk = sub.add_parser("skill", help="invoke a skill operation (k=v args)")
    sk.add_argument("skill")
    sk.add_argument("operation")
    sk.add_argument("kwargs", nargs="*", default=[])
    sk.set_defaults(func=cmd_skill)

    sub.add_parser("pending", help="list pending approvals").set_defaults(func=cmd_pending)

    ap = sub.add_parser("approve", help="approve a pending action")
    ap.add_argument("id")
    ap.set_defaults(func=cmd_approve)

    rj = sub.add_parser("reject", help="reject a pending action")
    rj.add_argument("id")
    rj.set_defaults(func=cmd_reject)

    sub.add_parser("reflect", help="24h action stats + heuristics").set_defaults(func=cmd_reflect)
    sub.add_parser("journal", help="write nightly reflection now").set_defaults(func=cmd_journal)

    b = sub.add_parser("build", help="master builder - autonomously plan and build applications")
    b.add_argument("goal", nargs="+")
    b.set_defaults(func=cmd_build)

    vnt = sub.add_parser("venture", help="run a multi-agent company orchestration loop")
    vnt.add_argument("objective", nargs="+")
    vnt.set_defaults(func=cmd_venture)

    sub.add_parser("distill", help="export teacher actions to a dataset for fine-tuning").set_defaults(func=cmd_distill)
    sub.add_parser("train", help="run MLX LoRA training on the latest distilled dataset").set_defaults(func=cmd_train)

    args = p.parse_args()
    if not hasattr(args, "func"):
        p.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
