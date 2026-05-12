#!/usr/bin/env python3
"""
Friday :: 10-Minute Ceiling Endurance Test
Sustained load for 600+ seconds: daemon running, continuous LLM calls,
parallel memory hammer, telegram pings, sensor sweeps — everything at once.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/AI"))

from friday.brain.engine import MultiEngine
from friday.brain.memory import Memory
from friday.brain.orchestrator import Orchestrator, Tool
from friday.actions import nexus, comms, computer
from friday.loops.heartbeat import sweep

FRIDAY = Path(os.path.expanduser("~/AI/friday"))
REPORT = FRIDAY / "data" / "endurance_report.json"

DURATION = 600  # 10 minutes

metrics = {
    "start": datetime.now().isoformat(),
    "duration_target_s": DURATION,
    "llm_calls": 0, "llm_errors": 0, "llm_total_s": 0.0,
    "mem_writes": 0, "mem_reads": 0, "mem_errors": 0,
    "nexus_snapshots": 0, "nexus_errors": 0,
    "telegram_pushes": 0, "telegram_errors": 0,
    "heartbeat_sweeps": 0, "heartbeat_errors": 0,
    "shell_calls": 0, "shell_errors": 0,
    "tool_routes": 0, "tool_errors": 0,
    "daemon_alive_checks": 0, "daemon_crashes": 0,
    "samples": [],  # periodic heartbeat samples
}

stop_flag = threading.Event()


def llm_worker(eng: MultiEngine):
    """Hammer the engine router with a mix of light queries."""
    qs = [
        "say online", "status one word", "alive?", "ping",
        "what time of day affects your tone?",
        "one word: ready or not",
    ]
    i = 0
    while not stop_flag.is_set():
        q = qs[i % len(qs)]
        i += 1
        t0 = time.time()
        try:
            r, u = eng.ask("You are Friday. Be terse.", q, force="ollama")
            metrics["llm_calls"] += 1
            metrics["llm_total_s"] += time.time() - t0
            if not r or "error" in u:
                metrics["llm_errors"] += 1
        except Exception:
            metrics["llm_errors"] += 1
        time.sleep(2)  # throttle so 10 min doesn't explode


def mem_worker(mem: Memory):
    """Continuous read+write on persistent memory."""
    i = 0
    while not stop_flag.is_set():
        try:
            mem.remember(f"endurance_k{i % 20}", f"v{i}", category="endurance")
            metrics["mem_writes"] += 1
            _ = mem.recall(f"endurance_k{i % 20}")
            metrics["mem_reads"] += 1
            mem.log_event("endurance_tick", {"i": i})
        except Exception:
            metrics["mem_errors"] += 1
        i += 1
        time.sleep(0.5)


def nexus_worker():
    """Exercise sensors continuously."""
    while not stop_flag.is_set():
        try:
            _ = nexus.snapshot()
            metrics["nexus_snapshots"] += 1
        except Exception:
            metrics["nexus_errors"] += 1
        time.sleep(5)


def telegram_worker():
    """Silent pings — don't spam the user, just validate the channel."""
    i = 0
    while not stop_flag.is_set():
        try:
            r = comms.telegram_push(f"_endurance tick {i}_", silent=True)
            if r.get("ok"):
                metrics["telegram_pushes"] += 1
            else:
                metrics["telegram_errors"] += 1
        except Exception:
            metrics["telegram_errors"] += 1
        i += 1
        time.sleep(30)  # 1 per 30s — 20 total over 10 min


def heartbeat_worker(mem: Memory):
    """Run loops.heartbeat.sweep repeatedly."""
    while not stop_flag.is_set():
        try:
            _ = sweep(mem)
            metrics["heartbeat_sweeps"] += 1
        except Exception:
            metrics["heartbeat_errors"] += 1
        time.sleep(20)


def shell_worker():
    """Continuous safe shell calls."""
    while not stop_flag.is_set():
        try:
            r = computer.shell("ls ~/AI/friday")
            metrics["shell_calls"] += 1
            if not r.get("ok"):
                metrics["shell_errors"] += 1
        except Exception:
            metrics["shell_errors"] += 1
        time.sleep(3)


