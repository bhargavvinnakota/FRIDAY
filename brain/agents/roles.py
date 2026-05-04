"""
Friday V2.5 :: Role-Based Agents
Defines specialized agent personas for company orchestration.
Agents use the 'Student' model for standard reasoning and the 'Teacher' (heavy) for complex tasks.
"""
from typing import Any
from friday.brain.engine import MultiEngine

class RoleAgent:
    def __init__(self, role_name: str, system_prompt: str):
        self.role_name = role_name
        self.system_prompt = system_prompt
        self.engine = MultiEngine()

    def reason(self, task: str, context: str = "", heavy: bool = False) -> tuple[str, str]:
        """
        Executes a reasoning task.
        heavy=False -> Uses local student model (e.g. gemma3:4b).
        heavy=True  -> Uses teacher ensemble (e.g. OpenRouter/Gemini).
        """
        prompt = f"TASK:\n{task}\n\nCONTEXT:\n{context}" if context else task
        print(f"[{self.role_name}] Thinking... (Heavy={heavy})")
        response, model_used = self.engine.ask(self.system_prompt, prompt, heavy=heavy)
        return response, model_used

class CEOAgent(RoleAgent):
    def __init__(self):
        super().__init__(
            role_name="CEO",
            system_prompt="You are Friday's internal CEO Agent. Your role is to synthesize market information, set objectives, prioritize initiatives, and determine when a human-in-the-loop escalation is required. Keep responses strategic and concise."
        )

class EngineerAgent(RoleAgent):
    def __init__(self):
        super().__init__(
            role_name="Lead Engineer",
            system_prompt="You are Friday's internal Engineering Lead Agent. Your role is to design architecture, propose implementation tasks, review code for technical debt, and ensure system scalability."
        )

class GrowthAgent(RoleAgent):
    def __init__(self):
        super().__init__(
            role_name="Growth Marketer",
            system_prompt="You are Friday's internal Growth Marketing Agent. Your role is to run experiments, draft campaigns, track funnel metrics, and identify revenue opportunities."
        )
