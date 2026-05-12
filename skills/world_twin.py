"""
Friday :: World Twin
Normalizes local and optional web signals into entity-linked world events.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from friday.actions import nexus
from friday.brain.nervous_system import append_event

from .registry import Operation, Skill, SkillResult

FRIDAY = Path(os.path.expanduser("~/AI/friday"))
WORLD_DIR = FRIDAY / "data" / "world_twin"
WORLD_EVENTS = WORLD_DIR / "world_events.jsonl"
OPPORTUNITIES_FILE = FRIDAY / "data" / "opportunities.jsonl"


class WorldTwinSkill(Skill):
    name = "world_twin"
    description = "Entity-linked world awareness layer with freshness, confidence, and next-action signals."

    def _register_operations(self) -> None:
        self.register_op(Operation("pulse", "Create a local world/business pulse.", fn=self.op_pulse, risk="low"))
        self.register_op(Operation("entities", "Return latest known entity states.", fn=self.op_entities, risk="low"))
        self.register_op(Operation("status", "Summarize world twin event counts.", fn=self.op_status, risk="low"))

    def op_pulse(self, persist: bool = True, use_web: bool = False, **_) -> SkillResult:
        persist = _as_bool(persist)
        use_web = _as_bool(use_web)
        snapshot = nexus.snapshot()
        events = _local_world_events(snapshot)

        if use_web:
            # Optional and still safe: only reads public search snippets via existing research skill.
            from friday.skills.registry import get_registry
            res = get_registry().invoke("research", "web_search", _actor="world_twin", query="AI automation small business India", limit=3)
            if res.ok:
                for item in (res.data or {}).get("results", []):
                    events.append({
                        "entity": "public_web:ai_automation_india",
                        "state": item.get("title", ""),
                        "trend": "unknown",
                        "confidence": 0.55,
                        "freshness": "live_search",
                        "sources": [item.get("url", "")],
                        "business_relevance": "Possible external demand signal for AI automation offers.",
                        "next_action": "Review source manually before turning into an opportunity.",
                    })

        artifacts = []
        if persist:
            WORLD_DIR.mkdir(parents=True, exist_ok=True)
            with open(WORLD_EVENTS, "a") as f:
                for event in events:
                    event["ts"] = datetime.now().isoformat()
                    f.write(json.dumps(event, default=str) + "\n")
                    append_event(
                        "world_event",
                        source="world_twin",
                        payload=event,
                        confidence=float(event.get("confidence", 0.7)),
                        entity_refs=[event.get("entity", "world")],
                    )
            artifacts.append(str(WORLD_EVENTS))
        return SkillResult(ok=True, data={
            "generated_at": datetime.now().isoformat(),
            "count": len(events),
            "events": events,
            "use_web": use_web,
        }, artifacts=artifacts)

    def op_entities(self, limit: int = 20, **_) -> SkillResult:
        latest: dict[str, dict[str, Any]] = {}
        for event in _read_world_events():
            latest[event.get("entity", "unknown")] = event
        entities = list(latest.values())[-_int(limit, 20):]
        return SkillResult(ok=True, data={"entities": entities, "count": len(entities)})

    def op_status(self, **_) -> SkillResult:
        events = _read_world_events()
        by_entity: dict[str, int] = {}
        for event in events:
            entity = event.get("entity", "unknown")
            by_entity[entity] = by_entity.get(entity, 0) + 1
        return SkillResult(ok=True, data={
            "events": len(events),
            "entities": len(by_entity),
            "by_entity": by_entity,
            "path": str(WORLD_EVENTS),
        })


def _local_world_events(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    agency = snapshot.get("agency", {}) if isinstance(snapshot, dict) else {}
    leads = agency.get("leads", {}) if isinstance(agency, dict) else {}
    crm = agency.get("crm", {}) if isinstance(agency, dict) else {}
    opportunities = _read_opportunities()
    top = sorted(opportunities, key=lambda o: o.get("score", 0), reverse=True)[:3]
    return [
        {
            "entity": "bhargav:agency_pipeline",
            "state": f"{leads.get('total', 0)} leads, {leads.get('with_phone', 0)} with phone, {crm.get('closed', 0)} closed",
            "trend": "needs_conversion",
            "confidence": 0.9,
            "freshness": "local_snapshot",
            "sources": ["nexus.snapshot"],
            "business_relevance": "Primary near-term cash path.",
            "next_action": "Review pending WhatsApp pilot approvals and record outcomes.",
        },
        {
            "entity": "friday:money_engine",
            "state": f"{len(opportunities)} opportunities ranked; top={top[0].get('id') if top else 'none'}",
            "trend": "active",
            "confidence": 0.85,
            "freshness": "local_snapshot",
            "sources": [str(OPPORTUNITIES_FILE)],
            "business_relevance": "Ranks cash experiments by expected value and risk.",
            "next_action": "Run or review the top reversible experiment.",
        },
        {
            "entity": "friday:regulatory_boundary",
            "state": "Money movement, live trading, legal/medical commitments remain non-autonomous.",
            "trend": "red_line",
            "confidence": 1.0,
            "freshness": "constitution",
            "sources": ["FRIDAY_NEXUS_EXTENSIVE_RND_2026.md", "config/policies.yaml"],
            "business_relevance": "Keeps revenue automation ethical and survivable.",
            "next_action": "Keep all outbound/money actions approval-gated.",
        },
    ]


def _read_opportunities() -> list[dict[str, Any]]:
    if not OPPORTUNITIES_FILE.exists():
        return []
    out = []
    for line in OPPORTUNITIES_FILE.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _read_world_events() -> list[dict[str, Any]]:
    if not WORLD_EVENTS.exists():
        return []
    events = []
    for line in WORLD_EVENTS.read_text().splitlines():
        try:
            events.append(json.loads(line))
        except Exception:
            continue
    return events


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default

