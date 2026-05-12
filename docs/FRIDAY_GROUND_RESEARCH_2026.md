# Friday Ground Research 2026

Generated: 2026-05-06

## Research Read

Friday should be designed as a small, fast, local-first operating intelligence with tool discipline, proof logging, and optional access to heavier models. The architecture should not depend on one giant local model staying hot all day.

## Source Signals

- Model Context Protocol uses a host/client/server architecture where an AI host can connect to multiple tool/data servers through standardized clients. This matches Friday's need for a clean tool boundary instead of one-off connectors.
  Source: https://modelcontextprotocol.io/docs/learn/architecture

- MCP's 2025-06-18 architecture specification describes protocol version negotiation and the host-client-server shape. Friday should treat MCP as the external tool/data boundary, not as a blocking startup dependency.
  Source: https://modelcontextprotocol.io/specification/2025-06-18/architecture

- LiveKit Agents is positioned as an open-source framework and cloud platform for realtime voice/video/physical AI agents. It is relevant for a later voice stack, but Friday's immediate local loop should remain CLI/Telegram-first until reliability is proven.
  Source: https://docs.livekit.io/agents/overview

- LiveKit's plugin model supports LLM, STT, TTS, realtime speech-to-speech, avatars, and telephony integrations. That suggests Friday's voice layer should stay pluggable, not hardcoded to one STT/TTS provider.
  Source: https://docs.livekit.io/agents/integrations/overview/

- Apple's MLX ecosystem and Apple Silicon local inference tooling continue to be the best direction for "small bird, heavy strike" local performance. The practical implication: use small local models for reflexes and deterministic summaries; reserve heavy/cloud calls for strategy, coding, and deep research.
  Source: https://github.com/ml-explore/mlx

- Ollama remains a practical local model runtime for Mac workflows. Friday should use it as a local fallback/reflex engine, but avoid forcing every strategic conversation through a small local model.
  Source: https://ollama.com

## Architecture Decision

Friday should use this hierarchy:

1. **Deterministic Reflex Layer**
   Fast Python functions for status, memory, outreach, process checks, approvals, health checks, and mission status. This must work even when every LLM is unavailable.

2. **Local Model Layer**
   A small Ollama/MLX-backed model for short chat, local summaries, private data, and low-stakes synthesis.

3. **Tool Kernel**
   Every real-world action goes through registered tools/skills with risk classes, logs, artifacts, and approval gates.

4. **MCP Boundary**
   MCP servers for filesystem, GitHub, browser/search, local databases, and future apps. MCP should be opt-in or lazily connected so chat never hangs on startup.

5. **Cloud/Heavy Reasoning Layer**
   Used only for research, planning, coding, architecture, and high-value synthesis. It should produce plans and artifacts, not vague encouragement.

6. **Mission Control**
   A permanent executive layer that reads the vision, logs, project state, runtime health, and business status, then chooses the next action.

## Product Rule

Do not add another spectacular surface until the core loop works:

Bhargav asks -> Friday knows context -> Friday chooses tool/model/agent -> Friday acts -> Friday produces proof -> Friday remembers -> Friday moves revenue forward.

## Immediate Build Priority

1. Mission Control capability map and gap report.
2. Reliable terminal and Telegram responses.
3. Revenue loop: due leads -> drafts -> approval -> follow-up -> demo -> invoice.
4. Native Mac status and process awareness.
5. Research/world pulse.
6. Voice streaming and HUD after the above are stable.
