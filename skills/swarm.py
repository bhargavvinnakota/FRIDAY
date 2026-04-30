from __future__ import annotations
import os
from pathlib import Path
from .registry import Skill, Operation, SkillResult

class SwarmSkill(Skill):
    name = "swarm"
    description = "Legendary 2026 Capability: Dynamically spins up, trains, and deploys hierarchical agentic swarms to solve massive, complex goals autonomously."

    def _register_operations(self) -> None:
        self.register_op(Operation(
            name="deploy_swarm",
            description="Deploy the full agentic swarm (Architect, Researcher, Engineer, QA_Judge) to solve a highly complex goal.",
            fn=self.op_deploy_swarm,
            risk="high",
            input_schema={"goal": "The massive goal the swarm must accomplish."}
        ))

    def op_deploy_swarm(self, goal: str, **_) -> SkillResult:
        from friday.brain.engine import MultiEngine
        from friday.brain.memory import Memory
        from friday.brain.swarm import SwarmOrchestrator
        from friday.skills.registry import get_registry
        
        eng = MultiEngine()
        mem = Memory()
        reg = get_registry()
        
        swarm = SwarmOrchestrator(eng, mem, reg)
        try:
            final_output = swarm.run_swarm(goal)
            return SkillResult(ok=True, data={"swarm_output": final_output})
        except Exception as e:
            return SkillResult(ok=False, error=str(e))
