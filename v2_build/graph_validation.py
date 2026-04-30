import sys
import os
sys.path.insert(0, os.path.expanduser("~/AI"))

from friday.brain.v2_mission import MissionGraph, GraphStep, MissionRunnerV2_1
from friday.brain.engine import MultiEngine
from friday.skills import get_registry

# 1. Setup
engine = MultiEngine()
reg = get_registry()
runner = MissionRunnerV2_1(engine=engine, skills=reg)

# 2. Construct a mission with a known failure + fallback
# Step 1: Intentionally fail by calling a nonexistent skill/op
# Step 2: Fallback to a healthy op
mission = MissionGraph(
    id="test-graph-001",
    goal="Test self-correction fallback",
    steps=[
        GraphStep(
            id=1, name="Intentional Failure",
            skill="system", operation="nonexistent_op", 
            route_map={"done": None, "failed": 2} # Should jump to 2
        ),
        GraphStep(
            id=2, name="Fallback Recovery",
            skill="system", operation="health_check",
            route_map={"done": None, "failed": None} # Terminal
        )
    ]
)

print("--- INITIATING CHAOS TEST ---")
result = runner.run(mission)

# 3. Assertions
if result.steps[0].status == "failed" and result.steps[1].status == "done":
    print("\n✅ SUCCESS: Mission self-healed via Graph Routing.")
    print(f"Final Status: {result.status}")
else:
    print("\n❌ FAILURE: Routing logic broke.")
    for s in result.steps:
        print(f"Step {s.id} ({s.name}): {s.status}")

