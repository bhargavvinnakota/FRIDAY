#!/usr/bin/env python3
"""
Friday :: Command Line Interface (v1.0)

    friday ask "<question>"       - one-shot query
    friday chat                   - interactive REPL
    friday status                 - empire snapshot
    friday briefing               - run morning briefing now
    friday debrief                - run evening debrief now
    friday heartbeat              - run one sensor sweep
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

# Always add the parent of the 'friday' package directory to sys.path
FRIDAY_ROOT = Path(os.path.expanduser("~/AI/friday"))
if str(FRIDAY_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(FRIDAY_ROOT.parent))

from friday.brain.engine import MultiEngine
from friday.brain.memory import Memory
from friday.brain.orchestrator import Orchestrator, Tool
from friday.actions import nexus, comms, computer


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
        r = computer.shell("ls ~/AI/friday")
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


def main():
    p = argparse.ArgumentParser(prog="friday", description="F.R.I.D.A.Y. v1.0 — Bhargav's autonomous sovereign AI")
    sub = p.add_subparsers(dest="cmd")

    a = sub.add_parser("ask", help="one-shot query")
    a.add_argument("query", nargs="+")
    a.add_argument("--heavy", action="store_true", help="use heavy model (gemma3:4b / opus)")
    a.set_defaults(func=cmd_ask)

    sub.add_parser("chat", help="interactive REPL").set_defaults(func=cmd_chat)
    sub.add_parser("status", help="empire snapshot").set_defaults(func=cmd_status)
    sub.add_parser("briefing", help="run morning briefing").set_defaults(func=cmd_briefing)
    sub.add_parser("debrief", help="run evening debrief").set_defaults(func=cmd_debrief)
    sub.add_parser("heartbeat", help="run one sensor sweep").set_defaults(func=cmd_heartbeat)

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

    args = p.parse_args()
    if not hasattr(args, "func"):
        p.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
