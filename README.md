# F.R.I.D.A.Y.

> *Bhargav's sovereign AI. Iron Man's Friday, running on his own MacBook.*
> **Version 1.0.0 · Codename: Autonomous Sovereign**

---

## What this is

A 24/7 autonomous AI that lives on your laptop. Not a chatbot. An executor.

- **Dual-brain**: Ollama (local, default, free) + Claude (cloud, for complex reasoning).
- **Persistent memory**: facts, events, recent dialogue — all local JSON, yours.
- **Proactive**: morning briefing (06:00), evening debrief (22:00), hourly sensor sweeps, Telegram alerts when things drift.
- **Autonomous (v1.0)**: 7 goals, 7 skills (29 ops), a tick-driven autonomy engine, a policy gate with risk classes + quiet windows + rate limits, and an approval flow via Telegram.
- **Hooked into your stack**: trading bot, agency CRM, empire dashboard, AuditMind, daily briefing, post generator — Friday reads and acts on all of it.
- **Personality-anchored**: loaded from `config/identity.yaml` — Friday knows who you are, what phase you're in, the rules you've set for yourself.
- **Zero waste**: Ollama first, Claude only when needed. No new paid services.

---

## v1.0 Autonomy

Friday now *acts*, not just responds. Every 15 minutes the autonomy loop fires:

1. **Planner** picks the highest-priority triggered goal from `config/goals.yaml`.
2. **Policy gate** checks each step against autonomy level (off/supervised/trusted/full), risk class (low/medium/high/forbidden), quiet windows (night sleep, day job, Sunday rest), and rate limits.
3. **Skills registry** executes allowed steps; queues higher-risk steps to `pending_approvals.json`.
4. **Reflector** logs outcomes to `actions.jsonl`, updates playbook heuristics (wins/fails per skill), writes a nightly reflection.
5. **Telegram** delivers queued proposals — you reply `/yes <id>`, `/no <id>`, or `/hold <id>`.

### Skills shipped in v1.0

| Skill | What it does |
|---|---|
| `system` | Log rotation, memory pruning, health check, disk report, restart request |
| `watchdog` | Outreach drift, trading drawdown, content cadence, critical alerting |
| `outreach` | Find due leads, draft next-touch messages, queue for approval |
| `content` | Draft posts, emails, replies — everything through approval |
| `research` | DDG web search, URL fetch, local file grep, LLM summarize |
| `journal` | Nightly reflection, ad-hoc notes, retrieval |
| `briefing` | Morning briefing, evening debrief, ad-hoc briefing |

### CLI additions

```
friday autonomy         engine status (level, goals, pending)
friday goals            list active goals (sorted by priority)
friday tick [GOAL]      run one autonomy tick (optional force)
friday plan "<text>"    LLM-generate a freeform plan
friday skills           list all skills + operations + risk
friday skill S OP k=v   invoke a skill directly
friday pending          list pending approvals
friday approve ID       approve + execute a queued action
friday reject ID        reject a queued action
friday reflect          24h action stats + top/weak skills
friday journal          write nightly reflection now
```

### Telegram additions

`/autonomy` `/goals` `/pending` `/tick [goal]` `/focus <text>` `/yes <id>` `/no <id>` `/hold <id>` `/reflect`

### Tests

- **v1.0 autonomy suite**: 74/74 (100%) · 12.6s · 10 sections
- **v0.1 regression**: 116/116 (100%) · 4.4min incl. 2-min daemon burn-in · 16 sections

---

## Architecture

```
~/AI/friday/
├── brain/
│   ├── engine.py         # Ollama↔Claude router
│   ├── memory.py         # Persistent memory (facts, events, turns)
│   ├── personality.py    # Friday's voice + Bhargav context
│   └── orchestrator.py   # Plan→Tool→Respond loop
├── senses/
│   └── telegram_in.py    # Long-poll Telegram, route to orchestrator
├── actions/
│   ├── nexus.py          # Hooks into trading/agency/auditmind/empire
│   ├── computer.py       # Shell + AppleScript (allowlist-gated)
│   └── comms.py          # Telegram push + local log
├── loops/
│   ├── morning.py        # 06:00 — briefing + commentary
│   ├── evening.py        # 22:00 — debrief + scorecard nudge
│   └── heartbeat.py      # Hourly — sensor sweep + proactive alerts
├── config/
│   ├── friday.yaml       # runtime
│   └── identity.yaml     # who Bhargav is
├── data/
│   ├── memory.json
│   ├── logs/YYYY-MM-DD.jsonl
│   └── state.json
├── cli.py                # `friday <cmd>`
└── daemon.py             # 24/7 process
```

