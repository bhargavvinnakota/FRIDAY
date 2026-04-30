"""
F.R.I.D.A.Y — Bhargav's Sovereign AI
Version 2.0.0 :: Real Autonomy

v2.0 replaces the chatbot illusion with a real operator:

  REAL WORLD REACH
    actions/web.py      — Brave → Tavily → Exa → DDG → Wikipedia search cascade
    actions/news.py     — HackerNews + Reddit + RSS + Google News aggregation

  SPECIALIST AGENTS (brain/agents/)
    Researcher   — turns a topic into a cited briefing (queries→fetch→synth)
    Planner      — decomposes a goal into a DAG of executable steps
    Critic       — verifies output grounding / voice / safety before release
    Synthesizer  — merges multi-source inputs into one Friday-voice response

  MISSION ORCHESTRATOR (brain/mission.py)
    Mission      — persistent goal-pursuit with steps, status, artifacts
    MissionRunner— plan → execute (DAG) → verify → report, survives restarts
    ${step_N}    — template expansion pipes prior outputs into later steps

  INTELLIGENCE SKILL (skills/intelligence.py)
    world_pulse / topic_pulse / deep_research / quick_brief / scan_web

  ROUTING
    Orchestrator intercepts world/research queries and dispatches to
    Researcher (deep) or news.world_pulse (broad). No more "not my beat".

v1.0 capabilities retained:
  - goals.yaml + policies.yaml + autonomy loop + 7 skills
  - reflector + nightly journal + supervised/trusted/full autonomy gates
"""
__version__ = "2.0.0"
__codename__ = "Real Autonomy"
