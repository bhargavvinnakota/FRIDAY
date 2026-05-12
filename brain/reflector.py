"""
Friday :: Reflector
Post-action and nightly reflection. Converts raw action outcomes into
learned heuristics stored in memory under category='playbook'.

Lightweight v1.0: rule-based summarization + optional LLM polish.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from friday.brain.memory import Memory

ACTION_LOG = Path(os.path.expanduser("~/AI/friday/data/actions.jsonl"))
REFLECTIONS = Path(os.path.expanduser("~/AI/friday/data/reflections.jsonl"))


class Reflector:
    def __init__(self, memory: Memory | None = None):
        self.memory = memory or Memory()

    def review_action(self, skill: str, operation: str, result: dict,
                      elapsed_ms: int, context: dict | None = None) -> None:
        """Called after every autonomous action. Writes event + optional playbook update."""
        ok = result.get("ok", False)
        # Event (dense, mechanical)
        self.memory.log_event("action_reviewed", {
            "skill": skill, "operation": operation,
            "ok": ok, "error": result.get("error"),
            "elapsed_ms": elapsed_ms,
            "artifacts_count": len(result.get("artifacts", [])),
            "context": context or {},
        })
        # Playbook heuristic — only on clear signals
        key = f"skill:{skill}:{operation}"
        existing = self.memory.recall(key, default={"wins": 0, "fails": 0})
        if isinstance(existing, dict):
            if ok:
                existing["wins"] = existing.get("wins", 0) + 1
            else:
                existing["fails"] = existing.get("fails", 0) + 1
            existing["last_outcome"] = "ok" if ok else (result.get("error") or "fail")[:200]
            existing["last_ts"] = datetime.now().isoformat()
            self.memory.remember(key, existing, category="playbook")

    def action_stats(self, hours: int = 24) -> dict:
        if not ACTION_LOG.exists():
            return {"total": 0, "ok": 0, "fail": 0, "by_skill": {}}
        cutoff = datetime.now() - timedelta(hours=hours)
        total, ok, fail = 0, 0, 0
        by_skill: dict[str, dict] = {}
        for line in ACTION_LOG.read_text().splitlines()[-2000:]:
            try:
                e = json.loads(line)
                ts = datetime.fromisoformat(e["ts"])
                if ts < cutoff:
                    continue
                total += 1
                if e.get("ok"):
                    ok += 1
                else:
                    fail += 1
                sn = e.get("skill", "?")
                s = by_skill.setdefault(sn, {"ok": 0, "fail": 0})
                s["ok" if e.get("ok") else "fail"] += 1
            except Exception:
                continue
        return {"window_hours": hours, "total": total, "ok": ok, "fail": fail,
                "success_rate": (ok / total) if total else 0.0,
                "by_skill": by_skill}

    def top_performers(self, top_n: int = 5) -> list[dict]:
        stats = self.action_stats(hours=168)  # 7 days
        ranked = []
        for skill, d in stats["by_skill"].items():
            n = d["ok"] + d["fail"]
            if n == 0:
                continue
            ranked.append({"skill": skill, "n": n,
                           "success_rate": d["ok"] / n,
                           "ok": d["ok"], "fail": d["fail"]})
        ranked.sort(key=lambda r: (r["success_rate"], r["n"]), reverse=True)
        return ranked[:top_n]

    def weakest_skills(self, min_runs: int = 3) -> list[dict]:
        stats = self.action_stats(hours=168)
        weak = []
        for skill, d in stats["by_skill"].items():
            n = d["ok"] + d["fail"]
            if n < min_runs:
                continue
            sr = d["ok"] / n
            if sr < 0.7:
                weak.append({"skill": skill, "n": n, "success_rate": sr})
        weak.sort(key=lambda r: r["success_rate"])
        return weak

    def write_heuristic(self, name: str, content: str) -> None:
        self.memory.remember(f"heuristic:{name}", content, category="playbook")
