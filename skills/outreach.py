"""
Friday :: Outreach Skill
Autonomous lead-nurture engine. Runs 18:00-22:00 daily (non-Sunday).

Flow:
  1. find_due_leads    — read leads CSV, find ones due a follow-up
  2. draft_next_touch  — LLM drafts personalized message for each
  3. queue_for_approval — push to pending_approvals.json + telegram

User approves via `/yes <id>` in telegram. Then a separate sender skill
(out of v1.0 scope — stub below) actually pushes to WhatsApp.
"""
from __future__ import annotations
import csv
import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from .registry import Skill, Operation, SkillResult

FRIDAY = Path(os.path.expanduser("~/AI/friday"))
LEADS_CSV = Path(os.path.expanduser("~/agency/outreach/leads.csv"))
CRM_CSV = Path(os.path.expanduser("~/agency/outreach/crm_tracker.csv"))
APPROVAL_FILE = FRIDAY / "data" / "pending_approvals.json"


def _load_leads() -> list[dict]:
    if not LEADS_CSV.exists():
        return []
    with open(LEADS_CSV) as f:
        return list(csv.DictReader(f))


def _load_crm() -> list[dict]:
    if not CRM_CSV.exists():
        return []
    with open(CRM_CSV) as f:
        return list(csv.DictReader(f))


def _save_approvals(approvals: list[dict]) -> None:
    APPROVAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    APPROVAL_FILE.write_text(json.dumps(approvals, indent=2, default=str))


def _load_approvals() -> list[dict]:
    if not APPROVAL_FILE.exists():
        return []
    try:
        return json.loads(APPROVAL_FILE.read_text())
    except Exception:
        return []


