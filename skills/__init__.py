"""
Friday :: Skills
Modular capability layer. Every autonomous action Friday takes goes through a Skill.
Skills are registered with the global registry and invoked by the autonomy engine.
"""
from .registry import SkillRegistry, Skill, SkillResult, get_registry

__all__ = ["SkillRegistry", "Skill", "SkillResult", "get_registry"]
