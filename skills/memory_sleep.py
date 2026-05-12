"""
Friday :: Memory Sleep Cycle
Consolidates logs into owner-visible deltas, facts, playbook nudges, and
benchmark inputs. This is the first "experience becomes improvement" loop.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from friday.brain.memory import Memory
from friday.brain.nervous_system import append_event, stats as nervous_stats
from friday.brain.reflector import Reflector

from .registry import Operation, Skill, SkillResult

FRIDAY = Path(os.path.expanduser("~/AI/friday"))
ACTION_LOG = FRIDAY / "data" / "actions.jsonl"
APPROVAL_FILE = FRIDAY / "data" / "pending_approvals.json"
OPPORTUNITIES_FILE = FRIDAY / "data" / "opportunities.jsonl"
EXPERIMENTS_FILE = FRIDAY / "data" / "money_experiments.jsonl"
SLEEP_DIR = FRIDAY / "data" / "memory_sleep"


class MemorySleepSkill(Skill):
    name = "memory_sleep"
    description = "Daily consolidation: logs become facts, playbook updates, open questions, and improvement hints."

    def _register_operations(self) -> None:
        self.register_op(Operation("consolidate", "Run the memory sleep consolidation cycle.", fn=self.op_consolidate, risk="low"))
        self.register_op(Operation("latest", "Return the latest sleep report.", fn=self.op_latest, risk="low"))

    def op_consolidate(self, dry_run: bool = False, write_report: bool = True, **_) -> SkillResult:
        dry_run = _as_bool(dry_run)
        write_report = _as_bool(write_report)
        mem = Memory()
        reflector = Reflector(mem)
        actions = _read_jsonl(ACTION_LOG)[-300:]
        approvals = _read_json(APPROVAL_FILE, [])
        opportunities = _read_jsonl(OPPORTUNITIES_FILE)
        experiments = _read_jsonl(EXPERIMENTS_FILE)
        action_stats = reflector.action_stats(hours=24)
        by_skill = Counter(a.get("skill", "unknown") for a in actions)
        pending = [a for a in approvals if a.get("status") == "pending"]
        top_opportunity = max(opportunities, key=lambda o: o.get("score", 0), default={})

        facts = {
            "sleep:last_run": datetime.now().isoformat(),
            "money:top_opportunity": top_opportunity.get("id", "none"),
            "money:experiments_total": len(experiments),
            "approvals:pending_count": len(pending),
            "nervous_system:events_total": nervous_stats().get("total", 0),
        }
        playbook = _playbook(action_stats, pending, experiments, top_opportunity)
        open_questions = _open_questions(pending, experiments, top_opportunity)
        report = {
            "generated_at": datetime.now().isoformat(),
            "dry_run": dry_run,
            "action_stats_24h": action_stats,
            "top_skills_in_recent_log": by_skill.most_common(10),
            "pending_approvals": len(pending),
            "opportunities": len(opportunities),
            "experiments": len(experiments),
            "facts": facts,
            "playbook_updates": playbook,
            "open_questions": open_questions,
        }

        artifacts = []
        if write_report:
            SLEEP_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_path = SLEEP_DIR / f"sleep_{stamp}.json"
            md_path = SLEEP_DIR / f"sleep_{stamp}.md"
            json_path.write_text(json.dumps(report, indent=2, default=str))
            md_path.write_text(_markdown(report))
            artifacts.extend([str(json_path), str(md_path)])
        if not dry_run:
            for key, value in facts.items():
                mem.remember(key, value, category="sleep")
            mem.remember("sleep:latest_playbook_updates", playbook, category="playbook")
            append_event("memory_sleep", source="memory_sleep", payload={
                "facts": len(facts),
                "playbook_updates": len(playbook),
                "open_questions": len(open_questions),
            }, entity_refs=["friday:memory"])
        return SkillResult(ok=True, data=report, artifacts=artifacts)

    def op_latest(self, **_) -> SkillResult:
        files = sorted(SLEEP_DIR.glob("sleep_*.json"))
        if not files:
            return SkillResult(ok=True, data={"found": False})
        data = json.loads(files[-1].read_text())
        return SkillResult(ok=True, data={"found": True, "path": str(files[-1]), "report": data}, artifacts=[str(files[-1])])


def _playbook(action_stats: dict, pending: list[dict], experiments: list[dict], top_opportunity: dict) -> list[str]:
    updates = []
    if pending:
        updates.append(f"Review {len(pending)} pending approvals before launching more outbound experiments.")
    if experiments and any(e.get("status") == "queued_for_approval" for e in experiments):
        updates.append("Money experiments should advance only after approval outcomes are recorded.")
    if top_opportunity:
        updates.append(f"Keep next cash action focused on {top_opportunity.get('id')} until the kill condition is reached.")
    if action_stats.get("total", 0) and action_stats.get("success_rate", 1) < 0.9:
        updates.append("Inspect weak skills before increasing autonomy; 24h success rate is below 90%.")
    if not updates:
        updates.append("No urgent playbook changes; continue proof-logged execution.")
    return updates


def _open_questions(pending: list[dict], experiments: list[dict], top_opportunity: dict) -> list[str]:
    questions = []
    if pending:
        questions.append("Which pending approvals should Bhargav approve, reject, or rewrite today?")
    if not experiments:
        questions.append("Should FRIDAY launch the top-ranked money experiment?")
    if top_opportunity and top_opportunity.get("risk_tier", 1) >= 3:
        questions.append("Are the approval and manual-send boundaries clear for the top opportunity?")
    return questions


def _markdown(report: dict) -> str:
    lines = [
        "# Friday Memory Sleep Delta",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "## Facts",
    ]
    for key, value in report["facts"].items():
        lines.append(f"- `{key}`: {value}")
    lines.append("\n## Playbook Updates")
    for item in report["playbook_updates"]:
        lines.append(f"- {item}")
    lines.append("\n## Open Questions")
    for item in report["open_questions"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                out.append(item)
        except Exception:
            continue
    return out


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)

