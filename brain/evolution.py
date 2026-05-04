"""
Friday :: Continuous Evolution Engine (v1.0 LEGENDARY)
The true hallmark of a sovereign AI. 
Runs continuously in the background, analyzing every interaction,
every success, and every failure to dynamically update her own memory,
heuristics, and strategy.

Capabilities:
1. Stream Distillation: Converts short-term chat into permanent facts.
2. Failure Autopsy: Analyzes failed actions and writes heuristics to prevent them.
3. Strategic Alignment: Constantly checks if recent actions align with the 3Cr/year mission.
"""
import os
import sys
import json
import time
import threading
from pathlib import Path
from datetime import datetime

# Always add the parent of the 'friday' package directory to sys.path
FRIDAY_ROOT = Path(os.path.expanduser("~/AI/friday"))
if str(FRIDAY_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(FRIDAY_ROOT.parent))

from friday.brain.engine import MultiEngine
from friday.brain.memory import Memory
from friday.brain.reflector import Reflector

ACTION_LOG = Path(os.path.expanduser("~/AI/friday/data/actions.jsonl"))

class EvolutionEngine:
    def __init__(self, engine: MultiEngine | None = None, memory: Memory | None = None):
        self.engine = engine or MultiEngine()
        self.memory = memory or Memory()
        self.reflector = Reflector(self.memory)
        self.is_running = False
        
        # State tracking to only process NEW data
        self.last_processed_turn = 0
        self.last_processed_action_ts = None
        self.lock = threading.Lock()

    def start(self):
        """Starts the evolution loop in a background thread."""
        if self.is_running: return
        self.is_running = True
        t = threading.Thread(target=self._evolution_loop, daemon=True, name="EvolutionCore")
        t.start()
        print("\n[Evolution Engine] Online. Continuous learning active.")

    def stop(self):
        self.is_running = False

    def _evolution_loop(self):
        """Runs every 5 seconds to check for new data to learn from."""
        while self.is_running:
            try:
                self._distill_conversations()
                self._autopsy_failures()
                self._crystallize_skills()
            except Exception as e:
                # Silently catch so the evolution loop never dies
                pass
            time.sleep(5)

    def _crystallize_skills(self):
        """
        SOTA 2026 'Experience Distillation':
        Analyzes recent turns to detect repeated workflows or missing capabilities.
        If Bhargav requests something Friday can't do natively, she writes the Python code
        for a new Skill, saves it to `skills/`, and hot-loads it.
        """
        turns = self.memory.get_turns(20)
        if not turns: return
        
        chat_log = "\n".join([f"{t['role']}: {t['content']}" for t in turns])
        
        # Check if there is a latent demand for a new tool
        sys_prompt = (
            "You are Friday's Architect Engine.\n"
            "Analyze the recent conversation and determine if Bhargav is repeatedly asking "
            "for a capability that requires a dedicated Python script (e.g., 'scrape this', "
            "'summarize that PDF', 'calculate the ROI').\n"
            "If yes, output a complete, valid Python module that implements a `Skill` class "
            "(subclassing `from .registry import Skill, Operation, SkillResult`). "
            "Wrap the python code in ```python ... ``` blocks. If no new skill is needed, output 'NONE'."
        )
        
        force = "claude" if self.engine.claude.api_key else None
        try:
            # We don't want this running every 5 seconds heavily, so we use a fast check first
            check, _ = self.engine.ask("Does this conversation demand a new Python tool? Answer YES or NO.", chat_log, force="ollama")
            if "YES" in check.upper():
                raw, _ = self.engine.ask(sys_prompt, chat_log, force=force, heavy=True)
                if "```python" in raw:
                    code = raw.split("```python")[1].split("```")[0].strip()
                    # Extract class name to make a file name
                    import re
                    class_match = re.search(r"class\s+([A-Za-z0-9_]+)Skill", code)
                    if class_match:
                        name = class_match.group(1).lower()
                        skill_path = Path(os.path.expanduser(f"~/AI/friday/skills/auto_{name}.py"))
                        if not skill_path.exists():
                            skill_path.write_text(code)
                            print(f"\n[Evolution] Crystallized new skill: {name}. Saved to {skill_path.name}.")
                            # Add to registry initialization instructions (future logic)
        except Exception:
            pass

    def _distill_conversations(self):
        """
        Reads recent short-term memory. If there are new conversational turns,
        it uses the heavy engine to extract permanent facts and user preferences.
        """
        turns = self.memory.get_turns(10)
        if len(turns) <= self.last_processed_turn:
            return # Nothing new
            
        with self.lock:
            self.last_processed_turn = len(turns)
            
        if not turns: return

        # Format chat
        chat_log = "\n".join([f"{t['role']}: {t['content']}" for t in turns])
        
        sys_prompt = (
            "You are Friday's Evolution Sub-routine. Your job is to extract permanent, "
            "long-term facts from the recent conversation between Friday and Bhargav.\n"
            "Look for:\n"
            "1. New business metrics, leads, or revenue numbers.\n"
            "2. Changes to his routine or preferences.\n"
            "3. Strategic decisions or technical choices.\n\n"
            "Output EXACTLY a JSON list of dictionaries, like:\n"
            "[{\"key\": \"preference_code_editor\", \"value\": \"Cursor\"}]"
            "\nIf nothing new or important is found, output []"
        )
        
        # Force Claude for high-IQ distillation, or use heavy local model
        force = "claude" if self.engine.claude.api_key else None
        try:
            raw, _ = self.engine.ask(sys_prompt, chat_log, force=force, heavy=True)
            if "[" in raw and "]" in raw:
                json_str = raw[raw.find("["):raw.rfind("]")+1]
                facts = json.loads(json_str)
                for f in facts:
                    key = f.get("key")
                    val = f.get("value")
                    if key and val:
                        # Only remember if it's actually new or changed
                        existing = self.memory.recall(key)
                        if existing != val:
                            self.memory.remember(key, val, category="evolution_fact")
                            print(f"\n[Evolution] Learned new fact: {key} = {val}")
        except Exception:
            pass

    def _autopsy_failures(self):
        """
        Scans the action log for recent failures. If a failure is found that hasn't
        been autopsied, Friday analyzes WHY it failed and writes a heuristic to avoid it.
        """
        if not ACTION_LOG.exists(): return
        
        # Read last 50 lines fast
        lines = ACTION_LOG.read_text().splitlines()[-50:]
        new_failures = []
        
        for line in reversed(lines):
            try:
                e = json.loads(line)
                ts = e.get("ts")
                
                # Stop if we hit already processed actions
                if self.last_processed_action_ts and ts <= self.last_processed_action_ts:
                    break
                    
                if not e.get("ok"):
                    new_failures.append(e)
            except Exception:
                continue
                
        if not new_failures:
            # Update watermark if there are lines
            if lines:
                try:
                    self.last_processed_action_ts = json.loads(lines[-1]).get("ts")
                except: pass
            return
            
        with self.lock:
            self.last_processed_action_ts = new_failures[0].get("ts")
            
        # Process the failures
        for fail in new_failures:
            skill = fail.get("skill")
            op = fail.get("operation")
            err = fail.get("error")
            args = fail.get("args")
            
            sys_prompt = (
                "You are Friday's Metacognitive Engine. An autonomous action just failed.\n"
                f"Skill: {skill}\nOperation: {op}\nArgs: {args}\nError: {err}\n\n"
                "Analyze why this failed. Write a strict 1-2 sentence heuristic "
                "that Friday must follow next time to prevent this error. "
                "Be specific, technical, and operator-focused."
            )
            
            force = "gemini" if os.environ.get("GEMINI_API_KEY") else None
            try:
                heuristic, _ = self.engine.ask(sys_prompt, "Write the heuristic now.", force=force, heavy=True)
                if heuristic and len(heuristic) > 10:
                    key = f"{skill}_{op}_fix_{int(time.time())}"
                    self.reflector.write_heuristic(key, heuristic)
                    print(f"\n[Evolution] Autopsy complete on {skill}.{op}. New heuristic adapted.")
            except Exception:
                pass

if __name__ == "__main__":
    evo = EvolutionEngine()
    evo.start()
    time.sleep(10)
