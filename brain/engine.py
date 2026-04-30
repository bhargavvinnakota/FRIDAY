"""
Friday :: Reasoning Engine
Multi-backend router: Ollama (local default) → Claude (cloud fallback).
Zero-waste: always tries local first unless complexity demands cloud.

Ollama via HTTP: http://localhost:11434/api/chat
Claude via Anthropic SDK (pip install anthropic) or raw HTTPS.
"""
from __future__ import annotations
import json
import os
import ssl
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()

FRIDAY_ROOT = Path(os.path.expanduser("~/AI/friday"))
CONFIG_PATH = FRIDAY_ROOT / "config" / "friday.yaml"


def load_config() -> dict:
    if yaml is None or not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f) or {}


class OllamaEngine:
    """Local Ollama backend. Default for every query (zero-waste rule)."""

    def __init__(self, host: str, model: str, temperature: float = 0.4):
        self.host = host.rstrip("/")
        self.model = model
        self.temperature = temperature

    def generate(self, system: str, user: str, history: list[dict] | None = None,
                 temperature: float | None = None, images: list[str] | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        if history:
            for h in history:
                if h.get("role") in ("user", "assistant"):
                    messages.append({"role": h["role"], "content": h["content"]})
        
        user_msg = {"role": "user", "content": user}
        if images:
            # images should be a list of base64 strings
            user_msg["images"] = images
        messages.append(user_msg)

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature or self.temperature},
        }
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read())
            return data.get("message", {}).get("content", "").strip()

    def health(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.host}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as r:
                return r.status == 200
        except Exception:
            return False


class ClaudeEngine:
    """Anthropic Claude backend. Used for complex reasoning, code, strategy."""

    def __init__(self, model: str, max_tokens: int = 2000, temperature: float = 0.5):
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    def generate(self, system: str, user: str, history: list[dict] | None = None,
                 temperature: float | None = None) -> str:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        messages = []
        if history:
            for h in history:
                if h.get("role") in ("user", "assistant"):
                    messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": user})

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": temperature or self.temperature,
            "system": system,
            "messages": messages,
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req, timeout=120, context=_SSL_CTX) as r:
            data = json.loads(r.read())
            blocks = data.get("content", [])
            text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
            return text.strip()


class MultiEngine:
    """Router. Tries local (Ollama) first, escalates to Claude if needed."""

    def __init__(self, config: dict | None = None):
        cfg = config or load_config()
        eng_cfg = cfg.get("engines", {})
        self.triggers = [t.lower() for t in eng_cfg.get("escalation_triggers", [])]

        o = eng_cfg.get("ollama", {})
        self.ollama = OllamaEngine(
            host=o.get("host", "http://localhost:11434"),
            model=o.get("model", "llama3.2:latest"),
            temperature=o.get("temperature", 0.4),
        )
        self.ollama_heavy_model = o.get("model_heavy", "gemma3:4b")

        c = eng_cfg.get("claude", {})
        self.claude = ClaudeEngine(
            model=c.get("model", "claude-sonnet-4-6"),
            max_tokens=c.get("max_tokens", 2000),
            temperature=c.get("temperature", 0.5),
        )
        self.claude_heavy_model = c.get("model_heavy", "claude-opus-4-7")

    def _should_escalate(self, user_input: str) -> bool:
        low = user_input.lower()
        return any(t in low for t in self.triggers)

    def _try_ollama(self, system: str, user: str, history, heavy: bool, images: list[str] | None = None) -> tuple[str, str]:
        model = self.ollama_heavy_model if heavy else self.ollama.model
        saved = self.ollama.model
        try:
            self.ollama.model = model
            return self.ollama.generate(system, user, history, images=images), f"ollama:{model}"
        finally:
            self.ollama.model = saved

    def _try_claude(self, system: str, user: str, history, heavy: bool, images: list[str] | None = None) -> tuple[str, str]:
        # Note: Current ClaudeEngine implementation doesn't use images yet, 
        # but we add it to the signature for future-proofing and consistency.
        model = self.claude_heavy_model if heavy else self.claude.model
        saved = self.claude.model
        try:
            self.claude.model = model
            return self.claude.generate(system, user, history), f"claude:{model}"
        finally:
            self.claude.model = saved

    def ask(self, system: str, user: str, history: list[dict] | None = None,
            force: str | None = None, heavy: bool = False, images: list[str] | None = None) -> tuple[str, str]:
        """
        Returns (response_text, engine_used).
        force: "ollama" | "claude" | None (auto-route)
        heavy: use the heavier model (gemma4:26b / opus)
        images: list of base64 encoded strings for vision tasks

        Routing policy (zero-waste):
          1. If force=claude, go Claude directly.
          2. Otherwise ALWAYS try Ollama first (don't pre-check health — just attempt).
          3. If Ollama throws AND claude has API key AND not force=ollama → fall to Claude.
          4. If both fail, return error string (never raise).
        """
        # Forced Claude
        if force == "claude":
            try:
                return self._try_claude(system, user, history, heavy, images=images)
            except Exception as e:
                return f"[claude error: {e}]", "claude:error"

        # Ollama first (always — free, local, default)
        ollama_err: Exception | None = None
        try:
            return self._try_ollama(system, user, history, heavy, images=images)
        except Exception as e:
            ollama_err = e
            if force == "ollama":
                return f"[ollama error: {ollama_err}]", "ollama:error"

        # Fall through to Claude only if API key exists
        if not self.claude.api_key:
            return (f"[ollama failed ({ollama_err}); no ANTHROPIC_API_KEY for fallback]",
                    "no_fallback")
        try:
            return self._try_claude(system, user, history, heavy, images=images)
        except Exception as e:
            return f"[both engines failed. ollama: {ollama_err}; claude: {e}]", "error"


if __name__ == "__main__":
    from .personality import system_prompt
    eng = MultiEngine()
    resp, used = eng.ask(system_prompt(), "Status check. One line.")
    print(f"[{used}] {resp}")
