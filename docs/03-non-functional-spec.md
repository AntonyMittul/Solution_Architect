# 03 — Non-Functional Specification

Targets are for GA in production. Staging must demonstrate them under load test before release
(see doc 12). Every NFR lists how it is verified.

---

## NFR-1 Performance & Latency

| Operation | Target | Verified by |
|---|---|---|
| API reads (p95) | < 200 ms | load test + prod SLO dashboards |
| API writes (p95) | < 400 ms | load test |
| First streamed token after run start (p95) | < 6 s | synthetic probe |
| Full blueprint run (p50 / p95) | < 4 min / < 10 min | eval harness timing |
| Frontend LCP (p75, dashboard) | < 2.5 s | Lighthouse CI |
| SSE event delivery lag (p95) | < 500 ms | integration test with timestamps |

LLM latency dominates run time and is outside our control; therefore run-time NFRs are managed
by **parallelizing independent agents** (doc 07) and **model tiering** (fast models for
low-stakes steps), not by hard latency guarantees.

## NFR-2 Scalability

- Design point: **10,000 workspaces, 1,000 concurrent users, 200 concurrent agent runs** without
  architectural change — only horizontal replica scaling.
- API tier: stateless, horizontally scalable (HPA on CPU + request latency).
- Worker tier: scales on queue depth (KEDA on Redis queue length).
- PostgreSQL: single primary + read replicas; pgvector queries bounded per-tenant; partition
  `agent_events` and `llm_usage` by month (highest-volume tables).
- Redis: single logical instance (queue + cache + pub/sub) sized for 10× design load; cluster
  mode is a known upgrade path, not needed at design point.
- Explicit non-goal at GA: multi-region active-active. Architecture must not preclude it
  (no local file state, UTC everywhere, IDs are ULIDs).

## NFR-3 Availability & Reliability

| Item | Target |
|---|---|
| API availability (monthly) | 99.9% |
| Run success rate (excluding user cancellations & content refusals) | ≥ 98% |
| RPO (data loss) | ≤ 5 min (WAL archiving / PITR) |
| RTO (region-level restore) | ≤ 4 h |

- Every LLM/provider call: timeout + retry with exponential backoff + jitter; provider
  failover chain (e.g., Anthropic → OpenAI) for transient outages, config-driven.
- Runs are **resumable**: orchestration state checkpoints to Postgres after every graph node
  (LangGraph checkpointer), so a worker crash resumes rather than restarts a run.
- All jobs idempotent (idempotency keys); at-least-once delivery from the queue is assumed.
- Graceful degradation: if RAG store is down, runs proceed without retrieval and artifacts are
  flagged; if MCP server unreachable, provisioning fails cleanly, blueprint unaffected.

## NFR-4 Cost Efficiency (LLM)

- Hard per-run token budget (plan-dependent, default 500k tokens) enforced in the orchestrator.
- Prompt caching used wherever the provider supports it (system prompts, RAG context).
- Model tiering policy: clarification/formatting → fast tier; design/reasoning → quality tier.
- Per-workspace monthly LLM spend cap with alerting (FS-12).

## NFR-5 Security & Privacy (detail in doc 09)

- All data encrypted in transit (TLS 1.2+) and at rest.
- Tenant isolation enforced at the data layer (Postgres RLS) in addition to application checks.
- Secrets never in code or logs; MCP/BYOK credentials envelope-encrypted per workspace.
- OWASP ASVS L2 as the baseline control set; OWASP LLM Top 10 addressed explicitly.

## NFR-6 Compliance & Data Handling

- GDPR: data export + deletion (30-day soft delete, then hard delete including vectors and
  object storage); EU data residency deferred but schema keeps `region` on workspace.
- User content is **never used to train models**; provider "no-training" endpoints/flags required
  for platform keys; stated in DPA.
- Audit log retention: 400 days. Conversation/artifact retention: life of project.

## NFR-7 Maintainability & Code Quality

- Python: mypy `--strict`, ruff, black; TypeScript: `strict: true`, ESLint, Prettier. CI-enforced.
- Module boundaries enforced by import-linter (Python) and ESLint boundaries rules (TS).
- Test coverage gate: ≥ 85% on domain and application layers (not a vanity global number).
- Every architectural decision recorded as an ADR in `docs/adr/`.
- Onboarding NFR: a new engineer runs the full stack locally with `docker compose up` + one
  seed command in < 30 minutes.

## NFR-8 Portability

- Cloud-agnostic Kubernetes deployment; only managed dependencies are Postgres, Redis,
  S3-compatible object storage, and an email provider — all with drop-in alternatives.
- No provider-proprietary services in the critical path (no AWS-only queues, etc.).

## NFR-9 Accessibility & i18n

- WCAG 2.1 AA for the web app (keyboard navigation, contrast, ARIA on the canvas toolbar;
  the diagram canvas itself gets a text alternative — the Mermaid view).
- UI copy externalized for future i18n; v1 ships English only. All timestamps stored UTC,
  rendered in user locale.

## NFR-10 Operability

- Any failed run diagnosable from trace + logs alone in < 10 minutes (verified by game days).
- Zero-downtime deploys (rolling), backward-compatible migrations only (expand/contract pattern).
- Feature flags for all risky paths (new agents, new providers, MCP actions).
