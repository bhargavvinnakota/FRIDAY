"""
Friday :: Telegram Sense
Long-poll Telegram for incoming messages from Bhargav.
Passes each to the orchestrator and pushes reply back.

Usage:
    python3 -m friday.senses.telegram_in
or imported by daemon.py as a worker thread.
"""
from __future__ import annotations
import json
import os
import signal
import sys
import time
from pathlib import Path

# Make ~/AI/friday importable
sys.path.insert(0, os.path.expanduser("~"))

from friday.brain.engine import MultiEngine
from friday.brain.memory import Memory
from friday.brain.orchestrator import Orchestrator, Tool
from friday.actions import comms, nexus, computer


OFFSET_FILE = Path(os.path.expanduser("~/AI/friday/data/telegram_offset.txt"))


def load_offset() -> int | None:
    if OFFSET_FILE.exists():
        try:
            return int(OFFSET_FILE.read_text().strip())
        except Exception:
            return None
    return None


def save_offset(offset: int) -> None:
    OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_FILE.write_text(str(offset))


def build_orchestrator() -> Orchestrator:
    eng = MultiEngine()
    mem = Memory()
    orch = Orchestrator(eng, mem)

    # Tool order matters — first match wins. Specific before general.
    orch.register(Tool(
        name="agency_summary",
        description="Agency clients + leads + CRM.",
        triggers=["client", "clients", "lead", "leads", "outreach", "crm", "agency", "whatsapp bot"],
        fn=lambda **kw: {"clients": nexus.agency_clients(),
                         "leads": nexus.leads_summary(),
                         "crm": nexus.crm_summary()},
    ))
    orch.register(Tool(
        name="trading_state",
        description="Trading brain + portfolio.",
        triggers=["trading", "trade", "portfolio", "p&l", "pnl", "regime", "positions", "nexus omega"],
        fn=lambda **kw: {"brain": nexus.trading_state(), "portfolio": nexus.portfolio_state()},
    ))
    orch.register(Tool(
        name="auditmind_status",
        description="AuditMind SaaS status.",
        triggers=["auditmind", "audit mind", "sox", "compliance"],
        fn=lambda **kw: nexus.auditmind_status(),
    ))
    orch.register(Tool(
        name="empire_snapshot",
        description="Unified status across all engines.",
        triggers=["empire", "snapshot", "status", "overview", "dashboard", "everything", "all engines"],
        fn=lambda **kw: nexus.snapshot(),
    ))
    orch.register(Tool(
        name="run_briefing",
        description="Generate today's full daily briefing.",
        triggers=["briefing", "brief me", "today's briefing", "morning brief"],
        fn=lambda **kw: nexus.run_daily_briefing(telegram=False),
    ))
    return orch


def handle_message(orch: Orchestrator, text: str, chat_id: str) -> None:
    # Only ack for genuinely long queries — not for normal chat
    if len(text) > 120:
        comms.telegram_push("_thinking..._", chat_id=chat_id, silent=True)

    # Detect if this is a strategic question → use heavy model
    heavy_keywords = ["strategy", "plan out", "analyze", "should i", "deep", "research",
                      "why should", "tradeoff", "pros and cons", "break down"]
    heavy = any(k in text.lower() for k in heavy_keywords)

    # Debug mode: user ends message with "??" to see engine tag
    show_tag = text.rstrip().endswith("??")

    result = orch.respond(text, use_tools=True, heavy=heavy)
    reply = result["reply"]

    if show_tag:
        tag = f"\n\n_{result['engine']}"
        if result["tool_used"]:
            tag += f" · {result['tool_used']}"
        tag += "_"
        reply = reply + tag

    comms.telegram_push(reply, chat_id=chat_id)
    comms.log_to_file("telegram_in", json.dumps({"q": text[:200], "r": reply[:500],
                                                  "engine": result["engine"],
                                                  "tool": result["tool_used"]}))


