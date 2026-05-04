"""
Friday :: Self-Refactor Skill
Enables Friday to analyze her own code and optimize it autonomously.
"""
from __future__ import annotations
import os
import sys
import subprocess
import shutil
from pathlib import Path
from .registry import Skill, Operation, SkillResult

PROJECT_ROOT = Path(os.path.expanduser("~/AI/friday"))
BACKUP_DIR = PROJECT_ROOT / "vault" / "backups" / "code"

class SelfRefactorSkill(Skill):
    name = "self_refactor"
    description = "Analyze and optimize Friday's own source code for better performance and cleaner architecture."

    def _register_operations(self) -> None:
        self.register_op(Operation("scan_for_debt", "Analyze a file for architectural debt or inefficiencies.",
                                   fn=self.op_scan_for_debt, risk="low"))
        self.register_op(Operation("apply_optimization", "Generate and apply an optimized version of a source file.",
                                   fn=self.op_apply_optimization, risk="high", requires_confirm=True))
        self.register_op(Operation("list_source_files", "List all relevant Python source files in the project.",
                                   fn=self.op_list_source_files, risk="low"))

    def op_list_source_files(self, **_) -> SkillResult:
        files = []
        for p in PROJECT_ROOT.rglob("*.py"):
            if "venv" in str(p) or "__pycache__" in str(p): continue
            files.append(str(p.relative_to(PROJECT_ROOT)))
        return SkillResult(ok=True, data={"files": sorted(files)})

    def op_scan_for_debt(self, file_path: str = "", **_) -> SkillResult:
        if not file_path: return SkillResult(ok=False, error="file_path required")
        full_path = PROJECT_ROOT / file_path
        if not full_path.exists(): return SkillResult(ok=False, error="File not found")
        
        content = full_path.read_text()
        
        from friday.brain.engine import MultiEngine
        eng = MultiEngine()
        
        sys_p = "You are a Senior AI Architect. Analyze the following code for inefficiencies, architectural debt, or performance bottlenecks. Be extremely critical."
        user_p = f"FILE: {file_path}\n\nCODE:\n```python\n{content}\n```\n\nIdentify 3 specific areas for improvement."
        
        try:
            analysis, engine = eng.ask(sys_p, user_p, heavy=True)
            return SkillResult(ok=True, data={"analysis": analysis, "engine_used": engine})
        except Exception as e:
            return SkillResult(ok=False, error=str(e))

    def op_apply_optimization(self, file_path: str = "", optimization_goal: str = "", **_) -> SkillResult:
        if not file_path: return SkillResult(ok=False, error="file_path required")
        full_path = PROJECT_ROOT / file_path
        if not full_path.exists(): return SkillResult(ok=False, error="File not found")
        
        content = full_path.read_text()
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup_path = BACKUP_DIR / f"{Path(file_path).name}.bak"
        shutil.copy2(full_path, backup_path)
        
        from friday.brain.engine import MultiEngine
        eng = MultiEngine()
        
        sys_p = (
            "You are Friday's Lead Developer. Refactor the provided code to be more efficient, "
            "idiomatic, and robust based on the optimization goal. "
            "STRICT: Return ONLY the raw Python code in a ```python block. No explanations."
        )
        user_p = f"FILE: {file_path}\nGOAL: {optimization_goal}\n\nORIGINAL CODE:\n```python\n{content}\n```"
        
        try:
            code_raw, engine = eng.ask(sys_p, user_p, heavy=True)
            if "```python" in code_raw:
                new_code = code_raw.split("```python")[1].split("```")[0].strip()
                
                # Validation Step 1: Syntax Check
                temp_file = full_path.with_suffix(".py.tmp")
                temp_file.write_text(new_code)
                
                res = subprocess.run([sys.executable, "-m", "py_compile", str(temp_file)], capture_output=True)
                if res.returncode != 0:
                    temp_file.unlink()
                    return SkillResult(ok=False, error=f"Generated code has syntax errors: {res.stderr.decode()}")
                
                # Validation Step 2: Behavioral Check (Run Smoke Tests)
                # We swap the file temporarily to run the project's own test suite.
                print(f"[Self-Refactor] Running behavioral validation for {file_path}...")
                original_content = full_path.read_text()
                try:
                    full_path.write_text(new_code)
                    # Run 'friday test' via subprocess
                    test_res = subprocess.run(["friday", "test"], capture_output=True, text=True)
                    if test_res.returncode != 0:
                        # Behavioral failure - revert immediately
                        full_path.write_text(original_content)
                        temp_file.unlink()
                        return SkillResult(ok=False, error=f"Behavioral validation failed (friday test). Reverting. Output: {test_res.stdout[-500:]}")
                    print(f"[Self-Refactor] Behavioral validation passed.")
                except Exception as test_err:
                    full_path.write_text(original_content)
                    temp_file.unlink()
                    return SkillResult(ok=False, error=f"Error during behavioral validation: {test_err}")

                # Apply (already written in try block, but we finalize here)
                temp_file.unlink()
                
                return SkillResult(ok=True, data={
                    "message": "Optimization applied and validated successfully.",
                    "backup": str(backup_path),
                    "engine_used": engine
                })
            else:
                return SkillResult(ok=False, error="No code block found in LLM response.")
        except Exception as e:
            # Revert if something went wrong before final write
            if backup_path.exists() and not full_path.read_text() == content:
                shutil.copy2(backup_path, full_path)
            return SkillResult(ok=False, error=str(e))
