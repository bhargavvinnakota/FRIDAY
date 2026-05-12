"""
Friday :: Nervous System
Append-only event stream for observations, tool calls, approvals, money events,
world pulses, memory consolidation, and safety scans.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from friday.brain.action_envelope import redact_inputs

FRIDAY = Path(os.path.expanduser("~/AI/friday"))
EVENT_DIR = FRIDAY / "data" / "nervous_system"
EVENTS_FILE = EVENT_DIR / "events.jsonl"
_LOCK = threading.RLock()


@dataclass
class NervousEvent:
    event_type: str
    source: str
    payload: dict[str, Any]
    confidence: float = 1.0
    sensitivity: str = "internal"
    owner_visible: bool = True
    trace_id: str | None = None
    entity_refs: list[str] = field(default_factory=list)
    proof_path: str | None = None
    ts: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def append_event(
    event_type: str,
    source: str,
    payload: dict[str, Any] | None = None,
    *,
    confidence: float = 1.0,
    sensitivity: str = "internal",
    owner_visible: bool = True,
    trace_id: str | None = None,
    entity_refs: list[str] | None = None,
    proof_path: str | None = None,
) -> NervousEvent:
    event = NervousEvent(
        event_type=event_type,
        source=source,
        payload=redact_inputs(payload or {}),
        confidence=max(0.0, min(1.0, float(confidence))),
        sensitivity=sensitivity,
        owner_visible=owner_visible,
        trace_id=trace_id,
        entity_refs=list(entity_refs or []),
        proof_path=proof_path,
    )
    EVENT_DIR.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        with open(EVENTS_FILE, "a") as f:
            f.write(json.dumps(event.to_dict(), default=str) + "\n")
    return event


def read_events(
    *,
    limit: int = 100,
    event_type: str | None = None,
    source: str | None = None,
    since_hours: int | None = None,
) -> list[dict[str, Any]]:
    if not EVENTS_FILE.exists():
        return []
    cutoff = datetime.now() - timedelta(hours=since_hours) if since_hours else None
    events: list[dict[str, Any]] = []
    with _LOCK:
        lines = EVENTS_FILE.read_text().splitlines()
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if event_type and item.get("event_type") != event_type:
            continue
        if source and item.get("source") != source:
            continue
        if cutoff:
            try:
                if datetime.fromisoformat(item.get("ts", "")) < cutoff:
                    continue
            except Exception:
                continue
        events.append(item)
        if len(events) >= limit:
            break
    return list(reversed(events))


def stats() -> dict[str, Any]:
    if not EVENTS_FILE.exists():
        return {"total": 0, "by_type": {}, "by_source": {}, "path": str(EVENTS_FILE)}
    by_type: dict[str, int] = {}
    by_source: dict[str, int] = {}
    total = 0
    latest_ts = None
    with _LOCK:
        lines = EVENTS_FILE.read_text().splitlines()
    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        total += 1
        by_type[item.get("event_type", "unknown")] = by_type.get(item.get("event_type", "unknown"), 0) + 1
        by_source[item.get("source", "unknown")] = by_source.get(item.get("source", "unknown"), 0) + 1
        latest_ts = item.get("ts") or latest_ts
    return {
        "total": total,
        "by_type": by_type,
        "by_source": by_source,
        "latest_ts": latest_ts,
        "path": str(EVENTS_FILE),
    }

