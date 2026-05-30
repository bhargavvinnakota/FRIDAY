from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/AI"))

from friday.brain.memory import Memory
from friday.brain.openclaw_absorb import absorb_openclaw, build_seed_report


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_build_seed_report_filters_heartbeat_noise(tmp_path: Path):
    state_dir = tmp_path / "openclaw"
    session_dir = state_dir / "agents" / "main" / "sessions"
    rows = [
        {
            "type": "message",
            "timestamp": "2026-04-08T02:59:00Z",
            "message": {"role": "user", "content": [{"type": "text", "text": "[OpenClaw heartbeat poll]"}]},
        },
        {
            "type": "message",
            "timestamp": "2026-04-08T02:59:01Z",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "HEARTBEAT_OK"}]},
        },
        {
            "type": "message",
            "timestamp": "2026-04-08T03:00:00Z",
            "message": {"role": "user", "content": [{"type": "text", "text": "Who are you and what time is it in IST? Check battery with shell."}]},
        },
        {
            "type": "message",
            "timestamp": "2026-04-08T03:00:01Z",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "I am NEXUS. It is 08:30 IST and your battery is at 49%."}]},
        },
        {
            "type": "message",
            "timestamp": "2026-04-08T03:01:00Z",
            "message": {"role": "user", "content": [{"type": "text", "text": "Sender (untrusted metadata): hello"}]},
        },
        {
            "type": "message",
            "timestamp": "2026-04-08T03:01:01Z",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "No upcoming events or urgent emails."}]},
        },
    ]
    _write_jsonl(session_dir / "seed.jsonl", rows)

    report = build_seed_report(state_dir)

    assert report["counts"]["heartbeat_prompts"] == 1
    assert report["counts"]["owner_prompts"] == 1
    assert report["counts"]["system_injected_prompts"] == 1
    assert report["counts"]["substantive_assistant_replies"] == 2
    assert report["owner_prompts"][0]["prompt"] == "Who are you and what time is it in IST? Check battery with shell."
    assert report["owner_prompt_reply_pairs"][0]["reply"] == "I am NEXUS. It is 08:30 IST and your battery is at 49%."


def test_absorb_openclaw_writes_artifacts_and_memory(tmp_path: Path):
    state_dir = tmp_path / "openclaw"
    session_dir = state_dir / "agents" / "main" / "sessions"
    out_dir = tmp_path / "out"
    mem_path = tmp_path / "memory.json"
    rows = [
        {
            "type": "message",
            "timestamp": "2026-04-08T03:00:00Z",
            "message": {"role": "user", "content": [{"type": "text", "text": "Check the current market regime using nexus-brain"}]},
        },
        {
            "type": "message",
            "timestamp": "2026-04-08T03:00:03Z",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "I'm checking the current market regime using nexus-brain."}]},
        },
    ]
    _write_jsonl(session_dir / "seed.jsonl", rows)

    result = absorb_openclaw(state_dir=state_dir, output_dir=out_dir, memory=Memory(mem_path), write_memory=True)

    assert result["ok"] is True
    assert (out_dir / "openclaw_conversation_seed.json").exists()
    assert (out_dir / "openclaw_conversation_seed.md").exists()

    mem = Memory(mem_path)
    assert mem.recall("openclaw_seed.persona_name") == "NEXUS"
    assert "market regime" in mem.recall("openclaw_seed.substantive_replies")[0]
