"""
Friday :: Auto Shorts Generator Skill
Provides F.R.I.D.A.Y. the ability to generate YouTube Shorts autonomously.
This acts as a bridge to the isolated 'video Generator' engine.
"""

import os
import json
import subprocess
from pathlib import Path
from termcolor import colored
from typing import Optional

from .registry import Skill, Operation, SkillResult, Risk

class AutoShortsSkill(Skill):
    name = "auto_shorts"
    description = "Generates vertical short-form videos with voiceovers and captions."

    def _register_operations(self) -> None:
        self.register_op(Operation(
            name="generate_short",
            description="Generates a YouTube Short via the video Generator backend.",
            fn=self.generate_short,
            risk="medium",
            requires_confirm=True,
            input_schema={
                "topic": "The subject matter for the short video.",
                "voice": "Optional voice ID (e.g., 'en-US-JennyNeural').",
                "custom_prompt": "Optional extra instructions for the script."
            }
        ))

    def generate_short(self, topic: str, voice: str = "en-US-JennyNeural", custom_prompt: Optional[str] = None) -> SkillResult:
        """
        Executes the ShortsGenerator logic via a headless subprocess.
        """
        # Path to the generator repo and its virtual environment
        generator_dir = Path(os.path.expanduser("~/video Generator/Backend"))
        venv_python = Path(os.path.expanduser("~/video Generator/venv/bin/python3"))
        
        if not generator_dir.exists() or not venv_python.exists():
            return SkillResult(ok=False, error="Video generator engine or venv not found.")
            
        # We write a temporary headless runner script inside the generator directory
        headless_script = generator_dir / "friday_headless_runner.py"
        script_code = f'''
import os
import sys
import json

from gpt import generate_script
from video import save_video
from classes.Shorts import Short

def run():
    topic = "{topic}"
    voice = "{voice}"
    custom_prompt = """{custom_prompt or ''}"""
    
    print(f"Generating script for: {{topic}}")
    try:
        # 1. Generate Script
        script = generate_script(topic, custom_prompt)
        
        # 2. Build Short Object
        short = Short(script, voice=voice)
        short.extract_music_theme()
        
        # 3. Compile Video
        output_path = save_video(short)
        
        result = {{"ok": True, "path": output_path}}
        print("FRIDAY_RESULT:" + json.dumps(result))
    except Exception as e:
        result = {{"ok": False, "error": str(e)}}
        print("FRIDAY_RESULT:" + json.dumps(result))
        sys.exit(1)

if __name__ == "__main__":
    run()
'''
        headless_script.write_text(script_code)
        
        try:
            # Execute the headless script using the isolated venv
            print(colored(f"[AutoShorts] Booting isolated engine for topic: {topic}", "magenta"))
            process = subprocess.run(
                [str(venv_python), str(headless_script)],
                cwd=str(generator_dir),
                capture_output=True,
                text=True,
                timeout=600  # Video generation takes time
            )
            
            # Clean up runner script
            if headless_script.exists():
                headless_script.unlink()
                
            if process.returncode != 0:
                return SkillResult(ok=False, error=f"Engine failed: {process.stderr}")
                
            # Parse F.R.I.D.A.Y. result tag from stdout
            output_lines = process.stdout.split("\\n")
            for line in reversed(output_lines):
                if line.startswith("FRIDAY_RESULT:"):
                    data = json.loads(line.replace("FRIDAY_RESULT:", ""))
                    if data.get("ok"):
                        return SkillResult(
                            ok=True, 
                            data={"path": data.get("path")},
                            artifacts=[data.get("path")]
                        )
                    else:
                        return SkillResult(ok=False, error=data.get("error"))
            
            return SkillResult(ok=False, error=f"No valid result returned. Output: {process.stdout}")
            
        except subprocess.TimeoutExpired:
            return SkillResult(ok=False, error="Video generation timed out.")
        except Exception as e:
            return SkillResult(ok=False, error=f"Unexpected failure: {str(e)}")
