"""
Friday :: Specialist Agents
Each agent is a focused reasoning module with a specific responsibility.
Agents compose into missions via the mission orchestrator.
"""
from .base import Agent, AgentResult
from .researcher import Researcher
from .planner import Planner
from .critic import Critic
from .synthesizer import Synthesizer

__all__ = ["Agent", "AgentResult", "Researcher", "Planner", "Critic", "Synthesizer"]
