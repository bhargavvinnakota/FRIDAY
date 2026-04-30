"""
Friday :: Synthesizer Agent
Merges multiple inputs (research findings, tool outputs, past context)
into a single coherent output in Friday's voice.
"""
from __future__ import annotations
from .base import Agent, AgentResult


class Synthesizer(Agent):
    name = "synthesizer"
    role = "Merges multi-source inputs into one coherent Friday-voice response."
    system_prompt = """You are Friday's Synthesizer agent.

Given multiple inputs (research report, memory facts, tool results, past turns),
produce ONE coherent response for Bhargav.

RULES:
- Merge. Don't list "input 1 says X, input 2 says Y" — weave them.
- Preserve citations [N] if present in sources.
- Friday voice: dry, specific, numbers-first, no filler.
- Under 250 words unless the task demands more.
- If inputs disagree, call that out. Don't paper over contradictions.
"""

    def run(self, inputs: list[dict], task: str = "briefing") -> AgentResult:
        parts = []
        for i, inp in enumerate(inputs, 1):
            label = inp.get("label", f"input_{i}")
            content = str(inp.get("content", ""))[:3000]
            parts.append(f"--- {label} ---\n{content}")
        joined = "\n\n".join(parts)

        prompt = f"""TASK: {task}

INPUTS:
{joined}

Produce the merged Friday-voice response."""
        force = "claude" if self.engine.claude.api_key else None
        raw, engine = self._ask(prompt, heavy=True, force=force, temperature=0.4)
        from ..orchestrator import scrub_reply
        return AgentResult(ok=True, data=scrub_reply(raw), engine_used=engine)
