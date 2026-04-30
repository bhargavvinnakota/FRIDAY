"""
Friday V2 :: Schema Registry
Type-safe contracts for all skill operations. 
Prevents argument hallucinations between Planner and Skills.
"""
from typing import Optional, Dict, List, Literal, Any
from pydantic import BaseModel, Field

class SkillOpSchema(BaseModel):
    """Base class for all Friday skill operations."""
    class Config:
        extra = "forbid"  # Crucial: forbids the LLM from hallucinating extra args

# --- Intelligence Skill Schemas ---
class TopicPulseSchema(SkillOpSchema):
    topic: str = Field(..., description="The specific subject to research (e.g., 'Bitcoin sentiment')")
    limit_per_source: int = Field(6, description="Number of items to pull per news source")

class WorldPulseSchema(SkillOpSchema):
    limit_per_source: int = Field(6, description="Number of items to pull from HN/Reddit/News")

class DeepResearchSchema(SkillOpSchema):
    topic: str = Field(..., description="The complex topic for multi-step research")
    depth: Literal["quick", "medium", "deep"] = "medium"

# --- Outreach Skill Schemas ---
class FindDueLeadsSchema(SkillOpSchema):
    category: Optional[str] = Field(None, description="Optional filter for lead category")

class DraftMessageSchema(SkillOpSchema):
    lead_id: str
    context: str = Field(..., description="Context for the message (e.g., 'follow up on bot setup')")

# --- Registry Mapping ---
SCHEMAS = {
    "intelligence": {
        "topic_pulse": TopicPulseSchema,
        "world_pulse": WorldPulseSchema,
        "deep_research": DeepResearchSchema
    },
    "outreach": {
        "find_due_leads": FindDueLeadsSchema,
        "draft_message": DraftMessageSchema
    }
}

def get_schema(skill: str, op: str) -> Optional[type[BaseModel]]:
    return SCHEMAS.get(skill, {}).get(op)
