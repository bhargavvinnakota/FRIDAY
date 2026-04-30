"""
Friday V2 :: Mission Orchestrator (Omni-Daemon Edition)
Features: Pydantic Validation, Self-Healing, and Graph Routing.
"""
import json
from typing import Any, List, Dict
from pydantic import ValidationError
from .v2_schema import get_schema

class MissionRunnerV2:
    def __init__(self, engine, skills):
        self.engine = engine
        self.skills = skills

    def validate_plan(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Validates every step in a plan against the strict Pydantic schemas.
        Returns a list of errors found.
        """
        errors = []
        for step in plan.get("steps", []):
            skill = step.get("skill")
            op = step.get("operation")
            args = step.get("args", {})
            
            schema_cls = get_schema(skill, op)
            if schema_cls:
                try:
                    schema_cls(**args)
                except ValidationError as e:
                    errors.append({
                        "step_id": step.get("id"),
                        "skill": skill,
                        "operation": op,
                        "error": e.errors(),
                        "received_args": args
                    })
            else:
                # Skill/Op not in schema registry - critical for sovereignty
                errors.append({
                    "step_id": step.get("id"),
                    "error": f"Security Violation: Skill '{skill}.{op}' not in the Allowlist Schema Registry."
                })
        return errors

    def self_heal(self, goal: str, plan: Dict[str, Any], errors: List[Dict[str, Any]], registry_desc: str) -> Dict[str, Any]:
        """
        Feeds validation errors back to the Planner to fix the hallucination.
        Constrained by the real Skills Registry.
        """
        sys_prompt = f"""You are Friday's Senior SRE. A plan failed structural validation. 
Fix the plan using ONLY the ALLOWED SKILLS below. 

ALLOWED SKILLS REGISTRY:
{registry_desc}

RULES:
1. Output STRICTLY valid JSON.
2. Use ONLY the skills and operations listed above.
3. Correct the arguments to match the Pydantic errors provided.
"""
        user_prompt = f"GOAL: {goal}\n\nFAILED PLAN: {json.dumps(plan)}\n\nVALIDATION ERRORS: {json.dumps(errors)}\n\nProvide the FIXED JSON plan."
        
        raw, _ = self.engine.ask(sys_prompt, user_prompt, heavy=True)
        return raw

# --- Validation Script ---
if __name__ == "__main__":
    print("MissionRunnerV2 Loaded.")
