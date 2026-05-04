"""
Friday :: Knowledge Distillation Skill
Compresses Teacher model outputs into fine-tuning datasets for the Student core.
"""
import os
import json
from pathlib import Path
from datetime import datetime
from .registry import Skill, Operation, SkillResult

class DistillationSkill(Skill):
    name = "distillation"
    description = "Exports successful complex agent interactions into a ShareGPT format dataset for local LoRA fine-tuning."

    def _register_operations(self) -> None:
        self.register_op(Operation(
            "export_dataset",
            "Scans recent actions and memory to build a fine-tuning dataset.",
            fn=self.op_export_dataset,
            risk="medium"
        ))

    def op_export_dataset(self, limit: int = 100, **_) -> SkillResult:
        try:
            log_path = Path(os.path.expanduser("~/AI/friday/data/actions.jsonl"))
            export_dir = Path(os.path.expanduser("~/AI/friday/data/training"))
            export_dir.mkdir(parents=True, exist_ok=True)
            
            out_file = export_dir / f"distill_dataset_{datetime.now().strftime('%Y%m%d_%H%M')}.jsonl"
            
            if not log_path.exists():
                return SkillResult(ok=False, error="No action log found for distillation.")
                
            dataset = []
            with open(log_path, "r") as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        # Look for successful, high-information actions
                        if record.get("ok") and record.get("risk") in ["medium", "high"]:
                            # Convert to ShareGPT format for MLX/llama.cpp training
                            system_msg = f"Execute skill {record.get('skill')} operation {record.get('operation')}."
                            user_msg = json.dumps(record.get("args", {}))
                            assistant_msg = json.dumps(record.get("artifacts", [])) # Simplified
                            
                            # In a real scenario, we'd retrieve the exact prompt/response from a prompt logger
                            dataset.append({
                                "messages": [
                                    {"role": "system", "content": system_msg},
                                    {"role": "user", "content": user_msg},
                                    {"role": "assistant", "content": assistant_msg}
                                ]
                            })
                    except Exception:
                        continue
                        
            if not dataset:
                return SkillResult(ok=False, error="No suitable high-signal examples found to distill.")
                
            with open(out_file, "w") as f:
                for item in dataset:
                    f.write(json.dumps(item) + "\n")
                    
            return SkillResult(ok=True, data={"exported_records": len(dataset), "file": str(out_file)})
            
        except Exception as e:
            return SkillResult(ok=False, error=str(e))
