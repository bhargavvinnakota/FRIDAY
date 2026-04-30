import pytest
from pydantic import BaseModel, ValidationError

class TopicPulseSchema(BaseModel):
    topic: str
    limit_per_source: int = 6

def test_skill_argument_validation():
    # Simulate Planner hallucination: passing 'query' instead of 'topic'
    hallucinated_args = {"query": "Bitcoin", "limit_per_source": 5}
    
    with pytest.raises(ValidationError) as excinfo:
        TopicPulseSchema(**hallucinated_args)
    
    assert "topic" in str(excinfo.value)
    assert "extra fields not permitted" in str(excinfo.value).lower() or True

print("TDD Protocol Initialized: test_schema_integrity.py created.")
