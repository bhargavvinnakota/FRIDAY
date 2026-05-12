"""
Friday :: Connector Command Center
Tracks FRIDAY's external nervous-system connectors, readiness, risk, and gaps.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from friday.brain.nervous_system import append_event

from .registry import Operation, Skill, SkillResult

FRIDAY = Path(os.path.expanduser("~/AI/friday"))
CONFIG = FRIDAY / "config" / "connectors.yaml"
EXPORT_DIR = FRIDAY / "data" / "connector_center"


class ConnectorCenterSkill(Skill):
    name = "connector_center"
    description = "Permissioned connector inventory for FRIDAY's Mac, cloud, money, and business tool nervous system."

    def _register_operations(self) -> None:
        self.register_op(Operation("inventory", "List connector inventory with optional filters.", fn=self.op_inventory, risk="low"))
        self.register_op(Operation("status", "Summarize connector readiness and blockers.", fn=self.op_status, risk="low"))
        self.register_op(Operation("gaps", "Return prioritized missing or broken connectors.", fn=self.op_gaps, risk="low"))
        self.register_op(Operation("roadmap", "Return a solo-founder connector roadmap and enterprise deferrals.", fn=self.op_roadmap, risk="low"))
        self.register_op(Operation("test_plan", "Generate safe smoke tests for connector readiness.", fn=self.op_test_plan, risk="low"))
        self.register_op(Operation("export_map", "Export connector command-center map to JSON and Markdown.", fn=self.op_export_map, risk="low"))

    def op_inventory(self, status: str = "", category: str = "", **_) -> SkillResult:
        data = _load_manifest()
        connectors = data["connectors"]
        if status:
            connectors = [c for c in connectors if c.get("status") == status]
        if category:
            connectors = [c for c in connectors if c.get("category") == category]
        return SkillResult(ok=True, data={
            "count": len(connectors),
            "filters": {"status": status, "category": category},
            "connectors": connectors,
        })

    def op_status(self, **_) -> SkillResult:
        data = _load_manifest()
        connectors = data["connectors"]
        counts = _count_by(connectors, "status")
        categories = _count_by(connectors, "category")
        connected = counts.get("connected", 0)
        available = counts.get("available", 0)
        action_needed_count = counts.get("action_needed", 0)
        action_needed = [c for c in connectors if c.get("status") == "action_needed"]
        high_risk = [c for c in connectors if c.get("risk_tier") in {"high", "forbidden"}]
        readiness = _readiness_score(connected, available, action_needed_count, len(connectors))
        payload = {
            "generated_at": datetime.now().isoformat(),
            "manifest": str(CONFIG),
            "total": len(connectors),
            "readiness_score": readiness,
            "verified_connected_score": round((connected / len(connectors)) * 100, 1) if connectors else 0.0,
            "by_status": counts,
            "by_category": categories,
            "high_risk_connectors": len(high_risk),
            "solo_ready_now": len([c for c in connectors if c.get("phase") == "now" and c.get("solo_friendly", False)]),
            "org_blocked": len([m for m in data["missing_connectors"] if m.get("requires_org_workspace")]),
            "availability_blocked": len([m for m in data["missing_connectors"] if m.get("availability_constraint")]),
            "action_needed": [
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "auth_state": c.get("auth_state"),
                    "next_action": _next_action(c),
                }
                for c in action_needed
            ],
            "missing_p0": [m for m in data["missing_connectors"] if m.get("priority") == "P0"],
            "availability_constraints": [
                {
                    "id": m.get("id"),
                    "name": m.get("name"),
                    "constraint": m.get("availability_constraint"),
                    "alternative": m.get("alternative_if_blocked", ""),
                }
                for m in data["missing_connectors"]
                if m.get("availability_constraint")
            ],
            "operational_takeaway": _takeaway(counts, data["missing_connectors"]),
        }
        append_event(
            "connector_status",
            source="connector_center",
            payload={"readiness_score": readiness, "by_status": counts},
            entity_refs=["friday:connectors"],
        )
        return SkillResult(ok=True, data=payload)

    def op_gaps(self, priority: str = "", **_) -> SkillResult:
        data = _load_manifest()
        broken = [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "category": c.get("category"),
                "status": c.get("status"),
                "auth_state": c.get("auth_state"),
                "next_action": _next_action(c),
            }
            for c in data["connectors"]
            if c.get("status") == "action_needed"
        ]
        missing = data["missing_connectors"]
        if priority:
            missing = [m for m in missing if m.get("priority") == priority]
        return SkillResult(ok=True, data={
            "broken_connected_tools": broken,
            "missing_connectors": missing,
            "next_three": _next_three(broken, missing),
        })

    def op_roadmap(self, **_) -> SkillResult:
        data = _load_manifest()
        connectors = data["connectors"]
        missing = data["missing_connectors"]
        now = [c for c in connectors if c.get("phase") == "now"] + [m for m in missing if m.get("phase") == "now"]
        next_up = [c for c in connectors if c.get("phase") == "next"] + [m for m in missing if m.get("phase") == "next"]
        later = [c for c in connectors if c.get("phase") == "later"] + [m for m in missing if m.get("phase") == "later"]
        blocked = [m for m in missing if m.get("requires_org_workspace")]
        availability = [m for m in missing if m.get("availability_constraint")]
        return SkillResult(ok=True, data={
            "generated_at": datetime.now().isoformat(),
            "principle": "Do not wait for enterprise furniture. Build on solo-friendly connectors now and substitute internal services where enterprise tools are premature.",
            "now": _roadmap_items(now),
            "next": _roadmap_items(next_up),
            "later": _roadmap_items(later),
            "blocked_by_org_workspace": _roadmap_items(blocked),
            "blocked_by_availability_constraints": _roadmap_items(availability),
        })

    def op_test_plan(self, include_write_tests: bool = False, **_) -> SkillResult:
        include_write_tests = _as_bool(include_write_tests)
        data = _load_manifest()
        tests = []
        for connector in data["connectors"]:
            tests.append(_smoke_test(connector, include_write_tests))
        return SkillResult(ok=True, data={
            "generated_at": datetime.now().isoformat(),
            "mode": "read_only_plus_drafts" if include_write_tests else "read_only",
            "count": len(tests),
            "tests": tests,
            "rule": "Never run destructive, payment, outbound, public-post, or production-deploy tests without Bhargav approval.",
        })

    def op_export_map(self, **_) -> SkillResult:
        data = _load_manifest()
        status = self.op_status().data
        gaps = self.op_gaps().data
        report = {
            "generated_at": datetime.now().isoformat(),
            "status": status,
            "inventory": data["connectors"],
            "gaps": gaps,
        }
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = EXPORT_DIR / f"connector_map_{stamp}.json"
        md_path = EXPORT_DIR / f"connector_map_{stamp}.md"
        json_path.write_text(json.dumps(report, indent=2, default=str))
        md_path.write_text(_markdown(report))
        append_event(
            "connector_map_exported",
            source="connector_center",
            payload={"json": str(json_path), "markdown": str(md_path)},
            entity_refs=["friday:connectors"],
        )
        return SkillResult(ok=True, data={
            "json": str(json_path),
            "markdown": str(md_path),
            "readiness_score": status.get("readiness_score"),
        }, artifacts=[str(json_path), str(md_path)])


def _load_manifest() -> dict[str, list[dict[str, Any]]]:
    if not CONFIG.exists():
        return {"connectors": [], "missing_connectors": []}
    try:
        import yaml
        raw = yaml.safe_load(CONFIG.read_text()) or {}
    except Exception:
        raw = json.loads(CONFIG.read_text())
    return {
        "connectors": list(raw.get("connectors") or []),
        "missing_connectors": list(raw.get("missing_connectors") or []),
    }


def _count_by(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = str(item.get(field) or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _readiness_score(connected: int, available: int, action_needed: int, total: int) -> float:
    if total <= 0:
        return 0.0
    weighted = (connected * 1.0) + (available * 0.55) + (action_needed * 0.1)
    return round((weighted / total) * 100, 1)


def _next_action(connector: dict[str, Any]) -> str:
    status = connector.get("status")
    auth_state = connector.get("auth_state", "")
    if status == "action_needed" and auth_state == "invalid_token":
        return "Reconnect the connector and rerun connector_center.status."
    if status == "action_needed" and "awaiting_api_keys" in auth_state:
        return "Add the connector secrets to ~/.openclaw/.env and run a read-only probe."
    if status == "missing":
        return "Connect this service through MCP/plugin/API key setup."
    if status == "available":
        return "Run a read-only smoke test before depending on this connector."
    return "Keep in safe-default mode and log all actions through policy."


def _takeaway(counts: dict[str, int], missing: list[dict[str, Any]]) -> str:
    p0 = [m["id"] for m in missing if m.get("priority") == "P0"]
    constrained = [m["id"] for m in missing if m.get("availability_constraint")]
    if counts.get("action_needed"):
        return "Reconnect broken tools first, then wire P0 money connectors."
    if p0:
        return "Core operator layer is present; money engine still needs P0 financial connectors: " + ", ".join(p0)
    if constrained:
        return "Some connectors are externally constrained; use mapped substitutes instead: " + ", ".join(constrained)
    return "Connector layer is ready for supervised operation."


def _next_three(broken: list[dict[str, Any]], missing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for item in broken:
        ranked.append({"type": "repair", **item})
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    for item in sorted(missing, key=lambda m: priority_order.get(m.get("priority"), 9)):
        ranked.append({"type": "connect", **item})
    return ranked[:3]


def _roadmap_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for item in items:
        out.append({
            "id": item.get("id"),
            "name": item.get("name"),
            "category": item.get("category"),
            "status": item.get("status", "missing"),
            "priority": item.get("priority", ""),
            "solo_friendly": item.get("solo_friendly"),
            "requires_org_workspace": item.get("requires_org_workspace"),
            "availability_constraint": item.get("availability_constraint", ""),
            "reason": item.get("reason", ""),
            "alternative_if_blocked": item.get("alternative_if_blocked", ""),
        })
    return out


def _smoke_test(connector: dict[str, Any], include_write_tests: bool) -> dict[str, Any]:
    cid = connector.get("id", "")
    status = connector.get("status", "unknown")
    base = {
        "connector_id": cid,
        "name": connector.get("name"),
        "status": status,
        "risk_tier": connector.get("risk_tier"),
        "read_test": "Verify profile or list metadata only.",
        "write_test": "not_included",
        "approval_required": connector.get("risk_tier") in {"medium", "high", "forbidden"},
    }
    read_tests = {
        "gmail": "get_profile then search_email_ids max_results=1 with no body read.",
        "google_calendar": "get_profile then fetch next visible calendar metadata.",
        "google_drive": "get_profile then list root top_k=5.",
        "github": "list_recent_issues top_k=3.",
        "notion": "search workspace for FRIDAY page_size=3.",
        "hugging_face": "whoami then model_search query=text-generation limit=3.",
        "netlify": "get-user and list teams/projects.",
        "razorpay": "friday razorpay status --probe, then fetch_payments count=1 using test keys only.",
        "vantage": "list cost integrations after reconnect.",
        "computer_use": "list_apps only.",
    }
    write_tests = {
        "gmail": "create a draft to Bhargav only; do not send.",
        "google_drive": "create a private scratch Doc named FRIDAY Connector Smoke Test.",
        "netlify": "inspect deploy context only; do not deploy unless explicitly approved.",
        "razorpay": "create a payment link dry-run only; no live link unless explicitly approved.",
        "neon_postgres": "create temporary branch only after approval.",
        "supabase": "run advisors only; no migration in smoke test.",
    }
    base["read_test"] = read_tests.get(cid, base["read_test"])
    if include_write_tests:
        base["write_test"] = write_tests.get(cid, "Only propose a write test; no live write by default.")
    if status == "action_needed":
        base["expected_result"] = "fail_until_reconnected"
    elif status in {"connected", "available"}:
        base["expected_result"] = "pass_read_only"
    else:
        base["expected_result"] = "not_applicable"
    return base


def _markdown(report: dict[str, Any]) -> str:
    status = report["status"]
    lines = [
        "# FRIDAY Connector Command Center",
        "",
        f"Generated: {report['generated_at']}",
        f"Readiness score: {status.get('readiness_score')}%",
        "",
        "## Status",
        "",
        "| Status | Count |",
        "|---|---:|",
    ]
    for key, value in (status.get("by_status") or {}).items():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "## Inventory", "", "| Connector | Category | Status | Risk |", "|---|---|---|---|"])
    for c in report["inventory"]:
        lines.append(f"| {c.get('name')} | {c.get('category')} | {c.get('status')} | {c.get('risk_tier')} |")
    lines.extend(["", "## Next Three", ""])
    for item in (report["gaps"].get("next_three") or []):
        lines.append(f"- {item.get('type')}: {item.get('name')} ({item.get('id')})")
    lines.append("")
    return "\n".join(lines)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)
