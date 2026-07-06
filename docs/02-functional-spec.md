# 02 — Functional Specification

Detailed behavior of the features summarized in the PRD. Each section defines inputs, behavior,
outputs, and edge cases. IDs (FS-x) map to PRD FR numbers.

---

## FS-1 Identity, Workspaces & Roles (FR-1)

- Signup via email+password and OAuth (GitHub, Google). Email verification required before
  project creation.
- Every user gets a **personal workspace**; users may create **team workspaces** (plan-gated).
- Roles per workspace: `owner`, `admin`, `member`, `viewer`.
  - `viewer`: read projects/artifacts, no runs, no exports on Free.
  - `member`: create/edit projects, trigger runs.
  - `admin`: member + manage members, MCP servers, LLM provider settings.
  - `owner`: admin + billing, workspace deletion (soft delete, 30-day recovery).
- All domain data is scoped to a workspace (tenant). No cross-workspace reads, ever.

## FS-2 Project Lifecycle (FR-2)

- A **project** = one software idea being architected. States: `active → archived → deleted(soft)`.
- Duplicate project copies requirements + latest artifact versions, not conversation history.
- Project settings: target cloud (AWS/GCP/Azure/agnostic), budget range, team size/skills,
  compliance flags (GDPR, HIPAA, PCI, none), scale expectation. These feed the agent context.

## FS-3 Conversational Intake & Clarification (FR-3, FR-4)

- Chat interface per project. User's first message is the idea description; file uploads
  (PDF, DOCX, MD, TXT ≤ 20 MB each) are ingested into the project's RAG corpus.
- The Requirements Analyst agent produces a **draft requirements document** and a list of
  **clarifying questions**, prioritized, max 5 per round, max 3 rounds by default (user can
  answer "use your best judgment" to skip; assumptions are then recorded explicitly).
- The requirements document is **structured** (goals, actors, functional requirements,
  non-functional requirements, constraints, assumptions, open questions), rendered as an
  editable form + markdown view. Every downstream artifact cites requirement IDs.
- Edge cases: contradictory answers → agent flags the contradiction and asks to resolve;
  non-software ideas → polite refusal with explanation; ideas requiring illegal/harmful
  systems → refusal per content policy.

## FS-4 Blueprint Generation (FR-5)

Triggered when the user clicks **"Generate blueprint"** (enabled once requirements reach state
`confirmed`). Runs the orchestration graph (doc 07). Artifacts produced:

| Artifact | Format(s) | Notes |
|---|---|---|
| System architecture doc | Markdown | Component responsibilities, data flows, key decisions with rationale |
| Architecture diagram | React Flow JSON (canonical) + Mermaid + PNG/SVG export | Layered: context, container, component views (C4-inspired) |
| Tech stack recommendation | Structured JSON + rendered table | Each choice: alternatives considered, trade-offs, fit to team skills |
| Cloud cost estimate | Structured JSON + rendered table | Line items per service, monthly range (low/expected/high), pricing-data version noted |
| API specification | OpenAPI 3.1 JSON/YAML | Validated with an OpenAPI linter before saving |
| Database schema | SQL DDL (PostgreSQL dialect default) + ERD (Mermaid) | Validated by parsing; must reference entities from requirements |
| Design document | Markdown | Executive summary stitching all artifacts, risks, roadmap suggestion |

Rules:
- Every artifact is **versioned** (FS-5) and records the requirements version + model + prompt
  version that produced it (provenance).
- Generation is **asynchronous**: the API returns a `run_id`; progress streams over SSE.
- Partial failure: if one agent fails after retries, the run completes with that artifact marked
  `failed`; the user can retry just that artifact.
- Cost estimates carry a visible disclaimer and the date of the pricing data.

## FS-5 Artifact Versioning & Regeneration (FR-7)

- Artifacts are immutable versions; edits create new versions. Manual user edits are flagged
  `edited_by_user` and are **never silently overwritten**.
- **Dependency graph:** requirements → (architecture ← diagram) → tech stack → costs;
  architecture → API spec → DB schema; all → design doc.
