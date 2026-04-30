"""
Friday V2.1 :: Mission Graph Orchestrator
Enables conditional branching and self-correction loops.
"""
import json
import logging
from datetime import datetime
from typing import Any, List, Dict, Optional
from pydantic import BaseModel, Field

# Using the V2 Schema Layer
from friday.brain.v2_schema import get_schema

class GraphStep(BaseModel):
    id: int
    name: str
    skill: str
    operation: str
    args: Dict[str, Any] = {}
    # Branching: { "status": next_id }
    route_map: Dict[str, Optional[int]] = {} 
    status: str = "pending"
    result: Any = None
    error: str = None

class MissionGraph(BaseModel):
    id: str
    goal: str
    steps: List[GraphStep]
    current_step_id: int = 1
    status: str = "running" # running | success | failure

class MissionRunnerV2_1:
    def __init__(self, engine, skills):
        self.engine = engine
        self.skills = skills

    def execute_step(self, mission: MissionGraph, step: GraphStep) -> bool:
        """Executes a single step and determines the next jump."""
        print(f"Executing Step {step.id}: {step.skill}.{step.operation}")
        step.status = "running"
        
        # 1. Validation Gate (from V2.0)
        schema_cls = get_schema(step.skill, step.operation)
        if schema_cls:
            try:
                schema_cls(**step.args)
            except Exception as e:
                step.status = "failed"
                step.error = f"Schema Violation: {e}"
                return False

        # 2. Skill Invocation
        try:
            # actor = f"mission:{mission.id}"
            res = self.skills.invoke(step.skill, step.operation, **step.args)
            step.result = res.data
            if res.ok:
                step.status = "done"
            else:
                step.status = "failed"
                step.error = res.error
        except Exception as e:
            step.status = "failed"
            step.error = str(e)

        return step.status == "done"

    def run(self, mission: MissionGraph):
        """Infinite loop traversal of the graph until a terminal state."""
        while mission.status == "running":
            step = next((s for s in mission.steps if s.id == mission.current_step_id), None)
            
            if not step:
                mission.status = "failure"
                print("Error: Reached dead-end node.")
                break

            success = self.execute_step(mission, step)
            status_key = "done" if success else "failed"
            
            # 3. Routing Logic
            next_id = step.route_map.get(status_key)
            if next_id is None:
                # Terminal state reached
                mission.status = "success" if success else "failure"
                break
            else:
                mission.current_step_id = next_id

        print(f"Mission Result: {mission.status}")
        return mission
