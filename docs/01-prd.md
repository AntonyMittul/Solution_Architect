# 01 — Product Requirements Document (PRD)

**Product:** AI Solution Architect
**Version:** 1.0 (planning baseline)
**Owner:** Antony Mittul
**Status:** Approved for architecture phase

---

## 1. Vision

Every software project begins with the same expensive, error-prone phase: turning a vague idea
into a concrete, buildable plan. Founders skip it, juniors can't do it, and seniors spend weeks
on it. AI Solution Architect compresses that phase from weeks to hours by pairing users with a
team of specialized AI agents that interview them, design the system, and produce the complete
engineering blueprint — requirements, architecture, diagrams, tech stack, cost estimates, API
specs, database schemas, and documentation — with the option to bootstrap real repositories and
infrastructure via MCP.

**One-liner:** "Describe your product; receive an engineering blueprint you can build from."

## 2. Target Users & Personas

| Persona | Description | Primary need |
|---|---|---|
| **Founder Fiona** | Non-technical/semi-technical founder validating an idea | A credible technical plan and cost estimate to share with investors and contractors |
| **Dev Dan** | Solo developer / freelancer starting client projects | Fast, defensible architecture decisions and bootstrapped repos so he can start coding day one |
| **Architect Aisha** | Senior engineer / consultant at an agency | A force multiplier: draft designs she can review, correct, and export as client deliverables |
| **Team Lead Tom** | Engineering lead at a startup | Standardized design docs across the team, versioned and reviewable |

Primary launch persona: **Dev Dan** (highest willingness to pay relative to acquisition cost,
tolerates rough edges, validates artifact quality quickly).

## 3. Problem Statements

1. Translating requirements into architecture requires scarce senior expertise.
2. Design artifacts (diagrams, specs, schemas) drift apart because they are authored separately.
3. Cloud cost implications of design decisions are discovered too late.
4. The gap between "design approved" and "repo scaffolded, CI running" wastes days.

## 4. Product Goals & Success Metrics

| Goal | Metric | Target (12 months post-GA) |
|---|---|---|
| Users complete a full design | Idea → complete blueprint conversion rate | ≥ 40% of started projects |
| Artifacts are trusted | User-rated artifact quality (1–5) | ≥ 4.0 average |
| Time-to-value | Median time from signup to first exported blueprint | ≤ 60 minutes |
| Retention | 3-month logo retention (paid) | ≥ 70% |
| MCP adoption | Projects using ≥1 provisioning action | ≥ 25% |
| Unit economics | LLM cost per completed blueprint | ≤ 15% of blueprint revenue |

## 5. Core User Journey

1. **Describe** — User creates a project and describes the idea in free text (optionally uploads
   existing docs for RAG context).
2. **Clarify** — The Requirements Analyst agent asks targeted clarifying questions (scale, budget,
   team skills, compliance, timeline). User answers in a chat interface; answers become structured
   requirements the user can review and edit.
3. **Design** — The orchestrator runs specialist agents to produce the blueprint: system
   architecture, diagrams (interactive React Flow + exportable Mermaid/PNG), technology
   recommendations with trade-off rationale, cloud cost estimate, OpenAPI specification,
   database schema (DDL + ERD), and a written design document.
4. **Iterate** — User comments on or edits any artifact; the system regenerates dependent
   artifacts consistently (e.g., schema change updates the API spec and cost estimate) with
   full version history.
5. **Deliver** — User exports the blueprint (Markdown/PDF/ZIP, OpenAPI JSON, SQL) and/or triggers
   MCP provisioning actions: create GitHub repo with scaffold and CI, generate IaC (Terraform),
   open tracked issues from the roadmap. Every provisioning action requires explicit user approval.

## 6. Functional Requirements (summary — detail in Functional Spec)

**Must have (MVP / GA):**
- FR-1 Account & workspace management (orgs, members, roles)
- FR-2 Project lifecycle (create, archive, duplicate)
- FR-3 Conversational requirements intake with clarifying questions
- FR-4 Structured, editable requirements document
- FR-5 Multi-agent blueprint generation (architecture, diagram, tech stack, costs, API spec, DB schema, design doc)
- FR-6 Interactive architecture diagram (React Flow) with export
- FR-7 Artifact versioning and regeneration with dependency propagation
- FR-8 Streaming progress UI (agent activity visible in real time)
- FR-9 Export bundle (Markdown, PDF, OpenAPI JSON, SQL DDL, ZIP)
- FR-10 MCP server registry per workspace; GitHub repo provisioning with human approval
- FR-11 Pluggable LLM providers (Anthropic, OpenAI, others) configurable per workspace
- FR-12 RAG over user-uploaded documents and a curated architecture knowledge base
- FR-13 Usage metering (tokens, runs) and plan limits

**Should have (post-GA):**
- FR-14 Terraform/IaC generation and cloud provisioning via MCP
- FR-15 Team review workflow (comments, approvals) on artifacts
- FR-16 Template library (SaaS starter, mobile backend, data platform, etc.)
- FR-17 Public share links for blueprints

**Won't have (v1):**
- Full application code generation (we generate scaffolds, not features)
- Real-time multiplayer editing
- On-prem deployment (architecture must not preclude it)

## 7. Pricing Model (informs metering requirements)

- **Free:** 1 project, capped agent runs, no MCP provisioning, watermark on exports.
- **Pro (per seat):** unlimited projects, fair-use agent runs, MCP provisioning, all exports.
- **Team:** Pro + shared workspaces, review workflow, priority queue, SSO (later).

Implication: usage metering, plan enforcement, and per-tenant LLM budget caps are **core domain
requirements**, not afterthoughts.

## 8. Competitive Landscape (positioning)

General chatbots (ChatGPT/Claude apps) can discuss architecture but produce unstructured,
non-versioned, non-consistent output with no provisioning. Diagramming tools (Eraser, Lucid AI)
generate diagrams but not the full consistent blueprint. IDE agents (Copilot Workspace, Devin)
start from code, not from product discovery. Our moat: **consistency across artifacts**
(one requirements model drives all outputs), **iteration with dependency propagation**, and
**MCP-based delivery into real infrastructure**.

## 9. Assumptions & Constraints

- Users accept AI-generated designs as drafts requiring human review; the UI must reinforce this.
- LLM API costs and latency remain the dominant variable cost; the design must meter and cap them.
- MCP is the strategic integration layer; all external tool execution goes through it (no bespoke
  one-off integrations).
- Initial team size is small (1–3 engineers) — this constrains the architecture decision (see ADR-001).

## 10. Release Criteria (GA)

- All Must-have FRs implemented and covered by the testing strategy (doc 12).
- NFR targets in doc 03 met in staging load tests.
- Security model (doc 09) implemented; external penetration test passed.
- Observability plan (doc 14) live: on-call can diagnose a failed agent run in < 10 minutes.
- Billing and plan enforcement functional.
