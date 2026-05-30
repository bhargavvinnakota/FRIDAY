from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .memory import Memory

FRIDAY_ROOT = Path(os.path.expanduser("~/AI/friday"))
DEFAULT_STATE_DIR = Path(os.path.expanduser("~/.openclaw"))
DEFAULT_OUTPUT_DIR = FRIDAY_ROOT / "data" / "openclaw"

IGNORED_ASSISTANT_TEXTS = {
    "",
    "NO_REPLY",
    "HEARTBEAT_OK",
    "[assistant turn failed before producing content]",
}


@dataclass
class TranscriptMessage:
    timestamp: str
    role: str
    text: str
    kind: str
    source_file: str


def _normalize_text(text: str) -> str:
    return " ".join((text or "").split())


def _extract_text(message: dict[str, Any]) -> str:
    content = message.get("content") or []
    parts: list[str] = []
    for item in content:
        if item.get("type") == "text":
            parts.append(item.get("text", ""))
    return _normalize_text(" ".join(parts))


def _clean_assistant_text(text: str) -> str:
    prefix = "[[reply_to_current]] "
    if text.startswith(prefix):
        text = text[len(prefix):]
    return text


def classify_user_prompt(text: str) -> str:
    if text == "[OpenClaw heartbeat poll]":
        return "heartbeat_poll"
    if text.startswith("Read HEARTBEAT.md if it exists"):
        return "heartbeat_prompt"
    if text.startswith("Sender (untrusted metadata):"):
        return "transport_metadata"
    if text.startswith("System:"):
        return "system_injected"
    return "owner_prompt"


def classify_assistant_reply(text: str) -> str:
    if text.startswith("⚠️ Agent failed before reply:"):
        return "ignored_assistant"
    if text in IGNORED_ASSISTANT_TEXTS:
        return "ignored_assistant"
    return "substantive_assistant"


def _session_files(state_dir: Path) -> list[Path]:
    session_dir = state_dir / "agents" / "main" / "sessions"
    if not session_dir.exists():
        return []
    files: list[Path] = []
    for path in session_dir.iterdir():
        name = path.name
        if not path.is_file():
            continue
        if name.endswith(".trajectory.jsonl") or name.endswith(".trajectory-path.json"):
            continue
        if name == "sessions.json" or ".bak-" in name:
            continue
        if name.endswith(".jsonl") or ".jsonl.reset." in name:
            files.append(path)
    return sorted(files)


def collect_messages(state_dir: Path = DEFAULT_STATE_DIR) -> list[TranscriptMessage]:
    messages: list[TranscriptMessage] = []
    for path in _session_files(state_dir):
        try:
            with open(path) as handle:
                for raw in handle:
                    raw = raw.strip()
                    if not raw:
                        continue
                    obj = json.loads(raw)
                    if obj.get("type") != "message":
                        continue
                    message = obj.get("message") or {}
                    role = message.get("role")
                    if role not in {"user", "assistant"}:
                        continue
                    text = _extract_text(message)
                    if role == "assistant":
                        text = _clean_assistant_text(text)
                    kind = classify_user_prompt(text) if role == "user" else classify_assistant_reply(text)
                    messages.append(
                        TranscriptMessage(
                            timestamp=obj.get("timestamp") or message.get("timestamp") or "",
                            role=role,
                            text=text,
                            kind=kind,
                            source_file=path.name,
                        )
                    )
        except Exception:
            continue
    messages.sort(key=lambda msg: (msg.timestamp, msg.source_file, msg.role))
    return messages


def _owner_prompt_pairs(messages: list[TranscriptMessage]) -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    pending: TranscriptMessage | None = None
    for msg in messages:
        if msg.role == "user":
            if msg.kind == "owner_prompt":
                pending = msg
            elif msg.kind in {"heartbeat_poll", "heartbeat_prompt"}:
                pending = None
        elif msg.role == "assistant":
            if pending is None:
                continue
            if msg.kind == "substantive_assistant":
                pairs.append(
                    {
                        "prompt_ts": pending.timestamp,
                        "prompt": pending.text,
                        "reply_ts": msg.timestamp,
                        "reply": msg.text,
                    }
                )
                pending = None
    return pairs


