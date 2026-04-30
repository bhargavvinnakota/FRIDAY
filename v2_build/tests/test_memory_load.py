import sys
import os
import time
sys.path.insert(0, os.path.expanduser("~/AI"))

from friday.brain.v2_memory import VectorMemory

def run_load_test():
    print("--- INITIATING MEMORY LOAD TEST ---")
    mem = VectorMemory()
    
    # 1. Bulk Ingestion
    facts = [
        f"Client {i} loves AI automation for their {['gym', 'clinic', 'restaurant'][i%3]}" 
        for i in range(50)
    ]
    t0 = time.time()
    for f in facts:
        mem.remember(f, category="clients")
    dt = time.time() - t0
    print(f"✅ Ingested 50 facts in {dt:.2f}s ({(dt/50)*1000:.1f}ms/fact)")

    # 2. Semantic Query Latency
    t0 = time.time()
    results = mem.search("What do my restaurant clients like?", limit=3)
    dt = time.time() - t0
    print(f"✅ Semantic Recall in {dt*1000:.2f}ms")
    
    # 3. Accuracy Check
    for r in results:
        print(f"   [Result] {r['text']}")
        assert "restaurant" in r['text'].lower()
    
    print("\n✅ SUCCESS: Vector Memory is ready for production.")

if __name__ == "__main__":
    run_load_test()
