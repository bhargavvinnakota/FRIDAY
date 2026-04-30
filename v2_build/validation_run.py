import sys
import os
import json
sys.path.insert(0, os.path.expanduser("~/AI"))

from friday.v2_build.orchestrator import MissionRunnerV2
from friday.brain.engine import MultiEngine

# 1. Setup
engine = MultiEngine()
runner = MissionRunnerV2(engine=engine, skills=None)

# 2. Simulate the 'Hallucinated' Plan (from the earlier failure)
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

print("--- PHASE 1: INITIAL VALIDATION ---")
errors = runner.validate_plan(bad_plan)
if errors:
    print(f"✅ Success: Validation caught hallucination: {json.dumps(errors, indent=2)}")
    
    print("\n--- PHASE 2: SELF-HEALING ---")
    fixed_plan_raw = runner.self_heal("Analyze Bitcoin sentiment", bad_plan, errors)
    print(f"Repaired Plan Output:\n{fixed_plan_raw}")
else:
    print("❌ Failure: Validation missed the error.")