def _top_substantive_assistant_replies(messages: list[TranscriptMessage]) -> list[dict[str, str]]:
    replies: list[dict[str, str]] = []
    seen: set[str] = set()
    for msg in messages:
        if msg.role != "assistant" or msg.kind != "substantive_assistant":
            continue
        if msg.text in seen:
            continue
        seen.add(msg.text)
        replies.append(
            {
                "timestamp": msg.timestamp,
                "reply": msg.text,
                "source_file": msg.source_file,
            }
        )
    return replies


def _system_injected_prompts(messages: list[TranscriptMessage]) -> list[dict[str, str]]:
    prompts: list[dict[str, str]] = []
    for msg in messages:
        if msg.role == "user" and msg.kind in {"transport_metadata", "system_injected"}:
            prompts.append(
                {
                    "timestamp": msg.timestamp,
                    "kind": msg.kind,
                    "prompt": msg.text,
                    "source_file": msg.source_file,
                }
            )
    return prompts


def _distilled_traits() -> list[str]:
    return [
        "Identity-led operator voice: names itself, speaks with purpose, avoids generic assistant phrasing.",
        "Anchors replies to live state: IST time, battery, system status, and concrete shell-verified facts.",
        "Keeps one eye on revenue: bot clients, leads, and short-term money targets surface repeatedly.",
        "Maintains trading awareness through Nexus Omega and market-regime checks.",
        "Uses short proactive heartbeat style: brief, direct, only speaks when there is signal.",
        "Prefers action and verification over abstraction: check battery, run the tool, then report.",
    ]


def _persona_context(state_dir: Path) -> dict[str, str]:
    workspace = state_dir / "workspace"
    identity = workspace / "IDENTITY.md"
    soul = workspace / "SOUL.md"
    out: dict[str, str] = {}
    if identity.exists():
        out["identity_file"] = str(identity)
    if soul.exists():
        out["soul_file"] = str(soul)
    out["persona_name"] = "NEXUS"
    out["persona_summary"] = "Bhargav's second brain, force multiplier, direct and execution-oriented."
    return out


def build_seed_report(state_dir: Path = DEFAULT_STATE_DIR) -> dict[str, Any]:
    messages = collect_messages(state_dir)
    owner_prompts = [
        {
            "timestamp": msg.timestamp,
            "prompt": msg.text,
            "source_file": msg.source_file,
        }
        for msg in messages
        if msg.role == "user" and msg.kind == "owner_prompt"
    ]
    report = {
        "generated_at": datetime.now().isoformat(),
        "source_state_dir": str(state_dir),
        "persona": _persona_context(state_dir),
        "counts": {
            "messages_total": len(messages),
            "user_messages": sum(1 for msg in messages if msg.role == "user"),
            "assistant_messages": sum(1 for msg in messages if msg.role == "assistant"),
            "owner_prompts": len(owner_prompts),
            "heartbeat_prompts": sum(1 for msg in messages if msg.kind == "heartbeat_poll"),
            "heartbeat_setup_prompts": sum(1 for msg in messages if msg.kind == "heartbeat_prompt"),
            "system_injected_prompts": sum(1 for msg in messages if msg.kind in {"transport_metadata", "system_injected"}),
            "substantive_assistant_replies": sum(1 for msg in messages if msg.kind == "substantive_assistant"),
        },
        "owner_prompts": owner_prompts,
        "owner_prompt_reply_pairs": _owner_prompt_pairs(messages),
        "system_injected_prompts": _system_injected_prompts(messages),
        "substantive_assistant_replies": _top_substantive_assistant_replies(messages),
        "distilled_traits": _distilled_traits(),
    }
    return report


