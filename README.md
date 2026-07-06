# AI Solution Architect

An AI-powered Solution Architect SaaS. Users describe a software idea in natural language
("Build a food delivery app for one million users") and the system analyzes requirements,
asks clarifying questions, designs the solution, generates architecture diagrams, recommends
technologies, estimates cloud costs, produces API specifications and database schemas, writes
documentation, and can optionally provision repositories or infrastructure through the
Model Context Protocol (MCP).

**Status:** Building — roadmap milestone **M0 (Foundations)**. The walking skeleton is live:
a request flows web → api → job queue → worker → event log → SSE → web, end to end.

## Repository Layout

```
backend/   FastAPI + worker (one codebase, two processes) — src/aisa/<module>/{domain,application,infrastructure,api}
web/       Next.js (App Router) + Tailwind
docs/      Architecture & planning documents (see index below)
.github/   CI (lint, strict type checks, architecture contracts, tests, migrations, compose smoke)
```

## Local Development

Prereqs: Docker, Python 3.12+ with [uv](https://docs.astral.sh/uv/), Node 22+.

```bash
docker compose up -d postgres redis          # infrastructure
cd backend && uv sync && uv run alembic upgrade head
uv run uvicorn aisa.platform.app:app --reload --port 8000   # terminal 1: api
uv run python -m aisa.platform.worker                        # terminal 2: worker
cd ../web && npm install && npm run dev                      # terminal 3: web -> http://localhost:3000
```

**LLM (Gemini):** the requirements-intake agent uses Google Gemini
(`gemini-3.1-flash-lite`). Set `AISA_GEMINI_API_KEY` in `backend/.env` to use it, or run with
`AISA_LLM_PROVIDER=fake` for a deterministic, key-less stub (also what CI uses). See
[ADR-002](docs/adr/ADR-002-llm-gemini-and-agent-layer.md) and
[ADR-003](docs/adr/ADR-003-defer-langgraph-to-m3.md) for the provider and orchestration decisions.

Quality gates (same as CI): `cd backend && uv run ruff check . && uv run mypy && uv run lint-imports && uv run pytest`
End-to-end smoke test: `cd backend && uv run python scripts/smoke.py`
Full stack in containers: `docker compose up --build`

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
