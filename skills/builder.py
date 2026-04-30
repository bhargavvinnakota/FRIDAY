from __future__ import annotations
import os
import subprocess
from pathlib import Path
from .registry import Skill, Operation, SkillResult

class BuilderSkill(Skill):
    name = "builder"
    description = "The absolute master creator. Grants Friday the ability to write code, execute bash scripts, and autonomously build full applications, platforms, or agencies from scratch."

    def _register_operations(self) -> None:
        self.register_op(Operation(
            name="run_shell",
            description="Execute any bash command on the Mac. Used for installing dependencies, running scripts, spinning up servers, or git operations.",
            fn=self.op_run_shell,
            risk="high",
            input_schema={"command": "The exact bash command to run.", "cwd": "Optional: working directory to run the command in."}
        ))
        self.register_op(Operation(
            name="write_file",
            description="Write complete code, configurations, or text to a specific file path. Overwrites if exists.",
            fn=self.op_write_file,
            risk="medium",
            input_schema={"file_path": "Absolute path to the file.", "content": "The full string content to write."}
        ))
        self.register_op(Operation(
            name="read_file",
            description="Read the contents of a file to understand existing code or configurations.",
            fn=self.op_read_file,
            risk="low",
            input_schema={"file_path": "Absolute path to the file."}
        ))
        self.register_op(Operation(
            name="mkdir",
            description="Create a directory (and all parent directories).",
            fn=self.op_mkdir,
            risk="low",
            input_schema={"dir_path": "Absolute path to the directory to create."}
        ))

    def op_run_shell(self, command: str, cwd: str = None, **_) -> SkillResult:
        if cwd and not os.path.exists(cwd):
            return SkillResult(ok=False, error=f"Directory {cwd} does not exist.")
            
        try:
            res = subprocess.run(
                command, 
                shell=True, 
                cwd=cwd or os.path.expanduser("~"), 
                capture_output=True, 
                text=True, 
                timeout=120
            )
            output = res.stdout if res.returncode == 0 else res.stderr
            return SkillResult(
                ok=res.returncode == 0, 
                data={"exit_code": res.returncode, "output": output.strip()[:4000]}, 
                error=res.stderr.strip()[:1000] if res.returncode != 0 else None
            )
        except subprocess.TimeoutExpired:
            return SkillResult(ok=False, error="Command timed out after 120 seconds.")
        except Exception as e:
            return SkillResult(ok=False, error=str(e))

    def op_write_file(self, file_path: str, content: str, **_) -> SkillResult:
        try:
            path = Path(os.path.expanduser(file_path))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            return SkillResult(ok=True, data={"path": str(path), "bytes_written": len(content)}, artifacts=[str(path)])
        except Exception as e:
            return SkillResult(ok=False, error=str(e))

    def op_read_file(self, file_path: str, **_) -> SkillResult:
        try:
            path = Path(os.path.expanduser(file_path))
            if not path.exists():
                return SkillResult(ok=False, error=f"File {file_path} not found.")
            content = path.read_text()
            return SkillResult(ok=True, data={"content": content[:5000] + ("\n...[TRUNCATED]" if len(content) > 5000 else "")})
        except Exception as e:
            return SkillResult(ok=False, error=str(e))

    def op_mkdir(self, dir_path: str, **_) -> SkillResult:
        try:
            path = Path(os.path.expanduser(dir_path))
            path.mkdir(parents=True, exist_ok=True)
            return SkillResult(ok=True, data={"created": str(path)}, artifacts=[str(path)])
        except Exception as e:
            return SkillResult(ok=False, error=str(e))
