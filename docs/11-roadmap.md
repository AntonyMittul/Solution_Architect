# 11 — Development Roadmap

Milestones are scoped for a 1–3 engineer team. Each has **exit criteria** — a milestone is not
done until they pass. Durations are estimates, not commitments; sequence is the contract.

---

## M0 — Foundations (≈ 2–3 weeks)

Scaffolding the production skeleton *before* features — this is the milestone that makes
"production-grade" true later.

- Monorepo layout (`backend/`, `web/`, `infra/`, `docs/`); module skeletons per doc 04 §3
  with import-linter contracts enforced in CI.
- FastAPI app + DI container + config + problem+json error handling + health endpoints.
- Postgres + Alembic baseline migration (identity tables), Redis, job runner skeleton
  (enqueue/consume/retry/idempotency), outbox relay.
- Next.js app shell, generated API client pipeline, Tailwind design tokens.
- Docker Compose local stack + seed script; CI pipeline (lint, type-check, test, build, scan)
  green; staging environment deployed via Helm.
- Observability bootstrap: structured logging, OTel tracing wired end-to-end, error tracking.

**Exit:** new-engineer onboarding < 30 min (NFR-7); a walking-skeleton request flows
web → api → job → worker → event → SSE → web in staging with a trace covering all hops.

## M1 — Identity & Projects (≈ 2 weeks)

- Auth (email+password, GitHub OAuth), sessions, email verification.
- Workspaces, memberships, RBAC; RLS policies live; audit log started.
- Project CRUD + settings; frontend for auth/workspace/project flows.

**Exit:** RBAC matrix tests pass; RLS cross-tenant test suite passes (attempted cross-tenant
reads return zero rows); soft-delete/recovery works.

## M2 — Conversational Intake (≈ 3 weeks)

- Threads/messages; upload + ingestion pipeline (S3, chunking, embeddings, pgvector).
- LLMService port + Anthropic and OpenAI adapters, retries/failover, usage recording.
- Intake LangGraph graph with requirements_analyst agent (PydanticAI), human-in-the-loop
  interrupt, checkpointing.
- Structured requirements doc: versioning, edit UI, confirm flow.
- SSE streaming end-to-end with reconnect replay.

**Exit:** a user can go idea → clarifying Q&A → confirmed requirements in staging;
run resume after forced worker kill passes; token accounting matches provider invoices ±2%.

## M3 — Blueprint Generation (≈ 4–5 weeks) — the product core

- Full blueprint graph (doc 07): solution_designer, diagram_generator, tech_stack_recommender,
  cost_estimator, api_designer, data_modeler, design_reviewer, docs_writer.
- Artifact store: versions, provenance, dependency graph, staleness, diff, restore.
- React Flow canvas (view + edit), Mermaid/PNG/SVG export; artifact viewers (OpenAPI, DDL,
  markdown); regenerate flows.
- Eval harness v1 (golden briefs + deterministic validators) running nightly.

**Exit:** ≥ 90% of golden briefs produce a complete blueprint with all deterministic validators
passing; p95 full run < 10 min; artifact regeneration propagates staleness correctly.

## M4 — SaaS Hardening (≈ 3 weeks)

- Metering + plan quotas + enforcement; usage dashboard; billing integration (Stripe) with
  free/pro plans; run budget guards.
- Exports (ZIP/PDF/MD); notifications (in-app + email); 2FA.
- Load test to NFR-2 design point; security review of §1–§6 controls; rate limiting live.

**Exit:** NFR-1/2 targets met in staging load test; plan limits enforced end-to-end;
Stripe test-mode lifecycle (subscribe/upgrade/cancel/dunning) passes.

## M5 — MCP Provisioning (≈ 3 weeks)

- MCP registry, discovery, allowlists, governor, executor (streamable HTTP transport).
- Credential vault (envelope encryption).
- Provisioner agent + plan-preview/approval UI; GitHub launch integration (repo, scaffold
  push, issues, Actions enablement).
- Audit trail UI for tool invocations. stdio sandboxing if community servers make the cut,
  else deferred with the flag off.

**Exit:** blueprint → approved plan → real GitHub repo with scaffold + running CI, entirely
through MCP; injection test suite passes (malicious tool output cannot trigger unapproved
writes); external pen test scheduled.

## M6 — Beta → GA (≈ 4 weeks)

- Private beta (design partners), feedback loop, prompt/eval iteration.
- Pen test remediation; DR drill; on-call runbooks + game day; observability SLO dashboards.
- Polish: onboarding flow, template briefs, docs site, marketing site.

**Exit:** PRD §10 release criteria all green → **GA**.

## Post-GA Backlog (ordered)

Terraform/IaC provisioning · team review workflow · template library · public share links ·
public API + API keys · SSO/SAML · EU data residency · exposing our own MCP server.

## Sequencing Rationale

Intake (M2) before blueprint (M3) because requirements quality bounds artifact quality — it
also de-risks the whole LLM stack (providers, streaming, checkpointing) on the simplest graph.
MCP (M5) after hardening (M4) because provisioning touches user cloud/GitHub accounts — the
security substrate must exist first. Billing in M4, not later: pricing pressure-tests metering
design while the schema is still cheap to change.
