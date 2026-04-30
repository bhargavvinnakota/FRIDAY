import sys
import os
import time
import json
from pathlib import Path

# Fix path to run directly
sys.path.insert(0, os.path.expanduser("~/AI"))

from friday.brain.mission import MissionRunner, new_mission, load_mission, Step
from friday.brain.engine import MultiEngine
from friday.brain.memory import Memory
from friday.skills import get_registry

class Reporter:
    def ok(self, cat, msg):
        print(f"  ✅ [{cat}] {msg}")
    def bad(self, cat, msg):
        print(f"  ❌ [{cat}] {msg}")
    def section(self, msg):
        print(f"\n════════════════════════════════════════════════════════════")
        print(f"  {msg}")
        print(f"════════════════════════════════════════════════════════════")

def run_v2_tests():
    R = Reporter()
    R.section("V2 MISSION ORCHESTRATOR")
    
    try:
        eng = MultiEngine()
        mem = Memory()
        reg = get_registry()
        runner = MissionRunner(engine=eng, memory=mem, skill_registry=reg)
        
        # Test 1: Create a simple mission and plan it
        R.section("1. MISSION PLANNING")
        m = new_mission(goal="Find the current price of Bitcoin and summarize the sentiment.", created_by="test")
        
        t0 = time.time()
        success = runner.plan(m)
        dt = time.time() - t0
        
        if success and m.status == "running" and len(m.steps) > 0:
            R.ok("planner", f"Decomposed goal into {len(m.steps)} steps in {dt:.1f}s")
            for s in m.steps:
                print(f"      Step {s.id}: {s.skill}.{s.operation} -> deps: {s.depends_on}")
        else:
            R.bad("planner", f"Failed to plan mission. Status: {m.status}, Notes: {m.notes}")
            return
            
        # Test 2: Execute the mission DAG sequentially
        R.section("2. MISSION EXECUTION")
        t0 = time.time()
        m = runner.run(m)
        dt = time.time() - t0
        
        if m.status == "done":
            R.ok("runner", f"Executed {len(m.steps)} steps successfully in {dt:.1f}s")
            for s in m.steps:
                if s.status == "done":
                    R.ok(f"step_{s.id}", f"{s.skill}.{s.operation} completed.")
                else:
                    R.bad(f"step_{s.id}", f"Status is {s.status}")
        else:
            R.bad("runner", f"Mission execution halted with status: {m.status}. Notes: {m.notes}")
            for s in m.steps:
                if s.status == "failed":
                    print(f"      Step {s.id} failed: {s.error}")
            
        # Test 3: Synthesizer final output check
        R.section("3. MISSION REPORT")
        if m.final_report:
            R.ok("synthesizer", f"Generated final report ({len(m.final_report)} chars)")
            print("\n--- FINAL REPORT ---")
            print(m.final_report)
            print("--------------------\n")
        else:
            R.bad("synthesizer", "No final report generated")

        # Test 4: Intelligence Skill Direct Invocation
        R.section("4. INTELLIGENCE SKILL")
        from friday.skills.intelligence import IntelligenceSkill
        intel = IntelligenceSkill()
        intel._register_operations()
        
        t0 = time.time()
        r = intel.op_quick_brief(topic="SpaceX recent launches")
        dt = time.time() - t0
        if r.ok:
            R.ok("intelligence", f"quick_brief executed in {dt:.1f}s")
            print(f"      Brief: {r.data.get('brief', '')[:200]}...")
        else:
            R.bad("intelligence", f"quick_brief failed: {r.error}")

    except Exception as e:
        R.bad("system", f"V2 test exception: {e}")

if __name__ == "__main__":
    run_v2_tests()