def tool_worker(orch: Orchestrator):
    """Exercise orchestrator tool routing."""
    qs = [
        "how many leads do I have",
        "empire status",
        "portfolio snapshot",
        "auditmind",
    ]
    i = 0
    while not stop_flag.is_set():
        try:
            r = orch.respond(qs[i % len(qs)], use_tools=True)
            metrics["tool_routes"] += 1
            if not r.get("reply"):
                metrics["tool_errors"] += 1
        except Exception:
            metrics["tool_errors"] += 1
        i += 1
        time.sleep(8)


def daemon_monitor(proc: subprocess.Popen):
    """Watch the daemon process for liveness."""
    while not stop_flag.is_set():
        if proc.poll() is None:
            metrics["daemon_alive_checks"] += 1
        else:
            metrics["daemon_crashes"] += 1
            break
        time.sleep(5)


def sampler():
    """Every 30s, snapshot RSS + counts."""
    while not stop_flag.is_set():
        try:
            rss_out = subprocess.check_output(
                ["bash", "-c", "ps aux | grep friday.daemon | grep -v grep | awk '{print $6}' | head -1"],
                timeout=5
            ).decode().strip()
            rss_kb = int(rss_out) if rss_out.isdigit() else 0
        except Exception:
            rss_kb = 0
        metrics["samples"].append({
            "t": int(time.time()),
            "llm_calls": metrics["llm_calls"],
            "mem_writes": metrics["mem_writes"],
            "nexus_snaps": metrics["nexus_snapshots"],
            "daemon_rss_mb": rss_kb // 1024,
        })
        time.sleep(30)


