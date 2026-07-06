# 14 — Observability Plan

Goal (NFR-10): any failed agent run diagnosable from telemetry alone in < 10 minutes.
Stack: **OpenTelemetry** everywhere → vendor-agnostic export (Grafana LGTM stack or a SaaS
like Datadog/Honeycomb — decided by ops budget at M0; instrumentation code is identical).

## 1. Structured Logging

- JSON logs (structlog) with mandatory fields: `timestamp, level, service, trace_id, span_id,
  workspace_id, user_id?, run_id?, agent?, event`.
- Log levels disciplined: `INFO` = state transitions; `WARNING` = handled anomalies (retry,
  failover); `ERROR` = user-visible failure or invariant breach. No debug logs in prod path.
- Scrubber middleware (doc 09 §4): secrets/tokens never logged; message/prompt bodies truncated
  and only at DEBUG.
- Frontend: console-free policy; errors go to error tracking (Sentry) with trace correlation.

## 2. Distributed Tracing

- OTel auto-instrumentation: FastAPI, SQLAlchemy, Redis, httpx; manual spans for domain steps.
- **The run trace is the flagship:** one trace per agent run spanning enqueue → each graph node →
  each LLM call (span attrs: provider, model, prompt_version, input/output/cached tokens,
  cost_usd, stop_reason) → each MCP invocation (server, tool, status) → artifact writes.
  Trace context propagates through the queue (job payload carries traceparent).
- `trace_id` returned in API error responses (doc 06) and shown in the UI's run debug panel →
  support tickets arrive with the trace id attached.
- Sampling: tail-based — 100% of errored/slow traces, 10% baseline.

## 3. Metrics & SLOs

**RED per endpoint** (rate, errors, duration) + **queue depth / job age** + **run funnel**.

LLM-specific metrics (the ones generic APM won't give us):

| Metric | Labels | Why |
|---|---|---|
| `llm_tokens_total` | provider, model, workspace_plan, byok | cost control |
| `llm_cost_usd_total` | provider, model | unit economics (PRD metric) |
| `llm_request_duration` | provider, model | provider health/failover tuning |
| `llm_failovers_total` | from, to, reason | provider reliability |
| `run_duration_seconds` | kind, status | NFR-1 p50/p95 |
| `run_outcomes_total` | status, failure_class | run success SLO (≥98%) |
| `agent_validation_retries_total` | agent | prompt-quality drift signal |
| `eval_score` | brief, rubric (from nightly harness) | model/prompt drift |
| `mcp_invocations_total` | server, tool, status | integration health |
| `budget_exceeded_total` | plan | pricing/limit tuning |

**SLOs & alerting (Alertmanager/PagerDuty):**
- API availability 99.9% (burn-rate alerts, 1h/6h windows)
- Run success ≥ 98%; first-token p95 < 6s (synthetic probe)
- Page-worthy: SLO burn, queue age > 5 min, DB/Redis saturation, outbox lag, RLS-denial > 0,
  sandbox egress attempt. Ticket-worthy: eval score drops, cost anomalies (workspace spend
  z-score), provider failover sustained.

## 4. Run Debug Panel (product feature, not just ops)

Per-run UI (admin + internal support view): timeline of graph nodes with status/durations,
token/cost ledger, retrieval citations used, validation retries, truncated prompt/response
inspection (internal role only, audit-logged access). This is the tool that makes the
10-minute-diagnosis NFR real — for both engineers and support.

## 5. Cost Observability

Daily rollup job: `llm_usage` → per-workspace/per-model/per-agent cost views; margin dashboard
(LLM cost vs plan revenue — the PRD's ≤15% target); anomaly detection on per-run cost.

## 6. Dashboards & Runbooks

Dashboards: service overview (RED), run pipeline (funnel, durations, failures by class),
LLM providers (latency, errors, failovers, cost), MCP health, DB (bloat, slow queries,
partition sizes), business (signups, runs, conversion — from domain events).
Every alert links to a runbook in `docs/runbooks/`; runbooks are exercised in M6 game days.
