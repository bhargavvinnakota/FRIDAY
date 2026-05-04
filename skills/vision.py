"""
Friday :: Vision Skill
Provides semantic analysis of screen captures and visual data.
"""
from __future__ import annotations
import os
from pathlib import Path
from .registry import Skill, Operation, SkillResult

class VisionSkill(Skill):
    name = "vision"
    description = "Analyze visual data and screen captures to understand the user's context."

    def _register_operations(self) -> None:
        self.register_op(Operation(
            "analyze_frame", 
            "Analyze a screen capture for semantic meaning.",
            fn=self.op_analyze_frame,
            risk="low",
            input_schema={"path": "Path to the image file"}
        ))

    def op_analyze_frame(self, path: str = "", prompt: str = "What is on the screen right now? Summarize the active window and context.", **_) -> SkillResult:
        if not path:
            return SkillResult(ok=False, error="Image path required")
        
        full_path = Path(path)
        if not full_path.exists():
            return SkillResult(ok=False, error=f"Image not found at {path}")

        from friday.brain.engine import MultiEngine
        eng = MultiEngine()
        
        # Use a heavy model or Gemini native for vision
        sys_p = "You are Friday's Vision System. Describe the provided screen capture accurately and concisely. Focus on the active application and any important notifications or status indicators."
        
        try:
            # Note: MultiEngine needs to be updated to handle the 'images' parameter properly
            res, engine = eng.ask(sys_p, prompt, images=[str(full_path)], heavy=True)
            return SkillResult(ok=True, data={"analysis": res, "engine_used": engine})
        except Exception as e:
            return SkillResult(ok=False, error=f"Vision analysis failed: {e}")
