"""
Friday :: Money Engine
Ranks ethical money opportunities as reversible experiments.

This is intentionally not a payment, trading, or auto-send module. It is the
opportunity science layer: model the offer, evidence, expected value, risk,
owner time, first action, and kill condition before FRIDAY spends reputation
or money.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from friday.actions import nexus
from friday.paths import FRIDAY_ROOT

from .registry import Operation, Skill, SkillResult

FRIDAY = FRIDAY_ROOT
DATA_DIR = FRIDAY / "data"
OPPORTUNITIES_FILE = DATA_DIR / "opportunities.jsonl"
EXPERIMENTS_FILE = DATA_DIR / "money_experiments.jsonl"
_OUTREACH_OPPORTUNITIES = {
    "opp_local_whatsapp_pilot",
    "opp_creator_repupose_automation",
    "opp_freelance_ai_ops_gigs",
}


@dataclass
class Opportunity:
    id: str
    title: str
    category: str
    hypothesis: str
    evidence: list[str]
    expected_income_inr: int
    probability_of_success: float
    speed_to_cash_days: int
    owner_time_hours: float
    cash_cost_inr: int
    legal_risk: float
    platform_risk: float
    execution_complexity: float
    compounding_potential: float
    ethical_risk: float
    first_reversible_action: str
    kill_condition: str
    risk_tier: int = 2
    status: str = "candidate"
    source: str = "seed"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MoneyEngineSkill(Skill):
    name = "money_engine"
    description = "Ranks ethical money opportunities and turns them into small, reversible experiments."

    def _register_operations(self) -> None:
        self.register_op(Operation(
            "scan_opportunities",
            "Generate or refresh money opportunities from Bhargav's current assets and pipeline.",
            fn=self.op_scan_opportunities,
            risk="low",
        ))
        self.register_op(Operation(
            "rank_opportunities",
            "Return opportunities sorted by risk-adjusted expected value.",
            fn=self.op_rank_opportunities,
            risk="low",
        ))
        self.register_op(Operation(
            "create_experiment",
            "Create the smallest reversible experiment for a ranked opportunity.",
            fn=self.op_create_experiment,
            risk="low",
        ))
        self.register_op(Operation(
            "launch_experiment",
            "Launch the first safe action for an opportunity; queues outbound work for approval only.",
            fn=self.op_launch_experiment,
            risk="medium",
        ))
        self.register_op(Operation(
            "record_result",
            "Record the result of a money experiment and update its status.",
            fn=self.op_record_result,
            risk="low",
        ))
        self.register_op(Operation(
            "status",
            "Summarize opportunity and experiment counts.",
            fn=self.op_status,
            risk="low",
        ))

    def op_scan_opportunities(self, persist: bool = True, **_) -> SkillResult:
        persist = _as_bool(persist)
        snapshot = nexus.snapshot()
        opportunities = [_score_opportunity(o) for o in _seed_opportunities(snapshot)]
        ranked = sorted(opportunities, key=lambda o: o.score, reverse=True)
        artifacts: list[str] = []
        if persist:
            _upsert_jsonl(OPPORTUNITIES_FILE, [o.to_dict() for o in ranked])
            artifacts.append(str(OPPORTUNITIES_FILE))
        return SkillResult(ok=True, data={
            "generated_at": datetime.now().isoformat(),
            "count": len(ranked),
            "top": [o.to_dict() for o in ranked[:5]],
            "snapshot_signals": _snapshot_signals(snapshot),
        }, artifacts=artifacts)

    def op_rank_opportunities(self, top_n: int = 10, refresh: bool = False, **_) -> SkillResult:
        top_n = _int(top_n, 10)
        if refresh or not OPPORTUNITIES_FILE.exists():
            scan = self.op_scan_opportunities(persist=True)
            if not scan.ok:
                return scan
        items = [_score_dict(o) for o in _read_jsonl(OPPORTUNITIES_FILE)]
        items = sorted(items, key=lambda o: o.get("score", 0), reverse=True)
        return SkillResult(ok=True, data={
            "generated_at": datetime.now().isoformat(),
            "count": len(items),
            "top_n": top_n,
            "opportunities": items[:top_n],
            "scoring": {
                "formula": "expected_income * probability * speed_factor * compounding / risk_penalty",
                "principle": "Prefer fast, ethical, low-cost, reversible routes to first cash and learning.",
            },
        }, artifacts=[str(OPPORTUNITIES_FILE)] if OPPORTUNITIES_FILE.exists() else [])

    def op_create_experiment(self, opportunity_id: str = "", **_) -> SkillResult:
        if not opportunity_id:
            ranked = self.op_rank_opportunities(top_n=1, refresh=True)
            opportunities = ranked.data.get("opportunities", []) if ranked.ok else []
            if not opportunities:
                return SkillResult(ok=False, error="no opportunities available")
            opportunity_id = opportunities[0]["id"]

        opportunity = _find_opportunity(opportunity_id)
        if not opportunity:
            return SkillResult(ok=False, error=f"opportunity not found: {opportunity_id}")

        experiment = {
            "id": f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{opportunity_id}",
            "opportunity_id": opportunity_id,
            "title": opportunity["title"],
            "hypothesis": opportunity["hypothesis"],
            "first_action": opportunity["first_reversible_action"],
            "kill_condition": opportunity["kill_condition"],
            "success_metric": _success_metric(opportunity),
            "risk_tier": opportunity.get("risk_tier", 2),
            "status": "planned",
            "created_at": datetime.now().isoformat(),
            "expected_income_inr": opportunity.get("expected_income_inr", 0),
            "score": opportunity.get("score", 0),
            "notes": "Do not send external messages or spend money without the normal approval flow.",
        }
        _append_jsonl(EXPERIMENTS_FILE, experiment)
        return SkillResult(ok=True, data=experiment, artifacts=[str(EXPERIMENTS_FILE)])

    def op_launch_experiment(self, opportunity_id: str = "", max_leads: int = 5,
                             dry_run: bool = False, **_) -> SkillResult:
        dry_run = _as_bool(dry_run)
        max_leads = max(1, min(_int(max_leads, 5), 10))
        if not opportunity_id:
            ranked = self.op_rank_opportunities(top_n=1, refresh=True)
            opportunities = ranked.data.get("opportunities", []) if ranked.ok else []
            if not opportunities:
                return SkillResult(ok=False, error="no opportunities available")
            opportunity_id = opportunities[0]["id"]

        opportunity = _find_opportunity(opportunity_id)
        if not opportunity:
            return SkillResult(ok=False, error=f"opportunity not found: {opportunity_id}")

        if dry_run:
            return SkillResult(ok=True, data={
                "dry_run": True,
                "opportunity_id": opportunity_id,
                "title": opportunity.get("title"),
                "would_create_experiment": True,
                "would_queue_outreach": opportunity_id in _OUTREACH_OPPORTUNITIES,
                "max_leads": max_leads,
                "first_reversible_action": opportunity.get("first_reversible_action"),
                "kill_condition": opportunity.get("kill_condition"),
                "safety": "No external messages, money movement, or public posts in dry-run.",
            })

        # Import here to avoid registry import cycles during module load.
        from friday.skills.registry import get_registry

        reg = get_registry()
        experiment = reg.invoke(
            "money_engine",
            "create_experiment",
            _actor="money_engine",
            _goal=opportunity_id,
            opportunity_id=opportunity_id,
        )
        if not experiment.ok:
            return experiment

        artifacts = list(experiment.artifacts)
        if opportunity_id not in _OUTREACH_OPPORTUNITIES:
            return SkillResult(ok=True, data={
                "experiment": experiment.data,
                "launched": False,
                "next_manual_action": opportunity.get("first_reversible_action"),
                "reason": "No automated safe launch adapter exists for this opportunity yet.",
            }, artifacts=artifacts)

        due = reg.invoke(
            "outreach",
            "find_due_leads",
            _actor="money_engine",
            _goal=experiment.data["id"],
            max_leads=max_leads,
        )
        if not due.ok:
            return SkillResult(ok=False, error=due.error or "failed to find due leads",
                               data={"experiment": experiment.data}, artifacts=artifacts + due.artifacts)

        drafts = reg.invoke(
            "outreach",
            "draft_next_touch",
            _actor="money_engine",
            _goal=experiment.data["id"],
            leads=(due.data or {}).get("due", [])[:max_leads],
        )
        if not drafts.ok:
            return SkillResult(ok=False, error=drafts.error or "failed to draft outreach",
                               data={"experiment": experiment.data, "due": due.data},
                               artifacts=artifacts + due.artifacts + drafts.artifacts)

        enriched_drafts = []
        for draft in (drafts.data or {}).get("drafts", [])[:max_leads]:
            enriched = dict(draft)
            enriched["experiment_id"] = experiment.data["id"]
            enriched["opportunity_id"] = opportunity_id
            enriched["money_engine"] = {
                "opportunity_title": opportunity.get("title"),
                "score": opportunity.get("score"),
                "kill_condition": opportunity.get("kill_condition"),
                "success_metric": experiment.data.get("success_metric"),
            }
            enriched_drafts.append(enriched)

        queued = reg.invoke(
            "outreach",
            "queue_for_approval",
            _actor="money_engine",
            _goal=experiment.data["id"],
            _expected_outcome="Queue money experiment outreach drafts for Bhargav review; do not send externally.",
            drafts=enriched_drafts,
        )
        if queued.ok:
            experiment.data.update(_update_experiment(
                experiment.data["id"],
                status="queued_for_approval",
                notes=f"Queued {len(enriched_drafts)} outreach drafts for Bhargav approval.",
                extra={"queued_for_approval": (queued.data or {}).get("queued", 0)},
            ) or {})
        artifacts.extend(due.artifacts)
        artifacts.extend(drafts.artifacts)
        artifacts.extend(queued.artifacts)
        artifacts = list(dict.fromkeys(artifacts))
        return SkillResult(ok=queued.ok, data={
            "experiment": experiment.data,
            "opportunity": opportunity,
            "due_leads": (due.data or {}).get("count", 0),
            "drafts": len(enriched_drafts),
            "queued_for_approval": (queued.data or {}).get("queued", 0),
            "next_step": "Bhargav reviews queued outreach drafts. Only after approval can Friday mark them for manual WhatsApp sending.",
            "nested_proofs": {
                "experiment": experiment.proof_path,
                "find_due_leads": due.proof_path,
                "draft_next_touch": drafts.proof_path,
                "queue_for_approval": queued.proof_path,
            },
        }, artifacts=artifacts, error=queued.error)

    def op_record_result(self, experiment_id: str = "", outcome: str = "", notes: str = "", **_) -> SkillResult:
        if not experiment_id:
            return SkillResult(ok=False, error="experiment_id required")
        valid = {"planned", "running", "won", "lost", "paused", "killed", "learned"}
        if outcome not in valid:
            return SkillResult(ok=False, error=f"invalid outcome '{outcome}'. Use one of {sorted(valid)}")
        experiments = _read_jsonl(EXPERIMENTS_FILE)
        for exp in experiments:
            if exp.get("id") == experiment_id:
                exp["status"] = outcome
                exp["result_notes"] = notes
                exp["updated_at"] = datetime.now().isoformat()
                _write_jsonl(EXPERIMENTS_FILE, experiments)
                return SkillResult(ok=True, data=exp, artifacts=[str(EXPERIMENTS_FILE)])
        return SkillResult(ok=False, error=f"experiment not found: {experiment_id}")

    def op_status(self, **_) -> SkillResult:
        opportunities = _read_jsonl(OPPORTUNITIES_FILE)
        experiments = _read_jsonl(EXPERIMENTS_FILE)
        by_exp_status: dict[str, int] = {}
        for exp in experiments:
            status = exp.get("status", "unknown")
            by_exp_status[status] = by_exp_status.get(status, 0) + 1
        top = sorted([_score_dict(o) for o in opportunities], key=lambda o: o.get("score", 0), reverse=True)[:3]
        return SkillResult(ok=True, data={
            "opportunities": len(opportunities),
            "experiments": len(experiments),
            "experiments_by_status": by_exp_status,
            "top_opportunities": top,
            "files": {
                "opportunities": str(OPPORTUNITIES_FILE),
                "experiments": str(EXPERIMENTS_FILE),
            },
        })


def _seed_opportunities(snapshot: dict[str, Any]) -> list[Opportunity]:
    signals = _snapshot_signals(snapshot)
    lead_count = signals["leads_total"]
    phone_count = signals["leads_with_phone"]
    closed = signals["crm_closed"]
    replied = signals["crm_replied"]

    whatsapp_probability = 0.22 + min(phone_count, 50) * 0.002 + min(replied, 5) * 0.02
    if closed == 0:
        whatsapp_probability -= 0.04
    whatsapp_probability = _clamp(whatsapp_probability, 0.12, 0.42)

    return [
        Opportunity(
            id="opp_local_whatsapp_pilot",
            title="Local WhatsApp AI bot pilot",
            category="agency",
            hypothesis="Local businesses with phone-heavy enquiry flows will pay for a 14-day WhatsApp bot pilot if the offer is concrete and low-risk.",
            evidence=[
                f"{lead_count} leads loaded",
                f"{phone_count} leads have phone numbers",
                "Existing outreach, approval queue, and manual WhatsApp outbox are wired",
            ],
            expected_income_inr=23000,
            probability_of_success=whatsapp_probability,
            speed_to_cash_days=7,
            owner_time_hours=4,
            cash_cost_inr=0,
            legal_risk=0.1,
            platform_risk=0.25,
            execution_complexity=2.0,
            compounding_potential=4.0,
            ethical_risk=0.05,
            first_reversible_action="Generate 10 approved WhatsApp pilot messages and manually send only after Bhargav reviews each one.",
            kill_condition="Kill or rewrite if 30 targeted sends produce zero qualified replies.",
            risk_tier=3,
            source="agency_pipeline",
        ),
        Opportunity(
            id="opp_auditmind_micro_audit",
            title="AuditMind SOX micro-audit offer",
            category="auditmind",
            hypothesis="Bhargav can package SOX/compliance knowledge into a fixed-scope AI-assisted audit workflow review.",
            evidence=[
                "AuditMind/SaaS lane exists in the FRIDAY capability manifest",
                "Bhargav has SOX/coaching context in the mission schedule",
                "Higher ticket size than generic automation gigs",
            ],
            expected_income_inr=50000,
            probability_of_success=0.16,
            speed_to_cash_days=21,
            owner_time_hours=10,
            cash_cost_inr=0,
            legal_risk=0.35,
            platform_risk=0.05,
            execution_complexity=3.5,
            compounding_potential=4.5,
            ethical_risk=0.1,
            first_reversible_action="Draft a one-page fixed-scope audit workflow review offer with explicit non-legal disclaimer and approval gate.",
            kill_condition="Pause if 10 warm prospects produce no calls or if compliance claims cannot be bounded safely.",
            risk_tier=3,
            source="auditmind_lane",
        ),
        Opportunity(
            id="opp_content_engine_build_in_public",
            title="Build-in-public AI automation content engine",
            category="content",
            hypothesis="Consistent proof-backed posts about FRIDAY/Nexus can attract leads and authority without ad spend.",
            evidence=[
                "Content drafting and auto-shorts skills exist",
                "FRIDAY now produces proof artifacts and capability reports",
                "Distribution can compound over time",
            ],
            expected_income_inr=12000,
            probability_of_success=0.28,
            speed_to_cash_days=30,
            owner_time_hours=3,
            cash_cost_inr=0,
            legal_risk=0.05,
            platform_risk=0.35,
            execution_complexity=1.5,
            compounding_potential=5.0,
            ethical_risk=0.05,
            first_reversible_action="Draft three proof-backed posts from recent FRIDAY build logs; queue for Bhargav approval before publishing.",
            kill_condition="Stop this angle if 20 posts produce no useful replies, calls, or inbound leads.",
            risk_tier=2,
            source="content_ai_studio",
        ),
        Opportunity(
            id="opp_creator_repupose_automation",
            title="Creator content repurposing automation package",
            category="agency",
            hypothesis="Small creators and coaches will pay for turning long content into posts, short scripts, and WhatsApp follow-ups.",
            evidence=[
                "Content drafting skill exists",
                "Auto-shorts adapter exists",
                "Offer can be demoed without touching client accounts",
            ],
            expected_income_inr=18000,
            probability_of_success=0.2,
            speed_to_cash_days=14,
            owner_time_hours=6,
            cash_cost_inr=0,
            legal_risk=0.08,
            platform_risk=0.3,
            execution_complexity=2.4,
            compounding_potential=3.8,
            ethical_risk=0.05,
            first_reversible_action="Create one sample repurposing pack from public/demo content and send only as a reviewed proposal.",
            kill_condition="Kill if 15 niche creator outreaches generate no demo requests.",
            risk_tier=3,
            source="content_ai_studio",
        ),
        Opportunity(
            id="opp_automation_template_marketplace",
            title="AI automation template pack",
            category="digital_product",
            hypothesis="Reusable prompts, SOPs, and lightweight scripts from FRIDAY/Nexus can become a low-ticket template product.",
            evidence=[
                "FRIDAY docs and playbooks are accumulating",
                "No client delivery dependency",
                "Low cash cost and high compounding potential",
            ],
            expected_income_inr=8000,
            probability_of_success=0.22,
            speed_to_cash_days=30,
            owner_time_hours=8,
            cash_cost_inr=0,
            legal_risk=0.05,
            platform_risk=0.2,
            execution_complexity=2.2,
            compounding_potential=4.2,
            ethical_risk=0.03,
            first_reversible_action="Package one internal SOP into a sanitized public template and validate interest with a draft landing note.",
            kill_condition="Do not build more than one pack until at least 5 people express interest.",
            risk_tier=2,
            source="knowledge_foundry",
        ),
        Opportunity(
            id="opp_freelance_ai_ops_gigs",
            title="Freelance AI ops implementation gigs",
            category="freelance",
            hypothesis="Businesses on freelance platforms need small AI automations; FRIDAY can help draft proposals and delivery plans.",
            evidence=[
                "Builder mode and research skills exist",
                "Agency offer can be reused",
                "External platform risk is manageable if Bhargav manually approves proposals",
            ],
            expected_income_inr=30000,
            probability_of_success=0.14,
            speed_to_cash_days=21,
            owner_time_hours=9,
            cash_cost_inr=0,
            legal_risk=0.12,
            platform_risk=0.45,
            execution_complexity=3.0,
            compounding_potential=3.0,
            ethical_risk=0.05,
            first_reversible_action="Draft five platform-specific proposal templates; Bhargav manually chooses whether to submit.",
            kill_condition="Pause if 25 tailored proposals produce no serious conversations.",
            risk_tier=3,
            source="freelance_lane",
        ),
        Opportunity(
            id="opp_trading_research_brief",
            title="Trading research brief product",
            category="research",
            hypothesis="Nexus Omega research can become educational market briefs without autonomous live trading.",
            evidence=[
                "Trading/Nexus state adapters exist",
                "Research and briefing skills exist",
                "Can remain educational and non-advisory",
            ],
            expected_income_inr=10000,
            probability_of_success=0.1,
            speed_to_cash_days=45,
            owner_time_hours=8,
            cash_cost_inr=0,
            legal_risk=0.55,
            platform_risk=0.25,
            execution_complexity=3.4,
            compounding_potential=3.5,
            ethical_risk=0.25,
            first_reversible_action="Draft one educational, non-advisory market research sample with clear disclaimers.",
            kill_condition="Do not monetize until compliance boundaries and audience demand are proven.",
            risk_tier=4,
            source="nexus_omega",
        ),
    ]


def _score_opportunity(opportunity: Opportunity) -> Opportunity:
    opportunity.score = _score_dict(opportunity.to_dict())["score"]
    opportunity.updated_at = datetime.now().isoformat()
    return opportunity


def _score_dict(opportunity: dict[str, Any]) -> dict[str, Any]:
    income = max(float(opportunity.get("expected_income_inr") or 0), 0)
    probability = _clamp(float(opportunity.get("probability_of_success") or 0), 0, 1)
    speed_days = max(float(opportunity.get("speed_to_cash_days") or 30), 1)
    owner_hours = max(float(opportunity.get("owner_time_hours") or 0), 0)
    cash_cost = max(float(opportunity.get("cash_cost_inr") or 0), 0)
    legal = _clamp(float(opportunity.get("legal_risk") or 0), 0, 1)
    platform = _clamp(float(opportunity.get("platform_risk") or 0), 0, 1)
    complexity = max(float(opportunity.get("execution_complexity") or 1), 0.1)
    compounding = max(float(opportunity.get("compounding_potential") or 1), 1)
    ethical = _clamp(float(opportunity.get("ethical_risk") or 0), 0, 1)

    speed_factor = 30 / speed_days
    compounding_factor = 1 + ((compounding - 1) * 0.2)
    risk_penalty = 1 + (legal * 2.0) + (platform * 1.5) + (ethical * 3.0) + (complexity * 0.35) + (owner_hours * 0.08) + (cash_cost / 10000)
    score = (income * probability * speed_factor * compounding_factor) / risk_penalty
    opportunity["score"] = round(score, 2)
    opportunity["score_label"] = _score_label(score)
    opportunity["updated_at"] = datetime.now().isoformat()
    return opportunity


def _snapshot_signals(snapshot: dict[str, Any]) -> dict[str, int]:
    agency = snapshot.get("agency", {}) if isinstance(snapshot, dict) else {}
    leads = agency.get("leads", {}) if isinstance(agency, dict) else {}
    crm = agency.get("crm", {}) if isinstance(agency, dict) else {}
    return {
        "leads_total": _int(leads.get("total"), 0),
        "leads_with_phone": _int(leads.get("with_phone"), 0),
        "crm_total_outreach": _int(crm.get("total_outreach"), 0),
        "crm_replied": _int(crm.get("replied"), 0),
        "crm_qualified": _int(crm.get("qualified"), 0),
        "crm_closed": _int(crm.get("closed"), 0),
    }


def _success_metric(opportunity: dict[str, Any]) -> str:
    category = opportunity.get("category")
    if category == "agency":
        return "qualified replies or booked demos"
    if category == "content":
        return "useful replies, inbound leads, or calls booked"
    if category == "auditmind":
        return "warm calls booked with bounded fixed-scope audit workflow offer"
    if category == "digital_product":
        return "validated interest before building more assets"
    return "measurable cash, lead, or learning outcome"


def _find_opportunity(opportunity_id: str) -> dict[str, Any] | None:
    if not OPPORTUNITIES_FILE.exists():
        MoneyEngineSkill().op_scan_opportunities(persist=True)
    for item in _read_jsonl(OPPORTUNITIES_FILE):
        if item.get("id") == opportunity_id:
            return _score_dict(item)
    return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                items.append(obj)
        except Exception:
            continue
    return items


def _write_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(item, default=str) for item in items) + ("\n" if items else ""))


def _update_experiment(experiment_id: str, status: str, notes: str = "",
                       extra: dict[str, Any] | None = None) -> dict[str, Any] | None:
    experiments = _read_jsonl(EXPERIMENTS_FILE)
    for exp in experiments:
        if exp.get("id") == experiment_id:
            exp["status"] = status
            exp["updated_at"] = datetime.now().isoformat()
            if notes:
                exp["launch_notes"] = notes
            if extra:
                exp.update(extra)
            _write_jsonl(EXPERIMENTS_FILE, experiments)
            return exp
    return None


def _append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(item, default=str) + "\n")


def _upsert_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    existing = {item.get("id"): item for item in _read_jsonl(path) if item.get("id")}
    for item in items:
        existing[item["id"]] = item
    _write_jsonl(path, list(existing.values()))


def _score_label(score: float) -> str:
    if score >= 2500:
        return "strike_now"
    if score >= 1000:
        return "test_next"
    if score >= 400:
        return "watch"
    return "low_priority"


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
