"""
Friday :: Razorpay Action Layer
Safe wrappers around Razorpay's REST APIs using stdlib HTTP.

Design notes:
  - Credentials are read from env or ~/.openclaw/.env.
  - All functions return dicts; they do not raise.
  - Create operations are exposed here, but higher layers decide on dry-run,
    approvals, and audit persistence.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

try:
    import certifi

    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()


BASE_URL = "https://api.razorpay.com/v1"
TIMEOUT = 20
UA = "Friday/2.0 (Razorpay Integration)"


def status(mode: str = "") -> dict[str, Any]:
    resolved_mode = _resolve_mode(mode)
    key_id = _credential("RAZORPAY_KEY_ID", resolved_mode)
    key_secret = _credential("RAZORPAY_KEY_SECRET", resolved_mode)
    webhook_secret = _credential("RAZORPAY_WEBHOOK_SECRET", resolved_mode)
    return {
        "ok": True,
        "mode": resolved_mode,
        "base_url": BASE_URL,
        "configured": bool(key_id and key_secret),
        "key_id_present": bool(key_id),
        "key_secret_present": bool(key_secret),
        "webhook_secret_present": bool(webhook_secret),
        "key_id_hint": _mask(key_id),
    }


def health(mode: str = "") -> dict[str, Any]:
    st = status(mode)
    if not st["configured"]:
        return {
            **st,
            "ok": False,
            "probe": "payments",
            "error": "Razorpay credentials are not configured.",
        }
    probe = _request_json("GET", "/payments", query={"count": 1}, mode=st["mode"])
    if not probe["ok"]:
        return {
            **st,
            "ok": False,
            "probe": "payments",
            "http_status": probe.get("http_status"),
            "error": probe.get("error", "probe failed"),
            "details": probe.get("details"),
        }
    items = _collection_items(probe.get("data"))
    return {
        **st,
        "ok": True,
        "probe": "payments",
        "count": len(items),
        "first_id": items[0].get("id") if items else None,
    }


def fetch_payments(
    count: int = 10,
    skip: int = 0,
    from_ts: int | None = None,
    to_ts: int | None = None,
    mode: str = "",
) -> dict[str, Any]:
    return _fetch_collection(
        "/payments",
        {"count": count, "skip": skip, "from": from_ts, "to": to_ts},
        mode=mode,
    )


def fetch_orders(
    count: int = 10,
    skip: int = 0,
    from_ts: int | None = None,
    to_ts: int | None = None,
    mode: str = "",
) -> dict[str, Any]:
    return _fetch_collection(
        "/orders",
        {"count": count, "skip": skip, "from": from_ts, "to": to_ts},
        mode=mode,
    )


def fetch_payment_links(
    count: int = 10,
    skip: int = 0,
    from_ts: int | None = None,
    to_ts: int | None = None,
    mode: str = "",
) -> dict[str, Any]:
    return _fetch_collection(
        "/payment_links",
        {"count": count, "skip": skip, "from": from_ts, "to": to_ts},
        mode=mode,
    )


def fetch_subscriptions(
    count: int = 10,
    skip: int = 0,
    mode: str = "",
) -> dict[str, Any]:
    return _fetch_collection(
        "/subscriptions",
        {"count": count, "skip": skip},
        mode=mode,
    )


def create_payment_link(payload: dict[str, Any], mode: str = "") -> dict[str, Any]:
    return _create("/payment_links", payload, mode=mode)


def create_order(payload: dict[str, Any], mode: str = "") -> dict[str, Any]:
    return _create("/orders", payload, mode=mode)


def create_subscription(payload: dict[str, Any], mode: str = "") -> dict[str, Any]:
    return _create("/subscriptions", payload, mode=mode)


def verify_payment_signature(
    order_id: str,
    payment_id: str,
    signature: str,
    key_secret: str = "",
    mode: str = "",
) -> dict[str, Any]:
    secret = key_secret or _credential("RAZORPAY_KEY_SECRET", _resolve_mode(mode))
    if not secret:
        return {"ok": False, "valid": False, "error": "Razorpay key secret is not configured."}
    message = f"{order_id}|{payment_id}"
    expected = _hmac_hex(secret, message)
    return {
        "ok": True,
        "valid": hmac.compare_digest(expected, signature or ""),
        "mode": _resolve_mode(mode),
        "message": message,
    }


def verify_webhook_signature(
    raw_body: str,
    signature: str,
    webhook_secret: str = "",
    mode: str = "",
) -> dict[str, Any]:
    secret = webhook_secret or _credential("RAZORPAY_WEBHOOK_SECRET", _resolve_mode(mode))
    if not secret:
        return {"ok": False, "valid": False, "error": "Razorpay webhook secret is not configured."}
    expected = _hmac_hex(secret, raw_body or "")
    return {
        "ok": True,
        "valid": hmac.compare_digest(expected, signature or ""),
        "mode": _resolve_mode(mode),
        "body_sha256": hashlib.sha256((raw_body or "").encode("utf-8")).hexdigest(),
    }


def _fetch_collection(path: str, query: dict[str, Any], mode: str = "") -> dict[str, Any]:
    st = status(mode)
    if not st["configured"]:
        return {**st, "ok": False, "items": [], "error": "Razorpay credentials are not configured."}
    response = _request_json("GET", path, query=query, mode=st["mode"])
    if not response["ok"]:
        return {
            **st,
            "ok": False,
            "items": [],
            "http_status": response.get("http_status"),
            "error": response.get("error", "request failed"),
            "details": response.get("details"),
        }
    data = response.get("data") or {}
    return {
        **st,
        "ok": True,
        "count": data.get("count", 0),
        "items": _collection_items(data),
        "entity": data.get("entity", "collection"),
    }


def _create(path: str, payload: dict[str, Any], mode: str = "") -> dict[str, Any]:
    st = status(mode)
    if not st["configured"]:
        return {**st, "ok": False, "error": "Razorpay credentials are not configured."}
    response = _request_json("POST", path, payload=payload, mode=st["mode"])
    if not response["ok"]:
        return {
            **st,
            "ok": False,
            "http_status": response.get("http_status"),
            "error": response.get("error", "request failed"),
            "details": response.get("details"),
        }
    data = response.get("data") or {}
    return {
        **st,
        "ok": True,
        "entity": data,
        "entity_type": data.get("entity"),
        "id": data.get("id"),
        "status_value": data.get("status"),
    }


def _request_json(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
    mode: str = "",
) -> dict[str, Any]:
    resolved_mode = _resolve_mode(mode)
    key_id = _credential("RAZORPAY_KEY_ID", resolved_mode)
    key_secret = _credential("RAZORPAY_KEY_SECRET", resolved_mode)
    if not key_id or not key_secret:
        return {"ok": False, "error": "missing credentials", "mode": resolved_mode}

    url = BASE_URL.rstrip("/") + "/" + path.strip("/")
    clean_query = {k: v for k, v in (query or {}).items() if v not in (None, "", [])}
    if clean_query:
        url += "?" + urllib.parse.urlencode(clean_query)

    headers = {
        "User-Agent": UA,
        "Accept": "application/json",
        "Authorization": "Basic " + _basic_auth(key_id, key_secret),
    }
    data: bytes | None = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL_CTX) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed = _json_loads(body)
            return {
                "ok": True,
                "mode": resolved_mode,
                "http_status": resp.status,
                "data": parsed,
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        parsed = _json_loads(body)
        return {
            "ok": False,
            "mode": resolved_mode,
            "http_status": e.code,
            "error": _extract_error(parsed, fallback=str(e)),
            "details": parsed,
        }
    except Exception as e:
        return {
            "ok": False,
            "mode": resolved_mode,
            "error": f"{type(e).__name__}: {e}",
        }


def _collection_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        items = data.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def _extract_error(data: Any, fallback: str = "") -> str:
    if isinstance(data, dict):
        if isinstance(data.get("error"), dict):
            err = data["error"]
            desc = err.get("description") or err.get("reason") or err.get("code")
            if desc:
                return str(desc)
        desc = data.get("description") or data.get("message")
        if desc:
            return str(desc)
    return fallback or "request failed"


def _basic_auth(key_id: str, key_secret: str) -> str:
    raw = f"{key_id}:{key_secret}".encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def _hmac_hex(secret: str, message: str) -> str:
    return hmac.new(secret.encode("utf-8"), (message or "").encode("utf-8"), hashlib.sha256).hexdigest()


def _resolve_mode(mode: str = "") -> str:
    raw = (mode or _env_get("RAZORPAY_MODE") or "test").strip().lower()
    return raw if raw in {"test", "live"} else "test"


def _credential(base: str, mode: str) -> str | None:
    mode = _resolve_mode(mode)
    specific = _env_get(f"{base}_{mode.upper()}")
    generic = _env_get(base)
    value = specific or generic
    return value.strip() if isinstance(value, str) and value.strip() else None


def _env_get(key: str) -> str | None:
    return os.environ.get(key) or _env_file_get(key)


def _env_file_get(key: str) -> str | None:
    env_file = Path(os.path.expanduser("~/.openclaw/.env"))
    if not env_file.exists():
        return None
    try:
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    except Exception:
        return None
    return None


def _json_loads(raw: str) -> Any:
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw[:1200]}


def _mask(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:6] + "..." + value[-4:]
