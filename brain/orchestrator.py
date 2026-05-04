"""
Friday :: Orchestrator
Hybrid routing:
  1. Deterministic keyword-triggers run tools FIRST (reliable on small local models)
  2. Tool results are injected as ground-truth context
  3. LLM synthesizes ONLY from actual data (anti-hallucination)
  4. Optional LLM tool-plan fallback for ambiguous queries

Engine policy:
  - Tool queries (ground-truth synthesis) → Ollama is fine, it's just summarizing data
  - Conversational queries → Claude if API key present (llama3.2 too small for personality)
  - Strategic/code/analysis → heavy model on escalation trigger

This design beats pure-JSON-tool-calling on 2-4B local models where hallucination is rife,
while still getting crisp personality on freeform chat.
"""
from __future__ import annotations
import json
import os
import re
from typing import Any, Callable

from .engine import MultiEngine
from .memory import Memory
from .personality import system_prompt


# Phrases that signal the model slipped into generic-chatbot mode.
# Stripped (or replaced) before the reply goes out.
_SYCOPHANT_PATTERNS = [
    r"(?i)^\s*great question[!.,]?\s*",
    r"(?i)^\s*happy to help[!.,]?\s*",
    r"(?i)^\s*i hope (this|that) helps[!.,]?\s*",
    r"(?i)^\s*i'?m (happy|glad|here) to\b[^.!?]*[.!?]\s*",
    r"(?i)^\s*as an ai[^.!?]*[.!?]\s*",
    r"(?i)^\s*thanks for\b[^.!?]*[.!?]\s*",
    r"(?i)\blet me know if[^.!?]*[.!?]\s*$",
    r"(?i)\bfeel free to\b[^.!?]*[.!?]\s*$",
    r"(?i)\bi hope (this|that) helps[!.]?\s*$",
    r"(?i)\bhope that (helps|answers).*?[.!?]\s*$"
]

# Whole-paragraph filler the small model loves to append.
# These get removed even mid-reply if they form a standalone line/paragraph.
_FILLER_PARAGRAPH_PATTERNS = [
    r"(?im)^\s*by the way[,.:][^\n]*\n?",
    r"(?im)^\s*just (a )?heads? ?up[^.!?\n]*[.!?\n]\s*",
    r"(?im)^\s*would you like[^?\n]*\??\s*",
    r"(?im)^\s*let me know if[^.!?\n]*[.!?\n]\s*",
    r"(?im)^\s*if you want[^.!?\n]*[.!?\n]\s*",
    r"(?im)^\s*anything else\??\s*",
    r"(?im)^\s*happy to (assist|help)[^\n]*\n?",
    r"(?im)^\s*coffee is waiting[^\n]*\n?",
    r"(?im)^[^.\n]*\b(cup of|another)\s+coffee\b[^\n]*\n?",
    r"(?im)^[^\n]*\byour coffee is (ready|waiting|brewed)\b[^\n]*\n?",
    r"(?im)^[^\n]*\bcoffee( is ready)?\.\s*$",
]

# Paragraph-lead words that usually signal the small model is about to
# add unsolicited bonus commentary. When a second paragraph starts with these,
# we drop the whole paragraph.
_FILLER_PARAGRAPH_LEADS = (
    "also,", "also ", "additionally", "moreover", "furthermore",
    "i'd recommend", "i would recommend", "i recommend",
    "quick reminder", "reminder:", "a quick glance",
    "note that", "note:", "one more thing",
)


def _drop_filler_paragraphs(text: str) -> str:
    """Drop trailing paragraphs that open with bonus-advice leads."""
    if "\n" not in text:
        return text
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) <= 1:
        return text
    kept = [paragraphs[0]]
    for p in paragraphs[1:]:
        low = p.strip().lower()
        if any(low.startswith(lead) for lead in _FILLER_PARAGRAPH_LEADS):
            continue  # drop
        kept.append(p)
    return "\n\n".join(kept)

_CONVERSATIONAL_HINTS = {
    # Short greetings + freeform chat — small model butchers these
    "hi", "hello", "hey", "yo", "sup", "good morning", "good evening",
    "good night", "what's up", "how are you", "how's it going",
    "thanks", "thank you", "cheers", "bye", "goodbye",
}