def render_seed_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# OpenClaw Conversational Seed",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Source: `{report['source_state_dir']}`",
        "",
        "## Summary",
        "",
        f"- Owner-authored prompts retained: `{report['counts']['owner_prompts']}`",
        f"- Heartbeat poll prompts: `{report['counts']['heartbeat_prompts']}`",
        f"- Heartbeat setup prompts: `{report['counts']['heartbeat_setup_prompts']}`",
        f"- System-injected prompt-like messages: `{report['counts']['system_injected_prompts']}`",
        f"- Substantive assistant replies retained: `{report['counts']['substantive_assistant_replies']}`",
        "",
        "## Persona Context",
        "",
        f"- Name: `{report['persona']['persona_name']}`",
        f"- Summary: {report['persona']['persona_summary']}",
    ]
    if report["persona"].get("identity_file"):
        lines.append(f"- Identity file: `{report['persona']['identity_file']}`")
    if report["persona"].get("soul_file"):
        lines.append(f"- Soul file: `{report['persona']['soul_file']}`")

    lines.extend(["", "## Owner Prompts", ""])
    if report["owner_prompts"]:
        for item in report["owner_prompts"]:
            lines.extend(
                [
                    f"### {item['timestamp']}",
                    "",
                    item["prompt"],
                    "",
                ]
            )
    else:
        lines.extend(["No substantive owner-authored prompts retained.", ""])

    lines.extend(["## Owner Prompt -> Reply Pairs", ""])
    if report["owner_prompt_reply_pairs"]:
        for item in report["owner_prompt_reply_pairs"]:
            lines.extend(
                [
                    f"### {item['prompt_ts']}",
                    "",
                    f"Prompt: {item['prompt']}",
                    "",
                    f"Reply: {item['reply']}",
                    "",
                ]
            )
    else:
        lines.extend(["No direct substantive prompt/reply pairs retained.", ""])

    lines.extend(["## System-Injected Prompt-Like Messages", ""])
    if report["system_injected_prompts"]:
        for item in report["system_injected_prompts"]:
            lines.extend(
                [
                    f"- `{item['timestamp']}` [{item['kind']}] {item['prompt']}",
                ]
            )
    else:
        lines.append("- None retained.")

    lines.extend(["", "## Substantive Assistant Replies", ""])
    if report["substantive_assistant_replies"]:
        for item in report["substantive_assistant_replies"]:
            lines.extend(
                [
                    f"- `{item['timestamp']}` {item['reply']}",
                ]
            )
    else:
        lines.append("- None retained.")

    lines.extend(["", "## Distilled Traits", ""])
    for trait in report["distilled_traits"]:
        lines.append(f"- {trait}")
    lines.append("")
    return "\n".join(lines)


def _write_artifacts(report: dict[str, Any], output_dir: Path) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "openclaw_conversation_seed.json"
    md_path = output_dir / "openclaw_conversation_seed.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=True))
    md_path.write_text(render_seed_markdown(report))
    return [str(json_path), str(md_path)]


def _write_memory(report: dict[str, Any], memory: Memory) -> None:
    owner_prompts = [item["prompt"] for item in report["owner_prompts"]]
    replies = [item["reply"] for item in report["substantive_assistant_replies"][:12]]
    memory.remember("openclaw_seed.persona_name", report["persona"]["persona_name"], category="openclaw_seed")
    memory.remember("openclaw_seed.persona_summary", report["persona"]["persona_summary"], category="openclaw_seed")
    memory.remember("openclaw_seed.owner_prompts", owner_prompts, category="openclaw_seed")
    memory.remember("openclaw_seed.substantive_replies", replies, category="openclaw_seed")
    memory.remember("openclaw_seed.distilled_traits", report["distilled_traits"], category="openclaw_seed")
    memory.log_event(
        "openclaw_absorb",
        {
            "owner_prompts": len(report["owner_prompts"]),
            "substantive_assistant_replies": report["counts"]["substantive_assistant_replies"],
            "source_state_dir": report["source_state_dir"],
        },
    )


def absorb_openclaw(
    state_dir: Path = DEFAULT_STATE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    memory: Memory | None = None,
    write_memory: bool = True,
) -> dict[str, Any]:
    report = build_seed_report(state_dir)
    artifacts = _write_artifacts(report, output_dir)
    if write_memory:
        _write_memory(report, memory or Memory())
    return {
        "ok": True,
        "counts": report["counts"],
        "artifacts": artifacts,
        "memory_written": write_memory,
    }
