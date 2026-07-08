# AI Solution Architect

An AI-powered Solution Architect SaaS. Users describe a software idea in natural language
("Build a food delivery app for one million users") and the system analyzes requirements,
asks clarifying questions, designs the solution, generates architecture diagrams, recommends
technologies, estimates cloud costs, produces API specifications and database schemas, writes
documentation, and can optionally provision repositories or infrastructure through the
Model Context Protocol (MCP).

**Status:** Milestones **M0–M6 complete**. The full loop works end to end:
sign up → conversational requirements intake → multi-agent blueprint → downloadable export →
cost controls (metering, quotas, per-run token budget) → governed MCP provisioning →
observability (traces + metrics).

## What it does

| Stage | What happens |
|---|---|
| **Intake** | A Requirements Analyst agent interviews you (max 5 questions/round, 3 rounds) and produces a versioned, structured requirements document you confirm. |
| **Blueprint** | A LangGraph fan-out runs 8 agents in parallel — solution designer, tech stack, API, data model, diagram, cost, a design reviewer (with a repair loop), and a docs writer — producing 7 versioned artifacts with provenance. |
| **Export** | One click downloads a ZIP: design doc, requirements, architecture, a valid **OpenAPI 3.1** spec, runnable **PostgreSQL DDL**, a **Mermaid** diagram, tech stack, and costs. |
| **Cost control** | Per-workspace monthly run quotas and a hard **per-run token budget** enforced inside the orchestrator; a usage dashboard shows runs, tokens, and estimated cost. |
| **Provisioning** | The provisioner *proposes* a plan of MCP tool calls; nothing executes until a human approves it. Tools must be explicitly allowlisted. |

## Repository Layout

```
backend/   FastAPI + worker (one codebase, two processes)
           src/aisa/<module>/{domain,application,infrastructure,api}
           modules: shared, llm, identity, projects, orchestration, intake,
                    artifacts, blueprint, exports, metering, integrations, platform
web/       Next.js (App Router) + Tailwind + React Flow
docs/      Architecture & planning documents (see index below) + docs/adr/
.github/   CI (lint, strict type checks, architecture contracts, tests, migrations, compose smoke)
```

Module boundaries are enforced in CI by **import-linter** (7 contracts): feature modules stay
independent, domains are framework-free, and layering runs api → infrastructure → application → domain.

## Quick start

Prereqs: **Docker Desktop**, **Python 3.12+** with [uv](https://docs.astral.sh/uv/), **Node 22+**.

```bash
# 0. one-time install
cd backend && uv sync && cd ../web && npm install && cd ..

# 1. infrastructure
docker compose up -d postgres redis

# 2. database schema (idempotent)
cd backend && uv run alembic upgrade head

# 3. three long-running processes, one terminal each
cd backend && uv run uvicorn aisa.platform.app:app --reload --port 8000   # API
cd backend && uv run python -m aisa.platform.worker                        # worker (runs the agents)
cd web     && npm run dev                                                  # web → http://localhost:3000
```

Open **http://localhost:3000**, register, click **Resend / verify** on the yellow banner (dev has no
SMTP, so verification completes in-app), create a project, and describe an idea — or pick a
template brief.

Stop with `Ctrl+C` in each terminal, then `docker compose down`.

### Configuration

Copy `backend/.env.example` to `backend/.env` (git-ignored — **real secrets go only there**).

| Variable | Purpose |
|---|---|
| `AISA_LLM_PROVIDER` | `gemini` (needs a key) or `fake` — deterministic, no network, no quota |
| `AISA_GEMINI_API_KEY` | Google Gemini key; model is `gemini-3.1-flash-lite` |
| `AISA_MCP_CLIENT` | `fake` (default) or `http` — real MCP over streamable HTTP |
| `AISA_MCP_AUTH_TOKEN` | Bearer token for the MCP server (e.g. a GitHub PAT) |
| `AISA_OTEL_ENABLED` | `true` to emit traces + metrics (console in dev, OTLP with an endpoint) |

**Everything runs key-less.** With `AISA_LLM_PROVIDER=fake` the whole app works end to end with
schema-valid placeholder content — no API key, no network, no quota. That's what CI uses.

