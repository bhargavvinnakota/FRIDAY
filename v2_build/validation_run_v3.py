import sys
import os
import json
import time
sys.path.insert(0, os.path.expanduser("~/AI"))

from friday.v2_build.orchestrator import MissionRunnerV2
from friday.brain.engine import MultiEngine
from friday.brain.agents.planner import Planner
from friday.skills import get_registry

def run_test():
    engine = MultiEngine()
    reg = get_registry()
    runner = MissionRunnerV2(engine=engine, skills=reg)
    planner_agent = Planner(engine)
    registry_desc = planner_agent._format_skills(reg.describe_all())

    bad_plan = {
        "steps": [
            {
                "id": 1,
                "skill": "intelligence",
                "operation": "topic_pulse",
                "args": {"query": "Bitcoin sentiment"}
            }
        ]
    }

    print("--- PHASE 1: VALIDATION ---")
    errors = runner.validate_plan(bad_plan)
    if not errors:
        return False

    print("--- PHASE 2: CONSTRAINED SELF-HEALING ---")
    for i in range(3):
        try:
            fixed_plan_raw = runner.self_heal("Analyze Bitcoin sentiment", bad_plan, errors, registry_desc)
            if "topic" in fixed_plan_raw.lower():
                print(f"✅ SUCCESS: Plan self-healed on attempt {i+1}.")
                print(fixed_plan_raw)
                return True
        except Exception as e:
            print(f"Attempt {i+1} failed: {e}")
            time.sleep(2)
    return False

if __name__ == "__main__":
    if run_test():
        sys.exit(0)
    else:
        sys.exit(1)
