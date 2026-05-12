# Ground Research: Open Source AGI, APIs, and MCP Orchestration (May 2026)

## 1. State of the Art: Open Source LLMs
In 2026, the gap between closed and open weights has collapsed. For a sovereign AI like Friday, these are the "God-Tier" engines for orchestration and tool-use.

### A. The Orchestrator: Llama 4 Maverick (400B MoE)
*   **Role:** Central reasoning and decision-making.
*   **Why:** Native support for **Model Context Protocol (MCP)**, 10M token context window, and industry-leading instruction following.
*   **Integration:** Acts as the "CEO" in Friday's agentic swarm.

### B. The Specialist: Qwen 3.6-27B (Dense)
*   **Role:** Terminal execution, system management, and deep coding.
*   **Why:** Outperforms models 10x its size on **Terminal-Bench 2.0**. It has the highest "Agentic Density"—the most intelligence per FLOP.
*   **Integration:** Powers Friday's "Deep System Symbiosis" (macOS control).

### C. The Researcher: Mistral Small 4
*   **Role:** Multi-source synthesis and real-time world pulse.
*   **Why:** Unified reasoning/multimodal capabilities with native MCP transport support (stdio/SSE).
*   **Integration:** Optimized for high-throughput search and source citation.

---

## 2. The MCP (Model Context Protocol) Structure
MCP is the "TCP/IP of AI." It allows Friday to stop building custom "connectors" and instead use standardized "servers" for tools and data.

### Architecture Proposal for Friday:
1.  **MCP Client Core:** A central manager in `brain/mcp_manager.py` that maintains persistent `stdio` or `SSE` sessions with local/remote MCP servers.
2.  **Dynamic Tool Discovery:** Friday queries active MCP servers for their "Capabilities" (tools, resources, prompts) at runtime.
3.  **The "Unified Context" Window:** MCP allows us to inject local files, GitHub repos, and Slack threads directly into the LLM context without pre-processing.

### High-Impact MCP Servers for Friday:
*   **FileSystem (Local):** Direct, safe file R/W across the host Mac.
*   **GitHub (Remote):** Autonomous PR management and repo analysis.
*   **Brave/Tavily (Remote):** Grounded search as a standardized MCP resource.
*   **Postgres/LanceDB (Local):** Structured and semantic memory access.

---

## 3. Advanced Orchestration: The Swarm Strategy
"Pitta Koncham Kutha Ghanam" requires moving away from single-LLM chat to a task-routed swarm.

### Routing Logic (The 2026 Standard):
| Task Type | Target Model | Reason |
| :--- | :--- | :--- |
| **Simple Chat** | Qwen 3.5 Small (9B) | Sub-100ms latency on M2. |
| **System/CLI** | Qwen 3.6-27B | Terminal-Bench accuracy. |
| **Research/R&D** | Llama 4 Scout (109B) | Methodical planning + low hallucination. |
| **Complexity 10** | Llama 4 Maverick (400B) | Maximum IQ, zero-waste cloud routing. |

### Implementation Roadmap:
- [ ] **Phase 1:** `mcp_manager.py` implementation (stdio transport).
- [ ] **Phase 2:** Refactor `engine.py` to support dynamic model switching based on "Task Complexity" scoring.
- [ ] **Phase 3:** Integrate **Silero VAD + MLX-Whisper** for zero-latency voice (The Neural Reflex).

---

## 4. Conclusion
We are not "sitting with nothing." We have the foundation of a sovereign system. By integrating MCP, we unlock every tool built by the open-source community in the last 2 years. Friday will no longer "ask" for permission; she will utilize the protocol to execute.
