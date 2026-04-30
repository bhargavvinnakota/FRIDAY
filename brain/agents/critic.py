"""
Friday :: Critic Agent
Verifies that a proposed action/output is grounded, safe, and aligned with Bhargav's rules.

Used before high-risk actions (public posts, outbound messages, money-adjacent).
Returns a verdict: APPROVE | REJECT | REVISE with specific reasons.
"""
from __future__ import annotations
import json
import re

from .base import Agent, AgentResult


class Critic(Agent):
    name = "critic"
    role = "Verifies output quality + grounding + policy alignment before release."
    system_prompt = """You are Friday's Critic agent. Your job: stress-test the proposed output before it ships.

Check these dimensions:
1. GROUNDING: Is every factual claim supported by the provided source material? Flag fabrications.
2. SPECIFICITY: Does it use real numbers, names, dates — or vibes?
3. POLICY: Does it violate Bhargav's hard rules (Sunday rest, build-vs-sell ratio, no KYC bypass, etc.)?
4. VOICE: Does it sound like Friday (dry, specific) or like a generic LLM (padded, sycophantic)?
5. SAFETY: Could this action harm Bhargav financially, legally, or reputationally if it went out?

Output STRICT JSON:
{
  "verdict": "APPROVE" | "REVISE" | "REJECT",
  "confidence": 0.0-1.0,
  "grounding_issues": ["..."],
  "voice_issues": ["..."],
  "safety_issues": ["..."],
  "revision_suggestions": ["..."],
  "summary": "<one-line justification>"
}

Be tough but specific. Vague criticism is worse than no criticism."""

    def run(self, proposed_output: str, context: str = "",
            source_material: str = "") -> AgentResult:
        prompt = f"""PROPOSED OUTPUT:
---
{proposed_output}
---

CONTEXT (what this was for):
{context}

SOURCE MATERIAL (what it was supposed to be grounded in):
{source_material[:3000] if source_material else '(none provided)'}

Produce the JSON verdict per schema."""
        force = "claude" if self.engine.claude.api_key else None
        raw, engine = self._ask(prompt, heavy=True, force=force, temperature=0.2)
        verdict = self._parse_json(raw)
        if not verdict:
            return AgentResult(ok=False, error="critic returned invalid JSON",
                               reasoning=raw[:400], engine_used=engine)
        return AgentResult(ok=True, data=verdict,
                           reasoning=verdict.get("summary", ""),
                           engine_used=engine)

    def _parse_json(self, raw: str) -> dict | None:
        raw = raw.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group())
        except Exception:
            return None
