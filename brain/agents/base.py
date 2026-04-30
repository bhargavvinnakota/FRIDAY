"""
Friday :: Agent Base
Each specialist agent subclasses Agent and implements run().
Agents are stateless — state lives in the mission.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

from ..engine import MultiEngine


@dataclass
class AgentResult:
    ok: bool
    data: Any = None
    reasoning: str = ""     # the agent's reasoning trace
    artifacts: list[str] = field(default_factory=list)
    cost_tokens: int = 0    # approx — for budget tracking
    engine_used: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok, "data": self.data, "reasoning": self.reasoning[:500],
            "artifacts": self.artifacts, "cost_tokens": self.cost_tokens,
            "engine_used": self.engine_used, "error": self.error,
        }


class Agent:
    """Base class for all specialist agents."""
    name: str = "agent"
    role: str = ""
    system_prompt: str = ""   # override in subclass

    def __init__(self, engine: MultiEngine):
        self.engine = engine

    def _ask(self, user_prompt: str, heavy: bool = False,
             force: str | None = None, temperature: float | None = None) -> tuple[str, str]:
        """Invoke the engine with this agent's system prompt."""
        # Set temp via the engine
        if temperature is not None:
            o_tmp = self.engine.ollama.temperature
            c_tmp = self.engine.claude.temperature
            self.engine.ollama.temperature = temperature
            self.engine.claude.temperature = temperature
        try:
            return self.engine.ask(self.system_prompt, user_prompt, force=force, heavy=heavy)
        finally:
            if temperature is not None:
                self.engine.ollama.temperature = o_tmp
                self.engine.claude.temperature = c_tmp

    def run(self, **kwargs) -> AgentResult:
        raise NotImplementedError