def run_forever() -> None:
    print("📡 Friday Telegram sense online. Listening...")
    orch = build_orchestrator()

    # Boot ping
    comms.telegram_push("*Friday online.* Standing by.")

    offset = load_offset()
    running = True

    def stop(*_):
        nonlocal running
        running = False
        print("\nShutting down Telegram sense...")

    # Only register signals if we're in the main thread (daemon runs us in a worker thread).
    import threading as _th
    if _th.current_thread() is _th.main_thread():
        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)

    while running:
        updates = comms.telegram_get_updates(offset=offset, timeout=25)
        for u in updates:
            offset = u["update_id"] + 1
            save_offset(offset)

            msg = u.get("message") or u.get("edited_message")
            if not msg:
                continue
            chat_id = str(msg["chat"]["id"])
            text = (msg.get("text") or "").strip()
            if not text:
                continue

            print(f"📥 [{chat_id}] {text[:100]}")

            # Commands
            if text.startswith("/"):
                parts = text.strip().split(maxsplit=1)
                cmd = parts[0].lower()
                arg = parts[1].strip() if len(parts) > 1 else ""

                if cmd == "/status":
                    snap = nexus.snapshot()
                    comms.telegram_push(f"```\n{json.dumps(snap, indent=2, default=str)[:3500]}\n```", chat_id=chat_id)
                    continue
                if cmd == "/briefing":
                    brief = nexus.run_daily_briefing(telegram=False)
                    comms.telegram_push(brief[:3900], chat_id=chat_id)
                    continue
                if cmd == "/memory":
                    mem = orch.memory
                    facts = mem._data.get("facts", {})
                    comms.telegram_push(f"*Facts:* {len(facts)}\n*Events:* {len(mem._data.get('events', []))}\n*Turns:* {len(mem._data.get('recent_turns', []))}", chat_id=chat_id)
                    continue
                if cmd == "/clear":
                    orch.memory.clear_turns()
                    comms.telegram_push("_short-term context cleared_", chat_id=chat_id)
                    continue

                # ---- v1.0 Autonomy commands ----
                if cmd == "/yes":
                    from friday.brain.autonomy import AutonomyEngine
                    r = AutonomyEngine().approve(arg)
                    comms.telegram_push(
                        f"{'✅' if r.get('ok') else '❌'} {json.dumps(r, default=str)[:1000]}",
                        chat_id=chat_id, silent=True)
                    continue
                if cmd == "/no":
                    from friday.brain.autonomy import AutonomyEngine
                    r = AutonomyEngine().reject(arg)
                    comms.telegram_push(f"{'❌ rejected' if r.get('ok') else r.get('error')}",
                                         chat_id=chat_id, silent=True)
                    continue
                if cmd == "/hold":
                    from friday.brain.autonomy import AutonomyEngine
                    r = AutonomyEngine().hold(arg, hours=1)
                    comms.telegram_push(f"{'⏸ held 1h' if r.get('ok') else r.get('error')}",
                                         chat_id=chat_id, silent=True)
                    continue
                if cmd == "/pending":
                    from friday.brain.autonomy import AutonomyEngine
                    pend = AutonomyEngine().pending_approvals()
                    if not pend:
                        comms.telegram_push("_no pending approvals_", chat_id=chat_id)
                    else:
                        lines = [f"*{len(pend)} pending:*"]
                        for p in pend[:10]:
                            lines.append(f"[{p['id']}] {p['skill']}.{p['operation']} — {p.get('reason','')[:80]}")
                        comms.telegram_push("\n".join(lines)[:3900], chat_id=chat_id)
                    continue
                if cmd == "/autonomy":
                    from friday.brain.autonomy import AutonomyEngine
                    st = AutonomyEngine().status()
                    comms.telegram_push(f"```\n{json.dumps(st, indent=2, default=str)[:3500]}\n```",
                                         chat_id=chat_id)
                    continue
                if cmd == "/tick":
                    from friday.brain.autonomy import AutonomyEngine
                    r = AutonomyEngine().tick(force_goal_id=arg or None)
                    comms.telegram_push(f"```\n{json.dumps(r.to_dict(), indent=2, default=str)[:3500]}\n```",
                                         chat_id=chat_id)
                    continue
                if cmd == "/focus":
                    from friday.brain.planner import Planner
                    from friday.brain.autonomy import AutonomyEngine
                    p = Planner()
                    plan = p.plan_freeform(arg)
                    comms.telegram_push(f"*Plan for:* {arg[:80]}\n```\n{json.dumps(plan.to_dict(), indent=2, default=str)[:3000]}\n```",
                                         chat_id=chat_id)
                    continue
                if cmd == "/goals":
                    from friday.brain.planner import Planner
                    goals = Planner().active_goals()
                    lines = [f"*{len(goals)} active goals:*"]
                    for g in goals[:15]:
                        lines.append(f"• [{g.get('priority')}] `{g.get('id')}` — {g.get('title','')[:60]}")
                    comms.telegram_push("\n".join(lines)[:3900], chat_id=chat_id)
                    continue
                if cmd == "/reflect":
                    from friday.brain.reflector import Reflector
                    r = Reflector()
                    stats = r.action_stats(hours=24)
                    top = r.top_performers(3)
                    weak = r.weakest_skills()
                    comms.telegram_push(
                        f"*24h stats:* {stats['ok']}/{stats['total']} ok ({stats['success_rate']*100:.0f}%)\n"
                        f"*Top:* {', '.join(t['skill'] for t in top) or '—'}\n"
                        f"*Weak:* {', '.join(w['skill'] for w in weak) or '—'}",
                        chat_id=chat_id)
                    continue

                if cmd == "/help":
                    comms.telegram_push(
                        "*Friday v1.0 commands:*\n"
                        "/status · /briefing · /memory · /clear\n"
                        "*Autonomy:*\n"
                        "/autonomy · /goals · /pending · /tick [goal]\n"
                        "/focus <topic> — freeform plan\n"
                        "/yes <id> · /no <id> · /hold <id>\n"
                        "/reflect — 24h action stats\n\n"
                        "Or just talk to me.",
                        chat_id=chat_id,
                    )
                    continue

            try:
                handle_message(orch, text, chat_id)
            except Exception as e:
                comms.telegram_push(f"_error: {e}_", chat_id=chat_id)

    print("Telegram sense stopped.")


if __name__ == "__main__":
    run_forever()
