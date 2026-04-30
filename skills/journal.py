"""
Friday :: Journal Skill
Writes nightly reflections + ad-hoc log entries. Friday's own memory of what happened
and why, separate from the mechanical event log.
"""
from __future__ import annotations
import json
import os
from datetime import datetime
from pathlib import Path

from .registry import Skill, Operation, SkillResult

FRIDAY = Path(os.path.expanduser("~/AI/friday"))
REFLECTIONS = FRIDAY / "data" / "reflections.jsonl"
JOURNAL_DIR = FRIDAY / "data" / "journal"


class JournalSkill(Skill):
    name = "journal"
    description = "Reflective journaling — what happened today, what Friday learned."

    def _register_operations(self) -> None:
        self.register_op(Operation("write_nightly_reflection",
                                   "Summarize today's actions, wins, misses.",
                                   fn=self.op_write_nightly_reflection, risk="low"))
        self.register_op(Operation("append_note", "Append an ad-hoc note.",
                                   fn=self.op_append_note, risk="low"))
        self.register_op(Operation("recent", "Return last N reflection entries.",
                                   fn=self.op_recent, risk="low"))

    def op_write_nightly_reflection(self, **_) -> SkillResult:
        from friday.brain.memory import Memory
        from friday.brain.engine import MultiEngine
        from friday.brain.personality import system_prompt
        from friday.actions import nexus

        mem = Memory()
        today = datetime.now().date()

        # Gather today's actions
        actions_log = FRIDAY / "data" / "actions.jsonl"
        today_actions = []
        if actions_log.exists():
            for line in actions_log.read_text().splitlines()[-500:]:
                try:
                    e = json.loads(line)
                    if datetime.fromisoformat(e["ts"]).date() == today:
                        today_actions.append(e)
                except Exception:
                    continue
        # Today's events
        today_events = [e for e in mem.recent_events(200)
                        if datetime.fromisoformat(e.get("ts", "")).date() == today]

        stats = {
            "actions": len(today_actions),
            "actions_ok": sum(1 for a in today_actions if a.get("ok")),
            "actions_failed": sum(1 for a in today_actions if not a.get("ok")),
            "events": len(today_events),
            "tool_calls": len([e for e in today_events if e.get("type") == "respond"]),
        }
        try:
            stats["empire_snapshot"] = nexus.snapshot()
        except Exception:
            pass

        # Have Friday reflect
        eng = MultiEngine()
        sysp = system_prompt(task_hint=(
            "Write a 4-6 line nightly reflection. Be blunt. What shipped, what didn't, "
            "one lesson, one priority for tomorrow. No fluff."
        ))
        prompt = (
            f"Today: {today.isoformat()}\n\n"
            f"Stats: {json.dumps(stats, indent=2, default=str)[:1500]}\n\n"
            f"Recent action log (last 10): {json.dumps(today_actions[-10:], indent=2, default=str)[:1500]}\n\n"
            "Write the reflection."
        )
        try:
            reflection, used = eng.ask(sysp, prompt, force="ollama")
        except Exception as e:
            reflection = f"[reflection error: {e}]"
            used = "error"

        entry = {
            "date": today.isoformat(),
            "ts": datetime.now().isoformat(),
            "stats": stats,
            "reflection": reflection,
            "engine": used,
        }
        REFLECTIONS.parent.mkdir(parents=True, exist_ok=True)
        with open(REFLECTIONS, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

        # Also write a dated markdown file
        JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
        md_path = JOURNAL_DIR / f"{today.isoformat()}.md"
        md_path.write_text(
            f"# {today.isoformat()} :: Nightly\n\n"
            f"**Stats:**\n- Actions: {stats['actions']} ({stats['actions_ok']} ok / "
            f"{stats['actions_failed']} failed)\n- Events: {stats['events']}\n"
            f"- Tool calls: {stats['tool_calls']}\n\n"
            f"**Reflection:**\n{reflection}\n"
        )
        # Push a short version to telegram
        from friday.actions import comms
        comms.telegram_push(f"📓 *Nightly reflection*\n\n{reflection[:1200]}", silent=True)

        return SkillResult(ok=True, data={"reflection": reflection, "stats": stats},
                           artifacts=[str(REFLECTIONS), str(md_path)])

    def op_append_note(self, text: str = "", tag: str = "note", **_) -> SkillResult:
        if not text:
            return SkillResult(ok=False, error="text required")
        REFLECTIONS.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": datetime.now().isoformat(), "tag": tag, "text": text}
        with open(REFLECTIONS, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        return SkillResult(ok=True, data=entry, artifacts=[str(REFLECTIONS)])

    def op_recent(self, n: int = 5, **_) -> SkillResult:
        if not REFLECTIONS.exists():
            return SkillResult(ok=True, data={"entries": []})
        lines = REFLECTIONS.read_text().splitlines()[-n:]
        out = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return SkillResult(ok=True, data={"entries": out, "count": len(out)})
