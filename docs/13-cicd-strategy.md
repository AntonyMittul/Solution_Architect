# 13 — CI/CD Strategy

GitHub Actions, trunk-based development. `main` is always deployable; work happens on
short-lived branches merged via PR.

## 1. Branch & Release Model

- Branch: `feat/...`, `fix/...`; PR required; 1 review (or self-merge allowed for solo phase
  with all gates green); squash merge; conventional commits (drives changelog + semver).
- `main` → auto-deploy to **staging**.
- Production: promotion of an already-built image via release tag (`vX.Y.Z`) with a manual
  approval environment gate in Actions. Build once, promote the same artifact — staging and
  prod never run different builds of the same version.

## 2. Pipelines

### `ci.yml` — every PR and push to main (target < 15 min)
Path-filtered so web-only changes skip backend jobs and vice versa.

```
backend:  ruff + black --check → mypy --strict → import-linter →
          unit (parallel) → component/contract (testcontainers services) →
          integration (compose) → coverage gate → alembic drift + up/down check
web:      eslint + prettier → tsc → vitest → build → generated-client freshness check
security: detect-secrets → pip-audit / npm audit → CodeQL
build:    docker build backend+web (buildx cache) → Trivy scan → SBOM →
          push :sha to registry (main only) → cosign sign
```

### `deploy-staging.yml` — on merge to main
Helm upgrade (staging values) → pre-deploy Alembic job → rolling deploy → smoke suite
(health, auth, walking-skeleton run with cassette LLM) → Playwright E2E → notify on failure
(auto-rollback to previous release on smoke failure).

### `release.yml` — on `v*` tag
Verify tag SHA passed CI → manual approval gate (production environment) → Helm upgrade prod →
post-deploy smoke → GitHub Release with changelog. Rollback = re-run with previous tag
(safe: expand/contract migrations).

### `evals.yml` — nightly + on changes under `prompts/`, `orchestration/`
Golden-brief harness on staging; hard-gate failures block prompt PRs; publishes trend report
artifact (scores, cost, latency per brief).

### `load.yml` — weekly + manually pre-release
k6 scenarios vs staging; asserts NFR-1/NFR-2 thresholds; report as artifact.

## 3. Quality Gates Summary (merge blockers)

lint/format · type-check (strict, both languages) · module-boundary check · unit+component+
integration+contract suites · coverage thresholds · migration drift/up-down · secret scan ·
dependency+image CVE scan (fail on critical) · generated API client up-to-date · eval hard
gates (when prompt/graph paths touched).

## 4. Secrets & Environments in CI

- GitHub Environments (`staging`, `production`) with required reviewers on production.
- Cloud auth via **OIDC federation** (no long-lived cloud keys in GitHub secrets).
- Test LLM keys are low-limit, isolated billing keys; cassette mode default in CI — live-LLM
  jobs (evals) run on a schedule, not per-PR.

## 5. Developer Experience

- `make ci` reproduces the full CI locally (same commands CI runs — no "works in CI only").
- pre-commit hooks: format, lint, detect-secrets (fast subset).
- PR template embeds the review checklist (tests added, migration safety, authz considered,
  docs/ADR updated).
- Dependabot weekly, auto-merge for patch updates with green CI.
