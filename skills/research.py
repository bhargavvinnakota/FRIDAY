"""
Friday :: Research Skill
Web search + doc reading + summarization.
v1.0: lightweight — DuckDuckGo HTML search (no API key needed) + local file grep.
v1.1 will wire Brave/Serper + headless browser.
"""
from __future__ import annotations
import json
import os
import re
import ssl
import urllib.parse
import urllib.request
from pathlib import Path
from html.parser import HTMLParser

from .registry import Skill, Operation, SkillResult

try:
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _CTX = ssl.create_default_context()

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"


class _DDGParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results: list[dict] = []
        self._in_result = False
        self._current = {}
        self._capture = None

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        cls = attrs_d.get("class", "")
        if tag == "a" and "result__a" in cls:
            self._current = {"url": attrs_d.get("href", "")}
            self._capture = "title"
        elif tag == "a" and "result__snippet" in cls:
            self._capture = "snippet"

    def handle_endtag(self, tag):
        if tag == "a" and self._capture in ("title", "snippet"):
            if self._capture == "snippet" and self._current:
                self.results.append(self._current)
                self._current = {}
            self._capture = None

    def handle_data(self, data):
        if self._capture == "title":
            self._current["title"] = (self._current.get("title", "") + data).strip()
        elif self._capture == "snippet" and self._current:
            self._current["snippet"] = (self._current.get("snippet", "") + data).strip()


class ResearchSkill(Skill):
    name = "research"
    description = "Web search, local doc grep, summarize findings."

    def _register_operations(self) -> None:
        self.register_op(Operation("web_search", "DuckDuckGo HTML search (top 5).",
                                   fn=self.op_web_search, risk="low"))
        self.register_op(Operation("fetch_page", "Fetch a URL's text content.",
                                   fn=self.op_fetch_page, risk="low"))
        self.register_op(Operation("local_search",
                                   "Grep a query across ~/AI/friday, ~/agency, ~/nexus-omega.",
                                   fn=self.op_local_search, risk="low"))
        self.register_op(Operation("summarize", "LLM-summarize a chunk of text.",
                                   fn=self.op_summarize, risk="low"))

    def op_web_search(self, query: str = "", limit: int = 5, **_) -> SkillResult:
        if not query:
            return SkillResult(ok=False, error="query required")
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=15, context=_CTX) as r:
                html = r.read().decode(errors="ignore")
            p = _DDGParser()
            p.feed(html)
            out = p.results[:limit]
            return SkillResult(ok=True, data={"query": query, "results": out, "count": len(out)})
        except Exception as e:
            return SkillResult(ok=False, error=str(e))

    def op_fetch_page(self, url: str = "", max_chars: int = 8000, **_) -> SkillResult:
        if not url:
            return SkillResult(ok=False, error="url required")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20, context=_CTX) as r:
                raw = r.read().decode(errors="ignore")
            # Strip HTML crudely
            text = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.DOTALL | re.I)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.I)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return SkillResult(ok=True, data={"url": url, "chars": len(text),
                                               "text": text[:max_chars]})
        except Exception as e:
            return SkillResult(ok=False, error=str(e))

    def op_local_search(self, query: str = "", limit: int = 20, **_) -> SkillResult:
        if not query:
            return SkillResult(ok=False, error="query required")
        roots = [Path(os.path.expanduser("~/AI/friday")),
                 Path(os.path.expanduser("~/agency")),
                 Path(os.path.expanduser("~/nexus-omega"))]
        matches = []
        q_low = query.lower()
        for root in roots:
            if not root.exists():
                continue
            for p in root.rglob("*"):
                if len(matches) >= limit:
                    break
                if p.is_file() and p.suffix in (".py", ".md", ".txt", ".yaml", ".yml", ".json", ".csv"):
                    try:
                        if p.stat().st_size > 2_000_000:
                            continue
                        content = p.read_text(errors="ignore")
                        if q_low in content.lower():
                            # Find line
                            for i, line in enumerate(content.splitlines(), 1):
                                if q_low in line.lower():
                                    matches.append({"path": str(p), "line": i,
                                                    "preview": line.strip()[:200]})
                                    break
                    except Exception:
                        continue
        return SkillResult(ok=True, data={"query": query, "matches": matches[:limit],
                                           "count": len(matches)})

    def op_summarize(self, text: str = "", instruction: str = "Summarize in 3 bullets.",
                     **_) -> SkillResult:
        if not text:
            return SkillResult(ok=False, error="text required")
        from friday.brain.engine import MultiEngine
        from friday.brain.personality import system_prompt
        eng = MultiEngine()
        sysp = system_prompt(task_hint="Summarize tightly. No fluff.")
        prompt = f"{instruction}\n\n---\n{text[:6000]}"
        try:
            out, used = eng.ask(sysp, prompt, force="ollama")
            return SkillResult(ok=True, data={"summary": out, "engine": used})
        except Exception as e:
            return SkillResult(ok=False, error=str(e))
