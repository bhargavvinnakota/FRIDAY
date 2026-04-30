"""
Friday V2.6 :: Auto-Upgrade Engine
Generates "challenges" for Friday, detects missing functionality,
and writes new Python skills autonomously to solve them.
"""
import os
import sys
import json
from pathlib import Path

# Add root to path
sys.path.insert(0, os.path.expanduser("~/AI"))

from friday.brain.engine import MultiEngine
from friday.brain.orchestrator import Orchestrator
from friday.brain.memory import Memory
from friday.skills import get_registry

class AutoUpgradeEngine:
    def __init__(self):
        self.engine = MultiEngine()
        self.memory = Memory()
        self.skills = get_registry()
        self.orch = Orchestrator(self.engine, self.memory)

    async def run_upgrade_cycle(self):
        import asyncio
        print("[Auto-Upgrade] Generating Stress Challenge...")
        
        # 1. Generate a complex, missing-skill challenge
        sys_p = "You are a Master AI Architect. Generate a complex, business-critical request that Friday might NOT currently be able to handle with her basic skills (system, research, outreach, etc.)."
        user_p = "Give me a single-sentence challenge for Friday."
        challenge, _ = await asyncio.to_thread(self.engine.ask, sys_p, user_p, force="ollama")
        print(f"[Auto-Upgrade] Challenge: {challenge}")

        # 2. Test Friday against the challenge
        res = await asyncio.to_thread(self.orch.respond, challenge, use_tools=True)
        
        if res.get("tool_used") is None:
            print("[Auto-Upgrade] ⚠️ Missing functionality detected. Initiating Code Synthesis...")
            
            # 3. Synthesize the missing Skill
            codegen_sys = (
                "You are Friday's Core Developer. Synthesize a new Python Skill module to handle the following challenge.\n"
                f"CHALLENGE: {challenge}\n"
                "STRICT REQUIREMENTS:\n"
                "1. Subclass `from .registry import Skill, Operation, SkillResult`.\n"
                "2. Set `name` and `description` as class attributes.\n"
                "3. Implement `_register_operations(self)` and use `self.register_op(Operation(...))`.\n"
                "4. Every operation must return a `SkillResult`.\n"
                "5. No external dependencies besides standard library and Friday components.\n"
                "\nTEMPLATE:\n"
                "```python\n"
                "from .registry import Skill, Operation, SkillResult\n\n"
                "class NewSkill(Skill):\n"
                "    name = 'new_skill_name'\n"
                "    description = '...' \n\n"
                "    def _register_operations(self):\n"
                "        self.register_op(Operation('op_name', 'desc', self.op_fn, risk='low'))\n\n"
                "    def op_fn(self, **kwargs):\n"
                "        return SkillResult(ok=True, data={'res': '...'})\n"
                "```"
            )
            code_raw, _ = await asyncio.to_thread(self.engine.ask, codegen_sys, "Output the Python code in a ```python block.", heavy=True)
            
            if "```python" in code_raw:
                code = code_raw.split("```python")[1].split("```")[0].strip()
                # Save to a new skill file
                skill_id = abs(hash(challenge)) % 10000
                path = Path(os.path.expanduser(f"~/AI/friday/skills/auto_upgrade_{skill_id}.py"))
                path.write_text(code)
                print(f"✅ [Auto-Upgrade] Deployed new skill: {path.name}")
                return True
        else:
            print(f"✅ [Auto-Upgrade] Friday handled the challenge using: {res['tool_used']}")
            return False

if __name__ == "__main__":
    import asyncio
    engine = AutoUpgradeEngine()
    asyncio.run(engine.run_upgrade_cycle())
