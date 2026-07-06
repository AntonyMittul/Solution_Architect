# 09 — Security Model

Baseline control set: **OWASP ASVS L2** + **OWASP Top 10 for LLM Applications**. This document
lists the decisions; implementation tickets derive from it.

## 1. Authentication

- Email/password: argon2id hashing; verification required; rate-limited login; breached-password
  check on set.
- OAuth: GitHub, Google (PKCE).
- Sessions: httpOnly, Secure, SameSite=Lax cookies; short-lived access token (15 min JWT) +
  rotating refresh token (revocable, stored hashed); refresh reuse detection kills the family.
- 2FA (TOTP): Pro/Team plans at GA; enforceable workspace-wide by admins.
- API keys (later): sha256-hashed, scoped, expiring; shown once.

## 2. Authorization

- RBAC per workspace (owner/admin/member/viewer) — matrix in doc 06.
- Enforced in the **application layer** (every use case receives an `Actor` and checks policy —
  no controller-level-only checks), with **Postgres RLS as the backstop** so a missed check
  cannot cross tenants.
- Object-level checks always (no "list is filtered but GET by id isn't" bugs — IDOR is the top
  SaaS vulnerability class).

## 3. Tenant Isolation

| Layer | Mechanism |
|---|---|
| Data | RLS on all tenant tables keyed by `app.workspace_id` (SET LOCAL per transaction) |
| RAG | chunk queries filtered by workspace_id + project_id in SQL; platform KB is a separate NULL-workspace corpus |
| Cache/queue | Redis keys namespaced `ws:{id}:...`; job payloads carry workspace and are re-validated on execution |
| Object storage | per-workspace prefixes; access via short-lived signed URLs only |
| LLM context | prompts assembled only from the current run's state; no cross-tenant retrieval possible by construction |

## 4. Secrets & Data Protection

- Platform secrets: injected via K8s secrets (External Secrets Operator → cloud secret manager);
  never in images or repo. `detect-secrets` in CI.
- Tenant credentials (MCP, BYOK): envelope encryption — per-workspace DEK (AES-256-GCM) wrapped
  by a KMS master key; key rotation supported via `key_version`; decrypt only at point of use.
- TLS 1.2+ everywhere external; in-cluster mTLS is a post-GA hardening item.
- Encryption at rest: managed-Postgres/S3 native encryption.
- PII inventory kept in this doc's appendix (email, name, IP in audit log); GDPR
  delete cascades: relational rows, chunks/vectors, S3 objects, provider-side data where APIs allow.
- Logs: structured, with a deny-list scrubber (credentials, tokens, message bodies beyond 200
  chars in non-debug).

## 5. LLM-Specific Threats (OWASP LLM Top 10 mapping)

| Threat | Mitigation |
|---|---|
| LLM01 Prompt injection (uploads, RAG, MCP results) | untrusted-content delimiting (doc 08 §4); structural controls: agents cannot execute write tools without human approval regardless of model output; injection test suite in evals |
| LLM02 Insecure output handling | artifacts rendered as text/JSON, never executed; markdown sanitized (no raw HTML); DDL/OpenAPI parsed, never run against user DBs |
| LLM04 Model DoS / cost abuse | per-run token budgets, per-workspace caps, rate limits, plan quotas |
| LLM06 Sensitive info disclosure | no cross-tenant context (§3); provider no-training endpoints; secrets never in prompts |
| LLM07 Insecure plugins (MCP) | allowlists, trust levels, sandboxing, re-approval on schema change (doc 08) |
| LLM08 Excessive agency | planner/executor split; human approval on all side effects; agents hold no credentials |
| LLM09 Overreliance | UI framing as draft-for-review; confidence/assumption annotations; cost-estimate disclaimers |

## 6. Application Security

- Input validation via Pydantic at every boundary; file uploads: type sniffing (not extension),
  size caps, malware scan (ClamAV job), never served from origin (S3 + signed URL).
- SSRF: MCP/webhook endpoints validated against private-IP ranges (deny RFC1918/link-local/metadata IPs, resolve-then-connect pinning).
- Standard headers: CSP (strict, nonce-based), HSTS, X-Content-Type-Options, frame-ancestors none.
- CSRF: SameSite=Lax + double-submit token on state-changing routes (cookie auth).
- Dependency & image scanning: Dependabot + `pip-audit`/`npm audit` + Trivy in CI; SBOM published.

## 7. Auditing & Detection

- `audit_log` for all security-relevant actions (auth events, role changes, MCP registration,
  approvals, exports, deletions); immutable (append-only role).
- Alerting: auth anomaly spikes, MCP failure spikes, cross-tenant RLS denials (should be zero —
  any hit is a bug alarm), egress from sandboxes.
- Pre-GA: external penetration test (release criterion, PRD §10). Post-GA: private bug bounty.

## 8. Availability Protection

- Rate limiting at ingress (per-IP) and application (per-user/workspace).
- Queue back-pressure: run queue depth caps per plan tier; overflow returns 429 with clear
  messaging rather than unbounded queuing.
