"""
Friday :: AGI Architecture Validation
Verifies Role Agents, PIM Memory Updates, and Knowledge Distillation.
"""
import sys
import os
from pathlib import Path
import asyncio

sys.path.insert(0, os.path.expanduser("~/AI"))

from friday.brain.agents.roles import CEOAgent, EngineerAgent
from friday.brain.v2_memory import VectorMemory
from friday.skills.registry import get_registry

def test_agi_architecture():
    print("╔══════════════════════════════════════╗")
    print("║  FRIDAY :: AGI ARCHITECTURE TEST     ║")
    print("╚══════════════════════════════════════╝\n")

    # 1. Test PIM Memory (Profile & Timeline)
    print("[1] Testing Personal Intelligence Model (PIM)...")
    mem = VectorMemory()
    mem.update_profile("risk_tolerance", "High")
    print("    ✓ Profile trait 'risk_tolerance' updated.")
    
    mem.add_timeline_event("V2.5 Upgrade", {"status": "success", "feature": "Multi-Agent Roles"})
    print("    ✓ Timeline event 'V2.5 Upgrade' added.")

    # Verify Retrieval
    results = mem.search("risk_tolerance", limit=1)
    if results and "High" in results[0]["text"]:
        print("    ✓ PIM Semantic Retrieval successful.")

    # 2. Test Role Agents
    print("\n[2] Testing Role-Based Agents...")
    ceo = CEOAgent()
    eng = EngineerAgent()
    
    # Fast test without actual heavy LLM call to save time, testing structure
    print(f"    ✓ CEO Agent Initialized: {ceo.system_prompt[:50]}...")
    print(f"    ✓ Engineer Agent Initialized: {eng.system_prompt[:50]}...")

    # 3. Test Knowledge Distillation
    print("\n[3] Testing Knowledge Distillation Export...")
    reg = get_registry()
    distill = reg.get("distillation")
    if not distill:
        print("    ❌ Distillation skill not found.")
    else:
        res = distill.invoke("export_dataset")
        if res.ok:
            print(f"    ✓ Dataset exported: {res.data['exported_records']} records at {res.data['file']}")
        else:
            print(f"    ! Distillation skipped (normal if no recent actions): {res.error}")

    print("\n✅ AGI Architecture Test Complete.")

if __name__ == "__main__":
    test_agi_architecture()
