"""
Friday :: Reasoning Engine
Multi-backend router: Ollama (Local) → OpenRouter (Primary Cloud) → Gemini (Native Backup).
Zero-waste: offloads to local for speed/privacy when possible.
"""
from __future__ import annotations
import json
import os
import ssl
import urllib.request
import urllib.error
import time
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

# Load .env
FRIDAY_ROOT = Path(os.path.expanduser("~/AI/friday"))
load_dotenv(FRIDAY_ROOT / ".env")

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

class OllamaEngine:
    """Local Ollama backend. Best for ground-truth synthesis and low-risk tasks."""
    def __init__(self, model: str = "gemma3:4b", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host.rstrip("/")
        self.temperature = 0.4

    def health(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=2) as r:
                return r.getcode() == 200
        except: return False

    def generate(self, system: str, user: str, history: list[dict] | None = None, 
                 stream: bool = False, temperature: float | None = None) -> Any:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        if history:
            for h in history:
                messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": user})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {"temperature": temperature or self.temperature}
        }
        
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}
        )
        
        if stream:
            return urllib.request.urlopen(req, timeout=30)
        
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            return data["message"]["content"].strip()

class OpenRouterEngine:
    """OpenRouter backend for ultra-fast, high-quality models."""
    def __init__(self, api_key: str, model: str = "google/gemini-2.0-flash-001"):
        self.api_key = api_key
        self.model = model
        self.temperature = 0.7

    def generate(self, system: str, user: str, history: list[dict] | None = None, stream: bool = False) -> Any:
        messages = [{"role": "system", "content": system}]
        if history:
            for h in history:
                messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": user})

        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps({
                "model": self.model,
                "messages": messages,
                "stream": stream,
                "temperature": self.temperature
            }).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://friday.ai",
                "X-Title": "Friday HUD"
            }
        )
        
        if stream:
            return urllib.request.urlopen(req, timeout=30)
        
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            return data["choices"][0]["message"]["content"].strip()

class MultiEngine:
    def __init__(self):
        self.or_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")
        
        # Internal Engines
        self.ollama = OllamaEngine(model="gemma3:4b")
        self.openrouter = OpenRouterEngine(self.or_key) if self.or_key else None
        
        # For legacy compatibility
        self.claude = self.openrouter # Redirect claude calls to OpenRouter
        
        self._client = None
        self.gemini_disabled = False

    def _ensure_gemini(self):
        if self._client is None and self.gemini_key and genai:
            self._client = genai.Client(api_key=self.gemini_key)

    def ask(self, system: str, user: str, history: list[dict] | None = None, 
            stream: bool = False, force: str | None = None, heavy: bool = False, 
            images: list[str] | None = None, temperature: float | None = None) -> Any:
        
        # 1. Handle Forced Engine
        if force == "ollama":
            return self._ask_ollama(system, user, history, stream, temperature), "ollama"
        if force in ("openrouter", "claude"):
            if self.openrouter:
                return self._ask_openrouter(system, user, history, stream, temperature, images=images), "openrouter"
        if force == "gemini":
            return self._ask_gemini_native(system, user, history, stream, temperature, images=images), "gemini"

        # 2. Heavy Model Routing (Always Cloud)
        if heavy:
            if self.openrouter:
                return self._ask_openrouter(system, user, history, stream, temperature, images=images), "openrouter"
            return self._ask_gemini_native(system, user, history, stream, temperature, images=images), "gemini"

        # 3. Default Routing Policy (Zero-Waste)
        # Images require Cloud (mostly)
        if images:
            if self.openrouter:
                return self._ask_openrouter(system, user, history, stream, temperature, images=images), "openrouter"
            return self._ask_gemini_native(system, user, history, stream, temperature, images=images), "gemini"

        # Try local first if healthy
        if self.ollama.health():
            try:
                return self._ask_ollama(system, user, history, stream, temperature), "ollama"
            except: pass
            
        # Fallback to OpenRouter
        if self.openrouter:
            try:
                return self._ask_openrouter(system, user, history, stream, temperature), "openrouter"
            except: pass
            
        # Fallback to Gemini Native
        return self._ask_gemini_native(system, user, history, stream, temperature), "gemini"

    def _ask_ollama(self, system, user, history, stream, temperature):
        if stream:
            raw = self.ollama.generate(system, user, history, stream=True, temperature=temperature)
            def gen():
                for line in raw:
                    if line:
                        chunk = json.loads(line.decode())
                        token = chunk.get("message", {}).get("content", "")
                        if token: yield token
            return gen()
        return self.ollama.generate(system, user, history, temperature=temperature)

    def _ask_openrouter(self, system, user, history, stream, temperature, images=None):
        # Temporarily override temperature if provided
        old_temp = self.openrouter.temperature
        if temperature is not None:
            self.openrouter.temperature = temperature
        
        try:
            messages = [{"role": "system", "content": system}]
            if history:
                for h in history:
                    messages.append({"role": h["role"], "content": h["content"]})
            
            user_content = [{"type": "text", "text": user}]
            if images:
                import base64
                for img_path in images:
                    with open(img_path, "rb") as f:
                        b64_img = base64.b64encode(f.read()).decode()
                        user_content.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64_img}"}
                        })
            messages.append({"role": "user", "content": user_content})

            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps({
                    "model": self.openrouter.model,
                    "messages": messages,
                    "stream": stream,
                    "temperature": self.openrouter.temperature
                }).encode(),
                headers={
                    "Authorization": f"Bearer {self.openrouter.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://friday.ai",
                    "X-Title": "Friday HUD"
                }
            )

            if stream:
                raw = urllib.request.urlopen(req, timeout=30)
                def gen():
                    for line in raw:
                        line = line.decode().strip()
                        if line.startswith("data: "):
                            if line == "data: [DONE]": break
                            try:
                                chunk = json.loads(line[6:])
                                token = chunk["choices"][0]["delta"].get("content", "")
                                if token: yield token
                            except: continue
                return gen()
            
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
                return data["choices"][0]["message"]["content"].strip()
        finally:
            self.openrouter.temperature = old_temp

    def _ask_gemini_native(self, system, user, history, stream, temperature, images=None):
        if not self.gemini_key or not genai:
            return "Gemini Native not configured.", "fail"
        
        try:
            self._ensure_gemini()
            contents = []
            if history:
                for h in history:
                    role = "user" if h.get("role") == "user" else "model"
                    contents.append(types.Content(role=role, parts=[types.Part(text=h["content"])]))
            
            parts = [types.Part(text=user)]
            if images:
                for img_path in images:
                    with open(img_path, "rb") as f:
                        img_data = f.read()
                        parts.append(types.Part(inline_data=types.Blob(data=img_data, mime_type="image/png")))
            
            contents.append(types.Content(role="user", parts=parts))
            
            config = types.GenerateContentConfig(system_instruction=system, temperature=temperature or 0.7)

            if stream:
                raw_resp = self._client.models.generate_content_stream(model="gemini-2.0-flash", contents=contents, config=config)
                def gemini_gen():
                    for chunk in raw_resp:
                        if chunk.text: yield chunk.text
                return gemini_gen()
            
            resp = self._client.models.generate_content(model="gemini-2.0-flash", contents=contents, config=config)
            return resp.text.strip()
        except Exception as e:
            return f"Gemini Error: {e}"

if __name__ == "__main__":
    eng = MultiEngine()
    print(eng.ask("You are Friday.", "Status check."))
