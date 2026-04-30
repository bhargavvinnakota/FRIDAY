"""
Friday :: Cognitive Operating System (2026 Sovereign SOTA)
Implements:
1. Monte Carlo / Self-Correction Loops (Judge/Critic).
2. Verifiable Output Constraints (JSON enforcement).
3. "ReasoningBank" Epistemology.
"""
import json
import logging
from typing import Any, Callable
from friday.brain.engine import MultiEngine

class CriticValidator:
    """A self-correcting judge that forces the primary engine to rethink flawed logic."""
    def __init__(self, engine: MultiEngine):
        self.engine = engine
        
    def execute_with_reflection(self, task_prompt: str, data: str, rules: str, max_retries: int = 2) -> str:
        """Runs the task, has the 'Judge' evaluate it against rules, and loops if failed."""
        
        # 1. First Attempt (Worker)
        worker_sys = f"You are the Worker. Execute the task.\nRULES:\n{rules}"
        draft, engine_used = self.engine.ask(worker_sys, f"TASK:\n{task_prompt}\nDATA:\n{data}")
        
        for attempt in range(max_retries):
            # 2. Evaluation (Judge)
            judge_sys = (
                "You are the Judge. Evaluate the Draft against the RULES. "
                "Output exactly a JSON object: {\"pass\": true/false, \"critique\": \"...\"}"
            )
            eval_prompt = f"RULES:\n{rules}\n\nDRAFT:\n{draft}"
            
            # Force small/fast model for the judge if possible to save compute
            raw_eval, _ = self.engine.ask(judge_sys, eval_prompt, force="ollama")
            
            try:
                # Extract JSON
                json_str = raw_eval[raw_eval.find("{"):raw_eval.rfind("}")+1]
                evaluation = json.loads(json_str)
                
                if evaluation.get("pass"):
                    print(f"[CognitiveOS] Output validated on attempt {attempt+1}.")
                    return draft
                else:
                    critique = evaluation.get("critique", "Failed rules.")
                    print(f"\n[CognitiveOS] Judge Rejected Draft (Attempt {attempt+1}): {critique}")
                    
                    # 3. Reflection & Correction (Worker)
                    correction_sys = (
                        "You are the Worker. Your previous draft failed the Judge's evaluation. "
                        f"\nRULES:\n{rules}\n\nJUDGE CRITIQUE:\n{critique}\n\n"
                        "Rewrite the draft to perfectly satisfy the rules and fix the critique."
                    )
                    draft, _ = self.engine.ask(correction_sys, f"PREVIOUS DRAFT:\n{draft}")
                    
            except Exception as e:
                print(f"[CognitiveOS] Judge parsing error: {e}")
                # Fallback to the draft if judge crashes
                break
                
        return draft