- When an upstream artifact changes, dependents are marked `stale` (visible badge). User chooses
  which to regenerate. Regeneration of a user-edited artifact requires explicit confirmation and
  produces a diff view (old vs new) before accepting.
- Version history UI: list, diff (text artifacts), restore.

## FS-6 Interactive Diagram (FR-6)

- React Flow canvas; nodes = components (typed: service, datastore, queue, external system,
  client), edges = interactions (labeled with protocol).
- User edits (move, rename, add, delete) create a new diagram version and mark dependents stale.
- Export: PNG, SVG, Mermaid text. Canonical storage format is our own JSON schema
  (`diagram.schema.json`), so we are not coupled to React Flow internals.

## FS-7 Runs & Streaming Progress (FR-8)

- A **run** is one orchestration execution. States:
  `queued → running → (completed | failed | cancelled | needs_input)`.
- `needs_input`: the graph paused for a human decision (clarifying question or MCP approval).
  Runs auto-expire from `needs_input` to `cancelled` after 7 days.
- SSE stream per run emits typed events: `run.status`, `agent.started`, `agent.token`,
  `agent.completed`, `artifact.created`, `approval.requested`, `run.completed`.
- Users can cancel a run; in-flight LLM calls are aborted; partial artifacts are kept as drafts.
- Concurrency: 1 active run per project; plan-based cap on concurrent runs per workspace.

## FS-8 Exports (FR-9)

- Bundle export: ZIP containing `README.md` (design doc), `requirements.md`, `architecture.md`,
  `diagram.svg` + `diagram.mmd`, `openapi.yaml`, `schema.sql`, `costs.md`, `stack.md`.
- Single-artifact exports in native formats. PDF rendering server-side (headless Chromium job).
- Free plan: watermarked PDF, no ZIP.

## FS-9 MCP Provisioning (FR-10, FR-14)

- Workspace admins register MCP servers (doc 08). Built-in first-party targets at launch:
  **GitHub** (create repo, push scaffold, create issues, enable Actions) via the GitHub MCP server.
- Provisioning flow: user selects action → system computes a **plan preview** (exact tool calls
  with arguments, e.g. "create private repo `food-delivery-api` under `AntonyMittul`") → user
  approves → tools execute → results (links, logs) attached to the project.
- **No MCP tool with side effects ever executes without an explicit, per-action user approval.**
  Read-only tools (search, fetch) may run without approval if the server is marked `trusted_read`.
- All tool calls and results are logged to the audit trail.

## FS-10 LLM Provider Management (FR-11)

- Platform default providers (our keys, metered). Workspace admins may **bring their own key**
  (BYOK) per provider; BYOK usage bypasses platform token metering but still enforces run caps.
- Model selection per workspace: `quality` (default), `fast`, or explicit model pin.
- Provider abstraction: all agents call a `LLMService` port; adding a provider = new adapter +
  config, zero agent changes.

## FS-11 RAG (FR-12)

- Two corpora: (a) per-project user uploads; (b) platform-curated architecture knowledge base
  (reference architectures, pricing guides, pattern catalog) maintained by us.
- Ingestion: extract text → chunk (semantic, ~512 tokens, overlap 64) → embed → store in pgvector.
- Retrieval: hybrid (vector + keyword), top-k with score threshold; retrieved chunks are cited in
  artifacts ("informed by: uploaded-brief.pdf §3").
- Tenant isolation: project corpus queries are always filtered by `workspace_id` + `project_id`
  at the SQL layer (not just in application code).

## FS-12 Metering & Plan Enforcement (FR-13)

- Metered: agent runs, LLM tokens (in/out per provider/model), storage bytes, MCP tool calls.
- Enforcement points: run creation (quota check), token budget guard inside orchestration
  (a run that exceeds its per-run token budget is stopped gracefully and marked `failed:budget`).
- Usage dashboard per workspace; admin alerts at 80%/100% of plan.

## FS-13 Notifications

- In-app + email: run completed/failed, approval requested, member invited, plan limits.
- Email is best-effort async (queued job); in-app is source of truth.
