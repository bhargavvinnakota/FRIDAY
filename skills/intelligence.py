"""
Friday :: Intelligence Skill
Real-world awareness. Web search, news aggregation, cited deep research.

This skill is what makes Friday stop sounding like a shut-in.
When Bhargav asks "what's happening in the world?" the answer comes from here —
live data, cited, synthesized into operator-grade briefings.

Operations:
  - world_pulse     : snapshot across HN / Reddit / RSS / Google News (fast, broad)
  - topic_pulse     : multi-source pull on one topic (fast, focused)
  - deep_research   : full Researcher pipeline — queries, fetches, cites, reports
  - scan_web        : raw web search (brave/tavily/ddg fallback)
  - quick_brief     : under 20s — grab top signals, synthesize 4 lines

Contract: every op returns real URLs/timestamps. No hallucinations, no padding.
"""
from __future__ import annotations
from typing import Any

from .registry import Skill, Operation, SkillResult


class IntelligenceSkill(Skill):
    name = "intelligence"
    description = "Real web/news awareness. World-scan + deep cited research."

    def _register_operations(self) -> None:
        self.register_op(Operation(
            "world_pulse",
            "Snapshot of what's happening across tech/markets/AI (HN, Reddit, RSS, Google News).",
            fn=self.op_world_pulse, risk="low",
            input_schema={"limit_per_source": "int (default 6)"},
        ))
        self.register_op(Operation(
            "topic_pulse",
            "Multi-source pull on one topic (Google News + HN Algolia + Reddit search).",
            fn=self.op_topic_pulse, risk="low",
            input_schema={"topic": "str", "limit_per_source": "int"},
        ))
        self.register_op(Operation(
            "deep_research",
            "Full Researcher pipeline: generate queries → search → fetch → synthesize cited briefing.",
            fn=self.op_deep_research, risk="low",
            input_schema={"topic": "str", "depth": "quick|medium|deep"},
        ))
        self.register_op(Operation(
            "scan_web",
            "Raw web search (Brave → Tavily → Exa → DDG fallback).",
            fn=self.op_scan_web, risk="low",
            input_schema={"query": "str", "count": "int"},
        ))
        self.register_op(Operation(
            "quick_brief",
            "Sub-20-second brief on a topic — top 4-5 signals, synthesized.",
            fn=self.op_quick_brief, risk="low",
            input_schema={"topic": "str"},
        ))

    # -------------------- ops --------------------

    def op_world_pulse(self, limit_per_source: int = 6, **_) -> SkillResult:
        try:
            from friday.actions import news
            data = news.world_pulse(limit_per_source=limit_per_source)
            return SkillResult(ok=True, data=data)
        except Exception as e:
            return SkillResult(ok=False, error=f"{type(e).__name__}: {e}")

    def op_topic_pulse(self, topic: str = "", limit_per_source: int = 6, **_) -> SkillResult:
        if not topic:
            return SkillResult(ok=False, error="topic required")
        try:
            from friday.actions import news
            data = news.topic_pulse(topic, limit_per_source=limit_per_source)
            return SkillResult(ok=True, data=data)
        except Exception as e:
            return SkillResult(ok=False, error=f"{type(e).__name__}: {e}")

    def op_deep_research(self, topic: str = "", depth: str = "medium",
                         max_sources: int = 8, **_) -> SkillResult:
        if not topic:
            return SkillResult(ok=False, error="topic required")
        try:
            from friday.brain.engine import MultiEngine
            from friday.brain.agents.researcher import Researcher
            eng = MultiEngine()
            r = Researcher(eng)
            result = r.run(topic=topic, depth=depth, max_sources=max_sources)
            if not result.ok:
                return SkillResult(ok=False, error=result.error or "researcher failed")
            return SkillResult(ok=True, data=result.data)
        except Exception as e:
            return SkillResult(ok=False, error=f"{type(e).__name__}: {e}")

    def op_scan_web(self, query: str = "", count: int = 8, **_) -> SkillResult:
        if not query:
            return SkillResult(ok=False, error="query required")
        try:
            from friday.actions import web
            data = web.search(query, count=count)
            return SkillResult(ok=True, data=data)
        except Exception as e:
            return SkillResult(ok=False, error=f"{type(e).__name__}: {e}")

    def op_quick_brief(self, topic: str = "", **_) -> SkillResult:
        """Sub-20s brief: pulse + quick LLM synth. No page fetches."""
        if not topic:
            return SkillResult(ok=False, error="topic required")
        try:
            from friday.actions import news
            from friday.brain.engine import MultiEngine
            pulse = news.topic_pulse(topic, limit_per_source=4)
            items = pulse.get("items", [])[:10]
            if not items:
                return SkillResult(ok=True, data={
                    "topic": topic,
                    "brief": "Coverage is thin right now. No recent items across tracked feeds.",
                    "items": [],
                })
            source_lines = []
            for i, it in enumerate(items, 1):
                title = it.get("title", "")[:140]
                src = it.get("source", "?")
                url = it.get("url", "")
                source_lines.append(f"[{i}] {title} — {src}\n    {url}")
            sources_str = "\n".join(source_lines)

            sysp = (
                "You are Friday's intelligence analyst. Produce a tight operator brief "
                "in Friday voice: dry, specific, numbers-first. Use ONLY facts from the "
                "headlines given. Cite [N] for claims. If coverage is thin, say so. "
                "Max 5 lines. No padding, no 'in conclusion'."
            )
            user = (
                f"TOPIC: {topic}\n\nHEADLINES ({len(items)}):\n{sources_str}\n\n"
                "Produce 4-5 line brief. First line TL;DR. Then 3 bullets of signal. "
                "Cite [N] inline."
            )
            eng = MultiEngine()
            force = "claude" if eng.claude.api_key else None
            raw, engine = eng.ask(sysp, user, force=force)
            from friday.brain.orchestrator import scrub_reply
            return SkillResult(ok=True, data={
                "topic": topic,
                "brief": scrub_reply(raw),
                "engine": engine,
                "items": [{"title": it.get("title"), "url": it.get("url"),
                           "source": it.get("source")} for it in items],
            })
        except Exception as e:
            return SkillResult(ok=False, error=f"{type(e).__name__}: {e}")