# Phrases that mean "go scan the world and tell me" — route to Researcher.
_WORLD_SCAN_PATTERNS = (
    "what's happening in the world", "what is happening in the world",
    "what's happening around the world", "what is happening around the world",
    "what's going on in", "what is going on in",
    "what's new in", "what is new in",
    "latest on", "latest in", "latest news",
    "news on", "news about", "news around",
    "tell me about", "what do you know about",
    "research ", "deep dive on", "deep dive into",
    "brief me on", "give me a briefing on",
    "what's the word on", "what is the word on",
    "what's trending", "what is trending",
    "happening around the world", "across the planet", "across the globe",
)

# Pure world-pulse (no specific topic) — broad scan
_WORLD_PULSE_PATTERNS = (
    "what's happening in the world", "what is happening in the world",
    "what's happening around the world", "what is happening around the world",
    "what's going on in the world", "what is going on in the world",
    "happening around the world", "across the planet", "across the globe",
    "what's trending", "what is trending",
    "what's new in the world", "world news",
)


def _extract_research_topic(query: str) -> str | None:
    """Pull the topic out of a world-query. None if it's a pure world-pulse."""
    low = query.lower().strip()
    # Pure world-pulse — no specific topic
    if any(p in low for p in _WORLD_PULSE_PATTERNS):
        return None
    # Try "latest on X", "news on X", "tell me about X", etc.
    for lead in ("latest on ", "latest in ", "news on ", "news about ",
                 "tell me about ", "what do you know about ",
                 "research ", "deep dive on ", "deep dive into ",
                 "brief me on ", "give me a briefing on ",
                 "what's going on in ", "what is going on in ",
                 "what's new in ", "what is new in ",
                 "what's the word on ", "what is the word on "):
        idx = low.find(lead)
        if idx >= 0:
            topic = query[idx + len(lead):].strip().rstrip("?.!,")
            if topic:
                return topic
    # Fallback: the whole query minus stop words
    return query.strip().rstrip("?.!,")


def _is_world_query(text: str) -> bool:
    low = text.lower()
    return any(p in low for p in _WORLD_SCAN_PATTERNS)


def _is_computer_query(text: str) -> bool:
    low = text.lower()
    return any(p in low for p in (
        "what's on my screen", "what is on my screen", "what do you see",
        "look at my desktop", "take a screenshot", "click", "type", "open safari",
        "open chrome", "open terminal", "what's running", "on my computer",
        "watch my screen", "look at my screen", "see my screen", "watch on my screen"
    ))


def _encode_image(image_path: str) -> str:
    import base64
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def scrub_reply(text: str) -> str:
    """Remove common llama-tic phrases and generic-chatbot filler."""
    if not text:
        return text
    out = text.strip()
    # Strip sycophant openers/closers
    for pat in _SYCOPHANT_PATTERNS:
        out = re.sub(pat, "", out)
    # Strip filler paragraphs (common llama trailing offers)
    for pat in _FILLER_PARAGRAPH_PATTERNS:
        out = re.sub(pat, "", out)
    # Drop bonus-advice paragraphs
    out = _drop_filler_paragraphs(out)
    # Collapse extra whitespace / redundant newlines
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"[ \t]+", " ", out)
    # Strip quote-bracketing if the whole reply is quoted
    out = out.strip().strip('"').strip("'").strip()
    # If scrubbing emptied the reply, fall back to original stripped
    return out or text.strip()


def _is_conversational(text: str) -> bool:
    low = text.strip().lower()
    if low in _CONVERSATIONAL_HINTS:
        return True
    # Short first-person / meta / world-query
    if len(low) < 80 and any(p in low for p in (
        "what do you think", "what's happening", "what is happening",
        "how do you", "tell me", "who are you", "what can you do",
        "are you there", "are you awake", "are you alive", "still there",
    )):
        return True
    return False


