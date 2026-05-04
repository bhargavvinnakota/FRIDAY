#!/usr/bin/env python3
"""
Friday :: Neural Evolution Crawler (v2: The Hive Mind Awakening)
A continuous, slow-burn daemon that slowly ingests the GitHub ecosystem AND 
autonomously interrogates Oracles to deepen its existing knowledge.
Mimics human learning: slow absorption, structured into the Vault, embedded into LanceDB.
"""
import os
import sys
from pathlib import Path

# Add the /Users/bhargav/AI directory to path so python can find the 'friday' package
sys.path.insert(0, "/Users/bhargav/AI")

import time
import random
import logging
from pathlib import Path

from friday.skills.broker import BrokerSkill
from friday.skills.oracle import OracleSkill

FRIDAY_ROOT = Path(os.path.expanduser("~/AI/friday"))
QUEUE_FILE = FRIDAY_ROOT / "data" / "evolution_queue.txt"
LOG_FILE = FRIDAY_ROOT / "logs" / "evolution_crawler.log"
VAULT_DIR = FRIDAY_ROOT / "vault"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Time between ingestions (15-45 minutes)
MIN_DELAY = 15 * 60
MAX_DELAY = 45 * 60

def get_next_target() -> str | None:
    if not QUEUE_FILE.exists():
        return None
    with open(QUEUE_FILE, "r") as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
    if not lines:
        return None
    target = lines[0]
    with open(QUEUE_FILE, "w") as f:
        f.write("\n".join(lines[1:]))
    return target

def random_vault_topic() -> str | None:
    """Picks a random file from the Vault to 'deep think' about."""
    if not VAULT_DIR.exists():
        return None
    files = list(VAULT_DIR.glob("*.md"))
    if not files:
        return None
    # Avoid picking the master index or already refined oracle notes
    valid_files = [f for f in files if not f.name.startswith("oracle_") and not f.name.startswith("awesome_master")]
    if not valid_files:
        return None
    return random.choice(valid_files).stem

def crawl_cycle():
    # 50% chance to ingest a new repo, 50% chance to 'Deep Think' via an Oracle
    action = random.choices(["ingest", "deep_think"], weights=[0.4, 0.6])[0]
    
    broker = BrokerSkill()
    oracle = OracleSkill()

    if action == "ingest":
        target = get_next_target()
        if not target:
            logging.info("Queue empty. Switching to Deep Think mode.")
            action = "deep_think"
        else:
            logging.info(f"[INGEST] Starting ingestion for: {target}")
            try:
                res = broker.op_ingest_repo(url=target)
                if res.ok:
                    file_name = res.data.get("file")
                    logging.info(f"  ✓ Saved to Vault: {file_name}")
                else:
                    logging.error(f"  ✗ Ingestion failed: {res.error}")
            except Exception as e:
                logging.error(f"  ✗ Critical error during crawl: {e}")

    if action == "deep_think":
        topic = random_vault_topic()
        if not topic:
            logging.info("Vault empty. Sleeping.")
        else:
            logging.info(f"[DEEP THINK] Interrogating Oracles about: {topic}")
            try:
                # Friday decides which oracle to use based on the topic name (heuristic)
                domain = "code"
                if any(x in topic.lower() for x in ["trading", "finance", "alpha", "market"]):
                    domain = "finance"
                elif any(x in topic.lower() for x in ["math", "algo", "quant"]):
                    domain = "math"
                
                query = f"I am reviewing the architectural concepts of '{topic}'. What are the undocumented hacks, zero-day strategies, or absolute expert-level truths regarding this technology that 99% of developers miss?"
                
                res = oracle.op_summon_and_interrogate(domain=domain, query=query)
                if res.ok:
                    logging.info(f"  ✓ Oracle Synthesis complete for {topic}. Saved to {res.data.get('vault_file')}")
                else:
                    logging.error(f"  ✗ Oracle Interrogation failed: {res.error}")
            except Exception as e:
                logging.error(f"  ✗ Critical error during Deep Think: {e}")

    # Sleep to simulate natural absorption
    delay = random.randint(MIN_DELAY, MAX_DELAY)
    logging.info(f"Cycle complete. Absorbing knowledge for {delay // 60} minutes before next trigger.")
    time.sleep(delay)

def main():
    logging.info("Neural Evolution Crawler v2 Started. Infinite Hive Mind evolution online.")
    print("Infinite Evolution Crawler online. Friday is now autonomous. See logs/evolution_crawler.log")
    
    while True:
        crawl_cycle()

if __name__ == "__main__":
    main()
