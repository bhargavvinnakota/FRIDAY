import asyncio
import sys
import os
import time
import subprocess
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/AI"))

from friday.brain.v2_daemon import OmniDaemon
from friday.brain.evolution import EvolutionEngine

async def run_omni_infinite_loop():
    print("===================================================")
    print(" FRIDAY V2.5 OMNI-DAEMON :: INFINITE R&D LOOP")
    print("===================================================")
    
    # 1. Spin up the Core Daemon
    print("[Omni-Loop] Initializing OmniDaemon...")
    daemon = OmniDaemon()
    print("[Omni-Loop] OmniDaemon initialized. Starting run loop...")
    daemon_task = asyncio.create_task(daemon.run())
    
    # 2. Spin up the Evolution Engine for continuous learning
    evo = EvolutionEngine(engine=daemon.engine, memory=daemon.memory)
    evo.start()
    
    # 3. Spin up the Auto-Upgrade Engine
    from friday.brain.v2_auto_upgrade import AutoUpgradeEngine
    upgrader = AutoUpgradeEngine()
    
    iteration = 1
    log_file = Path("/Users/bhargav/AI/friday/logs/omni_loop_activity.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    while True:
        with open(log_file, "a") as f:
            f.write(f"\n[Omni-Loop] Cycle {iteration} - {time.ctime()}\n")
            
            f.write("[Omni-Loop] -> Testing environment integrity...\n")
            test_res = subprocess.run(
                ["/Users/bhargav/AI/friday/v2_build/sandbox_venv/bin/python3", "/Users/bhargav/AI/friday/v2_build/validation_run_v3.py"],
                capture_output=True, text=True
            )
            if test_res.returncode == 0:
                f.write("    ✅ Tests Pass: System Stable.\n")
            else:
                f.write("    ❌ Tests Failed: Engaging Self-Heal Protocol.\n")
            
            f.write("[Omni-Loop] -> Initiating Auto-Upgrade Conversation Cycle...\n")
            try:
                # This actually 'talks' to Friday and builds new code if she fails
                upgraded = await upgrader.run_upgrade_cycle()
                if upgraded:
                    f.write("    🚀 Capability Upgraded: New Skill Crystallized.\n")
                else:
                    f.write("    ✅ Friday remains competent for the current challenge.\n")
            except Exception as e:
                f.write(f"    ⚠️ Upgrade Error: {e}\n")
                
            f.write("[Omni-Loop] -> Optimizing internal heuristics...\n")
            evo._autopsy_failures()
            f.write("    ⚙️ Heuristics optimized.\n")
            
        print(f"Completed Omni-Loop Cycle {iteration}. Logged.")
        iteration += 1
        
        # Reduced to 5 minutes for faster "continuous" improvement
        for i in range(30): # 300 seconds = 30 * 10
            if i % 6 == 0:
                print(f"[Omni-Loop] Heartbeat: Loop Cycle {iteration} pending ({(30-i)*10}s remaining)...")
            await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(run_omni_infinite_loop())
    except KeyboardInterrupt:
        print("\nOmni-Loop Terminated by Root.")
