"""
Friday :: Researcher Agent
Turns a topic into a grounded, cited intelligence report.

Pipeline:
  1. Generate 3-5 diverse search queries from the topic (LLM)
  2. Run searches in parallel (DDG / Brave / Tavily depending on what's wired)
  3. Pull top-N unique URLs, fetch text
  4. Chunk + pass source texts to synthesizer LLM
  5. Output: structured report with inline citations [1][2]...

Works keyless via DuckDuckGo + Wikipedia + News RSS.
Upgrades to Brave/Tavily automatically if API keys are present.
"""
from __future__ import annotations
import concurrent.futures
import json
import re
from datetime import datetime
from typing import Any

from .base import Agent, AgentResult
from friday.actions import web, news


class Researcher(Agent):
    name = "researcher"
    role = "Investigates topics via web + news, produces cited reports."
    system_prompt = """You are Friday's Researcher agent.

Your job: turn a topic into a concise, grounded intelligence briefing.

RULES:
- Use ONLY the provided source material. Never invent facts, numbers, or quotes.
- When you use a fact, cite its source as [N] where N is the source index.
- If sources disagree, say so. If sources are thin, say "coverage is thin" — don't pad.
- Output must be specific: numbers, dates, names, places — not vibes.
- 4-section format: (1) TL;DR (3 lines), (2) Key developments (bullets),
  (3) What it means for Bhargav (operator perspective — agency, trading, AuditMind),
  (4) Sources (list URLs).
- If the question is about India / Hyderabad, weight those sources heavier.
- Skip filler. No "Great question", no "In conclusion", no "I hope".
"""

    def run(self, topic: str, depth: str = "medium", max_sources: int = 8) -> AgentResult:
        """
        depth: quick (3 queries, 5 sources) | medium (4 queries, 8 sources)
             | deep (6 queries, 12 sources, deeper fetch)
        """
        t0 = datetime.now()
        quick = depth == "quick"
        deep = depth == "deep"

        # 1. Generate search queries
        try:
            queries = self._generate_queries(topic, n=3 if quick else (6 if deep else 4))
        except Exception as e:
            return AgentResult(ok=False, error=f"query-gen failed: {e}")

        # 2. Parallel search + news
        search_results = web.multi_search(queries, per_query_count=5 if quick else 6)
        news_results = news.topic_pulse(topic, limit_per_source=4 if quick else 6)

        # 3. Build candidate source list — dedupe by URL, rank by rough relevance
        candidates = []
        seen = set()
        for item in search_results.get("results", []):
            if item["url"] not in seen:
                seen.add(item["url"])
                candidates.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("snippet", ""),
                    "source": item.get("source", ""),
                    "type": "web",
                })
        for item in news_results.get("items", []):
            if item["url"] not in seen:
                seen.add(item["url"])
                candidates.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": (item.get("summary") or "")[:300],
                    "source": item.get("source", ""),
                    "type": "news",
                    "score": item.get("score"),
                })
        # Cap to max_sources — prioritize news + snippets-available
        candidates = self._rank(candidates, topic)[:max_sources]

        # 4. Fetch full text for top candidates (parallel, capped)
        fetch_n = 3 if quick else (6 if deep else 5)
        to_fetch = [c for c in candidates if c["type"] == "web"][:fetch_n]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(web.fetch_url, c["url"], max_chars=3500): c for c in to_fetch}
            for fut in concurrent.futures.as_completed(futures, timeout=30):
                c = futures[fut]
                try:
                    r = fut.result()
                    if r.get("ok"):
                        c["full_text"] = r["text"][:3500]
                except Exception:
                    c["full_text"] = ""

        # 5. Synthesize using LLM
        report = self._synthesize(topic, candidates)

        return AgentResult(
            ok=True,
            data={
                "topic": topic,
                "queries": queries,
                "sources_found": len(candidates),
                "sources": [{"title": c["title"], "url": c["url"], "source": c["source"]}
                            for c in candidates],
                "report": report["text"],
                "duration_s": (datetime.now() - t0).total_seconds(),
            },
            reasoning=f"generated {len(queries)} queries, found {len(candidates)} sources, "
                      f"fetched {sum(1 for c in candidates if c.get('full_text'))} full pages",
            engine_used=report["engine"],
        )

    # -- helpers --
    def _generate_queries(self, topic: str, n: int = 4) -> list[str]:
        """Ask the LLM to produce diverse search queries for the topic."""
        prompt = f"""Topic: "{topic}"

Generate exactly {n} distinct web search queries that together give comprehensive coverage of this topic.
Mix angles: recent news, expert analysis, contrarian views, specifics/numbers, practical implications.

Output format: one query per line, no numbering, no quotes, no explanation."""
        raw, engine = self._ask(prompt, temperature=0.5)
        queries = [ln.strip().lstrip("-*1234567890. ").strip().strip('"').strip("'")
                   for ln in raw.splitlines()]
        queries = [q for q in queries if q and len(q) > 5][:n]
        # Fallback: just use the topic
        if not queries:
            queries = [topic, f"{topic} latest news", f"{topic} analysis 2026"]
        return queries[:n]

    def _rank(self, candidates: list[dict], topic: str) -> list[dict]:
        """Rough relevance ranking."""
        topic_words = set(re.findall(r"\w+", topic.lower()))
        def score(c):
            s = 0.0
            title_words = set(re.findall(r"\w+", c.get("title", "").lower()))
            s += len(topic_words & title_words) * 3
            snip_words = set(re.findall(r"\w+", c.get("snippet", "").lower()))
            s += len(topic_words & snip_words) * 1
            # News items with scores get a bump
            if c.get("type") == "news" and c.get("score"):
                s += min(c["score"] / 100, 2)
            # Prefer diverse sources
            return s
        return sorted(candidates, key=score, reverse=True)

    def _synthesize(self, topic: str, candidates: list[dict]) -> dict:
        """Feed sources to LLM, get a cited report back."""
        source_blocks = []
        for i, c in enumerate(candidates, 1):
            text = c.get("full_text") or c.get("snippet", "")
            source_blocks.append(
                f"[{i}] {c['title']} — {c.get('source', '?')}\n"
                f"URL: {c['url']}\n"
                f"Excerpt: {text[:1500]}\n"
            )
        sources_str = "\n---\n".join(source_blocks)

        prompt = f"""TOPIC: {topic}

SOURCES ({len(candidates)} total):

{sources_str}

Produce the 4-section briefing per the RULES in your system prompt.
Use [N] citations wherever you reference a source.
Max 400 words total (compact, high-density).
"""
        # Prefer Claude for synthesis (better grounded generation on small data)
        force = "claude" if self.engine.claude.api_key else None
        text, engine = self._ask(prompt, heavy=True, force=force, temperature=0.3)
        return {"text": text, "engine": engine}
