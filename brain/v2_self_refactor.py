"""
Friday V2.6 :: Self-Refactor Engine
Autonomously scans Friday's source code, identifies architectural debt,
and applies optimizations via the SelfRefactorSkill.
"""
import os
import sys
import random
import asyncio
from pathlib import Path

# Add root to path
sys.path.insert(0, os.path.expanduser("~/AI"))

from friday.brain.engine import MultiEngine
from friday.brain.orchestrator import Orchestrator
from friday.brain.memory import Memory
from friday.skills import get_registry
from friday.brain.state_relay import update_hud_state

class SelfRefactorEngine:
    def __init__(self):
        self.engine = MultiEngine()
        self.memory = Memory()
        self.skills = get_registry()
        self.orch = Orchestrator(self.engine, self.memory)

    async def run_refactor_cycle(self):
        print("[Self-Refactor] Initiating code analysis cycle...")
        update_hud_state(status="REFACTORING", friday_output="Analyzing source for debt...")
        
        # 1. List all source files
        reg = get_registry()
        refactor_skill = reg.get("self_refactor")
        if not refactor_skill:
            print("[Self-Refactor] ❌ Error: self_refactor skill not found.")
            return False
            
        res_files = refactor_skill.invoke("list_source_files")
        if not res_files.ok:
            print(f"[Self-Refactor] ❌ Failed to list files: {res_files.error}")
            return False
            
        files = res_files.data.get("files", [])
        if not files:
            print("[Self-Refactor] No source files found.")
            return False
            
        # 2. Pick a random file to analyze (or target by priority)
        # Priority targets: skills, brain, core
        priority_files = [f for f in files if "skills/" in f or "brain/" in f]
        target_file = random.choice(priority_files if priority_files else files)
        print(f"[Self-Refactor] Target identified: {target_file}")
        
        # 3. Scan for debt
        print(f"[Self-Refactor] Scanning {target_file} for debt...")
        update_hud_state(status="REFACTORING", friday_output=f"Scanning {target_file}...")
        res_scan = await asyncio.to_thread(refactor_skill.invoke, "scan_for_debt", file_path=target_file)
        if not res_scan.ok:
            print(f"[Self-Refactor] ❌ Scan failed: {res_scan.error}")
            update_hud_state(status="IDLE", friday_output=f"Scan failed: {target_file}")
            return False
            
        analysis = res_scan.data.get("analysis", "")
        print(f"[Self-Refactor] Analysis Results:\n{analysis[:300]}...")
        
        # 4. Decide if optimization is worth it (Heuristic)
        # For now, we always try to optimize if debt is found.
        print(f"[Self-Refactor] Generating optimization for {target_file}...")
        update_hud_state(status="REFACTORING", 
                         friday_output=f"Optimizing {target_file}...",
                         telemetry={"activity": "code_gen", "target": target_file})
        
        res_opt = await asyncio.to_thread(refactor_skill.invoke, 
                                          "apply_optimization", 
                                          file_path=target_file, 
                                          optimization_goal=analysis)
                                          
        if res_opt.ok:
            print(f"✅ [Self-Refactor] Successfully optimized {target_file}.")
            update_hud_state(status="IDLE", friday_output=f"Optimization complete: {target_file}")
            print(f"    -> Backup created at: {res_opt.data.get('backup')}")
            return True
        else:
            print(f"❌ [Self-Refactor] Optimization failed for {target_file}: {res_opt.error}")
            update_hud_state(status="IDLE", friday_output=f"Refactor failed: {target_file}")
            return False

if __name__ == "__main__":
    engine = SelfRefactorEngine()
    asyncio.run(engine.run_refactor_cycle())
