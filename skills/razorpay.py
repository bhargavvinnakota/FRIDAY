"""
Friday :: Razorpay Skill
India-native payments rail with safe dry-runs, audit artifacts, and signature
verification.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from friday.actions import razorpay as rz
from friday.brain.nervous_system import append_event

from .registry import Operation, Skill, SkillResult

FRIDAY = Path(os.path.expanduser("~/AI/friday"))
CONFIG = FRIDAY / "config" / "friday.yaml"
DATA_DIR = FRIDAY / "data" / "razorpay"
PREVIEW_DIR = DATA_DIR / "previews"
RECEIPT_DIR = DATA_DIR / "receipts"
EVENTS_PATH = DATA_DIR / "events.jsonl"
WEBHOOKS_PATH = DATA_DIR / "webhooks.jsonl"


@dataclass
class RazorpaySettings:
    enabled: bool = True
    mode: str = "test"
    default_currency: str = "INR"
    dry_run_by_default: bool = True
    events_path: str = str(EVENTS_PATH)
    webhooks_path: str = str(WEBHOOKS_PATH)


class RazorpaySkill(Skill):
    name = "razorpay"
    description = "Razorpay collections rail for FRIDAY: payment links, orders, subscriptions, and signature verification."

    def _register_operations(self) -> None:
        self.register_op(Operation("status", "Show Razorpay readiness and optionally probe the API.", fn=self.op_status, risk="low"))
        self.register_op(Operation("fetch_payments", "Fetch recent Razorpay payments.", fn=self.op_fetch_payments, risk="low"))
        self.register_op(Operation("fetch_orders", "Fetch recent Razorpay orders.", fn=self.op_fetch_orders, risk="low"))
        self.register_op(Operation("fetch_payment_links", "Fetch recent Razorpay payment links.", fn=self.op_fetch_payment_links, risk="low"))
        self.register_op(Operation("fetch_subscriptions", "Fetch recent Razorpay subscriptions.", fn=self.op_fetch_subscriptions, risk="low"))
        self.register_op(Operation("create_payment_link", "Create or preview a Razorpay payment link.", fn=self.op_create_payment_link, risk="high", requires_confirm=True))
        self.register_op(Operation("create_order", "Create or preview a Razorpay order.", fn=self.op_create_order, risk="high", requires_confirm=True))
        self.register_op(Operation("create_subscription", "Create or preview a Razorpay subscription.", fn=self.op_create_subscription, risk="high", requires_confirm=True))
        self.register_op(Operation("verify_payment_signature", "Verify the checkout payment signature.", fn=self.op_verify_payment_signature, risk="low"))
        self.register_op(Operation("verify_webhook_signature", "Verify the webhook signature.", fn=self.op_verify_webhook_signature, risk="low"))
        self.register_op(Operation("record_webhook", "Verify and record a sanitized webhook receipt.", fn=self.op_record_webhook, risk="medium"))

    def op_status(self, probe: bool = False, mode: str = "", **_) -> SkillResult:
        settings = _load_settings()
        resolved_mode = _mode(mode, settings)
        payload = rz.status(resolved_mode)
        payload["settings"] = asdict(settings)
        payload["recommended_env_vars"] = [
            "RAZORPAY_MODE",
            "RAZORPAY_KEY_ID",
            "RAZORPAY_KEY_SECRET",
            "RAZORPAY_WEBHOOK_SECRET",
        ]
        payload["next_step"] = (
            "Run `friday razorpay status --probe` after adding test keys to ~/.openclaw/.env."
            if not payload.get("configured")
            else "Run a dry-run create-link, then switch to --commit only for approved collection flows."
        )
        if _as_bool(probe):
            probe_result = rz.health(resolved_mode)
            payload["probe_result"] = probe_result
            return SkillResult(
                ok=bool(probe_result.get("ok")),
                data=payload,
                error=None if probe_result.get("ok") else probe_result.get("error"),
            )
        return SkillResult(ok=True, data=payload)

    def op_fetch_payments(self, count: int = 10, skip: int = 0, from_ts: int = 0, to_ts: int = 0, mode: str = "", **_) -> SkillResult:
        settings = _load_settings()
        result = rz.fetch_payments(count=int(count), skip=int(skip), from_ts=_zero_none(from_ts), to_ts=_zero_none(to_ts), mode=_mode(mode, settings))
        return _skill_result(result)

    def op_fetch_orders(self, count: int = 10, skip: int = 0, from_ts: int = 0, to_ts: int = 0, mode: str = "", **_) -> SkillResult:
        settings = _load_settings()
        result = rz.fetch_orders(count=int(count), skip=int(skip), from_ts=_zero_none(from_ts), to_ts=_zero_none(to_ts), mode=_mode(mode, settings))
        return _skill_result(result)

    def op_fetch_payment_links(self, count: int = 10, skip: int = 0, from_ts: int = 0, to_ts: int = 0, mode: str = "", **_) -> SkillResult:
        settings = _load_settings()
        result = rz.fetch_payment_links(count=int(count), skip=int(skip), from_ts=_zero_none(from_ts), to_ts=_zero_none(to_ts), mode=_mode(mode, settings))
        return _skill_result(result)

    def op_fetch_subscriptions(self, count: int = 10, skip: int = 0, mode: str = "", **_) -> SkillResult:
        settings = _load_settings()
        result = rz.fetch_subscriptions(count=int(count), skip=int(skip), mode=_mode(mode, settings))
        return _skill_result(result)

    def op_create_payment_link(
        self,
        amount: Any = None,
        amount_inr: Any = None,
        amount_paise: Any = None,
        currency: str = "",
        customer_name: str = "",
        customer_email: str = "",
        customer_phone: str = "",
        description: str = "",
        reference_id: str = "",
        accept_partial: bool = False,
        first_min_partial_amount: Any = None,
        expire_by: int = 0,
        expiry_minutes: int = 0,
        notify_email: bool = False,
        notify_sms: bool = False,
        callback_url: str = "",
        callback_method: str = "",
        reminder_enable: bool = False,
        upi_link: bool = False,
        notes: dict[str, Any] | None = None,
        dry_run: bool | str | None = None,
        mode: str = "",
        **_,
    ) -> SkillResult:
        settings = _load_settings()
        resolved_mode = _mode(mode, settings)
        payload: dict[str, Any] = {
            "amount": _amount_paise(amount=amount, amount_inr=amount_inr, amount_paise=amount_paise),
            "currency": (currency or settings.default_currency or "INR").upper(),
            "description": description,
        }
        if reference_id:
            payload["reference_id"] = reference_id
        customer = _compact({
            "name": customer_name,
            "email": customer_email,
            "contact": customer_phone,
        })
        if customer:
            payload["customer"] = customer
        if _as_bool(accept_partial):
            payload["accept_partial"] = True
        if first_min_partial_amount not in (None, "", 0, "0"):
            payload["first_min_partial_amount"] = _amount_paise(amount=first_min_partial_amount)
        if int(expire_by or 0) > 0:
            payload["expire_by"] = int(expire_by)
        elif int(expiry_minutes or 0) > 0:
            payload["expire_by"] = int((datetime.now() + timedelta(minutes=int(expiry_minutes))).timestamp())
        if callback_url:
            payload["callback_url"] = callback_url
        if callback_method:
            payload["callback_method"] = callback_method.lower()
        if _as_bool(reminder_enable):
            payload["reminder_enable"] = True
        if _as_bool(upi_link):
            payload["upi_link"] = True
        notify = _compact({
            "email": _as_bool(notify_email) if notify_email not in ("", None) else None,
            "sms": _as_bool(notify_sms) if notify_sms not in ("", None) else None,
        })
        if notify:
            payload["notify"] = notify
        if notes:
            payload["notes"] = _sanitize_notes(notes)
        return self._create_or_preview("payment_link", payload, resolved_mode, dry_run)

    def op_create_order(
        self,
        amount: Any = None,
        amount_inr: Any = None,
        amount_paise: Any = None,
        currency: str = "",
        receipt: str = "",
        partial_payment: bool = False,
        first_payment_min_amount: Any = None,
        notes: dict[str, Any] | None = None,
        dry_run: bool | str | None = None,
        mode: str = "",
        **_,
    ) -> SkillResult:
        settings = _load_settings()
        resolved_mode = _mode(mode, settings)
        payload: dict[str, Any] = {
            "amount": _amount_paise(amount=amount, amount_inr=amount_inr, amount_paise=amount_paise),
            "currency": (currency or settings.default_currency or "INR").upper(),
        }
        if receipt:
            payload["receipt"] = receipt
        if _as_bool(partial_payment):
            payload["partial_payment"] = True
        if first_payment_min_amount not in (None, "", 0, "0"):
            payload["first_payment_min_amount"] = _amount_paise(amount=first_payment_min_amount)
        if notes:
            payload["notes"] = _sanitize_notes(notes)
        return self._create_or_preview("order", payload, resolved_mode, dry_run)

    def op_create_subscription(
        self,
        plan_id: str,
        total_count: int,
        quantity: int = 1,
        customer_notify: bool = False,
        start_at: int = 0,
        expire_by: int = 0,
        notes: dict[str, Any] | None = None,
        dry_run: bool | str | None = None,
        mode: str = "",
        **_,
    ) -> SkillResult:
        if not str(plan_id or "").strip():
            return SkillResult(ok=False, error="plan_id is required")
        payload: dict[str, Any] = {
            "plan_id": str(plan_id).strip(),
            "total_count": int(total_count),
            "quantity": int(quantity or 1),
        }
        if customer_notify not in ("", None):
            payload["customer_notify"] = _as_bool(customer_notify)
        if int(start_at or 0) > 0:
            payload["start_at"] = int(start_at)
        if int(expire_by or 0) > 0:
            payload["expire_by"] = int(expire_by)
        if notes:
            payload["notes"] = _sanitize_notes(notes)
        settings = _load_settings()
        return self._create_or_preview("subscription", payload, _mode(mode, settings), dry_run)

    def op_verify_payment_signature(
        self,
        order_id: str,
        payment_id: str,
        signature: str,
        key_secret: str = "",
        mode: str = "",
        **_,
    ) -> SkillResult:
        settings = _load_settings()
        result = rz.verify_payment_signature(order_id=order_id, payment_id=payment_id, signature=signature, key_secret=key_secret, mode=_mode(mode, settings))
        if result.get("ok"):
            append_event(
                "razorpay_signature_verified",
                source="razorpay",
                payload={"valid": result.get("valid"), "mode": result.get("mode")},
                entity_refs=["payments:razorpay"],
            )
        return _skill_result(result)

    def op_verify_webhook_signature(
        self,
        raw_body: str,
        signature: str,
        webhook_secret: str = "",
        mode: str = "",
        **_,
    ) -> SkillResult:
        settings = _load_settings()
        result = rz.verify_webhook_signature(raw_body=raw_body, signature=signature, webhook_secret=webhook_secret, mode=_mode(mode, settings))
        if result.get("ok"):
            append_event(
                "razorpay_webhook_signature_verified",
                source="razorpay",
                payload={"valid": result.get("valid"), "mode": result.get("mode")},
                entity_refs=["payments:razorpay"],
            )
        return _skill_result(result)

    def op_record_webhook(
        self,
        raw_body: str,
        signature: str,
        webhook_secret: str = "",
        mode: str = "",
        **_,
    ) -> SkillResult:
        settings = _load_settings()
        verify = rz.verify_webhook_signature(raw_body=raw_body, signature=signature, webhook_secret=webhook_secret, mode=_mode(mode, settings))
        parsed = _json_loads(raw_body)
        record = {
            "ts": datetime.now().isoformat(),
            "mode": verify.get("mode"),
            "valid": bool(verify.get("valid")),
            "body_sha256": hashlib.sha256((raw_body or "").encode("utf-8")).hexdigest(),
            "size_bytes": len((raw_body or "").encode("utf-8")),
            "event": parsed.get("event") if isinstance(parsed, dict) else "",
            "contains_entity": parsed.get("payload", {}).get("payment", {}).get("entity", {}).get("id", "") if isinstance(parsed, dict) else "",
        }
        path = Path(settings.webhooks_path).expanduser()
        _append_jsonl(path, record)
        append_event(
            "razorpay_webhook_recorded",
            source="razorpay",
            payload={"valid": record["valid"], "event": record["event"]},
            entity_refs=["payments:razorpay"],
        )
        return SkillResult(
            ok=bool(verify.get("ok") and verify.get("valid")),
            data={"recorded": True, "path": str(path), "webhook": record},
            artifacts=[str(path)],
            error=None if verify.get("valid") else verify.get("error") or "invalid webhook signature",
        )

    def _create_or_preview(self, kind: str, payload: dict[str, Any], mode: str, dry_run: bool | str | None) -> SkillResult:
        settings = _load_settings()
        do_dry_run = settings.dry_run_by_default if dry_run is None else _as_bool(dry_run)
        if do_dry_run:
            preview = {
                "generated_at": datetime.now().isoformat(),
                "operation": f"create_{kind}",
                "mode": mode,
                "dry_run": True,
                "payload": payload,
            }
            preview_path = _write_json(PREVIEW_DIR, f"{kind}_preview", preview)
            append_event(
                "razorpay_dry_run",
                source="razorpay",
                payload={"operation": kind, "mode": mode},
                entity_refs=["payments:razorpay"],
            )
            return SkillResult(
                ok=True,
                data=preview,
                artifacts=[preview_path],
                followup=[{
                    "action": f"friday razorpay create-{kind.replace('_', '-')}",
                    "mode": "commit_required",
                    "note": "Dry-run is ready. Use --commit only after approval and test-key validation.",
                }],
            )

        if kind == "payment_link":
            result = rz.create_payment_link(payload, mode=mode)
        elif kind == "order":
            result = rz.create_order(payload, mode=mode)
        else:
            result = rz.create_subscription(payload, mode=mode)
        if not result.get("ok"):
            return _skill_result(result)

        entity = result.get("entity") or {}
        summary = {
            "ts": datetime.now().isoformat(),
            "operation": f"create_{kind}",
            "mode": mode,
            "id": result.get("id") or entity.get("id"),
            "status": result.get("status_value") or entity.get("status"),
            "amount": entity.get("amount") or payload.get("amount"),
            "currency": entity.get("currency") or payload.get("currency", ""),
            "reference_id": entity.get("reference_id") or payload.get("reference_id", ""),
            "receipt": entity.get("receipt") or payload.get("receipt", ""),
            "short_url": entity.get("short_url", ""),
        }
        events_path = Path(settings.events_path).expanduser()
        _append_jsonl(events_path, summary)
        receipt_path = _write_json(RECEIPT_DIR, f"{kind}_receipt", summary)
        append_event(
            "razorpay_entity_created",
            source="razorpay",
            payload={"operation": kind, "id": summary["id"], "status": summary["status"], "mode": mode},
            entity_refs=["payments:razorpay"],
        )
        result["audit"] = summary
        return SkillResult(ok=True, data=result, artifacts=[str(events_path), receipt_path])


def _load_settings() -> RazorpaySettings:
    settings = RazorpaySettings()
    if not CONFIG.exists():
        return settings
    try:
        import yaml

        raw = yaml.safe_load(CONFIG.read_text()) or {}
    except Exception:
        return settings
    cfg = (((raw.get("payments") or {}).get("razorpay")) or {})
    if not isinstance(cfg, dict):
        return settings
    settings.enabled = _as_bool(cfg.get("enabled", settings.enabled))
    settings.mode = str(cfg.get("mode", settings.mode) or settings.mode)
    settings.default_currency = str(cfg.get("default_currency", settings.default_currency) or settings.default_currency)
    settings.dry_run_by_default = _as_bool(cfg.get("dry_run_by_default", settings.dry_run_by_default))
    settings.events_path = str(cfg.get("events_path", settings.events_path) or settings.events_path)
    settings.webhooks_path = str(cfg.get("webhooks_path", settings.webhooks_path) or settings.webhooks_path)
    return settings


def _mode(value: str = "", settings: RazorpaySettings | None = None) -> str:
    fallback = (settings.mode if settings else "test") or "test"
    raw = str(value or os.environ.get("RAZORPAY_MODE") or fallback).strip().lower()
    return raw if raw in {"test", "live"} else "test"


def _amount_paise(amount: Any = None, amount_inr: Any = None, amount_paise: Any = None) -> int:
    if amount_paise not in (None, ""):
        value = int(str(amount_paise).strip())
        if value <= 0:
            raise ValueError("amount_paise must be positive")
        return value
    raw = amount_inr if amount_inr not in (None, "") else amount
    if raw in (None, ""):
        raise ValueError("amount or amount_paise is required")
    rupees = Decimal(str(raw).strip())
    if rupees <= 0:
        raise ValueError("amount must be positive")
    return int((rupees * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(payload, default=str) + "\n")


def _write_json(directory: Path, prefix: str, payload: dict[str, Any]) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = directory / f"{prefix}_{stamp}.json"
    path.write_text(json.dumps(payload, indent=2, default=str))
    return str(path)


def _sanitize_notes(notes: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in (notes or {}).items():
        k = str(key).strip()[:64]
        if not k:
            continue
        out[k] = str(value).strip()[:255]
    return out


def _compact(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if v not in (None, "", [])}


def _json_loads(raw: str) -> Any:
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _skill_result(result: dict[str, Any]) -> SkillResult:
    return SkillResult(
        ok=bool(result.get("ok")),
        data=result,
        error=None if result.get("ok") else result.get("error"),
    )


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off", ""}
    return bool(value)


def _zero_none(value: Any) -> int | None:
    try:
        ivalue = int(value)
    except Exception:
        return None
    return None if ivalue <= 0 else ivalue
