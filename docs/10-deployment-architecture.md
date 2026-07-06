# 10 — Deployment Architecture

## 1. Environments

| Env | Purpose | Data | Deploy trigger |
|---|---|---|---|
| local | development | seeded fixtures | `docker compose up` |
| preview | PR review apps (web only + shared staging API) | synthetic | per-PR (Vercel/preview namespace) |
| staging | integration, load tests, eval runs | synthetic + anonymized | merge to `main` (auto) |
| production | users | real | tag / promotion (manual gate) |

## 2. Local Development

`docker-compose.yml` runs: `api`, `worker`, `web`, `postgres` (with pgvector), `redis`,
`minio` (S3), `mailpit` (email). One command + `make seed`. Hot reload for api (uvicorn
--reload) and web (next dev). LLM calls hit real providers with a dev key, or a **recorded
fixture mode** (VCR-style cassettes) for offline/deterministic work.

## 3. Container Images

- `backend` image (multi-stage: uv/pip install → distroless-style slim runtime; non-root;
  read-only rootfs). Same image for api and worker — entrypoint arg selects role. This
  guarantees api/worker never skew versions.
- `web` image (Next.js standalone output, non-root).
- Images tagged with git SHA; SBOM attached; Trivy-scanned; signed (cosign) — deploys verify
  signatures.

## 4. Kubernetes Topology (production)

```
namespace: aisa-prod
├── Deployment api        (HPA: 3→20 replicas; CPU + p95 latency)
├── Deployment worker     (KEDA: 2→50 replicas; Redis queue depth; long
│                          terminationGracePeriod so runs checkpoint before shutdown)
├── Deployment web        (HPA: 2→10)
├── Deployment mcp-sandbox-pool (if stdio servers enabled; gVisor runtimeClass,
│                          NetworkPolicy: deny-all egress + explicit allowlist)
├── CronJobs: outbox-relay-sweeper, partition-maintenance, usage-rollup,
│             stale-run-expirer, catalog-rediscovery
├── Ingress (NGINX/cloud LB): TLS, WAF, rate limits; SSE: proxy buffering OFF,
│             read timeout ≥ 24h on /events routes
└── External Secrets Operator ← cloud secret manager
Managed outside cluster: PostgreSQL (HA + PITR), Redis, S3, KMS, email provider
```

Cloud-agnostic: manifests via Helm chart in-repo; only external dependencies are the managed
services listed (all have equivalents on AWS/GCP/Azure — NFR-8).

## 5. Deployment & Release Strategy

- **Rolling deploys** with readiness gates; API and worker deploy together (same image tag).
- **Migrations before rollout** (Alembic job as a pre-deploy hook), expand/contract only, so
  old pods keep working during rollout — zero-downtime by construction.
- Workers drain gracefully: on SIGTERM stop claiming jobs, checkpoint current run, release job
  (resume elsewhere) — this is why runs are checkpoint-resumable (doc 04 §4.2).
- Feature flags (config-service-free: DB-backed flags table + cached) gate risky features;
  kill switches for: MCP execution, individual providers, new agents.
- Rollback = redeploy previous tag (safe because migrations are backward-compatible).

## 6. Scaling Policy Summary

| Component | Signal | Notes |
|---|---|---|
| api | CPU + request p95 | stateless |
| worker | Redis queue depth (KEDA) | scale-in respects in-flight runs via grace period |
| web | CPU/RPS | mostly static after build |
| postgres | vertical first; read replicas for dashboards/analytics | partitioned hot tables |
| redis | vertical; cluster mode is the documented upgrade path | |

## 7. DR & Backups

- Postgres: automated daily snapshots + WAL PITR (RPO ≤ 5 min); quarterly restore drills
  (a backup that's never been restored doesn't exist).
- S3: versioning + cross-region replication for the exports/uploads buckets.
- Redis: acceptable-loss store by design (jobs re-derivable from `runs` table via reconciler
  cron; cache rebuilds; SSE replays from `agent_events`). No Redis persistence dependency.
- Infra as code (Terraform) for the platform itself → environment rebuild is scripted (RTO ≤ 4h).
