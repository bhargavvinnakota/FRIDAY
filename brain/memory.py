"""
Friday :: Memory Layer
JSON-backed persistent memory with three tiers:
  - recent_turns : short-term dialogue (last N exchanges)
  - facts        : semantic long-term (key → value with metadata)
  - events       : episodic append-only log of what Friday did
"""
from __future__ import annotations
import copy
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

FRIDAY_ROOT = Path(os.path.expanduser("~/AI/friday"))
MEM_PATH = FRIDAY_ROOT / "data" / "memory.json"

DEFAULT_MEM = {
    "recent_turns": [],
    "facts": {},
    "events": [],
    "meta": {"created": None, "last_update": None, "version": 1},
}

# Global lock — serializes writes across all Memory instances pointing at same file.
_MEM_LOCK = threading.RLock()


class Memory:
    def __init__(self, path: Path = MEM_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            DEFAULT_MEM["meta"]["created"] = datetime.now().isoformat()
            with _MEM_LOCK:
                with open(self.path, "w") as f:
                    json.dump(DEFAULT_MEM, f, indent=2, default=str)
            return copy.deepcopy(DEFAULT_MEM)
        try:
            with open(self.path) as f:
                return json.load(f)
        except Exception:
            return copy.deepcopy(DEFAULT_MEM)

    def _save(self, data: dict | None = None) -> None:
        # Atomic write under lock to prevent concurrent-mutation corruption
        with _MEM_LOCK:
            d = data if data is not None else self._data
            d.setdefault("meta", {})["last_update"] = datetime.now().isoformat()
            # Deep copy the snapshot while holding lock so json.dump sees stable data
            snapshot = copy.deepcopy(d)
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w") as f:
                json.dump(snapshot, f, indent=2, default=str)
            os.replace(tmp, self.path)  # atomic rename

    # -------- Short-term dialogue --------
    def add_turn(self, role: str, content: str, max_turns: int = 40) -> None:
        with _MEM_LOCK:
            self._data["recent_turns"].append({
                "role": role, "content": content, "ts": datetime.now().isoformat()
            })
            self._data["recent_turns"] = self._data["recent_turns"][-max_turns:]
        self._save()

    def get_turns(self, n: int = 10) -> list[dict]:
        with _MEM_LOCK:
            return list(self._data["recent_turns"][-n:])

    def clear_turns(self) -> None:
        with _MEM_LOCK:
            self._data["recent_turns"] = []
        self._save()

    # -------- Long-term facts --------
    def remember(self, key: str, value: Any, category: str = "general") -> None:
        with _MEM_LOCK:
            self._data["facts"][key] = {
                "value": value,
                "category": category,
                "stored": datetime.now().isoformat(),
            }
        self._save()

    def recall(self, key: str, default: Any = None) -> Any:
        with _MEM_LOCK:
            entry = self._data["facts"].get(key)
            return entry["value"] if entry else default

    def recall_category(self, category: str) -> dict:
        with _MEM_LOCK:
            return {k: v["value"] for k, v in self._data["facts"].items()
                    if v.get("category") == category}

    def forget(self, key: str) -> bool:
        with _MEM_LOCK:
            removed = self._data["facts"].pop(key, None) is not None
        if removed:
            self._save()
        return removed

    # -------- Episodic events --------
    def log_event(self, event_type: str, data: dict, max_events: int = 1000) -> None:
        with _MEM_LOCK:
            self._data["events"].append({
                "type": event_type,
                "data": data,
                "ts": datetime.now().isoformat(),
            })
            self._data["events"] = self._data["events"][-max_events:]
        self._save()

    def recent_events(self, n: int = 20, event_type: str | None = None) -> list[dict]:
        with _MEM_LOCK:
            evs = list(self._data["events"])
        if event_type:
            evs = [e for e in evs if e["type"] == event_type]
        return evs[-n:]

    # -------- Context assembly for LLM --------
    def context_block(self, turns: int = 6, facts_category: str | None = None) -> str:
        """Produce a text block Friday can feed back to the LLM."""
        parts = []
        with _MEM_LOCK:
            facts_snapshot = dict(self._data["facts"])  # stable snapshot
        if facts_snapshot:
            parts.append("KNOWN FACTS:")
            items = (facts_snapshot.items() if not facts_category
                     else [(k, v) for k, v in facts_snapshot.items()
                           if v.get("category") == facts_category])
            for k, v in list(items)[:20]:
                parts.append(f"  - {k}: {v['value']}")
        recent = self.get_turns(turns)
        if recent:
            parts.append("\nRECENT DIALOGUE:")
            for t in recent:
                parts.append(f"  {t['role']}: {t['content'][:200]}")
        return "\n".join(parts)


if __name__ == "__main__":
    m = Memory()
    m.remember("revenue_target_month1", "₹50K-1L", category="mission")
    m.log_event("boot", {"version": "0.1.0"})
    print(m.context_block())