def main():
    print("╔══════════════════════════════════════════════════════╗")
    print("║  FRIDAY :: 10-MINUTE CEILING ENDURANCE               ║")
    print("╚══════════════════════════════════════════════════════╝\n")
    print(f"Duration: {DURATION}s ({DURATION//60}min)")
    print(f"Start:    {metrics['start']}\n")

    # Boot components
    eng = MultiEngine()
    mem = Memory()
    orch = Orchestrator(eng, mem)
    orch.register(Tool(
        "agency_summary", "Agency clients.",
        triggers=["client", "clients", "lead", "leads", "agency", "outreach", "crm"],
        fn=lambda **kw: {"clients": nexus.agency_clients(), "leads": nexus.leads_summary()},
    ))
    orch.register(Tool(
        "trading_state", "Trading state.",
        triggers=["trading", "trade", "portfolio", "regime", "pnl", "p&l"],
        fn=lambda **kw: {"brain": nexus.trading_state(), "portfolio": nexus.portfolio_state()},
    ))
    orch.register(Tool(
        "auditmind_status", "AuditMind.",
        triggers=["auditmind", "audit mind"],
        fn=lambda **kw: nexus.auditmind_status(),
    ))
    orch.register(Tool(
        "empire_snapshot", "Empire.",
        triggers=["empire", "snapshot", "status", "dashboard", "overview"],
        fn=lambda **kw: nexus.snapshot(),
    ))

    # Boot daemon in background
    log_path = FRIDAY / "logs" / "endurance_daemon.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_f = open(log_path, "w")
    daemon_proc = subprocess.Popen(
        ["python3", "-u", "-m", "friday.daemon"],
        cwd=os.path.expanduser("~"),
        stdout=log_f, stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )
    print(f"📡 Daemon started (pid={daemon_proc.pid}), log={log_path}")
    time.sleep(6)  # boot grace
    if daemon_proc.poll() is not None:
        print("⚠️  Daemon failed to boot")
        return

    # Spawn workers
    workers = [
        threading.Thread(target=llm_worker, args=(eng,), daemon=True, name="llm"),
        threading.Thread(target=mem_worker, args=(mem,), daemon=True, name="mem"),
        threading.Thread(target=nexus_worker, daemon=True, name="nexus"),
        threading.Thread(target=telegram_worker, daemon=True, name="telegram"),
        threading.Thread(target=heartbeat_worker, args=(mem,), daemon=True, name="heartbeat"),
        threading.Thread(target=shell_worker, daemon=True, name="shell"),
        threading.Thread(target=tool_worker, args=(orch,), daemon=True, name="tool"),
        threading.Thread(target=daemon_monitor, args=(daemon_proc,), daemon=True, name="monitor"),
        threading.Thread(target=sampler, daemon=True, name="sampler"),
    ]
    for w in workers:
        w.start()
    print(f"🚀 {len(workers)} workers running. Burning for {DURATION}s...\n")

    t0 = time.time()
    last_report = 0
    try:
        while time.time() - t0 < DURATION:
            elapsed = int(time.time() - t0)
            if elapsed >= last_report + 60:
                last_report = elapsed
                print(f"  t={elapsed:3d}s | llm={metrics['llm_calls']:3d} "
                      f"mem_w={metrics['mem_writes']:4d} "
                      f"nexus={metrics['nexus_snapshots']:3d} "
                      f"tools={metrics['tool_routes']:3d} "
                      f"tg={metrics['telegram_pushes']:2d} "
                      f"hb={metrics['heartbeat_sweeps']:2d}")
            time.sleep(1)
    finally:
        stop_flag.set()
        time.sleep(3)  # let workers finish current iteration

        # Kill daemon
        try:
            import signal as _sig
            os.killpg(os.getpgid(daemon_proc.pid), _sig.SIGTERM)
            daemon_proc.wait(timeout=10)
        except Exception:
            try:
                daemon_proc.kill()
            except Exception:
                pass
        log_f.close()

    metrics["end"] = datetime.now().isoformat()
    metrics["duration_actual_s"] = time.time() - t0
    metrics["daemon_exit_code"] = daemon_proc.returncode
    metrics["daemon_log_lines"] = sum(1 for _ in open(log_path))
    with open(log_path) as f:
        log_content = f.read()
    metrics["daemon_tracebacks"] = log_content.count("Traceback")

    # Report
    print("\n" + "═" * 60)
    print("  ENDURANCE REPORT")
    print("═" * 60)
    dur = metrics["duration_actual_s"]
    print(f"  Duration:       {dur:.1f}s ({dur/60:.1f}min)")
    print(f"  LLM calls:      {metrics['llm_calls']} (errors: {metrics['llm_errors']}, "
          f"avg {metrics['llm_total_s']/max(metrics['llm_calls'],1):.2f}s)")
    print(f"  Memory writes:  {metrics['mem_writes']} (errors: {metrics['mem_errors']})")
    print(f"  Memory reads:   {metrics['mem_reads']}")
    print(f"  Nexus snaps:    {metrics['nexus_snapshots']} (errors: {metrics['nexus_errors']})")
    print(f"  Telegram pings: {metrics['telegram_pushes']} (errors: {metrics['telegram_errors']})")
    print(f"  Heartbeats:     {metrics['heartbeat_sweeps']} (errors: {metrics['heartbeat_errors']})")
    print(f"  Shell calls:    {metrics['shell_calls']} (errors: {metrics['shell_errors']})")
    print(f"  Tool routes:    {metrics['tool_routes']} (errors: {metrics['tool_errors']})")
    print(f"  Daemon alive checks: {metrics['daemon_alive_checks']}, crashes: {metrics['daemon_crashes']}")
    print(f"  Daemon exit:    {metrics['daemon_exit_code']}")
    print(f"  Daemon tracebacks: {metrics['daemon_tracebacks']}")
    print(f"  Samples taken:  {len(metrics['samples'])}")

    total_errors = (metrics["llm_errors"] + metrics["mem_errors"] + metrics["nexus_errors"]
                    + metrics["telegram_errors"] + metrics["heartbeat_errors"]
                    + metrics["shell_errors"] + metrics["tool_errors"]
                    + metrics["daemon_crashes"] + metrics["daemon_tracebacks"])
    total_ops = (metrics["llm_calls"] + metrics["mem_writes"] + metrics["nexus_snapshots"]
                 + metrics["telegram_pushes"] + metrics["heartbeat_sweeps"]
                 + metrics["shell_calls"] + metrics["tool_routes"])
    print(f"\n  Total operations: {total_ops}")
    print(f"  Total errors:     {total_errors}")
    print(f"  Error rate:       {total_errors/max(total_ops,1)*100:.3f}%")

    verdict = "✅ PASSED" if (total_errors == 0 and metrics["daemon_crashes"] == 0
                              and metrics["daemon_tracebacks"] == 0) else "⚠️  SEE ERRORS"
    print(f"\n  Verdict: {verdict}")

    with open(REPORT, "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    print(f"\nReport: {REPORT}")


if __name__ == "__main__":
    main()
