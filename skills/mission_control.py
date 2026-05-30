"""
Friday :: Mission Control Skill
Turns Bhargav's scattered vision into an executable capability/gap/next-action report.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from friday.paths import FRIDAY_ROOT
from .registry import Skill, Operation, SkillResult

FRIDAY = FRIDAY_ROOT
MANIFEST = FRIDAY / "docs" / "FRIDAY_MASTER_CAPABILITY_MANIFEST.md"
RESEARCH = FRIDAY / "docs" / "FRIDAY_GROUND_RESEARCH_2026.md"
REPORT_DIR = FRIDAY / "data" / "capability_reports"
PYTHON = FRIDAY / "venv" / "bin" / "python3"


CAPABILITY_CHECKS: list[tuple[str, str, str, list[Path]]] = [
    ("conversational_presence", "Conversational Presence", "CLI/chat, Telegram, and useful replies.", [FRIDAY / "cli.py", FRIDAY / "senses" / "telegram_in.py", FRIDAY / "brain" / "orchestrator.py"]),
    ("voice_system", "Voice System", "Streaming voice, STT/TTS, interruptibility.", [FRIDAY / "senses" / "voice_core.py", FRIDAY / "senses" / "v2_voice_streaming.py", FRIDAY / "senses" / "voice_live.py"]),
    ("native_mac_control", "Native Mac Control", "macOS Accessibility, AppleScript, app/window/process control.", [FRIDAY / "skills" / "mac.py", FRIDAY / "actions" / "computer.py"]),
    ("system_awareness", "System Awareness", "Process, disk, health, daemon, and telemetry checks.", [FRIDAY / "skills" / "system.py", FRIDAY / "daemon.py"]),
    ("persistent_memory", "Persistent Memory", "Facts, turns, events, and project continuity.", [FRIDAY / "brain" / "memory.py", FRIDAY / "data" / "memory.json"]),
    ("autonomous_omni_daemon", "Autonomous Omni-Daemon", "Background goals, ticks, policy gates, approvals, quiet hours.", [FRIDAY / "brain" / "autonomy.py", FRIDAY / "loops" / "autonomy_loop.py"]),
    ("mcp_tool_architecture", "MCP/Tool Architecture", "Standardized tool boundary and skill registry.", [FRIDAY / "brain" / "mcp_manager.py", FRIDAY / "config" / "mcp_servers.json", FRIDAY / "skills" / "registry.py"]),
    ("multi_model_orchestration", "Multi-Model Orchestration", "Local/cloud model routing, fallback paths, and cost-aware routing.", [FRIDAY / "brain" / "engine.py"]),
    ("knowledge_ingestion", "Knowledge Ingestion", "Repo/docs ingestion, vault mapping, and distilled SOPs.", [FRIDAY / "skills" / "broker.py", FRIDAY / "brain" / "neural_crawler.py"]),
    ("daily_evolution", "Daily Evolution", "Background learning, failure autopsy, skill crystallization.", [FRIDAY / "brain" / "evolution.py", FRIDAY / "logs" / "evolution_crawler.log"]),
    ("research_world_awareness", "Research And World Awareness", "Real web/news/research pulse with local fallback.", [FRIDAY / "skills" / "research.py", FRIDAY / "skills" / "intelligence.py", FRIDAY / "actions" / "news.py"]),
    ("builder_mode", "Builder Mode", "Idea -> validation -> plan -> code -> test -> proof.", [FRIDAY / "skills" / "builder.py", FRIDAY / "brain" / "mission.py"]),
    ("agentic_swarm", "Agentic Swarm", "Specialist agents and swarm orchestration.", [FRIDAY / "skills" / "swarm.py", FRIDAY / "brain" / "swarm.py"]),
    ("financial_sovereignty_engine", "Financial Sovereignty Engine", "Revenue state, executive mission focus, and closed-client tracking.", [FRIDAY / "skills" / "empire.py", FRIDAY / "actions" / "nexus.py"]),
    ("agency_automation", "Agency Automation", "Leads, outreach drafts, approvals, CRM, follow-ups.", [FRIDAY / "skills" / "outreach.py"]),
    ("trading_nexus_omega", "Trading/Nexus Omega", "Trading state, portfolio adapter, market-risk visibility.", [FRIDAY / "actions" / "nexus.py", FRIDAY / "data" / "trading_signal.txt"]),
    ("auditmind_saas_engine", "AuditMind/SaaS Engine", "AuditMind dashboard adapter and SaaS execution lane.", [FRIDAY / "actions" / "nexus.py", FRIDAY / "docs" / "FRIDAY_MASTER_CAPABILITY_MANIFEST.md"]),
    ("content_ai_studio", "Content/AI Studio", "Drafting and faceless content workflow adapters.", [FRIDAY / "skills" / "content.py", FRIDAY / "skills" / "auto_shorts.py"]),
    ("god_tier_ui_hud", "God-Tier UI/HUD", "Native HUD state surface and proof/action display.", [FRIDAY / "native_hud" / "Sources" / "HUDView.swift", FRIDAY / "brain" / "state_relay.py"]),
    ("proof_anti_hallucination", "Proof And Anti-Hallucination", "Tests, logs, artifacts, and planned/attempted/done separation.", [FRIDAY / "tests" / "v1_autonomy_test.py", FRIDAY / "data" / "actions.jsonl"]),
]


class MissionControlSkill(Skill):
    name = "mission_control"
    description = "Executive layer: reads Friday's vision, project state, runtime evidence, and returns capability gaps plus the next action."

    def _register_operations(self) -> None:
        self.register_op(Operation(
            "capability_map",
            "List Friday's intended capabilities with evidence of what exists now.",
            fn=self.op_capability_map,
            risk="low",
        ))
        self.register_op(Operation(
            "gap_report",
            "Identify the highest-risk gaps between Bhargav's vision and current Friday.",
            fn=self.op_gap_report,
            risk="low",
        ))
        self.register_op(Operation(
            "next_action",
            "Choose the next proof-backed action Friday should execute.",
            fn=self.op_next_action,
            risk="low",
        ))
        self.register_op(Operation(
            "mission_brief",
            "Return a compact mission brief: capabilities, gaps, next action, and proof.",
            fn=self.op_mission_brief,
            risk="low",
        ))
        self.register_op(Operation(
            "test_capabilities",
            "Run a safe local proof test across Friday's 20 capability domains.",
            fn=self.op_test_capabilities,
            risk="low",
        ))
        self.register_op(Operation(
            "unlock_all",
            "Unlock every capability through its safe local path, then write a proof report.",
            fn=self.op_unlock_all,
            risk="low",
        ))

    def op_capability_map(self, **_) -> SkillResult:
        runtime = _runtime_evidence()
        report = _latest_capability_report()
        capabilities = [_capability_status(cap, label, desc, paths, runtime, report) for cap, label, desc, paths in CAPABILITY_CHECKS]
        return SkillResult(ok=True, data={
            "generated_at": datetime.now().isoformat(),
            "capabilities": capabilities,
            "readiness_counts": _readiness_counts(capabilities),
            "latest_test_report": report.get("path"),
            "connector_status": runtime.get("connectors", {}),
            "manifest": str(MANIFEST),
            "research": str(RESEARCH),
        }, artifacts=[str(MANIFEST), str(RESEARCH)])

    def op_gap_report(self, **_) -> SkillResult:
        runtime = _runtime_evidence()
        report = _latest_capability_report()
        capabilities = [_capability_status(cap, label, desc, paths, runtime, report) for cap, label, desc, paths in CAPABILITY_CHECKS]
        weak = [c for c in capabilities if c["status"] != "present" or c["readiness"] in ("prototype", "blocked")]
        gaps = []

        if not runtime["friday_cli_ok"]:
            gaps.append("CLI/runtime reliability is not proven right now.")
        if runtime["agency"].get("closed", 0) == 0:
            gaps.append("Revenue loop is wired, but no closed client is recorded yet.")
        if "voice_system" in {c["capability"] for c in weak}:
            gaps.append("Voice has a safe local proof, but microphone/STT live turn-taking still needs a human-run session.")
        if "god_tier_ui_hud" in {c["capability"] for c in weak}:
            gaps.append("HUD state writes are testable; the native UI should still be visually checked when launched.")
        connector_state = runtime.get("connectors", {})
        if connector_state.get("action_needed"):
            gaps.append("Connector layer has a broken integration: " + ", ".join(item.get("id", "?") for item in connector_state.get("action_needed", [])))
        if connector_state.get("missing_p0"):
            gaps.append("Money stack is not complete; missing P0 connectors: " + ", ".join(item.get("id", "?") for item in connector_state.get("missing_p0", [])))
        revenue = runtime.get("revenue", {})
        if revenue.get("entries", 0) == 0:
            gaps.append("Revenue ledger is wired but still empty; ingest webhooks or sync Razorpay once test keys are loaded.")

        return SkillResult(ok=True, data={
            "generated_at": datetime.now().isoformat(),
            "capability_gaps": weak,
            "readiness_counts": _readiness_counts(capabilities),
            "runtime_gaps": gaps,
            "runtime": runtime,
        })

    def op_next_action(self, **_) -> SkillResult:
        runtime = _runtime_evidence()
        connectors = runtime.get("connectors", {})
        if connectors.get("action_needed"):
            broken = connectors["action_needed"][0]
            action = {
                "priority": 1,
                "action": "repair_connector_surface",
                "reason": "FRIDAY should repair broken senses before trusting downstream ops.",
                "proof": f"Reconnect `{broken.get('id')}` and rerun `friday connectors status` until it clears from action_needed.",
            }
        elif connectors.get("missing_p0"):
            missing = connectors["missing_p0"][0]
            action = {
                "priority": 1,
                "action": "wire_money_connector",
                "reason": "The money engine cannot become real until the financial toolchain is connected.",
                "proof": f"Connect `{missing.get('id')}` and export a fresh connector map showing one fewer P0 gap.",
            }
        elif not runtime["friday_cli_ok"]:
            action = {
                "priority": 1,
                "action": "stabilize_cli_loop",
                "reason": "If `friday ask` is unreliable, every other capability feels fake.",
                "proof": "Run `friday ask \"status check in one short sentence\"` and log the result.",
            }
        elif runtime["agency"].get("closed", 0) == 0:
            action = {
                "priority": 1,
                "action": "advance_agency_revenue_loop",
                "reason": "Financial sovereignty is the core mission; zero closed clients is the loudest business gap.",
                "proof": "Run due-lead draft generation, queue approvals, and record outreach state.",
            }
        else:
            action = {
                "priority": 1,
                "action": "expand_native_mac_awareness",
                "reason": "Once the revenue loop is moving, deepen Mac-native control and proof surfaces.",
                "proof": "Report active app, process state, and a safe UI-tree read.",
            }
        return SkillResult(ok=True, data={
            "generated_at": datetime.now().isoformat(),
            "next_action": action,
            "runtime": runtime,
        })

    def op_mission_brief(self, **_) -> SkillResult:
        cap = self.op_capability_map().data
        gaps = self.op_gap_report().data
        next_action = self.op_next_action().data
        present = [c["capability"] for c in cap["capabilities"] if c["status"] == "present"]
        partial = [c["capability"] for c in cap["capabilities"] if c["status"] == "partial"]
        missing = [c["capability"] for c in cap["capabilities"] if c["status"] == "missing"]
        proven = [c["capability"] for c in cap["capabilities"] if c["readiness"] == "proven"]
        wired = [c["capability"] for c in cap["capabilities"] if c["readiness"] == "wired"]
        prototype = [c["capability"] for c in cap["capabilities"] if c["readiness"] == "prototype"]
        blocked = [c["capability"] for c in cap["capabilities"] if c["readiness"] == "blocked"]
        return SkillResult(ok=True, data={
            "generated_at": datetime.now().isoformat(),
            "north_star": "Friday is Bhargav's local-first operating intelligence for Mac control, proof-backed action, continuous learning, and financial sovereignty.",
            "present_capabilities": present,
            "partial_capabilities": partial,
            "missing_capabilities": missing,
            "readiness_counts": cap["readiness_counts"],
            "proven_capabilities": proven,
            "wired_capabilities": wired,
            "prototype_capabilities": prototype,
            "blocked_capabilities": blocked,
            "runtime_gaps": gaps["runtime_gaps"],
            "connector_status": cap.get("connector_status", {}),
            "next_action": next_action["next_action"],
            "proof": {
                "manifest": str(MANIFEST),
                "research": str(RESEARCH),
                "actions_log": str(FRIDAY / "data" / "actions.jsonl"),
            },
        }, artifacts=[str(MANIFEST), str(RESEARCH)])

    def op_test_capabilities(self, write_report: bool = True, generate_artifacts: bool = True, **_) -> SkillResult:
        write_report = _as_bool(write_report)
        generate_artifacts = _as_bool(generate_artifacts)
        report = _run_capability_tests(generate_artifacts=generate_artifacts)
        artifacts = list(report.get("artifacts", []))
        if write_report:
            REPORT_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = REPORT_DIR / f"capability_unlock_{stamp}.json"
            report["path"] = str(path)
            path.write_text(json.dumps(report, indent=2, default=str))
            artifacts.append(str(path))
        return SkillResult(
            ok=report["summary"]["failed"] == 0,
            data=report,
            artifacts=artifacts,
            error=None if report["summary"]["failed"] == 0 else "one or more capability tests failed",
        )

    def op_unlock_all(self, **kwargs) -> SkillResult:
        return self.op_test_capabilities(write_report=True, generate_artifacts=True, **kwargs)


def _capability_status(capability: str, label: str, description: str, paths: list[Path],
                       runtime: dict[str, Any], report: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = [str(p) for p in paths if p.exists()]
    missing = [str(p) for p in paths if not p.exists()]
    if len(existing) == len(paths):
        status = "present"
    elif existing:
        status = "partial"
    else:
        status = "missing"
    latest_test = _test_for(report or {}, capability)
    return {
        "capability": capability,
        "label": label,
        "description": description,
        "status": status,
        "readiness": _readiness(capability, status, runtime, latest_test),
        "latest_test": latest_test,
        "evidence": existing,
        "missing": missing,
    }


def _readiness(capability: str, status: str, runtime: dict[str, Any],
               latest_test: dict[str, Any] | None = None) -> str:
    """Readiness is stricter than code presence."""
    if status == "missing":
        return "blocked"
    if latest_test:
        if latest_test.get("ok") and not latest_test.get("live_limit"):
            return "proven"
        if latest_test.get("ok"):
            return "wired"
        return "blocked"
    agency = runtime.get("agency", {})
    if capability == "conversational_presence":
        return "proven" if runtime.get("friday_cli_ok") else "blocked"
    if capability == "system_awareness":
        return "proven" if runtime.get("disk") else "wired"
    if capability == "agency_automation":
        return "wired" if agency.get("outreach", 0) > 1 else "prototype"
    if capability == "financial_sovereignty_engine":
        return "proven" if agency.get("closed", 0) > 0 else "wired"
    if capability in {"voice_system", "god_tier_ui_hud", "agentic_swarm", "knowledge_ingestion"}:
        return "prototype"
    if capability in {
        "native_mac_control", "mcp_tool_architecture", "multi_model_orchestration",
        "research_world_awareness", "builder_mode", "autonomous_omni_daemon",
        "persistent_memory", "proof_anti_hallucination", "daily_evolution",
        "trading_nexus_omega", "auditmind_saas_engine", "content_ai_studio",
    }:
        return "wired"
    return "wired" if status == "present" else "prototype"


def _readiness_counts(capabilities: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"proven": 0, "wired": 0, "prototype": 0, "blocked": 0}
    for c in capabilities:
        r = c.get("readiness", "prototype")
        counts[r] = counts.get(r, 0) + 1
    return counts


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _latest_capability_report() -> dict[str, Any]:
    try:
        files = sorted(REPORT_DIR.glob("capability_unlock_*.json"))
        if not files:
            return {}
        data = json.loads(files[-1].read_text())
        data["path"] = str(files[-1])
        return data
    except Exception:
        return {}


def _test_for(report: dict[str, Any], capability: str) -> dict[str, Any] | None:
    for item in report.get("capabilities", []):
        if item.get("capability") == capability:
            return {
                "ok": item.get("ok", False),
                "status": item.get("status"),
                "summary": item.get("summary"),
                "live_limit": item.get("live_limit", ""),
                "tested_at": report.get("generated_at"),
                "report": report.get("path"),
            }
    return None


def _cap_result(capability: str, ok: bool, summary: str, *,
                data: dict[str, Any] | None = None,
                artifacts: list[str] | None = None,
                live_limit: str = "",
                start: float | None = None) -> dict[str, Any]:
    elapsed_ms = round((time.perf_counter() - start) * 1000, 1) if start else 0
    return {
        "capability": capability,
        "ok": bool(ok),
        "status": "pass" if ok else "fail",
        "summary": summary,
        "data": data or {},
        "artifacts": artifacts or [],
        "live_limit": live_limit,
        "duration_ms": elapsed_ms,
    }


def _cap_error(capability: str, exc: Exception, start: float) -> dict[str, Any]:
    return _cap_result(
        capability,
        False,
        f"{type(exc).__name__}: {exc}",
        start=start,
    )


def _run_capability_tests(generate_artifacts: bool = True) -> dict[str, Any]:
    tests = [
        _test_conversational_presence,
        _test_voice_system,
        _test_native_mac_control,
        _test_system_awareness,
        _test_persistent_memory,
        _test_autonomous_omni_daemon,
        _test_mcp_tool_architecture,
        _test_multi_model_orchestration,
        _test_knowledge_ingestion,
        _test_daily_evolution,
        _test_research_world_awareness,
        _test_builder_mode,
        _test_agentic_swarm,
        _test_financial_sovereignty_engine,
        _test_agency_automation,
        _test_trading_nexus_omega,
        _test_auditmind_saas_engine,
        _test_content_ai_studio,
        _test_god_tier_ui_hud,
        _test_proof_anti_hallucination,
    ]
    results = []
    artifacts: list[str] = []
    for fn in tests:
        start = time.perf_counter()
        capability = fn.__name__.replace("_test_", "")
        try:
            result = fn(generate_artifacts=generate_artifacts, start=start)
        except Exception as exc:
            result = _cap_error(capability, exc, start)
        results.append(result)
        artifacts.extend(result.get("artifacts", []))

    passed = sum(1 for item in results if item.get("ok"))
    failed = len(results) - passed
    live_limits = [item for item in results if item.get("live_limit")]
    return {
        "generated_at": datetime.now().isoformat(),
        "mode": "safe_local",
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "live_limited": len(live_limits),
        },
        "capabilities": results,
        "artifacts": sorted(set(artifacts)),
    }


def _run_python(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    python = str(PYTHON if PYTHON.exists() else shutil.which("python3") or "python3")
    return subprocess.run(
        [python, *args],
        cwd=str(FRIDAY),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _test_conversational_presence(generate_artifacts: bool, start: float) -> dict[str, Any]:
    proc = _run_python([str(FRIDAY / "cli.py"), "ask", "status check in one short sentence"], timeout=45)
    out = (proc.stdout or proc.stderr).strip()
    ok = proc.returncode == 0 and bool(out)
    return _cap_result(
        "conversational_presence",
        ok,
        "CLI ask loop returned a usable reply." if ok else "CLI ask loop failed.",
        data={"returncode": proc.returncode, "preview": out[:300]},
        start=start,
    )


def _test_voice_system(generate_artifacts: bool, start: float) -> dict[str, Any]:
    proc = _run_python(["-m", "py_compile", "senses/voice_core.py", "senses/v2_voice_streaming.py", "senses/voice_live.py"], timeout=20)
    say_available = shutil.which("say") is not None
    ok = proc.returncode == 0
    return _cap_result(
        "voice_system",
        ok,
        "Voice scripts compile; macOS TTS path detected." if ok and say_available else "Voice scripts compile; live audio needs a manual run." if ok else "Voice compile check failed.",
        data={"say_available": say_available, "stderr": proc.stderr[:300]},
        live_limit="Microphone/STT turn-taking was not started during this safe test.",
        start=start,
    )


def _test_native_mac_control(generate_artifacts: bool, start: float) -> dict[str, Any]:
    from friday.actions import computer

    shell = computer.shell("pwd", timeout=10)
    osascript = shutil.which("osascript") is not None
    active_app = computer.applescript('tell application "System Events" to get name of first process whose frontmost is true', timeout=5) if osascript else {"ok": False, "error": "osascript missing"}
    ok = bool(shell.get("ok")) and osascript
    limit = "" if active_app.get("ok") else "Accessibility/frontmost-app read may require macOS permissions."
    return _cap_result(
        "native_mac_control",
        ok,
        "Safe shell and AppleScript bridge are available." if ok else "Native Mac bridge failed.",
        data={"shell_ok": shell.get("ok"), "osascript": osascript, "active_app_ok": active_app.get("ok"), "active_app_error": active_app.get("error", "")[:200]},
        live_limit=limit,
        start=start,
    )


def _test_system_awareness(generate_artifacts: bool, start: float) -> dict[str, Any]:
    from friday.skills.system import SystemSkill

    res = SystemSkill().op_health_check()
    data = res.data or {}
    telemetry_readable = {"disk_pct_used", "memory_file_ok", "python_version"} <= set(data.keys())
    limit = "" if res.ok else "System telemetry is readable, but health_check is warning on disk or memory thresholds."
    return _cap_result(
        "system_awareness",
        telemetry_readable,
        "System health probe returned disk, memory, and Python telemetry." if telemetry_readable else "System health probe could not read telemetry.",
        data=data or {"error": res.error},
        live_limit=limit,
        start=start,
    )


def _test_persistent_memory(generate_artifacts: bool, start: float) -> dict[str, Any]:
    from friday.brain.memory import Memory

    mem = Memory()
    key = "capability_probe_temp"
    value = datetime.now().isoformat()
    mem.remember(key, value, category="capability_test")
    recalled = mem.recall(key)
    removed = mem.forget(key)
    ok = recalled == value and removed
    return _cap_result(
        "persistent_memory",
        ok,
        "Memory write/read/delete cycle passed." if ok else "Memory cycle failed.",
        data={"recalled": recalled == value, "removed": removed},
        start=start,
    )


def _test_autonomous_omni_daemon(generate_artifacts: bool, start: float) -> dict[str, Any]:
    from friday.brain.autonomy import AutonomyEngine
    from friday.brain.planner import Planner

    status = AutonomyEngine().status()
    goals = Planner().active_goals()
    ok = isinstance(status, dict) and len(goals) > 0
    return _cap_result(
        "autonomous_omni_daemon",
        ok,
        "Autonomy engine status and active goals are readable." if ok else "Autonomy engine or planner failed.",
        data={"goals": len(goals), "status_keys": sorted(status.keys())[:10]},
        start=start,
    )


def _test_mcp_tool_architecture(generate_artifacts: bool, start: float) -> dict[str, Any]:
    try:
        from friday.brain.mcp_manager import MCPManager
        manager = MCPManager()
        ok = bool(manager.server_configs)
        data = {"servers": sorted(manager.server_configs.keys())}
        summary = "MCP manager and server config loaded."
    except Exception as exc:
        ok = False
        data = {"error": f"{type(exc).__name__}: {exc}"}
        summary = "MCP manager failed to load."
    return _cap_result("mcp_tool_architecture", ok, summary, data=data, live_limit="MCP server processes are opt-in and were not connected in this safe test.", start=start)


def _test_multi_model_orchestration(generate_artifacts: bool, start: float) -> dict[str, Any]:
    from friday.brain.engine import MultiEngine

    eng = MultiEngine()
    ollama_up = eng.ollama.health()
    configured = bool(ollama_up or eng.openrouter or eng.gemini_key)
    routes = {
        "code": eng._score_complexity("build code"),
        "research": eng._score_complexity("latest research"),
        "plan": eng._score_complexity("plan mission"),
        "default": eng._score_complexity("hello"),
    }
    return _cap_result(
        "multi_model_orchestration",
        configured,
        "At least one model backend is available/configured." if configured else "No model backend is available/configured.",
        data={"ollama_up": ollama_up, "openrouter_configured": bool(eng.openrouter), "gemini_configured": bool(eng.gemini_key), "routes": routes},
        live_limit="" if ollama_up else "Local Ollama generation is not up; cloud/configured fallback may be used.",
        start=start,
    )


def _test_knowledge_ingestion(generate_artifacts: bool, start: float) -> dict[str, Any]:
    from friday.skills.broker import BrokerSkill

    res = BrokerSkill().op_map_vault()
    return _cap_result(
        "knowledge_ingestion",
        res.ok,
        "Knowledge vault map operation passed." if res.ok else "Knowledge vault map failed.",
        data=res.data or {"error": res.error},
        start=start,
    )


def _test_daily_evolution(generate_artifacts: bool, start: float) -> dict[str, Any]:
    from friday.brain.evolution import EvolutionEngine

    evo = EvolutionEngine()
    ok = hasattr(evo, "_distill_conversations") and hasattr(evo, "_autopsy_failures") and hasattr(evo, "_crystallize_skills")
    return _cap_result(
        "daily_evolution",
        ok,
        "Evolution engine loaded without starting the background loop." if ok else "Evolution engine is missing core routines.",
        data={"running": evo.is_running},
        live_limit="Continuous background loop was not started during this safe test.",
        start=start,
    )


def _test_research_world_awareness(generate_artifacts: bool, start: float) -> dict[str, Any]:
    from friday.skills.research import ResearchSkill

    res = ResearchSkill().op_local_search(query="Friday", limit=5)
    return _cap_result(
        "research_world_awareness",
        res.ok,
        "Local research/search path passed." if res.ok else "Local research/search failed.",
        data=res.data or {"error": res.error},
        live_limit="Live web/news sources were not queried during this safe test.",
        start=start,
    )


def _test_builder_mode(generate_artifacts: bool, start: float) -> dict[str, Any]:
    from friday.skills.builder import BuilderSkill

    res = BuilderSkill().op_read_file(file_path=str(FRIDAY / "README.md"))
    return _cap_result(
        "builder_mode",
        res.ok,
        "Builder read-file tool passed." if res.ok else "Builder read-file tool failed.",
        data={"content_chars": len((res.data or {}).get("content", "")) if res.ok else 0, "error": res.error},
        start=start,
    )


def _test_agentic_swarm(generate_artifacts: bool, start: float) -> dict[str, Any]:
    from friday.brain.engine import MultiEngine
    from friday.brain.memory import Memory
    from friday.brain.swarm import SwarmOrchestrator

    swarm = SwarmOrchestrator(MultiEngine(), Memory())
    names = sorted(swarm.agents.keys())
    ok = {"Architect", "Engineer", "Researcher", "QA_Judge"} <= set(names)
    return _cap_result(
        "agentic_swarm",
        ok,
        "Swarm orchestrator loaded with core specialist agents." if ok else "Swarm core agents missing.",
        data={"agents": names},
        live_limit="LLM swarm execution was not run because it can write/execute tools.",
        start=start,
    )


def _test_financial_sovereignty_engine(generate_artifacts: bool, start: float) -> dict[str, Any]:
    from friday.actions import nexus

    snap = nexus.snapshot()
    closed = snap.get("agency", {}).get("crm", {}).get("closed", 0)
    ok = "agency" in snap and "trading" in snap
    return _cap_result(
        "financial_sovereignty_engine",
        ok,
        "Empire/revenue snapshot adapter returned current state." if ok else "Empire/revenue snapshot failed.",
        data={"closed_clients": closed, "agency": snap.get("agency", {})},
        live_limit="No closed client is recorded yet; revenue outcome remains a business blocker." if closed == 0 else "",
        start=start,
    )


def _test_agency_automation(generate_artifacts: bool, start: float) -> dict[str, Any]:
    from friday.skills.outreach import OutreachSkill

    skill = OutreachSkill()
    status = skill.op_status()
    artifacts: list[str] = []
    outbox_data = {}
    if generate_artifacts:
        outbox = skill.op_manual_send_outbox()
        if outbox.ok:
            artifacts.extend(outbox.artifacts)
            outbox_data = outbox.data or {}
    ok = status.ok and (not generate_artifacts or bool(outbox_data))
    return _cap_result(
        "agency_automation",
        ok,
        "Outreach status and manual-send outbox passed." if ok else "Agency automation failed.",
        data={"status": status.data, "outbox": outbox_data},
        artifacts=artifacts,
        live_limit="WhatsApp API/browser sending is still manual; outbox is the safe send surface.",
        start=start,
    )


def _test_trading_nexus_omega(generate_artifacts: bool, start: float) -> dict[str, Any]:
    from friday.actions import nexus

    trading = nexus.trading_state()
    portfolio = nexus.portfolio_state()
    ok = isinstance(trading, dict) and isinstance(portfolio, dict)
    no_data = trading.get("status") == "no_data" or portfolio.get("status") == "no_data"
    return _cap_result(
        "trading_nexus_omega",
        ok,
        "Trading and portfolio adapters returned state." if ok else "Trading adapter failed.",
        data={"trading_status": trading.get("status", "ok"), "portfolio_status": portfolio.get("status", "ok")},
        live_limit="Trading data adapter is present, but live/paper trading state was not found." if no_data else "",
        start=start,
    )


def _test_auditmind_saas_engine(generate_artifacts: bool, start: float) -> dict[str, Any]:
    from friday.actions import nexus

    audit = nexus.auditmind_status()
    ok = isinstance(audit, dict)
    offline = audit.get("status") == "offline"
    return _cap_result(
        "auditmind_saas_engine",
        ok,
        "AuditMind/SaaS adapter returned dashboard status." if ok else "AuditMind/SaaS adapter failed.",
        data=audit,
        live_limit="AuditMind dashboard is offline right now." if offline else "",
        start=start,
    )


def _test_content_ai_studio(generate_artifacts: bool, start: float) -> dict[str, Any]:
    from friday.skills.content import ContentSkill, _deterministic_draft

    skill = ContentSkill()
    if generate_artifacts:
        res = skill.op_draft_post(topic="Friday capability proof", platform="linkedin", tone="operator")
        ok = res.ok
        draft_path = (res.data or {}).get("path")
        error = res.error
        artifacts = res.artifacts if res.ok else []
    else:
        draft = _deterministic_draft("Draft a linkedin post.", "Topic: Friday capability proof")
        ok = bool(draft.strip()) and "draft_post" in skill.operations
        draft_path = None
        error = None if ok else "deterministic content fallback failed"
        artifacts = []
    video_engine = Path(os.path.expanduser("~/video Generator/Backend")).exists()
    return _cap_result(
        "content_ai_studio",
        ok,
        "Content studio produced a draft artifact." if generate_artifacts and ok else "Content studio fallback generated a draft." if ok else "Content studio draft failed.",
        data={"draft_path": draft_path, "video_engine_available": video_engine, "error": error},
        artifacts=artifacts,
        live_limit="" if video_engine else "Video generator backend is not present; short-video publishing remains external.",
        start=start,
    )


def _test_god_tier_ui_hud(generate_artifacts: bool, start: float) -> dict[str, Any]:
    from friday.brain.state_relay import STATE_FILE, update_hud_state

    update_hud_state(status="CAPABILITY_TEST", friday_output="20 capability unlock pass running")
    data = json.loads(Path(STATE_FILE).read_text())
    ok = data.get("status") == "CAPABILITY_TEST"
    return _cap_result(
        "god_tier_ui_hud",
        ok,
        "HUD state relay wrote and read current state." if ok else "HUD state relay failed.",
        data={"state_file": str(STATE_FILE), "status": data.get("status")},
        artifacts=[str(STATE_FILE)] if generate_artifacts else [],
        live_limit="Native HUD window was not launched/visually inspected in this safe test.",
        start=start,
    )


def _test_proof_anti_hallucination(generate_artifacts: bool, start: float) -> dict[str, Any]:
    actions = FRIDAY / "data" / "actions.jsonl"
    v1_report = FRIDAY / "data" / "v1_autonomy_report.json"
    ok = actions.exists() and actions.stat().st_size > 0 and (FRIDAY / "tests" / "v1_autonomy_test.py").exists()
    data = {
        "actions_log_bytes": actions.stat().st_size if actions.exists() else 0,
        "v1_report_exists": v1_report.exists(),
    }
    artifacts = [str(actions)]
    if v1_report.exists():
        artifacts.append(str(v1_report))
    return _cap_result(
        "proof_anti_hallucination",
        ok,
        "Proof logs and test harness are present." if ok else "Proof layer is missing actions log or tests.",
        data=data,
        artifacts=artifacts if generate_artifacts else [],
        start=start,
    )


def _runtime_evidence() -> dict[str, Any]:
    agency = {"total_leads": 0, "with_phone": 0, "closed": 0, "outreach": 0}
    try:
        from friday.actions import nexus
        leads = nexus.leads_summary()
        crm = nexus.crm_summary()
        agency = {
            "total_leads": leads.get("total", 0),
            "with_phone": leads.get("with_phone", 0),
            "closed": crm.get("closed", 0),
            "outreach": crm.get("total_outreach", 0),
        }
    except Exception as e:
        agency["error"] = str(e)[:200]

    try:
        du = shutil.disk_usage(str(FRIDAY))
        disk = {
            "free_gb": round(du.free / 1e9, 2),
            "used_pct": round((du.used / du.total) * 100, 1),
        }
    except Exception:
        disk = {}

    friday_cli_ok = False
    cli_probe = ""
    try:
        r = subprocess.run(
            [str(FRIDAY / "venv" / "bin" / "python3"), str(FRIDAY / "cli.py"), "status"],
            cwd=str(FRIDAY),
            capture_output=True,
            text=True,
            timeout=10,
        )
        friday_cli_ok = r.returncode == 0
        cli_probe = (r.stdout or r.stderr)[:500]
    except Exception as e:
        cli_probe = str(e)[:500]

    connectors = _connector_status()
    revenue = _revenue_status()

    return {
        "friday_cli_ok": friday_cli_ok,
        "cli_probe": cli_probe,
        "agency": agency,
        "disk": disk,
        "connectors": connectors,
        "revenue": revenue,
        "time": datetime.now().isoformat(),
    }


def _connector_status() -> dict[str, Any]:
    try:
        from friday.skills.connector_center import ConnectorCenterSkill

        res = ConnectorCenterSkill().op_status()
        if res.ok and isinstance(res.data, dict):
            return res.data
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"[:200]}
    return {}


def _revenue_status() -> dict[str, Any]:
    try:
        from friday.skills.revenue_ledger import RevenueLedgerSkill

        res = RevenueLedgerSkill().op_status()
        if res.ok and isinstance(res.data, dict):
            return res.data
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"[:200]}
    return {}
