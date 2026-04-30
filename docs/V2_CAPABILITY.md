# Friday v2.0 — Real Autonomy

**Released:** 2026-04-21
**Codename:** Real Autonomy
**Target operator:** Bhargav Vinnakota

---

## What changed from v1.0

v1.0 was a well-organized chatbot with cron-triggered goals. It could talk,
it could log, it could queue outreach drafts. But when you asked "what's
happening around the world?" it said *"Not my beat."* That's a refusal, not
a capability.

v2.0 replaces the refusal with a real pipeline.

| Area | v1.0 | v2.0 |
|---|---|---|
| World awareness | canned refusals | live web + news cascade |
| Research | LLM hallucination | queries → fetch → cite → synthesize |
| Long-running goals | tick-based cron | **Mission** orchestrator (plan-DAG, persisted) |
| Output verification | none | Critic agent (grounding / voice / safety) |
| Multi-source synthesis | string concat | Synthesizer agent (Friday-voice merge) |

---

## Architecture

```
 User query
     │
     ▼
 Orchestrator.respond()
     │
     ├── _is_world_query()?  ──► Researcher / world_pulse  ──► cited briefing
     ├── _match_tool()?       ──► tool (local truth)        ──► LLM synthesis
     └── else                  ──► engine.ask()              ──► conversational

 For multi-step goals:
     MissionRunner.run(mission)
         ├── Planner.run(goal, skills_catalog)       → step DAG
         ├── for step in dag (respecting depends_on):
         │     ├── researcher / critic / synthesizer (agent dispatch)
         │     ├── skills.invoke(skill, op, args)   (registry dispatch)
         │     └── ${step_N} template expansion
         ├── Critic.run(...) on risky outputs
         └── Synthesizer.run(all prior) → final report
```

---

## Real web reach

**`friday/actions/web.py`** — provider cascade:
1. **Brave Search API** (best agent grounding, $5/mo free tier)
2. **Tavily** ($30/mo, agent-optimized)
3. **Exa** (semantic embeddings)
4. **DuckDuckGo HTML** (keyless fallback)
5. **Wikipedia** (last resort)

All keys read from `~/.openclaw/.env`. 15-minute search cache.
`fetch_url(url)` pulls page text with HTML→text regex (no BeautifulSoup dep).

**`friday/actions/news.py`** — keyless aggregators:
- HackerNews Firebase + Algolia search
- Reddit public JSON (9 tracked subs: `artificial`, `Entrepreneur`, `LocalLLaMA`, etc.)
- RSS (9 feeds: TechCrunch, Verge, Anthropic, OpenAI, Bloomberg, Reuters, …)
- Google News RSS

`world_pulse()` → broad snapshot. `topic_pulse(topic)` → focused multi-source pull.

---

## Specialist agents

**`brain/agents/researcher.py`** — pipeline:
1. LLM generates 3-6 diverse search queries from topic
2. Parallel `multi_search()` + `topic_pulse()` — all results deduped
3. Top-N candidates ranked by topic-word overlap
4. Parallel `fetch_url()` for deeper context (ThreadPoolExecutor, 4 workers)
5. LLM synthesizes 4-section briefing with **[N] citations**

Depth modes: `quick` (3 queries / 5 sources) · `medium` (4/8) · `deep` (6/12).

**`brain/agents/planner.py`** — strict JSON output:
```json
{"goal": "...", "risk": "low|medium|high",
 "steps": [{"id": 1, "skill": "...", "operation": "...",
            "depends_on": [], "args": {...}, "expected_output": "..."}]}
```

Rules: minimize steps (3-8), front-load a `researcher` step if info gaps exist,
insert `critic` before risky actions, require `confirm` for high-risk, end
with `report`.

**`brain/agents/critic.py`** — 5-dimension check (grounding, specificity,
policy, voice, safety) → `{verdict: APPROVE|REVISE|REJECT, confidence, ...}`.

**`brain/agents/synthesizer.py`** — merges multi-source inputs into one
Friday-voice response. Preserves `[N]` citations if present. Scrubs filler.

---

## Mission orchestrator

**`brain/mission.py`** — persistent goal-pursuit, survives daemon restarts.

- `Mission` dataclass → `~/AI/friday/data/missions/{id}.json`
- `Step` status: `pending | running | done | failed | skipped`
- `MissionRunner.run(mission, on_step=callback)` — executes DAG sequentially,
  respecting `depends_on`. Template `${step_N}` expansion pipes prior outputs
  forward.
