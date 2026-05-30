"""
Friday :: Action Envelope
Proof-carrying metadata for every registry-mediated skill/tool action.

The envelope is intentionally model-agnostic and JSON-friendly. It gives
Friday a standard place to record the policy decision, trace id, redacted
inputs, expected outcome, rollback note, and proof artifact for each action.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from friday.paths import FRIDAY_ROOT

FRIDAY = FRIDAY_ROOT
PROOF_DIR = FRIDAY / "data" / "action_proofs"

SENSITIVE_KEY_PARTS = {
    "api_key", "apikey", "authorization", "bearer", "cookie", "email",
    "mobile", "otp", "pass", "password", "phone", "secret", "token",
    "upi", "whatsapp",
}

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
DIGIT_RUN_RE = re.compile(r"(?<!\d)(?:\+?\d[\d -]{7,}\d)(?!\d)")


@dataclass
class ActionEnvelope:
    goal: str
    action_type: str
    skill: str
    operation: str
    actor: str
    risk_tier: str
    policy_decision: str
    policy_reason: str
    autonomy_level: str
    requires_approval: bool
    evidence: list[str] = field(default_factory=list)
    inputs_redacted: dict[str, Any] = field(default_factory=dict)
    expected_outcome: str = "Execute the requested operation and record proof."
    rollback: str = "No automatic rollback declared; inspect proof and artifacts."
    notification: str = "summary"
    post_action_metric: str = "action_ok"
    trace_id: str = ""
    approval_id: str | None = None
    proof_path: str | None = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def new_trace_id(skill: str, operation: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"act_{stamp}_{skill}_{operation}_{uuid.uuid4().hex[:8]}"


def build_action_envelope(
    *,
    skill: str,
    operation: str,
    actor: str,
    risk_tier: str,
    args: dict[str, Any] | None = None,
    policy_decision: dict[str, Any] | str | None = None,
    goal: str | None = None,
    action_type: str | None = None,
    approval_id: str | None = None,
    evidence: list[str] | None = None,
    expected_outcome: str | None = None,
    rollback: str | None = None,
    notification: str | None = None,
    post_action_metric: str | None = None,
    trace_id: str | None = None,
) -> ActionEnvelope:
    decision_label, reason, requires_approval, autonomy_level = _normalize_policy_decision(policy_decision)
    return ActionEnvelope(
        goal=goal or "unspecified",
        action_type=action_type or f"{skill}.{operation}",
        skill=skill,
        operation=operation,
        actor=actor,
        risk_tier=risk_tier,
        policy_decision=decision_label,
        policy_reason=reason,
        autonomy_level=autonomy_level,
        requires_approval=requires_approval,
        evidence=list(evidence or []),
        inputs_redacted=redact_inputs(args or {}),
        expected_outcome=expected_outcome or "Execute the requested operation and record proof.",
        rollback=rollback or "No automatic rollback declared; inspect proof and artifacts.",
        notification=notification or _default_notification(risk_tier),
        post_action_metric=post_action_metric or "action_ok",
        trace_id=trace_id or new_trace_id(skill, operation),
        approval_id=approval_id,
        created_at=datetime.now().isoformat(),
    )


def write_action_proof(envelope: ActionEnvelope, result: dict[str, Any]) -> str:
    """Write a durable proof JSON artifact and return its path."""
    date_dir = PROOF_DIR / datetime.now().strftime("%Y%m%d")
    date_dir.mkdir(parents=True, exist_ok=True)
    path = date_dir / f"{_safe_filename(envelope.trace_id)}.json"
    envelope.proof_path = str(path)
    payload = {
        "action_envelope": envelope.to_dict(),
        "result": _proof_result(result),
        "written_at": datetime.now().isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2, default=str))
    return str(path)


def redact_inputs(value: Any, *, key: str = "") -> Any:
    """Recursively redact secrets and personal contact details while preserving shape."""
    if isinstance(value, dict):
        return {str(k): redact_inputs(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_inputs(v, key=key) for v in value[:50]]
    if isinstance(value, tuple):
        return [redact_inputs(v, key=key) for v in value[:50]]
    if isinstance(value, str):
        if _is_sensitive_key(key):
            return _fingerprint(value)
        scrubbed = EMAIL_RE.sub(lambda m: _fingerprint(m.group(0), label="email"), value)
        scrubbed = DIGIT_RUN_RE.sub(lambda m: _fingerprint(m.group(0), label="number"), scrubbed)
        return scrubbed[:500] + ("...[truncated]" if len(scrubbed) > 500 else "")
    if isinstance(value, (int, float, bool, type(None))):
        return value
    return str(type(value).__name__)


def _normalize_policy_decision(decision: dict[str, Any] | str | None) -> tuple[str, str, bool, str]:
    if isinstance(decision, str):
        return decision, decision, False, "unknown"
    if isinstance(decision, dict):
        label = decision.get("policy_decision")
        if not label:
            if decision.get("allow"):
                label = "allow"
            elif decision.get("requires_approval"):
                label = "queue"
            else:
                label = "deny"
        return (
            str(label),
            str(decision.get("reason", "")),
            bool(decision.get("requires_approval", False)),
            str(decision.get("autonomy_level", "unknown")),
        )
    return "allow", "direct registry invocation", False, "unknown"


def _proof_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(result.get("ok")),
        "error": result.get("error"),
        "artifacts": list(result.get("artifacts") or []),
        "has_followup": bool(result.get("followup")),
        "data_preview": redact_inputs(result.get("data")),
    }


def _default_notification(risk_tier: str) -> str:
    if risk_tier in {"high", "forbidden"}:
        return "immediate"
    if risk_tier == "medium":
        return "summary"
    return "none"


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def _fingerprint(value: Any, *, label: str = "redacted") -> str:
    text = str(value or "")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]
    return f"[{label}:{digest}]"


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)[:180]
