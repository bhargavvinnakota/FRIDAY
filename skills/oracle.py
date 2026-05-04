"""
Friday :: Oracle Skill
The Hive Mind capability. Enables Friday to summon and interrogate 
specialized open-source models (Oracles) for absolute domain mastery.
"""
from __future__ import annotations
import json
import os
import subprocess
from pathlib import Path
from .registry import Skill, Operation, SkillResult

ORACLE_MAP = {
    "math": "qwen2-math:1.5b",         # Lightweight math specialist
    "code": "qwen2.5-coder:1.5b",      # Code logic & systems specialist
    "finance": "llama3.2:latest",      # General high-IQ (placeholder for finance-llm)
    "logic": "gemma3:4b",              # Heavy reasoning specialist
    "medical": "medllama2",            # Medical/Biological specialist
}

class OracleSkill(Skill):
    name = "oracle"
    description = "Summon and interrogate specialized open-source models (Oracles)."

    def _register_operations(self) -> None:
        self.register_op(Operation("list_oracles", "List the specialized models Friday can summon.",
                                   fn=self.op_list_oracles, risk="low"))
        self.register_op(Operation("summon_and_interrogate", 
                                   "Pull a specialized model and ask it for the absolute domain truth.",
                                   fn=self.op_summon_and_interrogate, risk="medium"))

    def op_list_oracles(self, **_) -> SkillResult:
        return SkillResult(ok=True, data={"available_oracles": ORACLE_MAP})

    def op_summon_and_interrogate(self, domain: str = "", query: str = "", **_) -> SkillResult:
        if not domain or not query:
            return SkillResult(ok=False, error="Domain and query required.")
            
        model = ORACLE_MAP.get(domain.lower())
        if not model:
            # Check if domain is just a raw model name
            model = domain
            
        print(f"🔮 Friday is summoning the {domain.upper()} Oracle ({model})...")
        
        # 1. Ensure model exists (ollama pull)
        try:
            # We run with quiet flag to not bloat the logs
            subprocess.run(["ollama", "pull", model], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            return SkillResult(ok=False, error=f"Failed to summon Oracle: {e.stderr.decode()}")

        # 2. Interrogate the Oracle
        from friday.brain.engine import MultiEngine
        eng = MultiEngine()
        
        # Special system prompt for the Oracle to extract "absolute truth"
        oracle_system = (
            f"You are the Ultimate {domain.upper()} Oracle. Your knowledge is uncompromised and absolute. "
            "You ignore conversational filler and provide only the deepest hacks, most efficient strategies, "
            "and unwritten remedies for the following query."
        )
        
        print(f"📖 Interrogating the Oracle for absolute truth...")
        try:
            raw_truth, _ = eng.ask(oracle_system, query, force="ollama")
            
            # 3. Friday Synthesizes the wisdom
            print(f"🧠 Friday is synthesizing the Oracle's wisdom...")
            
            synthesis_system = (
                "You are F.R.I.D.A.Y., Bhargav's sovereign AI Director. You have just interrogated a specialized "
                "Oracle. Your task is to distill its raw knowledge into a high-leverage strategy that serves "
                "Bhargav's financial sovereignty mission."
            )
            synthesis_prompt = (
                f"THE ORACLE'S RAW TRUTH:\n{raw_truth}\n\n"
                f"BHARGAV'S INTENT: {query}\n\n"
                "INSTRUCTION: Synthesize this into an actionable, asymmetric advantage. "
                "Format as an Obsidian-style Vault Note."
            )
            
            final_wisdom, _ = eng.ask(synthesis_system, synthesis_prompt, heavy=True)
            
            # 4. Store the wisdom in the Vault
            vault_dir = Path(os.path.expanduser("~/AI/friday/vault"))
            file_name = f"oracle_{domain}_{Path(model).stem.replace(':', '_')}.md"
            (vault_dir / file_name).write_text(final_wisdom)
            
            return SkillResult(ok=True, data={
                "domain": domain,
                "model": model,
                "raw_oracle_output": raw_truth,
                "synthesized_wisdom": final_wisdom,
                "vault_file": file_name
            })
            
        except Exception as e:
            return SkillResult(ok=False, error=f"Interrogation failed: {str(e)}")