- `MissionRunner.spawn(mission)` — daemon thread version.
- Auto-summary: last step with `operation ∈ {report, final_report, summarize}`
  becomes `mission.final_report`; otherwise synthesizer auto-generates one.
- Thread-safe via `threading.RLock()`.

Dispatch inside `_execute_step`:
- `skill="researcher" | "critic" | "synthesizer"` → agent
- `skill="confirm" | "approval"` → mission marked **blocked**, awaits approval
- `skill="report" | "final_report"` → synthesizer over all prior step outputs
- anything else → `skills.invoke(skill, operation, **args)`

---

## Intelligence skill

**`skills/intelligence.py`** exposes 5 ops:
| op | purpose | latency |
|---|---|---|
| `world_pulse` | broad snapshot across HN/Reddit/RSS/Google News | ~5s |
| `topic_pulse` | multi-source pull on one topic | ~3s |
| `deep_research` | full Researcher pipeline with fetch + synth | ~25–45s |
| `scan_web` | raw Brave/Tavily/DDG search | ~2s |
| `quick_brief` | sub-20s headline-only synth | ~8s |

---

## Conversational routing

`brain/orchestrator.py::_is_world_query()` matches phrases like:
- "what's happening around the world"
- "latest on <X>"
- "news about <X>"
- "tell me about <X>"
- "research <X>" / "deep dive on <X>" / "brief me on <X>"
- "across the planet / globe"

Pure broad queries → `news.world_pulse()` + Friday-voice synth (~6–8 line brief).
Specific topic → `Researcher.run(topic, depth="quick"|"medium")`.
Falls back to normal LLM path on any error — never crashes the reply.

---

## Cost model

| Path | Engine | Approx cost |
|---|---|---|
| Greeting / conversational | Claude Sonnet (0.75 temp) | $0.003 per turn |
| Tool synthesis (has ground truth) | Ollama local | $0 |
| World-pulse briefing | Claude Sonnet | $0.005 per turn |
| Deep research (medium) | Claude + DDG free + HN/Reddit free | $0.02–0.05 per briefing |
| Deep research with Brave key | + $0 (free tier: 2000 queries/mo) | same |
| Mission (5–8 steps, mixed) | Planner + N agent calls | $0.05–0.30 |

Local-first routing means zero-cost for most interactions. Cloud model fires
only when (a) Claude API key present AND (b) conversational or heavy.

---

## Known gaps — roadmap to v3.0

**Not yet built:**
- [ ] `actions/youtube.py` + `actions/tts.py` + `actions/video.py`
  — needed for "automate a faceless YouTube channel end-to-end"
- [ ] `actions/builder.py` — codegen + test harness for "build me an app"
- [ ] `skills/mission_launch_channel.py` — the YouTube end-to-end mission spec
- [ ] `skills/mission_build_app.py` — idea → validation → build → test → deploy
- [ ] `skills/mission_revenue_scan.py` — arbitrage opportunity scanner
- [ ] Parallel step execution in MissionRunner (currently sequential)
- [ ] Mid-flight plan amendment (Planner re-invocation when a step surfaces
      information that invalidates downstream steps)
- [ ] Critic verdict → Reviser (auto-rewrite on REVISE verdict)
- [ ] Self-learning reflector — flag patterns across failed missions

**Approach for v3.0:**
Add action modules for each real-world surface (YouTube Studio API, gTTS/
ElevenLabs, ffmpeg pipeline, Cloud Run deploy, Stripe, Gmail SMTP). Wrap each
in a skill with explicit risk class. Mission specs then become pre-authored
DAGs that compose these skills — Planner can either instantiate a template
or decompose freeform.

**Constraint:** every new external surface gets `risk="medium"` minimum and
requires confirmation until the operator explicitly trusts it (per
`policies.yaml`). This is non-negotiable — arbitrage bots that "make money
on their own" go wrong fast without hard approval gates.

---

## How to invoke

```python
from friday.brain.engine import MultiEngine
from friday.brain.memory import Memory
from friday.brain.orchestrator import Orchestrator

orch = Orchestrator(MultiEngine(), Memory())

# Conversational → just works
orch.respond("hi")

# World query → routes to intelligence automatically
orch.respond("what's happening around the world?")
orch.respond("latest on Anthropic Claude")

# Explicit research
from friday.skills import get_registry
reg = get_registry()
reg.invoke("intelligence", "deep_research", topic="AI agent arbitrage", depth="medium")

# Missions
from friday.brain.mission import new_mission, MissionRunner
m = new_mission("Research AI agent arbitrage and draft 3 monetization angles")
runner = MissionRunner(MultiEngine(), Memory())
runner.run(m)
print(m.final_report)
```
