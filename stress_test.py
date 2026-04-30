import os
import sys
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

FRIDAY_ROOT = Path(os.path.expanduser("~/AI/friday"))

def run_stress():
    print("╔══════════════════════════════════════╗")
    print("║  FRIDAY :: 10-MINUTE STRESS TEST     ║")
    print("║  Pushing Apple Silicon to capacity   ║")
    print("╚══════════════════════════════════════╝")
    
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=10)
    print(f"Started at: {start_time.strftime('%H:%M:%S')}")
    print(f"Will finish at: {end_time.strftime('%H:%M:%S')}")
    
    queries = [
        # Heavy reasoning (uses gemma3:4b via --heavy)
        ["--heavy", "Write a highly detailed, 2000-word architectural design document for a distributed microservices platform using Go and gRPC."],
        
        # Heavy research/planning (forces multi-threading and web fetch)
        ["--heavy", "Design a complete automated trading system using local LLMs and Interactive Brokers API. Include risk management, data ingestion, and execution loops."],
        
        # Vision/Context (forces screenshot capture and vision inference)
        ["", "Take a screenshot of my screen right now. Describe every single window, text, and icon you see in extreme detail."],
        
        # Synthesis
        ["--heavy", "Explain the complete history of the Roman Empire's economic policies and how they relate to modern inflation, using specific dates and figures."],
        
        # Fast inference
        ["", "Write a Python script that automates the deployment of a Dockerized application to an AWS EC2 instance using GitHub Actions."]
    ]
    
    iteration = 1
    log_file = FRIDAY_ROOT / "stress_test.log"
    
    with open(log_file, "w") as f:
        f.write(f"Stress test started at {start_time}\n")
        
        while datetime.now() < end_time:
            for params in queries:
                if datetime.now() >= end_time:
                    break
                
                flag = params[0]
                q = params[1]
                
                print(f"\n[Iteration {iteration}] Executing task: {q[:50]}...")
                f.write(f"\n--- Iteration {iteration} | Query: {q} ---\n")
                
                cmd = ["python3", "cli.py", "ask"]
                if flag:
                    cmd.append(flag)
                cmd.append(q)
                
                env = os.environ.copy()
                env["PYTHONPATH"] = str(FRIDAY_ROOT.parent)
                
                t0 = time.time()
                # Run via CLI to test the full pipeline end-to-end
                try:
                    result = subprocess.run(
                        cmd,
                        cwd=str(FRIDAY_ROOT),
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=300 # 5 min timeout per heavy query
                    )
                    duration = time.time() - t0
                    print(f"Task completed in {duration:.1f} seconds. Output: {len(result.stdout)} chars.")
                    f.write(f"Time taken: {duration:.1f}s\n")
                    f.write(f"Output:\n{result.stdout}\n")
                    if result.stderr:
                        f.write(f"Errors:\n{result.stderr}\n")
                except subprocess.TimeoutExpired:
                    print(f"Task timed out after 300s.")
                    f.write("Task timed out.\n")
                except Exception as e:
                    print(f"Task failed: {e}")
                    f.write(f"Task failed: {e}\n")
                    
                iteration += 1

    print(f"\n[!] Stress test completed successfully at {datetime.now().strftime('%H:%M:%S')}.")
    print(f"Check {log_file} for full details.")

if __name__ == "__main__":
    run_stress()
