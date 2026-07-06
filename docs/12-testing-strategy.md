# 12 — Testing Strategy

Principle: **deterministic tests for deterministic code; evals for model behavior; never mix
the two.** LLM calls are behind the `LLMService` port, so 95% of the codebase tests without
any model.

## 1. Test Pyramid

| Layer | Scope | Tooling | Runs |
|---|---|---|---|
| Unit | domain + application logic, pure; ports mocked/faked | pytest, hypothesis (property tests for budget math, staleness graph, version logic) | every push, < 2 min |
| Component | one module incl. its infrastructure against real Postgres/Redis | pytest + testcontainers | every push, < 8 min |
| API/contract | HTTP layer: schemas, authz matrix, problem+json, pagination, idempotency | pytest + httpx against the app; schemathesis fuzzing from OpenAPI | every push |
| Integration | cross-module flows: run lifecycle, checkpoint resume, SSE replay, outbox delivery | docker-compose stack; LLM via recorded cassettes | every push, < 15 min |
| E2E | golden-path user journeys in a browser | Playwright vs staging (recorded LLM mode) | merge to main + nightly |
| Load | NFR-1/NFR-2 targets | k6 vs staging | weekly + pre-release |
| Security | RLS cross-tenant suite, authz matrix, dependency/image scans, injection suite | pytest + CI scanners | every push / nightly |

## 2. What Gets Special Attention

- **Tenant isolation:** a dedicated suite creates two workspaces and attempts every read/write
  cross-tenant, both through the API (expect 403/404) and through raw SQL with RLS role
  (expect zero rows). This suite is a merge blocker forever.
- **Run resilience:** kill the worker mid-run at every graph node (parameterized) → assert
  resume completes with no duplicate artifacts/events (idempotency proof).
- **SSE:** reconnect with `Last-Event-ID` mid-run → assert zero gaps/duplicates in event seq.
- **Migrations:** CI job runs alembic upgrade → downgrade → upgrade against a snapshot of the
  previous release's schema; drift check between models and migrations.
- **Frontend:** vitest + React Testing Library for logic-bearing components (canvas state,
  version diff view); Playwright for journeys; visual regression on the diagram canvas.

## 3. LLM / Agent Evaluation (the "tests" for model behavior)

**Golden-brief harness** (extends doc 07 §6):
- ~30 curated briefs spanning personas, domains, scales (todo app → 1M-user marketplace),
  including adversarial briefs (contradictory requirements, vague one-liners, non-software asks,
  prompt-injection payloads embedded in uploads).
- **Deterministic validators** (hard gates): OpenAPI 3.1 parses + lints; DDL parses (sqlglot);
  diagram JSON validates against schema; every diagram component referenced in architecture doc;
  every infra component priced in cost estimate; requirement-ID citations resolve.
- **LLM-as-judge rubrics** (scored, trended, soft gates): requirement coverage, architectural
  soundness, trade-off quality, doc clarity. Judge prompts and rubric versions are in-repo.
- **Regression protocol:** any change to prompts, graph topology, model defaults, or providers
  runs the harness; merges blocked on hard-gate regressions; soft-score drops > 5% require
  explicit sign-off in the PR.
- Nightly full-harness run trends scores and per-brief cost/latency (catches provider drift).

## 4. Test Data & Fixtures

- Factory-boy factories per aggregate; seed script builds a realistic demo workspace.
- LLM cassettes (recorded request/response) refreshed deliberately, never auto — cassette
  changes appear in PR diffs.
- No production data in tests or staging, ever; anonymized-shape data generated synthetically.

## 5. Coverage & Quality Gates (CI-enforced)

- Domain + application layers: ≥ 85% line, ≥ 75% branch. Infrastructure/API layers: covered by
  component/contract suites (no vanity global gate).
- mypy --strict and tsc --strict: zero errors. Ruff/ESLint: zero warnings on changed code.
- New use case without tests = failing review checklist item (enforced socially + by coverage
  diff bot).
