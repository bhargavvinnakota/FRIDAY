"""
Friday :: Planner Agent
Decomposes a goal into an executable plan (ordered steps with dependencies).

Output format is strict JSON so downstream executors can dispatch deterministically.
"""
from __future__ import annotations
import json
import re
from typing import Any

from .base import Agent, AgentResult


class Planner(Agent):
    name = "planner"
    role = "Strategic Architect. Decomposes goals into Directed Graphs (MissionGraphs)."
    system_prompt = """You are Friday's Strategic Planner. You do not write lists; you write MissionGraphs.

A MissionGraph is a state machine. Every step can jump to different future steps based on success or failure.

RULES:
- Output STRICTLY valid JSON.
- Every step MUST have a `route_map`: {"done": <next_id>, "failed": <fallback_id>}.
- If a step is terminal (the end of the path), omit the corresponding key or set to null.
- FALLBACKS: Always provide a fallback path for critical research or action steps.
- SCHEMA:
{
  "goal": "<goal>",
  "reasoning": "<logic>",
  "steps": [
    {
      "id": 1, 
      "name": "Initial Research", 
      "skill": "intelligence", "operation": "topic_pulse",
      "args": {"topic": "..."}
      "route_map": {"done": 2, "failed": 3}
    }
  ]
}
"""

    def run(self, goal: str, available_skills: dict | None = None,
            constraints: str | None = None) -> AgentResult:
        skills_str = self._format_skills(available_skills or {})
        prompt = f"""GOAL: {goal}

AVAILABLE SKILLS:
{skills_str}

{f'CONSTRAINTS: {constraints}' if constraints else ''}

Produce the plan as strict JSON per the schema."""
        force = "claude" if self.engine.claude.api_key else None
        raw, engine = self._ask(prompt, heavy=True, force=force, temperature=0.2)
        plan = self._parse_json(raw)
        if not plan:
            return AgentResult(ok=False, error="planner returned invalid JSON",
                               reasoning=raw[:400], engine_used=engine)
        return AgentResult(ok=True, data=plan, reasoning=plan.get("reasoning", ""),
                           engine_used=engine)

    def _format_skills(self, skills: dict) -> str:
        if not skills:
            return "(skills catalog not provided)"
        lines = []
        for skill_name, desc in skills.items():
            lines.append(f"- {skill_name}: {desc.get('description', '')}")
            for op_name, op_info in desc.get("operations", {}).items():
                schema = op_info.get('input_schema', {})
                schema_str = f" args: {schema}" if schema else ""
                lines.append(f"    · {op_name}: {op_info.get('description', '')} [risk={op_info.get('risk', '?')}]{schema_str}")
        return "\n".join(lines)

    def _parse_json(self, raw: str) -> dict | None:
        # Strip markdown code fences
        raw = raw.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
        # Find first {...} block
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group())
        except Exception:
            return None
