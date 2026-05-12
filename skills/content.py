"""
Friday :: Content Skill
Drafts posts, emails, replies. Everything passes through approval gate.
"""
from __future__ import annotations
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from .registry import Skill, Operation, SkillResult

FRIDAY = Path(os.path.expanduser("~/AI/friday"))
DRAFTS_DIR = FRIDAY / "data" / "drafts"
APPROVAL_FILE = FRIDAY / "data" / "pending_approvals.json"


def _save_draft(kind: str, content: str, meta: dict) -> str:
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    did = uuid.uuid4().hex[:8]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = DRAFTS_DIR / f"{stamp}_{kind}_{did}.md"
    path.write_text(f"# {kind} · {did}\n\n{json.dumps(meta, indent=2, default=str)}\n\n---\n\n{content}\n")
    return str(path)


def _field(prompt: str, name: str) -> str:
    prefix = f"{name}:"
    for line in prompt.splitlines():
        if line.lower().startswith(prefix.lower()):
            return line.split(":", 1)[1].strip()
    return ""


def _deterministic_draft(system_hint: str, prompt: str) -> str:
    """Local fallback so content workflows work even when no LLM is up."""
    topic = _field(prompt, "Topic")
    intent = _field(prompt, "Intent")
    incoming = _field(prompt, "Incoming")
    subject = _field(prompt, "Subject")

    if "reply" in system_hint.lower() or incoming:
        return (
            "Thanks for sending this. I have the context now.\n\n"
            "My direct take: we should move this to the next concrete step, keep the scope tight, "
            "and make sure there is proof of execution before we expand it."
        )

    if "email" in system_hint.lower() or intent:
        subject_line = subject or "Quick note"
        body_intent = intent or "move the conversation to a clear next step"
        return (
            f"Subject: {subject_line}\n\n"
            f"Hi,\n\n"
            f"I am reaching out with one specific intent: {body_intent}.\n\n"
            "If this is relevant, I can share a short working demo and keep it practical: problem, "
            "workflow, expected outcome, and next step.\n\n"
            "Best,\n"
            "Bhargav"
        )

    topic = topic or "Friday capability proof"
    return (
        f"Building {topic} is not about making a chatbot sound impressive.\n\n"
        "The useful bar is harder: it must understand the mission, act through tools, produce proof, "
        "remember what changed, and push the next revenue-bearing action.\n\n"
        "Today the focus is simple: less theatre, more operating loop. Capability without evidence is noise."
    )


class ContentSkill(Skill):
    name = "content"
    description = "Draft posts, emails, replies. Never publishes without approval."

    def _register_operations(self) -> None:
        self.register_op(Operation("draft_post", "Draft a LinkedIn/Twitter post.",
                                   fn=self.op_draft_post, risk="low"))
        self.register_op(Operation("draft_email", "Draft an outbound email.",
                                   fn=self.op_draft_email, risk="low"))
        self.register_op(Operation("draft_reply", "Draft a reply to an incoming message.",
                                   fn=self.op_draft_reply, risk="low"))
        self.register_op(Operation("queue_for_approval", "Queue a draft for Telegram approval.",
                                   fn=self.op_queue_for_approval, risk="medium"))

    def _gen(self, system_hint: str, prompt: str) -> str:
        if os.environ.get("FRIDAY_LLM_CONTENT", "").strip().lower() not in {"1", "true", "yes"}:
            return _deterministic_draft(system_hint, prompt)
        from friday.brain.engine import MultiEngine
        from friday.brain.personality import system_prompt
        try:
            eng = MultiEngine()
            sysp = system_prompt(task_hint=system_hint)
            msg, _ = eng.ask(sysp, prompt, force="ollama")
            return msg.strip()
        except Exception:
            return _deterministic_draft(system_hint, prompt)

    def op_draft_post(self, topic: str = "", tone: str = "builder-honest",
                      platform: str = "linkedin", **_) -> SkillResult:
        if not topic:
            return SkillResult(ok=False, error="topic required")
        system_hint = (f"Draft a {platform} post. Tone: {tone}. "
                       f"Skin-in-the-game. Numbers-first. 100-200 words. No hashtags spam.")
        content = self._gen(system_hint, f"Topic: {topic}")
        path = _save_draft("post", content, {"topic": topic, "platform": platform, "tone": tone})
        return SkillResult(ok=True, data={"draft": content, "path": path,
                                           "id": uuid.uuid4().hex[:8]},
                           artifacts=[path])

    def op_draft_email(self, to: str = "", subject: str = "", intent: str = "", **_) -> SkillResult:
        if not intent:
            return SkillResult(ok=False, error="intent required")
        system_hint = "Draft a business email. Under 120 words. No 'hope this finds you well'. Direct."
        prompt = f"To: {to}\nSubject: {subject}\nIntent: {intent}\n\nDraft the email body."
        content = self._gen(system_hint, prompt)
        path = _save_draft("email", content, {"to": to, "subject": subject, "intent": intent})
        return SkillResult(ok=True, data={"draft": content, "path": path, "to": to, "subject": subject},
                           artifacts=[path])

    def op_draft_reply(self, incoming: str = "", context: str = "", **_) -> SkillResult:
        if not incoming:
            return SkillResult(ok=False, error="incoming message required")
        system_hint = "Draft a reply. Match tone of incoming. Under 80 words. No hedging."
        prompt = f"Incoming: {incoming}\nContext: {context}\n\nDraft reply:"
        content = self._gen(system_hint, prompt)
        path = _save_draft("reply", content, {"incoming_preview": incoming[:120]})
        return SkillResult(ok=True, data={"draft": content, "path": path},
                           artifacts=[path])

    def op_queue_for_approval(self, draft: str, kind: str = "content",
                              meta: dict | None = None, **_) -> SkillResult:
        """Generic content approval queuer."""
        if not draft:
            return SkillResult(ok=False, error="draft required")
        pending = []
        if APPROVAL_FILE.exists():
            try:
                pending = json.loads(APPROVAL_FILE.read_text())
            except Exception:
                pending = []
        did = uuid.uuid4().hex[:8]
        pending.append({
            "id": did, "kind": kind, "skill": "content", "operation": "approved_publish",
            "payload": {"draft": draft, "meta": meta or {}},
            "created_at": datetime.now().isoformat(),
            "status": "pending",
        })
        APPROVAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        APPROVAL_FILE.write_text(json.dumps(pending, indent=2, default=str))
        from friday.actions import comms
        comms.telegram_push(
            f"📝 *Draft queued [{did}]* ({kind})\n\n{draft[:500]}...\n\n/yes {did} · /no {did}",
            silent=True,
        )
        return SkillResult(ok=True, data={"id": did, "queued": True},
                           artifacts=[str(APPROVAL_FILE)])
