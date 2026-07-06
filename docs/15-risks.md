# 15 — Risks & Mitigation Strategies

Scored Impact × Likelihood (H/M/L). Owner = accountable role. Reviewed at every milestone exit.

## Technical Risks

| # | Risk | I | L | Mitigation | Early signal |
|---|------|---|---|-----------|--------------|
| T1 | **Artifact quality below the credibility bar** — designs look plausible but are wrong; product's core value fails | H | M | Golden-brief eval harness from M3 with hard deterministic gates; design_reviewer consistency agent; design-partner review in beta; "draft for review" product framing | Eval soundness scores plateau below rubric target |
| T2 | **LLM provider outage/degradation** | H | M | Provider failover chain; checkpointed resumable runs; kill switch per provider; cassette-based degradation drills | `llm_failovers_total` spikes |
| T3 | **LLM cost blowout** (margin destroyed) | H | M | Per-run token budgets; model tiering; prompt caching; per-workspace caps; daily margin dashboard vs 15% target | Cost-per-blueprint trend up 2 weeks running |
| T4 | **Prompt injection via uploads/MCP results causes harmful tool calls** | H | M | Structural defense: human approval on all writes regardless of model output; sandboxed stdio servers; injection suite in evals (doc 08 §4, doc 09 §5) | Injection suite regressions; sandbox egress alerts |
| T5 | **Cross-tenant data leak** | H | L | RLS backstop + app checks + dedicated cross-tenant test suite as permanent merge blocker; RLS-denial alert (any hit = bug) | RLS-denial metric > 0 |
| T6 | **Run-state complexity bugs** (resume duplicates artifacts/events) | M | M | Kill-worker-at-every-node test matrix; idempotent nodes; event seq uniqueness constraints | Duplicate-event constraint violations in staging |
| T7 | **pgvector performance at scale** (RAG latency) | M | L | HNSW indexes; per-tenant filters use composite indexes; fallback plan documented (dedicated vector DB behind the retriever port — port design makes this a swap) | Retrieval p95 > 300ms |
| T8 | **Framework churn** (LangGraph/PydanticAI/MCP are young, breaking changes) | M | H | Pin versions; wrap both behind our own orchestration/agent base classes (already required by DI design); upgrade PRs run full eval harness; MCP SDK is official/spec-tracked | Upgrade PR eval failures |
| T9 | **Diagram JSON ↔ React Flow coupling** | L | M | Own canonical schema with converters; visual regression tests | Converter test failures on RF upgrades |

## Product Risks

| # | Risk | I | L | Mitigation | Early signal |
|---|------|---|---|-----------|--------------|
| P1 | **"ChatGPT is good enough" — users won't pay** | H | M | Moat = consistency, versioning, propagation, MCP delivery (things chat can't do); Dev-Dan-first GTM; free tier funnels to a paid provisioning "aha" | Free→Pro conversion < 2% in beta |
| P2 | **Users distrust cost estimates** (worst artifact to be wrong on) | M | M | Ranges not points; versioned pricing dataset with date shown; per-line-item assumptions expandable | Cost-artifact rating < other artifacts |
| P3 | **Scope creep into code generation** | M | H | PRD "won't have" is explicit; scaffolds only; revisit post-GA with data | Roadmap debates recur |
| P4 | **Clarification fatigue** (users abandon during Q&A) | M | M | Max 5 questions/round, 3 rounds; "use your best judgment" escape hatch with recorded assumptions | Intake abandonment > 30% |

## Operational Risks

| # | Risk | I | L | Mitigation | Early signal |
|---|------|---|---|-----------|--------------|
| O1 | **Tiny team + broad surface = burnout/bus factor** | H | M | Modular monolith (one deployable pair); managed services everywhere; ruthless milestone scope; runbooks + game days so ops is procedural | Milestone exit criteria slipping twice |
| O2 | **GitHub/MCP third-party API changes break provisioning** | M | M | MCP as the seam (server updates absorb API changes); contract tests against GitHub MCP server in nightly; feature kill switch | Nightly contract test failures |
| O3 | **Compliance surprise** (enterprise deal needs SOC2/residency early) | M | L | ASVS L2 + audit log + encryption from day one make SOC2 a documentation exercise, not a rebuild; `region` field reserved | Enterprise leads blocked in sales |
| O4 | **Abuse** (free tier used as general LLM proxy / crypto-brief spam) | M | M | Tight free quotas; domain-scoped prompts refuse off-topic use; anomaly alerts on usage patterns | Off-topic run classifications rising |

## Decisions Deliberately Deferred (tracked, not risks yet)

- Observability vendor (Grafana stack vs SaaS) — decide at M0 by ops budget.
- stdio MCP sandbox in v1 vs HTTP-only launch — decide at M5 by demand for community servers.
- Embedding-model-per-workspace vector dimension handling — decide when BYO-embedding is requested.
- Dedicated vector DB — only if T7 signal fires.

## Risk Review Cadence

Risk register reviewed at each milestone exit and after any Sev-1 incident; each accepted risk
must name its early signal, and each early signal must exist as a dashboard/alert (doc 14) —
a risk without a detectable signal is not "mitigated," it's ignored.