class OutreachSkill(Skill):
    name = "outreach"
    description = "Find due leads, draft personalized next-touches, queue for approval."

    def _register_operations(self) -> None:
        self.register_op(Operation("find_due_leads", "Return leads due for a follow-up touch.",
                                   fn=self.op_find_due_leads, risk="low"))
        self.register_op(Operation("draft_next_touch", "Draft a personalized message per lead.",
                                   fn=self.op_draft_next_touch, risk="low"))
        self.register_op(Operation("queue_for_approval",
                                   "Push proposed messages to Telegram for approval.",
                                   fn=self.op_queue_for_approval, risk="medium"))
        self.register_op(Operation("send_approved",
                                   "Actually send messages with approved IDs (stub until WA client wired).",
                                   fn=self.op_send_approved, risk="high", requires_confirm=True))
        self.register_op(Operation("status", "Outreach pipeline summary.",
                                   fn=self.op_status, risk="low"))

    # -- operations --
    def op_find_due_leads(self, max_leads: int = 10, **_) -> SkillResult:
        leads = _load_leads()
        crm = _load_crm()
        # crm has columns: phone, last_touch, stage, touches
        last_touch_by_phone = {}
        for row in crm:
            phone = row.get("phone", "").strip()
            if phone:
                last_touch_by_phone[phone] = row
        now = datetime.now()
        due = []
        for lead in leads:
            phone = lead.get("phone", "").strip()
            if not phone:
                continue
            crm_row = last_touch_by_phone.get(phone, {})
            stage = crm_row.get("stage", "cold")
            last_ts = crm_row.get("last_touch", "")
            try:
                last_dt = datetime.fromisoformat(last_ts) if last_ts else None
            except Exception:
                last_dt = None
            # Rule: cold → touch if never touched. warm → 48h. negotiation → 24h.
            if stage == "cold" and last_dt is None:
                due.append({**lead, "stage": stage, "reason": "never touched"})
            elif last_dt is not None:
                age_h = (now - last_dt).total_seconds() / 3600
                if stage == "cold" and age_h >= 72:
                    due.append({**lead, "stage": stage, "reason": f"cold {age_h:.0f}h"})
                elif stage == "warm" and age_h >= 48:
                    due.append({**lead, "stage": stage, "reason": f"warm {age_h:.0f}h"})
                elif stage == "negotiation" and age_h >= 24:
                    due.append({**lead, "stage": stage, "reason": f"negotiation {age_h:.0f}h"})
            if len(due) >= max_leads:
                break
        return SkillResult(ok=True, data={"due": due, "count": len(due),
                                           "total_leads": len(leads)})

    def op_draft_next_touch(self, leads: list[dict] | None = None, **_) -> SkillResult:
        if leads is None:
            leads = self.op_find_due_leads().data.get("due", [])
        if not leads:
            return SkillResult(ok=True, data={"drafts": [], "count": 0})
        # Use the engine to draft each
        from friday.brain.engine import MultiEngine
        from friday.brain.personality import system_prompt
        eng = MultiEngine()
        sysp = system_prompt(task_hint="Draft a single-paragraph WhatsApp outreach message. No greeting fluff. Hyderabad/India context. Include one specific pain + one specific outcome. <120 words.")
        drafts = []
        for lead in leads[:10]:
            biz = lead.get("business", lead.get("name", "the business"))
            niche = lead.get("niche", "")
            stage = lead.get("stage", "cold")
            prompt = (f"Lead: {biz} ({niche}). Stage: {stage}. Reason to follow up: {lead.get('reason', '')}.\n"
                      f"Draft a WhatsApp message from Bhargav (founder, Nexus Automation). "
                      f"We build WhatsApp AI bots: ₹15K setup + ₹8K/mo. Offer: 14-day pilot, zero risk.")
            try:
                msg, _ = eng.ask(sysp, prompt, force="ollama")
            except Exception as e:
                msg = f"[draft error: {e}]"
            drafts.append({
                "id": uuid.uuid4().hex[:8],
                "lead": lead,
                "proposed_message": msg.strip(),
                "drafted_at": datetime.now().isoformat(),
                "status": "proposed",
            })
        return SkillResult(ok=True, data={"drafts": drafts, "count": len(drafts)})

    def op_queue_for_approval(self, drafts: list[dict] | None = None, **_) -> SkillResult:
        if drafts is None:
            drafts = self.op_draft_next_touch().data.get("drafts", [])
        if not drafts:
            return SkillResult(ok=True, data={"queued": 0}, error="no drafts to queue")
        pending = _load_approvals()
        for d in drafts:
            pending.append({
                "id": d["id"],
                "kind": "outreach_message",
                "skill": "outreach",
                "operation": "send_approved",
                "payload": d,
                "created_at": datetime.now().isoformat(),
                "status": "pending",
            })
        _save_approvals(pending)
        # Notify
        from friday.actions import comms
        lines = [f"📨 *{len(drafts)} outreach drafts queued. Review + approve:*\n"]
        for d in drafts[:5]:
            biz = d["lead"].get("business", d["lead"].get("name", "?"))
            preview = d["proposed_message"][:180].replace("*", "")
            lines.append(f"*[{d['id']}]* {biz}:\n{preview}...\n")
        lines.append(f"\nApprove: /yes <id>  |  Reject: /no <id>")
        comms.telegram_push("\n".join(lines)[:3900], silent=True)
        return SkillResult(ok=True, data={"queued": len(drafts)},
                           artifacts=[str(APPROVAL_FILE)])

    def op_send_approved(self, approval_id: str | None = None, **_) -> SkillResult:
        pending = _load_approvals()
        to_send = [p for p in pending if p.get("status") == "approved"
                   and (approval_id is None or p.get("id") == approval_id)]
        if not to_send:
            return SkillResult(ok=False, error="no approved messages to send")
        # STUB: In v1.0 we log + mark-sent. Real WA send wired in v1.1.
        sent = 0
        for p in to_send:
            p["status"] = "sent_stub"
            p["sent_at"] = datetime.now().isoformat()
            sent += 1
        _save_approvals(pending)
        return SkillResult(ok=True, data={"sent": sent, "note": "stub — WA client not wired in v1.0"})

    def op_status(self, **_) -> SkillResult:
        leads = _load_leads()
        pending = _load_approvals()
        statuses = {}
        for p in pending:
            statuses[p.get("status", "?")] = statuses.get(p.get("status", "?"), 0) + 1
        return SkillResult(ok=True, data={
            "total_leads": len(leads),
            "approval_queue": statuses,
            "pending_count": statuses.get("pending", 0),
        })