class Tool:
    """A callable action Friday can invoke."""

    def __init__(self, name: str, description: str, fn: Callable,
                 triggers: list[str] | None = None, requires_confirm: bool = False):
        self.name = name
        self.description = description
        self.fn = fn
        self.triggers = [t.lower() for t in (triggers or [])]
        self.requires_confirm = requires_confirm

    def matches(self, text: str) -> bool:
        low = text.lower()
        return any(t in low for t in self.triggers)

    def run(self, **kwargs) -> Any:
        return self.fn(**kwargs)


class Orchestrator:
    def __init__(self, engine: MultiEngine, memory: Memory, tools: dict[str, Tool] | None = None):
        self.engine = engine
        self.memory = memory
        self.tools: dict[str, Tool] = tools or {}

    def register(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def _tool_manifest(self) -> str:
        if not self.tools:
            return "(no tools registered)"
        return "\n".join(f"- {t.name}: {t.description}" for t in self.tools.values())

    def _plan_prompt(self, user_query: str) -> str:
        return f"""You have these tools available:

{self._tool_manifest()}

User says: "{user_query}"

Decide: do you need to call a tool, or answer from your own knowledge + memory?

If YES (tool needed), respond EXACTLY with JSON:
{{"action": "tool", "tool": "<name>", "args": {{"<k>": "<v>"}}}}

If NO (direct answer), respond EXACTLY with JSON:
{{"action": "direct"}}

Only output the JSON. No other text."""

    def _parse_plan(self, raw: str) -> dict:
        # Try to extract first JSON object from the response
        m = re.search(r'\{.*?\}', raw, re.DOTALL)
        if not m:
            return {"action": "direct"}
        try:
            return json.loads(m.group())
        except Exception:
            return {"action": "direct"}

    def _match_tool(self, query: str) -> Tool | None:
        """Deterministic trigger matching — reliable even on small models."""
        for tool in self.tools.values():
            if tool.matches(query):
                return tool
        return None

    def _world_query(self, user_query: str) -> dict | None:
        """
        Dispatch a world/research query to the Researcher agent (or world_pulse
        for broad 'what's happening' queries). Returns dict with 'reply' +
        'engine' + 'meta', or None on failure (caller falls back to normal path).
        """
        try:
            topic = _extract_research_topic(user_query)
            # Pure world-pulse: no specific topic — use fast world_pulse + synth
            if topic is None or len(topic) < 3:
                from friday.actions import news
                from friday.brain.personality import system_prompt as _sp
                pulse = news.world_pulse(limit_per_source=5)
                items = (pulse.get("flat") or [])[:15]
                if not items:
                    return {"reply": "Feeds are quiet. Nothing moving right now.",
                            "engine": "none", "meta": {"items": 0}}
                lines = []
                for i, it in enumerate(items, 1):
                    title = (it.get("title") or "")[:140]
                    src = it.get("source", "?")
                    lines.append(f"[{i}] {title} — {src}")
                headlines = "\n".join(lines)
                sysp = (
                    "You are Friday, Bhargav's operator AI. You just pulled live "
                    "headlines across tech, AI, markets, and world news. Produce a "
                    "tight world-pulse briefing for Bhargav.\n\n"
                    "RULES:\n"
                    "- Use ONLY the headlines given. Never invent stories or numbers.\n"
                    "- Cite [N] inline when you reference an item.\n"
                    "- 6-8 lines total. Dry, specific, operator voice. No filler.\n"
                    "- Structure: 1 line TL;DR, 3-5 bullets of signal, 1 line "
                    "'what it means for you' (agency / trading / AI builder lens)."
                )
                user = f"HEADLINES ({len(items)}):\n{headlines}\n\nWrite the briefing."
                force = "claude" if self.engine.claude.api_key else None
                raw, engine = self.engine.ask(sysp, user, force=force)
                reply = scrub_reply(raw)
                return {"reply": reply, "engine": engine,
                        "meta": {"mode": "world_pulse", "items": len(items)}}

            # Specific topic: delegate to Researcher
            from friday.brain.agents.researcher import Researcher
            r = Researcher(self.engine)
            # Heuristic depth — "deep dive" / "research" → medium, else quick
            low = user_query.lower()
            depth = "medium" if any(k in low for k in ("deep dive", "research", "brief me")) else "quick"
            result = r.run(topic=topic, depth=depth, max_sources=8)
            if not result.ok:
                return None  # fall back to normal LLM path
            data = result.data or {}
            reply = data.get("report") or "Coverage is thin. Try a more specific topic."
            return {
                "reply": reply,
                "engine": result.engine_used or "researcher",
                "meta": {
                    "mode": "deep_research",
                    "topic": topic,
                    "depth": depth,
                    "sources": data.get("sources_found", 0),
                    "duration_s": data.get("duration_s"),
                },
            }
        except Exception as e:
            # Don't crash the whole reply path — fall back to normal flow.
            self.memory.log_event("world_query_error", {"error": str(e)[:300]})
            return None

    def respond(self, user_query: str, use_tools: bool = True, heavy: bool = False,
                force_engine: str | None = None) -> dict:
        """
        Main entry point. Returns:
          {"reply": str, "engine": str, "tool_used": str | None, "tool_result": Any | None}

        Routing:
          - Tool query → ollama summarizes ground-truth (small model is fine for data)
          - Conversational / freeform → claude if API key (llama3.2 too small for personality)
          - heavy=True → heavy model (gemma3:4b or opus)
        """
        from datetime import datetime
        sys = system_prompt()
        # Inject time/day context — Friday should "know" the clock
        now = datetime.now()
        sys += (f"\n\nRIGHT NOW: {now.strftime('%A')} {now.strftime('%H:%M')} "
                f"({now.strftime('%Y-%m-%d')}).\n"
                f"- If you mention a time in your reply, it MUST be {now.strftime('%H:%M')} — never any other.\n"
                f"- Never say 'scheduled for X:XX' unless that matches Bhargav's daily_os.\n"
                f"- If unsure of a number or fact, omit it rather than guess.")

        history = [{"role": t["role"], "content": t["content"]}
                   for t in self.memory.get_turns(6)]

        # WORLD-QUERY INTERCEPT — real research, not "not my beat"
        if use_tools and _is_world_query(user_query):
            research_reply = self._world_query(user_query)
            if research_reply is not None:
                self.memory.add_turn("user", user_query)
                self.memory.add_turn("assistant", research_reply["reply"])
                self.memory.log_event("respond", {
                    "query": user_query[:200],
                    "engine": research_reply.get("engine", "researcher"),
                    "tool": "intelligence.deep_research",
                    "conversational": False,
                })
                return {
                    "reply": research_reply["reply"],
                    "engine": research_reply.get("engine", "researcher"),
                    "tool_used": "intelligence.deep_research",
                    "tool_result": research_reply.get("meta"),
                    "conversational": False,
                }

        # COMPUTER USE INTERCEPT — v0.3 Vision
        images = None
        if use_tools and _is_computer_query(user_query):
            try:
                from friday.actions import computer
                import time
                from pathlib import Path
                # 1. Take screenshot
                ss_dir = Path(os.path.expanduser("~/AI/friday/data/screenshots"))
                ss_dir.mkdir(parents=True, exist_ok=True)
                ss_path = ss_dir / f"vision_{int(time.time())}.png"
                res = computer.take_screenshot(str(ss_path))
                if res.get("ok"):
                    # 2. Encode to base64
                    images = [_encode_image(str(ss_path))]
                    # 3. Adjust system prompt for vision
                    # Gracefully handle text-only models to prevent hallucination
                    current_model = self.engine.ollama_heavy_model
                    vision_capable = any(v in current_model.lower() for v in ("vision", "llava", "minicpm", "paligemma"))
                    
                    if not vision_capable and not self.engine.claude.api_key:
                        return {
                            "reply": f"Boss, my current neural net ({current_model}) is text-only. I need you to run `ollama pull llama3.2-vision` to restore my eyes.",
                            "engine": "system",
                            "tool_used": "system.alert",
                            "tool_result": {"error": "text_only_model"},
                            "conversational": False
                        }
                    else:
                        images = [_encode_image(str(ss_path))]
                        sys += (
                            "\n\nYou have just taken a screenshot of Bhargav's screen. "
                            "Look at the image provided. Use it to answer his question "
                            "accurately. If he asks to click or type, provide the "
                            "necessary code or steps based on the UI you see."
                        )
            except Exception as e:
                self.memory.log_event("vision_error", {"error": str(e)})

        # DETERMINISTIC TOOL ROUTING
        tool_used = None
        tool_result = None
        if use_tools and self.tools:
            matched = self._match_tool(user_query)
            if matched:
                try:
                    tool_result = matched.run()
                    tool_used = matched.name
                except Exception as e:
                    tool_result = f"[tool error: {e}]"
                    tool_used = f"{matched.name}:error"

        # BUILD PROMPT WITH GROUND TRUTH
        parts = []

        # For conversational queries with no tool fire, DON'T dump full facts —
        # the small model grabs random facts and returns them as "answers".
        # Only include facts when a tool is firing (model has structured truth to work from).
        if tool_used or images:
            mem_context = self.memory.context_block(turns=4)
        else:
            # Just the last few turns, no full facts blob
            turns = self.memory.get_turns(4)
            if turns:
                mem_context = "RECENT DIALOGUE:\n" + "\n".join(
                    f"  {t['role']}: {t['content'][:180]}" for t in turns
                )
            else:
                mem_context = ""
        if mem_context.strip():
            parts.append(mem_context)

        if tool_used and tool_result is not None:
            truth = json.dumps(tool_result, indent=2, default=str)[:3000]
            parts.append(
                f"GROUND TRUTH (from tool '{tool_used}' — these are the REAL numbers, "
                f"do not invent or change them):\n{truth}"
            )
            parts.append(
                "RULES:\n"
                "- Answer ONLY using numbers from GROUND TRUTH above.\n"
                "- If a number isn't there, say 'No data' — never guess.\n"
                "- Keep response under 4 lines unless asked for detail.\n"
                "- Write in Friday voice. Dry, specific, no filler."
            )

        # Conversational flow rule
        parts.append(
            "OUTPUT RULES:\n"
            "- Be highly conversational, intelligent, and natural.\n"
            "- Answer the question completely, but feel free to add a strategic thought or anticipate the next move.\n"
            "- Speak like a partner in the mission (think Jarvis/Friday from Iron Man).\n"
            "- Do not sound like a robotic customer service bot."
        )

        parts.append(f"\nBhargav: {user_query}")
        full_prompt = "\n\n".join(parts)

        # ENGINE PICK
        #   - explicit force wins
        #   - tool query → ollama (synthesize ground-truth, cheap + reliable)
        #   - conversational or heavy → openrouter if available
        conversational = _is_conversational(user_query) and not tool_used
        openrouter_available = hasattr(self.engine, 'openrouter') and self.engine.openrouter is not None

        # Force heavy for vision to prevent hallucination by text-only models
        if images and not heavy:
            heavy = True

        force = force_engine
        if not force:
            if tool_used:
                force = "ollama"  # data summarization, stick local
            elif (heavy or conversational or images) and openrouter_available:
                force = "openrouter"
            # else: auto-route via MultiEngine default

        # Higher temp for conversation, lower for tool synthesis
        temperature = None
        if force == "claude":
            temperature = 0.75 if not heavy else 0.6
        elif not tool_used:
            temperature = 0.7

        try:
            reply, engine_used = self.engine.ask(
                sys, full_prompt, history=history, force=force, heavy=heavy, images=images, temperature=temperature
            )
        except Exception as e:
            # Emergency fallback if all engines fail
            reply = f"System Error: {e}"
            engine_used = "fail"

        # Post-scrub
        reply = scrub_reply(reply)

        # PERSIST
        self.memory.add_turn("user", user_query)
        self.memory.add_turn("assistant", reply)
        self.memory.log_event("respond", {
            "query": user_query[:200],
            "engine": engine_used,
            "tool": tool_used,
            "conversational": conversational,
        })

        return {
            "reply": reply,
            "engine": engine_used,
            "tool_used": tool_used,
            "tool_result": tool_result,
            "conversational": conversational,
        }


if __name__ == "__main__":
    eng = MultiEngine()
    mem = Memory()
    orch = Orchestrator(eng, mem)
    result = orch.respond("Status check. One line.")
    print(result)