### Verifying

```bash
cd backend
uv run pytest                       # 120 tests (unit + component against real Postgres/Redis)
uv run ruff check . && uv run mypy && uv run lint-imports   # lint, strict types, architecture
uv run python scripts/smoke.py      # walking-skeleton smoke against a running api+worker
docker compose up --build           # the whole stack in containers
```

### Troubleshooting

- **No verification email.** Expected — SMTP is not wired. Click **Resend / verify** on the banner
  (dev returns the token and verifies in-app), or copy the `verify_path` printed in the API terminal.
- **`429 RESOURCE_EXHAUSTED` / blueprint run fails.** Your Gemini quota is exhausted. The app retries
  with backoff (honouring the API's `retryDelay`) and then fails the run cleanly. Wait for the quota
  window, or set `AISA_LLM_PROVIDER=fake` to keep working.
- **Postgres/Redis refused.** Start Docker Desktop, then `docker compose up -d postgres redis`.

See [ADR-002](docs/adr/ADR-002-llm-gemini-and-agent-layer.md) (Gemini behind an `LLMService` port;
no PydanticAI) and [ADR-003](docs/adr/ADR-003-defer-langgraph-to-m3.md) (LangGraph scoped to the
blueprint graph) for the key implementation decisions.

## Documentation Index

| # | Document | Contents |
|---|----------|----------|
| 01 | [Product Requirements Document](docs/01-prd.md) | Vision, personas, user journeys, feature requirements, success metrics, out of scope |
| 02 | [Functional Specification](docs/02-functional-spec.md) | Detailed behavior of every feature, state machines, artifact types |
| 03 | [Non-Functional Specification](docs/03-non-functional-spec.md) | Performance, scalability, availability, compliance targets |
| 04 | [System Architecture](docs/04-system-architecture.md) | Component architecture, modular monolith vs microservices decision (ADR-001), data flows |
| 05 | [Database Schema](docs/05-database-schema.md) | Full PostgreSQL schema with DDL, multi-tenancy strategy, pgvector RAG tables |
| 06 | [API Design](docs/06-api-design.md) | REST resource model, streaming design, versioning, error contract |
| 07 | [Agent Architecture](docs/07-agent-architecture.md) | LangGraph orchestration graph, specialist agents, PydanticAI typed contracts |
| 08 | [MCP Integration Architecture](docs/08-mcp-integration.md) | MCP host design, server registry, tool governance, credential handling |
| 09 | [Security Model](docs/09-security-model.md) | AuthN/AuthZ, tenant isolation, secrets, LLM-specific threats (prompt injection) |
| 10 | [Deployment Architecture](docs/10-deployment-architecture.md) | Docker, Kubernetes topology, environments, scaling policy |
| 11 | [Development Roadmap](docs/11-roadmap.md) | Milestones M0–M6 with exit criteria |
| 12 | [Testing Strategy](docs/12-testing-strategy.md) | Test pyramid, agent/LLM evaluation, contract tests |
| 13 | [CI/CD Strategy](docs/13-cicd-strategy.md) | GitHub Actions pipelines, quality gates, release process |
| 14 | [Observability Plan](docs/14-observability.md) | Logging, metrics, tracing, LLM-specific telemetry, cost tracking |
| 15 | [Risks & Mitigations](docs/15-risks.md) | Technical, product, and operational risk register |

## Tech Stack (agreed)

- **Backend:** FastAPI, PostgreSQL (+pgvector), Redis, SQLAlchemy 2.x, Alembic, LangGraph, PydanticAI
- **Frontend:** Next.js (App Router), TypeScript, Tailwind CSS, React Flow
- **Infrastructure:** Docker, Kubernetes-ready, GitHub Actions
- **AI:** Pluggable LLM providers, MCP-compliant tool execution, RAG

## Core Principles

Production-ready code only · Modular architecture · Domain-driven design · SOLID ·
Dependency injection · Type safety · Comprehensive testing · Extensible MCP integration ·
Multi-agent orchestration · Observability · Dockerized · CI/CD ready
