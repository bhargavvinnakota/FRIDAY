"""
Friday :: Revenue Ledger
Provider-agnostic internal money-event memory with approval-aware followups.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from friday.actions import razorpay as rz
from friday.brain.memory import Memory
from friday.brain.nervous_system import append_event
from friday.paths import FRIDAY_ROOT

from .registry import Operation, Skill, SkillResult

FRIDAY = FRIDAY_ROOT
CONFIG = FRIDAY / "config" / "friday.yaml"
LEDGER_DIR = FRIDAY / "data" / "revenue_ledger"
ENTRIES_FILE = LEDGER_DIR / "entries.jsonl"
STATE_FILE = LEDGER_DIR / "state.json"
RECEIPTS_FILE = LEDGER_DIR / "razorpay_webhook_receipts.jsonl"


@dataclass
class RevenueLedgerSettings:
    enabled: bool = True
    ledger_path: str = str(ENTRIES_FILE)
    state_path: str = str(STATE_FILE)
    receipts_path: str = str(RECEIPTS_FILE)
    default_window_days: int = 30


class RevenueLedgerSkill(Skill):
    name = "revenue_ledger"
    description = "Internal revenue memory for payment events, normalized ledger entries, and approval-aware followups."

    def _register_operations(self) -> None:
        self.register_op(Operation("status", "Summarize revenue ledger state and money-memory totals.", fn=self.op_status, risk="low"))
        self.register_op(Operation("latest", "Return latest normalized revenue ledger entries.", fn=self.op_latest, risk="low"))
        self.register_op(Operation("followups", "Return payment-related next actions and whether approval is required.", fn=self.op_followups, risk="low"))
        self.register_op(Operation("ingest_razorpay_webhook", "Verify and ingest a Razorpay webhook into FRIDAY's revenue ledger.", fn=self.op_ingest_razorpay_webhook, risk="low"))
        self.register_op(Operation("sync_razorpay", "Pull recent Razorpay objects and normalize them into the revenue ledger.", fn=self.op_sync_razorpay, risk="low"))

    def op_status(self, days: int = 30, **_) -> SkillResult:
        days = _int(days, _load_settings().default_window_days)
        entries = _read_entries()
        summary = _summarize(entries, days=days)
        followups = _followups(entries, limit=10)
        summary["open_followups"] = len(followups)
        summary["followups_preview"] = followups[:5]
        summary["path"] = str(_ledger_path())
        return SkillResult(ok=True, data=summary)

    def op_latest(self, limit: int = 10, **_) -> SkillResult:
        entries = _read_entries()
        limit = _int(limit, 10)
        return SkillResult(ok=True, data={"count": min(limit, len(entries)), "entries": entries[-limit:]})

    def op_followups(self, limit: int = 10, **_) -> SkillResult:
        limit = _int(limit, 10)
        items = _followups(_read_entries(), limit=limit)
        return SkillResult(ok=True, data={"count": len(items), "followups": items})

    def op_ingest_razorpay_webhook(
        self,
        raw_body: str,
        signature: str,
        webhook_secret: str = "",
        mode: str = "",
        source: str = "webhook",
        **_,
    ) -> SkillResult:
        verify = rz.verify_webhook_signature(raw_body=raw_body, signature=signature, webhook_secret=webhook_secret, mode=mode)
        if not verify.get("ok"):
            return SkillResult(ok=False, error=verify.get("error", "webhook verification failed"))
        if not verify.get("valid"):
            return SkillResult(ok=False, error="invalid webhook signature")

        payload = _json_loads(raw_body)
        if not isinstance(payload, dict):
            return SkillResult(ok=False, error="webhook body must be valid JSON")
        entry = _normalize_razorpay_webhook(payload, mode=verify.get("mode", "test"), source=source)
        if not entry:
            return SkillResult(ok=False, error="unsupported or empty Razorpay webhook payload")

        inserted = _store_entry(entry)
        receipt = {
            "ts": datetime.now().isoformat(),
            "provider": "razorpay",
            "mode": verify.get("mode", "test"),
            "event": payload.get("event", ""),
            "entity_id": entry.get("entity_id", ""),
            "entity_type": entry.get("entity_type", ""),
            "valid": True,
            "body_sha256": hashlib.sha256(raw_body.encode("utf-8")).hexdigest(),
        }
        _append_jsonl(Path(_load_settings().receipts_path).expanduser(), receipt)
        _refresh_money_memory()
        append_event(
            "money_event",
            source="revenue_ledger",
            payload=entry,
            sensitivity="internal",
            entity_refs=[f"money:{entry.get('provider','unknown')}", f"money:{entry.get('entity_type','event')}:{entry.get('entity_id','unknown')}"],
        )
        return SkillResult(
            ok=True,
            data={
                "inserted": inserted,
                "provider": "razorpay",
                "mode": verify.get("mode", "test"),
                "entry": entry,
                "receipt_path": str(Path(_load_settings().receipts_path).expanduser()),
            },
            artifacts=[str(_ledger_path()), str(Path(_load_settings().receipts_path).expanduser())],
        )

    def op_sync_razorpay(
        self,
        count: int = 10,
        include_payments: bool = True,
        include_links: bool = True,
        include_orders: bool = True,
        include_subscriptions: bool = False,
        mode: str = "",
        **_,
    ) -> SkillResult:
        count = _int(count, 10)
        sync_plan = []
        if _as_bool(include_payments):
            sync_plan.append(("payment", rz.fetch_payments(count=count, mode=mode)))
        if _as_bool(include_links):
            sync_plan.append(("payment_link", rz.fetch_payment_links(count=count, mode=mode)))
        if _as_bool(include_orders):
            sync_plan.append(("order", rz.fetch_orders(count=count, mode=mode)))
        if _as_bool(include_subscriptions):
            sync_plan.append(("subscription", rz.fetch_subscriptions(count=count, mode=mode)))

        inserted = 0
        scans = []
        for entity_type, response in sync_plan:
            if not response.get("ok"):
                scans.append({"entity_type": entity_type, "ok": False, "error": response.get("error", "fetch failed")})
                continue
            items = response.get("items", [])
            local_inserted = 0
            for item in items:
                entry = _normalize_snapshot_item(item, entity_type=entity_type, mode=response.get("mode", mode or "test"))
                if entry and _store_entry(entry):
                    inserted += 1
                    local_inserted += 1
            scans.append({"entity_type": entity_type, "ok": True, "fetched": len(items), "inserted": local_inserted})
        _refresh_money_memory()
        return SkillResult(
            ok=any(scan.get("ok") for scan in scans),
            data={"provider": "razorpay", "inserted": inserted, "scans": scans, "path": str(_ledger_path())},
            error=None if any(scan.get("ok") for scan in scans) else "razorpay sync failed; credentials may be missing",
            artifacts=[str(_ledger_path())],
        )


def _load_settings() -> RevenueLedgerSettings:
    settings = RevenueLedgerSettings()
    if not CONFIG.exists():
        return settings
    try:
        import yaml

        raw = yaml.safe_load(CONFIG.read_text()) or {}
    except Exception:
        return settings
    cfg = ((raw.get("revenue_ledger") or {}))
    if not isinstance(cfg, dict):
        return settings
    settings.enabled = _as_bool(cfg.get("enabled", settings.enabled))
    settings.ledger_path = str(cfg.get("ledger_path", settings.ledger_path) or settings.ledger_path)
    settings.state_path = str(cfg.get("state_path", settings.state_path) or settings.state_path)
    settings.receipts_path = str(cfg.get("receipts_path", settings.receipts_path) or settings.receipts_path)
    settings.default_window_days = _int(cfg.get("default_window_days", settings.default_window_days), settings.default_window_days)
    return settings


def _ledger_path() -> Path:
    return Path(_load_settings().ledger_path).expanduser()


def _state_path() -> Path:
    return Path(_load_settings().state_path).expanduser()


def _read_entries() -> list[dict[str, Any]]:
    path = _ledger_path()
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


def _store_entry(entry: dict[str, Any]) -> bool:
    key = _entry_key(entry)
    state = _read_state()
    seen = set(state.get("seen_keys", []))
    if key in seen:
        return False
    entry["ledger_key"] = key
    entry["ingested_at"] = datetime.now().isoformat()
    _append_jsonl(_ledger_path(), entry)
    seen.add(key)
    state["seen_keys"] = list(sorted(seen))[-5000:]
    state["last_ingest_at"] = datetime.now().isoformat()
    state["last_entity_id"] = entry.get("entity_id", "")
    _write_state(state)
    return True


def _read_state() -> dict[str, Any]:
    path = _state_path()
    if not path.exists():
        return {"seen_keys": [], "last_ingest_at": None}
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {"seen_keys": [], "last_ingest_at": None}
    except Exception:
        return {"seen_keys": [], "last_ingest_at": None}


def _write_state(state: dict[str, Any]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, default=str))


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(payload, default=str) + "\n")


def _normalize_razorpay_webhook(payload: dict[str, Any], mode: str, source: str) -> dict[str, Any] | None:
    event_name = str(payload.get("event", "")).strip()
    main = _extract_razorpay_entity(payload, event_name)
    if not main:
        return None
    entity_name, entity = main
    payment = _nested_entity(payload, "payment")
    customer = _compact({
        "name": entity.get("name") or entity.get("customer_name") or "",
        "email": entity.get("email") or entity.get("customer_email") or "",
        "contact": entity.get("contact") or entity.get("customer_contact") or "",
    })
    amount_paise = _int(
        entity.get("amount")
        or entity.get("amount_paid")
        or entity.get("first_payment_min_amount")
        or entity.get("value")
        or 0,
        0,
    )
    money_id = ""
    if isinstance(payment, dict):
        money_id = str(payment.get("id") or "")
    if not money_id:
        money_id = str(entity.get("id") or entity.get("payment_id") or entity.get("order_id") or "")
    status = str(entity.get("status") or _infer_status_from_event(event_name)).strip()
    followup = _followup_hint(entity_type=entity_name, status=status, event_type=event_name)
    return {
        "provider": "razorpay",
        "source": source,
        "mode": mode or "test",
        "event_type": event_name or f"{entity_name}.{status or 'event'}",
        "entity_type": entity_name,
        "entity_id": str(entity.get("id") or money_id or ""),
        "money_id": money_id,
        "status": status,
        "ledger_role": _ledger_role(entity_name, status, event_name),
        "amount_paise": amount_paise,
        "amount_inr": round(amount_paise / 100.0, 2),
        "currency": str(entity.get("currency") or "INR"),
        "reference_id": str(entity.get("reference_id") or entity.get("receipt") or entity.get("order_id") or ""),
        "customer": customer,
        "approval_required_followup": followup.get("approval_required"),
        "followup_action": followup.get("action"),
        "followup_reason": followup.get("reason"),
        "occurred_at": _iso_from_epoch(entity.get("created_at")) or datetime.now().isoformat(),
    }


def _normalize_snapshot_item(item: dict[str, Any], entity_type: str, mode: str) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    amount_paise = _int(item.get("amount") or item.get("amount_paid") or item.get("first_payment_min_amount") or 0, 0)
    status = str(item.get("status") or "").strip()
    event_type = f"{entity_type}.{status or 'observed'}"
    followup = _followup_hint(entity_type=entity_type, status=status, event_type=event_type)
    customer = _compact({
        "name": item.get("name") or item.get("customer_name") or "",
        "email": item.get("email") or item.get("customer_email") or "",
        "contact": item.get("contact") or item.get("customer_contact") or "",
    })
    return {
        "provider": "razorpay",
        "source": "api_snapshot",
        "mode": mode or "test",
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": str(item.get("id") or ""),
        "money_id": str(item.get("id") or item.get("payment_id") or item.get("order_id") or ""),
        "status": status,
        "ledger_role": _ledger_role(entity_type, status, event_type),
        "amount_paise": amount_paise,
        "amount_inr": round(amount_paise / 100.0, 2),
        "currency": str(item.get("currency") or "INR"),
        "reference_id": str(item.get("reference_id") or item.get("receipt") or item.get("order_id") or ""),
        "customer": customer,
        "approval_required_followup": followup.get("approval_required"),
        "followup_action": followup.get("action"),
        "followup_reason": followup.get("reason"),
        "occurred_at": _iso_from_epoch(item.get("created_at")) or datetime.now().isoformat(),
    }


def _extract_razorpay_entity(payload: dict[str, Any], event_name: str) -> tuple[str, dict[str, Any]] | None:
    preferred = event_name.split(".", 1)[0].replace("_", " ").replace(" ", "_")
    for name in [preferred, "payment", "payment_link", "order", "subscription"]:
        entity = _nested_entity(payload, name)
        if isinstance(entity, dict) and entity:
            return name, entity
    for name in ("payment", "payment_link", "order", "subscription"):
        entity = _nested_entity(payload, name)
        if isinstance(entity, dict) and entity:
            return name, entity
    return None


def _nested_entity(payload: dict[str, Any], name: str) -> dict[str, Any] | None:
    body = payload.get("payload", {})
    if not isinstance(body, dict):
        return None
    node = body.get(name, {})
    if not isinstance(node, dict):
        return None
    entity = node.get("entity")
    return entity if isinstance(entity, dict) else None


def _entry_key(entry: dict[str, Any]) -> str:
    return "::".join([
        str(entry.get("provider", "")),
        str(entry.get("source", "")),
        str(entry.get("event_type", "")),
        str(entry.get("entity_type", "")),
        str(entry.get("entity_id", "")),
        str(entry.get("status", "")),
        str(entry.get("money_id", "")),
    ])


def _refresh_money_memory() -> None:
    entries = _read_entries()
    summary = _summarize(entries, days=_load_settings().default_window_days)
    mem = Memory()
    mem.remember("money:revenue_ledger_entries", summary.get("entries", 0), category="money")
    mem.remember("money:captured_payments_count", summary.get("captured_payments_count", 0), category="money")
    mem.remember("money:captured_payments_inr_total", summary.get("captured_payments_inr_total", 0.0), category="money")
    mem.remember("money:last_payment_event", summary.get("last_event", {}), category="money")
    mem.remember("money:open_revenue_followups", len(_followups(entries, limit=20)), category="money")
    mem.log_event("revenue_ledger_update", summary)


def _summarize(entries: list[dict[str, Any]], days: int = 30) -> dict[str, Any]:
    recent = _recent_entries(entries, days)
    captured = [e for e in recent if e.get("entity_type") == "payment" and e.get("status") in {"captured", "paid"}]
    links = [e for e in recent if e.get("entity_type") == "payment_link"]
    orders = [e for e in recent if e.get("entity_type") == "order"]
    subscriptions = [e for e in recent if e.get("entity_type") == "subscription"]
    return {
        "generated_at": datetime.now().isoformat(),
        "window_days": days,
        "entries": len(recent),
        "captured_payments_count": len(captured),
        "captured_payments_inr_total": round(sum(float(e.get("amount_inr") or 0.0) for e in captured), 2),
        "payment_links_observed": len(links),
        "orders_observed": len(orders),
        "subscriptions_observed": len(subscriptions),
        "last_event": recent[-1] if recent else {},
    }


def _recent_entries(entries: list[dict[str, Any]], days: int) -> list[dict[str, Any]]:
    cutoff = datetime.now().timestamp() - (days * 86400)
    out = []
    for entry in entries:
        ts = _parse_iso(entry.get("occurred_at")) or _parse_iso(entry.get("ingested_at"))
        if ts and ts.timestamp() >= cutoff:
            out.append(entry)
    return out


def _followups(entries: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = f"{entry.get('provider','')}::{entry.get('entity_type','')}::{entry.get('entity_id','')}"
        latest[key] = entry
    items = []
    for entry in reversed(list(latest.values())):
        hint = _followup_hint(
            entity_type=str(entry.get("entity_type") or ""),
            status=str(entry.get("status") or ""),
            event_type=str(entry.get("event_type") or ""),
        )
        if not hint.get("action"):
            continue
        items.append({
            "provider": entry.get("provider"),
            "entity_type": entry.get("entity_type"),
            "entity_id": entry.get("entity_id"),
            "status": entry.get("status"),
            "event_type": entry.get("event_type"),
            "amount_inr": entry.get("amount_inr"),
            "customer": entry.get("customer", {}),
            "action": hint.get("action"),
            "reason": hint.get("reason"),
            "approval_required": hint.get("approval_required"),
            "risk_tier": "high" if hint.get("approval_required") else "low",
        })
        if len(items) >= limit:
            break
    return items


def _followup_hint(entity_type: str, status: str, event_type: str) -> dict[str, Any]:
    entity_type = (entity_type or "").strip()
    status = (status or "").strip().lower()
    event_type = (event_type or "").strip().lower()
    if entity_type == "payment" and status in {"captured", "paid"}:
        return {
            "action": "acknowledge_payment_and_trigger_fulfilment",
            "reason": "A payment landed. Any outward confirmation or fulfilment should stay approval-gated.",
            "approval_required": True,
        }
    if entity_type == "payment" and status in {"failed", "refunded"}:
        return {
            "action": "review_payment_exception",
            "reason": "A payment failed or reversed. Internal review is needed before any owner-visible action.",
            "approval_required": False,
        }
    if entity_type == "payment_link" and status in {"created", "issued"}:
        return {
            "action": "send_or_remind_payment_link",
            "reason": "The payment link exists, but delivery or reminder is externally visible and should require approval.",
            "approval_required": True,
        }
    if entity_type == "payment_link" and status in {"paid"}:
        return {
            "action": "confirm_payment_link_conversion",
            "reason": "A link converted. Customer-facing confirmation stays approval-gated.",
            "approval_required": True,
        }
    if entity_type == "order" and status in {"paid"}:
        return {
            "action": "reconcile_paid_order",
            "reason": "The order is paid. Reconcile internally before customer-visible followups.",
            "approval_required": False,
        }
    if entity_type == "subscription" and ("charged" in event_type or status in {"active", "authenticated"}):
        return {
            "action": "monitor_subscription_state",
            "reason": "Subscriptions need retention monitoring, but no automatic outward action is required yet.",
            "approval_required": False,
        }
    return {"action": "", "reason": "", "approval_required": False}


def _ledger_role(entity_type: str, status: str, event_type: str) -> str:
    if entity_type == "payment" and status in {"captured", "paid", "failed", "refunded"}:
        return "cash_event"
    if "charged" in event_type.lower():
        return "cash_event"
    return "collection_artifact"


def _infer_status_from_event(event_name: str) -> str:
    if "." in event_name:
        return event_name.rsplit(".", 1)[-1]
    return ""


def _iso_from_epoch(value: Any) -> str | None:
    try:
        ivalue = int(value)
    except Exception:
        return None
    if ivalue <= 0:
        return None
    return datetime.fromtimestamp(ivalue).isoformat()


def _parse_iso(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _compact(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if v not in ("", None, [])}


def _json_loads(raw: str) -> Any:
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off", ""}
    return bool(value)


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


if __name__ == "__main__":
    sample = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_demo",
                    "entity": "payment",
                    "amount": 19900,
                    "currency": "INR",
                    "status": "captured",
                    "contact": "9876543210",
                    "email": "demo@example.com",
                    "created_at": int(datetime.now().timestamp()),
                }
            }
        },
    }
    secret = "demo-secret"
    raw = json.dumps(sample)
    signature = hmac.new(secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
    print(RevenueLedgerSkill().op_ingest_razorpay_webhook(raw, signature, webhook_secret=secret).to_dict())
