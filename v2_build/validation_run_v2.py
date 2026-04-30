import sys
import os
import json
sys.path.insert(0, os.path.expanduser("~/AI"))

from friday.v2_build.orchestrator import MissionRunnerV2
from friday.brain.engine import MultiEngine
from friday.brain.agents.planner import Planner
from friday.skills import get_registry

# 1. Setup
engine = MultiEngine()
reg = get_registry()
runner = MissionRunnerV2(engine=engine, skills=reg)
planner_agent = Planner(engine)

# 2. Get Registry Description
registry_desc = planner_agent._format_skills(reg.describe_all())

# 3. Simulate the 'Hallucinated' Plan
bad_plan = {
    "steps": [
        {
            "id": 1,
            "skill": "intelligence",
            "operation": "topic_pulse",
            "args": {"query": "Bitcoin sentiment"} # ERROR: should be 'topic'
        }
    ]
}

print("--- PHASE 1: VALIDATION ---")
errors = runner.validate_plan(bad_plan)
if errors:
    print(f"✅ Caught Error.")
    
    print("\n--- PHASE 2: CONSTRAINED SELF-HEALING ---")
    fixed_plan_raw = runner.self_heal("Analyze Bitcoin sentiment", bad_plan, errors, registry_desc)
    print(f"Repaired Plan Output:\n{fixed_plan_raw}")
    
    # Final assertion: check if 'topic' exists in the new plan
    if '"topic":' in fixed_plan_raw and '"query":' not in fixed_plan_raw:
        print("\n✅ SUCCESS: Plan self-healed into valid schema.")
    else:
        print("\n❌ FAILURE: Plan still hallucinating or misaligned.")
else:
    print("❌ Failure: Validation missed the error.")
