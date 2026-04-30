"""
Friday :: System Skill
Self-maintenance. Runs daily at 03:00 via autonomy loop.
Keeps Friday healthy without human intervention.
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from .registry import Skill, Operation, SkillResult

FRIDAY = Path(os.path.expanduser("~/AI/friday"))


class SystemSkill(Skill):
    name = "system"
    description = "Self-maintenance: log rotation, memory pruning, health checks, disk watch."

    def _register_operations(self) -> None:
        self.register_op(Operation("rotate_logs", "Compress logs older than 7d, delete older than 30d.",
                                   fn=self.op_rotate_logs, risk="low"))
        self.register_op(Operation("prune_memory", "Drop events older than 60d from memory.json.",
                                   fn=self.op_prune_memory, risk="low"))
        self.register_op(Operation("health_check", "Check disk, python, ollama, memory file.",
                                   fn=self.op_health_check, risk="low"))
        self.register_op(Operation("disk_report", "Free space across ~/AI/friday and ~/nexus-omega.",
                                   fn=self.op_disk_report, risk="low"))
        self.register_op(Operation("restart_daemon", "Request daemon self-restart via touch file.",
                                   fn=self.op_restart_daemon, risk="medium", requires_confirm=True))

    # -- operations --
    def op_rotate_logs(self, **_) -> SkillResult:
        logs = FRIDAY / "logs"
        if not logs.exists():
            return SkillResult(ok=True, data={"rotated": 0, "deleted": 0, "note": "no log dir"})
        now = datetime.now()
        rotated, deleted = 0, 0
        artifacts = []
        for f in logs.glob("*.jsonl"):
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                age = now - mtime
                if age > timedelta(days=30):
                    f.unlink()
                    deleted += 1
                elif age > timedelta(days=7) and not f.name.endswith(".gz"):
                    subprocess.run(["gzip", str(f)], check=False, timeout=30)
                    rotated += 1
                    artifacts.append(str(f) + ".gz")
            except Exception:
                continue
        return SkillResult(ok=True, data={"rotated": rotated, "deleted": deleted},
                           artifacts=artifacts)

    def op_prune_memory(self, **_) -> SkillResult:
        from friday.brain.memory import Memory, _MEM_LOCK
        mem = Memory()
        cutoff = datetime.now() - timedelta(days=60)
        with _MEM_LOCK:
            evs = mem._data.get("events", [])
            kept = []
            dropped = 0
            for e in evs:
                try:
                    ts = datetime.fromisoformat(e.get("ts", ""))
                    if ts >= cutoff:
                        kept.append(e)
                    else:
                        dropped += 1
                except Exception:
                    kept.append(e)
            mem._data["events"] = kept
        mem._save()
        return SkillResult(ok=True, data={"events_dropped": dropped, "events_kept": len(kept)})

    def op_health_check(self, **_) -> SkillResult:
        checks = {}
        # Disk
        try:
            du = shutil.disk_usage(str(FRIDAY))
            pct = (du.used / du.total) * 100
            checks["disk_pct_used"] = round(pct, 1)
            checks["disk_free_gb"] = round(du.free / 1e9, 2)
            checks["disk_ok"] = pct < 90
        except Exception as e:
            checks["disk_ok"] = False
            checks["disk_err"] = str(e)
        # Memory file
        mem_f = FRIDAY / "data" / "memory.json"
        checks["memory_file_exists"] = mem_f.exists()
        checks["memory_file_kb"] = mem_f.stat().st_size // 1024 if mem_f.exists() else 0
        checks["memory_file_ok"] = checks["memory_file_exists"] and checks["memory_file_kb"] < 50_000
        # Ollama
        try:
            import urllib.request
            with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as r:
                checks["ollama_up"] = r.status == 200
        except Exception:
            checks["ollama_up"] = False
        # Python
        checks["python_version"] = ".".join(map(str, __import__("sys").version_info[:3]))
        overall_ok = checks["disk_ok"] and checks["memory_file_ok"]
        return SkillResult(ok=overall_ok, data=checks)

    def op_disk_report(self, **_) -> SkillResult:
        report = {}
        for target in [FRIDAY, Path(os.path.expanduser("~/nexus-omega")), Path(os.path.expanduser("~/agency"))]:
            if not target.exists():
                continue
            try:
                out = subprocess.check_output(["du", "-sh", str(target)], timeout=15).decode().split()[0]
                report[target.name] = out
            except Exception:
                report[target.name] = "error"
        try:
            du = shutil.disk_usage(str(FRIDAY))
            report["free_gb"] = round(du.free / 1e9, 2)
        except Exception:
            pass
        return SkillResult(ok=True, data=report)

    def op_restart_daemon(self, **_) -> SkillResult:
        # Touch a file daemon can watch — or send SIGHUP via pidfile
        marker = FRIDAY / "data" / "restart.requested"
        marker.write_text(datetime.now().isoformat())
        return SkillResult(ok=True, data={"restart_marker": str(marker)},
                           artifacts=[str(marker)])
