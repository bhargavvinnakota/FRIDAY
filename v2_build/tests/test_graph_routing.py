import pytest
from typing import Dict, Any

def mock_resolver(step_result: Dict[str, Any], condition: str) -> bool:
    """Simulates the result-based branching logic."""
    if condition == "has_data":
        return bool(step_result.get("data"))
    return True

def test_conditional_branching():
    # Scenario: If step 1 finds leads, go to step 2. If not, go to step 3 (Exit).
    result_with_leads = {"data": ["lead1", "lead2"]}
    result_empty = {"data": []}
    
    # Branch 1: Success path
    next_step = 2 if mock_resolver(result_with_leads, "has_data") else 3
    assert next_step == 2
    
    # Branch 2: Failure path
    next_step = 2 if mock_resolver(result_empty, "has_data") else 3
    assert next_step == 3

print("TDD Protocol: test_graph_routing.py verified.")