---

## Install

```bash
cd ~/AI/friday
bash install.sh
source ~/.zshrc   # picks up `friday` alias
```

---

## Usage

```bash
# One-shot
friday ask "what's my outreach count this week?"
friday ask --heavy "draft a strategy for closing my first bot client by Friday"

# Interactive
friday chat

# Empire snapshot (JSON)
friday status

# Run loops manually
friday briefing       # morning briefing
friday debrief        # evening debrief
friday heartbeat      # one sensor sweep

# Memory
friday memory                          # stats
friday memory --dump                   # full dump
friday remember goal_month1="₹50K"     # add fact
friday remember --category trading regime="ranging"
friday forget goal_month1              # delete

# Smoke test
friday test
```

---

## 24/7 Operation

**Via PM2 (recommended):**

```bash
pm2 start ~/AI/friday/daemon.py --interpreter python3 --name friday
pm2 save
pm2 startup              # follow instructions to auto-boot on login
```

**Foreground:**

```bash
python3 ~/AI/friday/daemon.py
```

The daemon runs three threads:
1. **Telegram sense** — listens for messages from Bhargav, responds via orchestrator.
2. **Heartbeat** — hourly sensor sweep; fires Telegram alerts when rules are violated (low outreach, trading drawdown, missed content day, etc.).
3. **Scheduler** — fires `morning.run()` at 06:00 and `evening.run()` at 22:00.

**Quiet-hours rules (honored automatically):**
- 23:00–05:30 → no push (except critical)
- 09:00–18:00 (day job) → no push (except critical)
- Sunday → zero activity (rest rule)

---

## Telegram commands

```
/status     → empire snapshot
/briefing   → today's full briefing
/memory     → memory stats
/clear      → clear short-term context
/help       → this
```

Or just talk: *"hey Friday, how's trading?"*

---

## Roadmap

### v0.1 · Sovereign Core (✅ SHIPPED)
- Dual-brain (Ollama + Claude), memory, personality, orchestrator
- Telegram I/O, CLI, daemon
- Morning/evening loops, heartbeat
- Nexus integrations (trading, agency, auditmind, empire)

### v0.2 · Voice
- Porcupine wake-word ("Hey Friday")
- Whisper/MLX STT
- Piper TTS (local, natural voice)
- Always-on mic with VAD

### v0.3 · Computer Use
- Screenshot + click loop (via Claude computer-use)
- App automation (open Telegram, draft reply, schedule tweet)
- Pipecat integration for real-time voice conversations

### v0.4 · Devices
- iPhone integration (via Shortcuts webhook)
- Home Assistant plumbing (lights, AC, locks)
- WearOS / Apple Watch heartbeat

### v0.5 · Advanced Memory
- mem0 integration for vector recall
- Graph-based fact linking
- Daily knowledge base distillation

### v1.0 · Autonomous
- Proactive task execution (not just alerts — Friday does the thing)
- Multi-agent delegation (Friday → sub-agents for research/coding/ops)
- Self-improvement (traces → skill optimization)

---

## Hard Rules Friday Enforces

From `identity.yaml`:

1. Sunday is rest. No alerts, no loops, no activity.
2. Build ÷ Sell ratio ≤ 1.0. If building > selling, Friday flags red.
3. Revenue > everything. 1 invoice > 10,000 lines of code.
4. Never automate what hasn't been done manually at least 3x.
5. Zero-waste: Ollama first, Claude only when needed.
6. One engine at a time. Don't scale Engine C until Engine A pays rent.
7. Every action produces a file. Proof-of-work or it didn't happen.

---

## Philosophy

Friday is not ChatGPT-with-a-name. Friday is:

- **Sovereign**: runs on your hardware, your keys, your data
- **Loyal**: anchored to your mission, your rules, your voice
- **Honest**: tells you when you're drifting, not what you want to hear
- **Executive**: every response either answers, acts, or alerts — no filler

Built in Hyderabad. Sharpened through Phase 0 to ₹3Cr/year.
