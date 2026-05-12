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
from urllib.parse import quote

from .registry import Skill, Operation, SkillResult

FRIDAY = Path(os.path.expanduser("~/AI/friday"))
LEADS_CSV = Path(os.path.expanduser("~/agency/outreach/leads.csv"))
CRM_CSV = Path(os.path.expanduser("~/agency/outreach/crm_tracker.csv"))
APPROVAL_FILE = FRIDAY / "data" / "pending_approvals.json"
OUTBOX_DIR = FRIDAY / "data" / "outbox"

CRM_FIELDS = [
    "#", "Business Name", "Type", "Contact Person", "Phone", "WhatsApp",
    "Email", "Location", "Channel", "First Contact", "Response", "Status",
    "Follow Up Date", "Notes", "Deal Value"
]


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


def _crm_fieldnames() -> list[str]:
    if not CRM_CSV.exists() or CRM_CSV.stat().st_size == 0:
        return list(CRM_FIELDS)
    with open(CRM_CSV, newline="") as f:
        reader = csv.reader(f)
        try:
            fields = next(reader)
        except StopIteration:
            return list(CRM_FIELDS)
    return fields or list(CRM_FIELDS)


def _append_crm_touch(draft: dict, outcome: str = "sent_stub", notes: str = "") -> dict:
    CRM_CSV.parent.mkdir(parents=True, exist_ok=True)
    rows = _load_crm()
    fields = _crm_fieldnames()
    lead = draft.get("lead", {}) if isinstance(draft, dict) else {}
    phone = lead.get("phone", "")
    biz = lead.get("business") or lead.get("name", "")
    category = lead.get("category") or lead.get("type", "")
    location = lead.get("area") or lead.get("location", "")
    now = datetime.now()

    # Existing tracker uses business-facing headers. Keep that schema intact.
    row = {f: "" for f in fields}
    row.update({
        "#": str(len([r for r in rows if any((v or "").strip() for v in r.values())]) + 1),
        "Business Name": biz,
        "Type": category,
        "Phone": phone,
        "WhatsApp": phone,
        "Location": location,
        "Channel": "WhatsApp",
        "First Contact": now.isoformat(),
        "Response": outcome,
        "Status": outcome,
        "Notes": notes or f"Friday outreach draft {draft.get('id', '')}: {draft.get('proposed_message', '')[:220]}",
    })

    # Also support older lowercase schemas if present.
    row.update({
        "phone": phone,
        "last_touch": now.isoformat(),
        "stage": outcome,
        "touches": "1",
        "business": biz,
        "message": draft.get("proposed_message", ""),
    })
    row = {k: v for k, v in row.items() if k in fields}

    exists = CRM_CSV.exists() and CRM_CSV.stat().st_size > 0
    with open(CRM_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow(row)
    return {"business": biz, "phone": phone, "outcome": outcome, "crm": str(CRM_CSV)}


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


def _phone_digits(phone: str) -> str:
    return "".join(ch for ch in str(phone or "") if ch.isdigit())


def _wa_phone(phone: str) -> str:
    digits = _phone_digits(phone)
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0") and len(digits) > 10:
        digits = digits.lstrip("0")
    if len(digits) == 10:
        return "91" + digits
    if len(digits) == 11 and digits.startswith("0"):
        return "91" + digits[1:]
    return digits


def _wa_link(phone: str, message: str) -> str:
    return f"https://wa.me/{_wa_phone(phone)}?text={quote(message or '')}"


def _outreach_items(statuses: set[str] | None = None) -> list[dict]:
    statuses = statuses or {"sent_stub", "manual_ready"}
    items = []
    for approval in _load_approvals():
        if approval.get("kind") != "outreach_message":
            continue
        if approval.get("status") not in statuses:
            continue
        payload = approval.get("payload") or {}
        lead = payload.get("lead") or {}
        message = payload.get("proposed_message", "")
        phone = lead.get("phone", "")
        items.append({
            "id": approval.get("id"),
            "status": approval.get("status"),
            "business": lead.get("business") or lead.get("name", ""),
            "category": lead.get("category", ""),
            "area": lead.get("area", ""),
            "phone": phone,
            "wa_phone": _wa_phone(phone),
            "message": message,
            "whatsapp_url": _wa_link(phone, message),
        })
    return items


def _write_outbox(items: list[dict]) -> list[str]:
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = OUTBOX_DIR / f"whatsapp_outbox_{stamp}.md"
    csv_path = OUTBOX_DIR / f"whatsapp_outbox_{stamp}.csv"
    html_path = OUTBOX_DIR / f"whatsapp_outbox_{stamp}.html"

    md_lines = [
        "# Friday WhatsApp Manual Send Outbox",
        "",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "Open each WhatsApp link, verify the message, then press send manually.",
        "After sending, run:",
        "",
        "`friday skill outreach record_outcome approval_id=<ID> outcome=manual_sent notes=\"sent manually\"`",
        "",
    ]
    for item in items:
        md_lines.extend([
            f"## {item['business']} [{item['id']}]",
            "",
            f"- Phone: `{item['phone']}`",
            f"- WhatsApp: [{item['wa_phone']}]({item['whatsapp_url']})",
            f"- Status: `{item['status']}`",
            "",
            "```text",
            item["message"],
            "```",
            "",
        ])
    md_path.write_text("\n".join(md_lines))

    with open(csv_path, "w", newline="") as f:
        fields = ["id", "business", "category", "area", "phone", "wa_phone", "status", "whatsapp_url", "message"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for item in items:
            writer.writerow({k: item.get(k, "") for k in fields})

    cards = []
    for item in items:
        message = (item["message"] or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        cards.append(f"""
        <section class="card">
          <div class="meta">{item['id']} · {item['status']} · {item['category']} · {item['area']}</div>
          <h2>{item['business']}</h2>
          <p class="phone">{item['phone']} → {item['wa_phone']}</p>
          <pre>{message}</pre>
          <a class="button" href="{item['whatsapp_url']}">Open WhatsApp</a>
          <p class="cmd">friday skill outreach record_outcome approval_id={item['id']} outcome=manual_sent notes="sent manually"</p>
        </section>
        """)
    html_path.write_text(f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Friday WhatsApp Outbox</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; background: #f7f7f4; color: #181816; }}
    h1 {{ margin-bottom: 4px; }}
    .sub {{ color: #666; margin-bottom: 24px; }}
    .card {{ background: white; border: 1px solid #deded8; border-radius: 8px; padding: 18px; margin: 14px 0; max-width: 900px; }}
    .meta, .cmd, .phone {{ color: #666; font-size: 13px; }}
    pre {{ white-space: pre-wrap; font-size: 14px; line-height: 1.45; background: #f1f1ed; padding: 12px; border-radius: 6px; }}
    .button {{ display: inline-block; background: #0b7a3b; color: white; text-decoration: none; padding: 10px 14px; border-radius: 6px; font-weight: 600; }}
  </style>
</head>
<body>
  <h1>Friday WhatsApp Manual Send Outbox</h1>
  <p class="sub">Generated {datetime.now().isoformat()} · Open, verify, send manually, then record outcome.</p>
  {''.join(cards)}
</body>
</html>
""")
    return [str(md_path), str(csv_path), str(html_path)]


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
        self.register_op(Operation("record_outcome",
                                   "Record an outreach outcome/reply in the CRM tracker.",
                                   fn=self.op_record_outcome, risk="medium"))
        self.register_op(Operation("manual_send_outbox",
                                   "Generate WhatsApp manual-send links for approved/stubbed outreach.",
                                   fn=self.op_manual_send_outbox, risk="low"))
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
        drafts = []
        for lead in leads[:10]:
            biz = lead.get("business", lead.get("name", "the business"))
            niche = lead.get("niche", "")
            stage = lead.get("stage", "cold")
            if os.environ.get("FRIDAY_LLM_OUTREACH") == "1":
                from friday.brain.engine import MultiEngine
                from friday.brain.personality import system_prompt
                eng = MultiEngine()
                sysp = system_prompt(task_hint="Draft a single-paragraph WhatsApp outreach message. No greeting fluff. Hyderabad/India context. Include one specific pain + one specific outcome. <120 words.")
                prompt = (f"Lead: {biz} ({niche}). Stage: {stage}. Reason to follow up: {lead.get('reason', '')}.\n"
                          f"Draft a WhatsApp message from Bhargav (founder, Nexus Automation). "
                          f"We build WhatsApp AI bots: ₹15K setup + ₹8K/mo. Offer: 14-day pilot, zero risk.")
                try:
                    msg, _ = eng.ask(sysp, prompt, force="ollama")
                except Exception as e:
                    msg = f"[draft error: {e}]"
            else:
                niche_text = f" for {niche}" if niche else ""
                stage_text = "following up" if stage != "cold" else "reaching out"
                msg = (
                    f"Hi {biz}, Bhargav here from Nexus Automation. I am {stage_text} "
                    f"because many Hyderabad businesses{niche_text} lose enquiries when "
                    f"WhatsApp replies are slow or inconsistent. We set up a WhatsApp AI "
                    f"bot that answers FAQs, captures leads, and escalates serious buyers "
                    f"to you. Setup is ₹15K plus ₹8K/month, with a 14-day pilot so you can "
                    f"see the replies before committing. Worth testing this week?"
                )
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
        crm_records = []
        for p in to_send:
            payload = p.get("payload") or {}
            p["status"] = "sent_stub"
            p["sent_at"] = datetime.now().isoformat()
            if payload:
                crm_records.append(_append_crm_touch(
                    payload,
                    outcome="sent_stub",
                    notes="Approved in Friday. WhatsApp client not wired; manual send required."
                ))
            sent += 1
        _save_approvals(pending)
        return SkillResult(ok=True, data={
            "sent": sent,
            "crm_records": crm_records,
            "note": "stub — WA client not wired in v1.0; CRM touch recorded for manual send follow-up"
        }, artifacts=[str(CRM_CSV)])

    def op_record_outcome(self, approval_id: str = "", outcome: str = "replied",
                          notes: str = "", **_) -> SkillResult:
        valid = {"sent_stub", "manual_sent", "no_reply", "replied", "qualified", "closed", "lost"}
        if outcome not in valid:
            return SkillResult(ok=False, error=f"invalid outcome '{outcome}'. Use one of {sorted(valid)}")
        pending = _load_approvals()
        match = next((p for p in pending if p.get("id") == approval_id), None)
        if not match:
            return SkillResult(ok=False, error=f"approval_id not found: {approval_id}")
        payload = match.get("payload") or match.get("kwargs", {}).get("payload") or {}
        if not payload and match.get("kwargs", {}).get("drafts"):
            return SkillResult(ok=False, error="approval_id points to a batch, not a single outreach draft")
        rec = _append_crm_touch(payload, outcome=outcome, notes=notes)
        match["status"] = outcome
        match["outcome_at"] = datetime.now().isoformat()
        match["outcome_notes"] = notes
        _save_approvals(pending)
        return SkillResult(ok=True, data=rec, artifacts=[str(CRM_CSV)])

    def op_manual_send_outbox(self, statuses: str = "sent_stub,manual_ready", **_) -> SkillResult:
        wanted = {s.strip() for s in statuses.split(",") if s.strip()}
        items = _outreach_items(wanted)
        if not items:
            return SkillResult(ok=True, data={
                "count": 0,
                "note": f"no outreach approvals with statuses {sorted(wanted)}"
            })
        artifacts = _write_outbox(items)
        return SkillResult(ok=True, data={
            "count": len(items),
            "statuses": sorted(wanted),
            "outbox_markdown": artifacts[0],
            "outbox_csv": artifacts[1],
            "outbox_html": artifacts[2],
            "next_instruction": "Open the HTML/Markdown outbox, send manually in WhatsApp, then record manual_sent/replied/qualified/closed outcomes."
        }, artifacts=artifacts)

    def op_status(self, **_) -> SkillResult:
        leads = _load_leads()
        pending = _load_approvals()
        crm = _load_crm()
        statuses = {}
        for p in pending:
            statuses[p.get("status", "?")] = statuses.get(p.get("status", "?"), 0) + 1
        crm_stages = {}
        for row in crm:
            if not any((v or "").strip() for v in row.values()):
                continue
            stage = (row.get("stage") or row.get("Status") or row.get("Response") or "unknown").strip().lower()
            crm_stages[stage] = crm_stages.get(stage, 0) + 1
        return SkillResult(ok=True, data={
            "total_leads": len(leads),
            "approval_queue": statuses,
            "pending_count": statuses.get("pending", 0),
            "crm_total": sum(crm_stages.values()),
            "crm_stages": crm_stages,
        })
