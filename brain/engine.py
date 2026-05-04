"""
Friday :: Reasoning Engine
Multi-backend router: OpenRouter (Primary) → Gemini (Backup) → Ollama (Fallback).
Zero-waste: offloads to cloud for speed and thermal health.
"""
from __future__ import annotations
import json
import os
import ssl
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

# Load .env
FRIDAY_ROOT = Path(os.path.expanduser("~/AI/friday"))
load_dotenv(FRIDAY_ROOT / ".env")

from google import genai
from google.genai import types

class OpenRouterEngine:
    """OpenRouter backend for ultra-fast, free-model routing."""
    def __init__(self, api_key: str, model: str = "google/gemini-2.0-flash-001"):
        self.api_key = api_key
        self.model = model

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
                "stream": stream
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
        
        # We'll use Gemini-2.0-Flash on OpenRouter as primary (often free/cheap)
        self.openrouter = OpenRouterEngine(self.or_key) if self.or_key else None
        
        self._client = None # Gemini native client
        self.gemini_disabled = False

    def _ensure_gemini(self):
        if self._client is None and self.gemini_key:
            self._client = genai.Client(api_key=self.gemini_key)

    def ask(self, system: str, user: str, history: list[dict] | None = None, stream: bool = False) -> Any:
        # 1. Try OpenRouter First (Fastest)
        if self.openrouter:
            try:
                if stream:
                    raw_resp = self.openrouter.generate(system, user, history, stream=True)
                    def or_token_generator():
                        for line in raw_resp:
                            if line:
                                try:
                                    chunk = json.loads(line.decode().replace("data: ", ""))
                                    token = chunk["choices"][0]["delta"].get("content", "")
                                    if token: yield token
                                except: continue
                    return or_token_generator()
                return self.openrouter.generate(system, user, history), "openrouter"
            except Exception as e:
                print(f"[Engine] OpenRouter failed: {e}")

        # 2. Try Gemini Native
        if self.gemini_key and not self.gemini_disabled:
            try:
                self._ensure_gemini()
                contents = []
                if history:
                    for h in history:
                        role = "user" if h.get("role") == "user" else "model"
                        contents.append(types.Content(role=role, parts=[types.Part(text=h["content"])]))
                contents.append(types.Content(role="user", parts=[types.Part(text=user)]))
                
                config = types.GenerateContentConfig(system_instruction=system, temperature=0.7)

                if stream:
                    raw_resp = self._client.models.generate_content_stream(model="gemini-2.0-flash", contents=contents, config=config)
                    def gemini_gen():
                        for chunk in raw_resp:
                            if chunk.text: yield chunk.text
                    return gemini_gen()
                
                resp = self._client.models.generate_content(model="gemini-2.0-flash", contents=contents, config=config)
                return resp.text.strip(), "gemini"
            except Exception as e:
                if "429" in str(e): self.gemini_disabled = True
                print(f"[Engine] Gemini failed: {e}")

        # 3. Last Resort: Emergency Local Fail-safe
        return "System logic currently restricted. Please check uplink.", "fail"

if __name__ == "__main__":
    eng = MultiEngine()
    print(eng.ask("You are Friday.", "Hello?"))
