"""
Friday :: Communications
Outbound channels: OpenClaw message intents, optional legacy Telegram, log.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import os
import ssl
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

# SSL context — use certifi if available (handles corp CA chain issues)
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()


def _load_env() -> dict:
    env_path = Path(os.path.expanduser("~/.openclaw/.env"))
    env = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    # overlay actual environment
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "ANTHROPIC_API_KEY"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


ENV = _load_env()
TRUE_VALUES = {"1", "true", "yes", "on"}


def telegram_direct_enabled() -> bool:
    """Direct Telegram is legacy-only; OpenClaw owns Telegram by default."""
    owner = os.environ.get("OPENCLAW_TELEGRAM_OWNER", "openclaw").strip().lower()
    direct = os.environ.get("FRIDAY_TELEGRAM_DIRECT", "").strip().lower()
    return owner in {"friday", "friday-legacy"} and direct in TRUE_VALUES


def _intent_dir() -> Path:
    raw = os.environ.get(
        "OPENCLAW_MESSAGE_INTENT_DIR",
        "~/.openclaw/workspace/message_intents",
    )
    return Path(os.path.expanduser(raw))


def _hash_optional(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def _write_openclaw_intent(text: str, chat_id: str | None = None, silent: bool = False) -> str:
    """Write a local-only intent for OpenClaw to review and deliver later."""
    target_dir = _intent_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    record = {
        "schema": "openclaw.message_intent.v1",
        "created_at": now.isoformat(),
        "source": "friday",
        "channel": "telegram",
        "delivery_owner": "openclaw",
        "delivery_allowed": False,
        "reason": "telegram_single_owner_policy",
        "risk_class": "R2",
        "target": {
            "chat_id_sha256_12": _hash_optional(chat_id),
            "raw_target_stored": False,
        },
        "render": {
            "text": text[:4000],
            "parse_mode": "Markdown",
            "silent": bool(silent),
        },
    }
    path = target_dir / f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-friday-{uuid.uuid4().hex[:8]}.json"
    with open(path, "w") as f:
        json.dump(record, f, indent=2)
        f.write("\n")
    return str(path)


def telegram_push(text: str, chat_id: str | None = None, silent: bool = False) -> dict:
    """Route Telegram output through OpenClaw unless legacy direct mode is explicit."""
    if not telegram_direct_enabled():
        intent_path = _write_openclaw_intent(text, chat_id=chat_id, silent=silent)
        return {
            "ok": True,
            "delivered": False,
            "routed_to_openclaw": True,
            "intent_path": intent_path,
            "error": "telegram_direct_disabled_openclaw_single_owner",
        }

    token = ENV.get("TELEGRAM_BOT_TOKEN")
    chat = chat_id or ENV.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return {"ok": False, "error": "missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID"}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat,
        "text": text[:4000],   # Telegram limit
        "parse_mode": "Markdown",
        "disable_notification": silent,
    }
    try:
        data = urllib.parse.urlencode(payload).encode()
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as r:
            body = json.loads(r.read())
            return {"ok": body.get("ok", False), "id": body.get("result", {}).get("message_id")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def telegram_get_updates(offset: int | None = None, timeout: int = 20) -> list[dict]:
    """Long-poll for incoming messages only in explicit legacy direct mode."""
    if not telegram_direct_enabled():
        return []

    token = ENV.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return []
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    url = f"{url}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=timeout + 5, context=_SSL_CTX) as r:
            body = json.loads(r.read())
            if body.get("ok"):
                return body.get("result", [])
    except Exception:
        pass
    return []


def log_to_file(channel: str, text: str) -> None:
    """Append to ~/AI/friday/data/logs/YYYY-MM-DD.jsonl — proof-of-work."""
    from datetime import datetime
    logs = Path(os.path.expanduser("~/AI/friday/data/logs"))
    logs.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    with open(logs / f"{today}.jsonl", "a") as f:
        f.write(json.dumps({
            "ts": datetime.now().isoformat(),
            "channel": channel,
            "text": text[:4000],
        }) + "\n")


if __name__ == "__main__":
    r = telegram_push("Friday online. Standing by. 🤖")
    print(r)
