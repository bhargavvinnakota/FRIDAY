# FRIDAY Automation Operating Model

## Mission

Build FRIDAY as Bhargav's sovereign operator: a local-first agentic OS that senses the world, manages revenue systems, runs business operations, and expands its reach without leaking data, permissions, or control.

The system must behave like a disciplined operating company, not a clever chatbot.

## Design Principle

Do not wait for enterprise furniture.

Many connectors and SaaS workflows assume a work email, a team workspace, or a legal entity. That should not block FRIDAY. For a solo founder, the right move is:

1. Use solo-friendly connectors now.
2. Replace premature enterprise tools with internal FRIDAY services and lightweight substitutes.
3. Add enterprise connectors later when the business actually has the surface area to justify them.

## Recommended Connector Stack

### Phase Now

- Gmail
- Google Calendar
- Google Drive
- GitHub
- Notion
- Netlify or Vercel
- Supabase or Neon
- Computer Use
- Razorpay or Cashfree
- Password manager

Optional if access is available:

- Stripe for international expansion

This is enough to run founder operations, revenue workflows, product deployment, lightweight CRM, content production, and approval-based execution.

### Phase Next

- Vantage
- Canva
- Hugging Face
- YouTube and AdSense
- Cloudflare
- Account Aggregator sandbox
- Lemon Squeezy or Gumroad for digital-product fallback

This phase deepens cost visibility, content leverage, model experimentation, infrastructure control, and financial awareness.

### Phase Later

- Slack
- Linear or Jira
- HubSpot or Salesforce
- LinkedIn automation surfaces
- Broker read-only APIs

These are useful, but they are not required to make FRIDAY operational for a solo founder. Several also tend to assume workspace or organization context.

## India Reality

Stripe is not a reliable day-one assumption for an India-based solo operator. Stripe's own support documentation says new Stripe accounts in India are invite-only, with support focused on a select set of businesses. FRIDAY should therefore treat Stripe as optional for later international expansion, not as a primary blocker.

For the money stack, the default priority should be:

1. Razorpay or Cashfree
2. Account Aggregator sandbox when onboarding is practical
3. Stripe only if invited

## Solo-Founder Substitutions

When a connector asks for a work email or workspace we do not have, FRIDAY should substitute instead of stalling:

- Slack -> Telegram + Gmail + Notion
- Linear/Jira -> Notion database + GitHub issues
- HubSpot/Salesforce -> Notion CRM + Gmail + Calendar
- SharePoint/Confluence -> Google Drive + Notion

The point is operational throughput, not brand-name stack completeness.

## Operating Hierarchy

### Control Plane

- `Orchestrator`: decomposes objectives, routes to specialist agents, merges outputs.
- `Policy Engine`: classifies every action by risk and decides allow, queue, or deny.
- `Audit Agent`: writes proofs, hashes artifacts, detects leakage and anomalies.
- `Monitor Agent`: watches connector health, queue age, costs, failures, and duplicate actions.

### Execution Plane

- `ExecutiveAssistantAgent`: inbox, calendar, docs, reminders, daily plans.
- `FinanceAgent`: revenue, subscriptions, payouts visibility, opportunity ranking.
- `GrowthAgent`: outreach, content, distribution, lead capture, experiment design.
- `OpsAgent`: deploys, databases, infra, incident response, staging and rollback.
- `ResearchAgent`: world awareness, competition, market signals, model/tool scouting.
- `CreatorAgent`: decks, content assets, creative packaging.

### Memory Plane

- Structured memory: facts, customers, experiments, approvals, incidents, financial events.
- Unstructured memory: notes, docs, transcripts, research.
- Retrieval boundary: agents only read the slices they need.

## Approval Hierarchy

### Tier 0

Read-only sensing, indexing, summarization, anomaly detection.

Auto-allow.

### Tier 1

Draft creation with no external side effect.

Auto-allow.

### Tier 2

Internal reversible writes: local state, scratch docs, dev branches, staging configs.

Auto-allow if reversible and logged.

### Tier 3

External reversible writes: calendar holds, CRM notes, staging deploys, draft emails.

Require Bhargav approval.

### Tier 4

External irreversible or public actions: sending emails, publishing content, production deploys, customer-visible mutations, subscription changes.

Require Bhargav approval with explicit preview and confirmation.

### Tier 5

Forbidden autonomous actions: live money movement, live trading, raw secrets handling, legal commitments, medical actions.

Never autonomous.

## Guardrails

- Every action must carry a `trace_id`.
- Every external action must have an `idempotency key`.
- Every connector should use least-privilege scopes.
- No plaintext secrets in repo, chat logs, or artifacts.
- No production deploy without preview artifact and rollback path.
- No outbound message without target binding, preview, and audit record.
- No financial connector action without explicit risk classification.
- No browser-driven credential flows should be stored or replayed by FRIDAY.

## Auditing

Each action record should include:

- actor
- goal
- connector
- operation
- risk tier
- policy decision
- approval id
- artifact paths
- verification result
- timestamp

Weekly review should include:

- broken connectors
- new scopes granted
- failed automations
- duplicate sends or retries
- unexplained cloud spend
- approval queue backlog

## Monitoring

FRIDAY should continuously monitor:

- connector health
- missing webhook events
- approval queue age
- deploy failures
- outreach response rate
- revenue pipeline movement
- cost anomalies
- incident counts

## Enterprise Reality

FRIDAY can already act as architect plus operator across the stack, but full autonomy depends less on model intelligence than on connector discipline and control design.

The groundbreaking version is not the one with the most connectors.

It is the one where:

- every permission is intentional
- every automation is observable
- every risky action is previewed
- every failure is auditable
- every subsystem can be paused without collapsing the whole machine

That is how FRIDAY becomes financially useful instead of theatrically powerful.
