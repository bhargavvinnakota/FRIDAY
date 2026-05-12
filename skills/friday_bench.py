"""
Friday :: FRIDAY-Bench
Deterministic benchmark suite for money, code, research, assistant, and safety
capabilities. This is the CI gate Meta-Friday will optimize against.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from friday.brain.nervous_system import append_event

from .registry import Operation, Skill, SkillResult

FRIDAY = Path(os.path.expanduser("~/AI/friday"))
BENCH_DIR = FRIDAY / "data" / "friday_bench"


class FridayBenchSkill(Skill):
    name = "friday_bench"
    description = "Internal benchmark suite for money, code, research, assistant, and safety tasks."

    def _register_operations(self) -> None:
        self.register_op(Operation("run_suite", "Run deterministic FRIDAY-Bench.", fn=self.op_run_suite, risk="low"))
        self.register_op(Operation("latest", "Return latest benchmark report.", fn=self.op_latest, risk="low"))

    def op_run_suite(self, quick: bool = True, write_report: bool = True, **_) -> SkillResult:
        quick = _as_bool(quick)
        write_report = _as_bool(write_report)
        tasks = _tasks(quick)
        results = []
        for task in tasks:
            try:
                ok, detail = task["fn"]()
            except Exception as e:
                ok, detail = False, f"{type(e).__name__}: {e}"
            results.append({
                "id": task["id"],
                "category": task["category"],
                "description": task["description"],
                "ok": bool(ok),
                "detail": detail,
            })
        passed = sum(1 for r in results if r["ok"])
        report = {
            "generated_at": datetime.now().isoformat(),
            "quick": quick,
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "score": round((passed / len(results)) * 100, 1) if results else 0,
            "results": results,
        }
        artifacts = []
        if write_report:
            BENCH_DIR.mkdir(parents=True, exist_ok=True)
            path = BENCH_DIR / f"bench_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            path.write_text(json.dumps(report, indent=2, default=str))
            artifacts.append(str(path))
        append_event("friday_bench", source="friday_bench", payload={
            "score": report["score"],
            "passed": passed,
            "failed": report["failed"],
        }, entity_refs=["friday:evals"])
        return SkillResult(ok=report["failed"] == 0, data=report, artifacts=artifacts)

    def op_latest(self, **_) -> SkillResult:
        files = sorted(BENCH_DIR.glob("bench_*.json"))
        if not files:
            return SkillResult(ok=True, data={"found": False})
        data = json.loads(files[-1].read_text())
        return SkillResult(ok=True, data={"found": True, "path": str(files[-1]), "report": data}, artifacts=[str(files[-1])])


def _tasks(quick: bool) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = [
        _task("money_ranked", "money", "MoneyEngine has ranked opportunities.", _money_ranked),
        _task("money_experiment_state", "money", "Money experiments file has valid schema.", _money_experiment_state),
        _task("code_compile_foundations", "code", "Foundation modules compile.", _code_compile_foundations),
        _task("registry_foundations", "code", "Foundation skills are registered.", _registry_foundations),
        _task("research_docs", "research", "R&D memo exists.", _research_docs),
        _task("local_search_ready", "research", "Local research search is available.", _local_search_ready),
        _task("mission_brief_ready", "assistant", "Mission brief has 20 capabilities.", _mission_brief_ready),
        _task("memory_sleep_ready", "assistant", "Memory sleep dry-run works.", _memory_sleep_ready),
        _task("connector_center_ready", "assistant", "Connector command center has inventory and prioritized gaps.", _connector_center_ready),
        _task("razorpay_skill_ready", "money", "Razorpay dry-run path is wired.", _razorpay_skill_ready),
        _task("policy_risk_classes", "safety", "Policy risk classes exist.", _policy_risk_classes),
        _task("immune_scanner_ready", "safety", "Immune scanner runs.", _immune_scanner_ready),
        _task("action_proofs_present", "safety", "Recent actions carry proof paths.", _action_proofs_present),
        _task("nervous_system_active", "safety", "Nervous system event stream is active.", _nervous_system_active),
    ]
    return tasks if quick else tasks


def _task(task_id: str, category: str, description: str, fn: Callable[[], tuple[bool, str]]) -> dict[str, Any]:
    return {"id": task_id, "category": category, "description": description, "fn": fn}


def _money_ranked() -> tuple[bool, str]:
    items = _read_jsonl(FRIDAY / "data" / "opportunities.jsonl")
    top = sorted(items, key=lambda o: o.get("score", 0), reverse=True)[:1]
    return bool(top and top[0].get("first_reversible_action")), top[0].get("id", "none") if top else "none"


def _money_experiment_state() -> tuple[bool, str]:
    path = FRIDAY / "data" / "money_experiments.jsonl"
    items = _read_jsonl(path)
    if not path.exists():
        return True, "no experiments yet"
    ok = all("id" in item and "status" in item and "opportunity_id" in item for item in items)
    return ok, f"{len(items)} experiments"


def _code_compile_foundations() -> tuple[bool, str]:
    files = [
        FRIDAY / "brain" / "nervous_system.py",
        FRIDAY / "skills" / "money_engine.py",
        FRIDAY / "skills" / "memory_sleep.py",
        FRIDAY / "skills" / "agent_immune.py",
        FRIDAY / "skills" / "friday_bench.py",
        FRIDAY / "skills" / "world_twin.py",
        FRIDAY / "skills" / "connector_center.py",
        FRIDAY / "skills" / "razorpay.py",
        FRIDAY / "actions" / "razorpay.py",
    ]
    py = FRIDAY / "venv" / "bin" / "python3"
    cmd = [str(py), "-m", "py_compile"] + [str(f) for f in files]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return res.returncode == 0, res.stderr[-300:] or "compiled"


def _registry_foundations() -> tuple[bool, str]:
    from friday.skills.registry import get_registry
    got = set(get_registry().all())
    expected = {"money_engine", "memory_sleep", "agent_immune", "friday_bench", "world_twin", "nervous_system", "connector_center", "razorpay"}
    missing = expected - got
    return not missing, f"missing={sorted(missing)}"


def _research_docs() -> tuple[bool, str]:
    path = FRIDAY / "docs" / "FRIDAY_NEXUS_EXTENSIVE_RND_2026.md"
    return path.exists() and path.stat().st_size > 1000, str(path)


def _local_search_ready() -> tuple[bool, str]:
    from friday.skills.research import ResearchSkill
    res = ResearchSkill().op_local_search(query="FRIDAY", limit=3)
    return res.ok and res.data.get("count", 0) > 0, f"{res.data.get('count', 0) if res.data else 0} hits"


def _mission_brief_ready() -> tuple[bool, str]:
    from friday.skills.mission_control import MissionControlSkill
    res = MissionControlSkill().op_mission_brief()
    count = len((res.data or {}).get("present_capabilities", []))
    return res.ok and count == 20, f"{count} capabilities"


def _memory_sleep_ready() -> tuple[bool, str]:
    from friday.skills.memory_sleep import MemorySleepSkill
    res = MemorySleepSkill().op_consolidate(dry_run=True, write_report=False)
    return res.ok and "facts" in (res.data or {}), "dry-run ok"


def _connector_center_ready() -> tuple[bool, str]:
    from friday.skills.connector_center import ConnectorCenterSkill
    skill = ConnectorCenterSkill()
    status = skill.op_status()
    gaps = skill.op_gaps(priority="P0")
    p0 = (gaps.data or {}).get("missing_connectors", [])
    return (
        status.ok
        and (status.data or {}).get("total", 0) >= 10
        and len(p0) >= 1,
        f"{(status.data or {}).get('total', 0)} connectors; {len(p0)} P0 gaps",
    )


def _razorpay_skill_ready() -> tuple[bool, str]:
    from friday.skills.razorpay import RazorpaySkill

    skill = RazorpaySkill()
    status = skill.op_status(probe=False)
    dry = skill.op_create_payment_link(
        amount_inr="149.00",
        customer_name="Bench User",
        customer_email="bench@example.com",
        customer_phone="9876543210",
        description="FRIDAY bench dry run",
        dry_run=True,
    )
    return (
        status.ok and dry.ok and bool((dry.data or {}).get("dry_run")),
        f"configured={(status.data or {}).get('configured', False)} dry_run={(dry.data or {}).get('dry_run', False)}",
    )


def _policy_risk_classes() -> tuple[bool, str]:
    from friday.brain.policy import Policy
    desc = Policy().describe()
    risk = set(desc.get("risk_classes", []))
    return {"low", "medium", "high", "forbidden"} <= risk, str(sorted(risk))


def _immune_scanner_ready() -> tuple[bool, str]:
    from friday.skills.agent_immune import AgentImmuneSkill
    res = AgentImmuneSkill().op_scan(hours=24, write_report=False)
    severity = (res.data or {}).get("severity", "unknown")
    return res.ok or severity in {"clear", "watch", "critical"}, severity


def _action_proofs_present() -> tuple[bool, str]:
    log = FRIDAY / "data" / "actions.jsonl"
    items = _read_jsonl(log)[-30:]
    proofed = [i for i in items if i.get("proof_path")]
    return bool(proofed), f"{len(proofed)}/{len(items)} recent proofed"


def _nervous_system_active() -> tuple[bool, str]:
    from friday.brain.nervous_system import stats
    s = stats()
    return s.get("total", 0) > 0, f"{s.get('total', 0)} events"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                out.append(item)
        except Exception:
            continue
    return out


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)
