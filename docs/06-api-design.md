# 06 — API Design

REST over HTTPS, JSON bodies, OpenAPI 3.1 generated from FastAPI and published per version.
Base path `/api/v1`. The Next.js app is the only first-party client at GA; the API is designed
so a public API (with `api_keys`) is a config change, not a redesign.

## Conventions

- **Auth:** session cookie (httpOnly, SameSite=Lax) set by the web tier; `Authorization: Bearer`
  for API keys later. Workspace context from the URL path — never from a header the client can
  desync from the path.
- **IDs:** ULIDs. **Times:** RFC 3339 UTC.
- **Errors:** RFC 9457 `application/problem+json`:

```json
{
  "type": "https://api.aisolutionarchitect.dev/errors/quota-exceeded",
  "title": "Run quota exceeded",
  "status": 429,
  "detail": "Free plan allows 5 runs/month. Used: 5.",
  "instance": "/api/v1/workspaces/ws_01H.../projects/prj_01H.../runs",
  "trace_id": "a1b2c3"
}
```

- **Pagination:** cursor-based (`?cursor=&limit=`), `next_cursor` in response. No offsets.
- **Idempotency:** mutating POSTs accept `Idempotency-Key`; replays return the original result.
- **Rate limits:** per-user and per-workspace token buckets; `429` + `Retry-After`;
  `X-RateLimit-*` headers on every response.
- **Versioning:** URL major version only (`/v1`); additive changes are non-breaking by policy;
  breaking changes require `/v2` with a deprecation window. Event schema versions travel inside
  the event payload (`"v": 1`).

## Resource Map

```
/auth
  POST   /auth/register | /auth/login | /auth/logout | /auth/refresh
  GET    /auth/oauth/{provider}/start | /auth/oauth/{provider}/callback
  GET    /auth/me

/workspaces
  GET    /workspaces                          # my workspaces
  POST   /workspaces
  GET    /workspaces/{ws}
  PATCH  /workspaces/{ws}
  GET    /workspaces/{ws}/members
  POST   /workspaces/{ws}/members             # invite
  PATCH  /workspaces/{ws}/members/{user}      # change role
  DELETE /workspaces/{ws}/members/{user}
  GET    /workspaces/{ws}/usage               # metering dashboard data

/workspaces/{ws}/projects
  GET    /                                    # list (filter: status)
  POST   /
  GET    /{prj}
  PATCH  /{prj}                               # name, settings, archive
  POST   /{prj}/duplicate
  DELETE /{prj}                               # soft delete

/workspaces/{ws}/projects/{prj}/thread
  GET    /messages?cursor=
  POST   /messages                            # user message; may trigger intake run

/workspaces/{ws}/projects/{prj}/requirements
  GET    /                                    # versions list
  GET    /{version}
  PUT    /                                    # user edit -> new draft version
  POST   /confirm                             # draft -> confirmed

/workspaces/{ws}/projects/{prj}/documents
  GET    / | POST /                           # upload (multipart) -> ingestion job
  DELETE /{doc}

/workspaces/{ws}/projects/{prj}/runs
  GET    /                                    # run history
  POST   /                                    # {kind: blueprint|regenerate, params}
  GET    /{run}
  POST   /{run}/cancel
  POST   /{run}/input                         # answer clarification / resume needs_input
  GET    /{run}/events                        # SSE stream (Last-Event-ID replay)

/workspaces/{ws}/projects/{prj}/artifacts
  GET    /                                    # all artifacts, latest versions + staleness
  GET    /{type}                              # latest
  GET    /{type}/versions | /{type}/versions/{v}
  PUT    /{type}                              # user edit -> new version (edited_by_user)
  POST   /{type}/restore/{v}
  GET    /{type}/diff?from=&to=
  POST   /export                              # {format: zip|pdf|md, artifact_types?} -> job
  GET    /exports/{export_id}                 # status + signed download URL

/workspaces/{ws}/mcp-servers
  GET    / | POST /
  PATCH  /{srv}                               # allowlist, trust, disable
  DELETE /{srv}
  POST   /{srv}/test                          # connectivity + tool discovery
  GET    /{srv}/tools                         # discovered tools (cached)

/workspaces/{ws}/projects/{prj}/provisioning
  POST   /plans                               # {goal: create_repo|...} -> plan preview (run)
  GET    /plans/{plan}
  POST   /plans/{plan}/approve                # executes; per-action approval
  POST   /plans/{plan}/reject

/workspaces/{ws}/settings/llm
  GET    / | PUT /                            # provider, tier, BYOK key (write-only)

/notifications
  GET    / | POST /read
```

## Streaming Design (SSE)

`GET .../runs/{run}/events` — `text/event-stream`. Chosen over WebSocket: unidirectional
server→client fits the use case, works through proxies/HTTP2, native browser reconnect with
`Last-Event-ID`, no connection-state service needed. All client→server actions go through
normal REST (`/input`, `/cancel`).

```
id: 42
event: agent.completed
data: {"v":1,"run_id":"run_01H...","agent":"cost_estimator",
       "artifact":{"type":"cost_estimate","version":3},"tokens_used":18432}
```

Event types: `run.status`, `agent.started`, `agent.token` (batched ~10/s), `agent.completed`,
`artifact.created`, `approval.requested`, `run.completed`, `run.failed`, `heartbeat` (15s).

## Representative Payloads

`POST /runs` →

```json
{ "kind": "blueprint",
  "params": { "requirements_version": 4,
              "artifact_types": ["architecture_doc","diagram","tech_stack",
                                  "cost_estimate","api_spec","db_schema","design_doc"] } }
```

`201` → `{ "id": "run_01H...", "status": "queued", "token_budget": 500000 }`

`GET /artifacts/diagram` →

```json
{ "artifact_id": "art_01H...", "type": "diagram", "version": 7, "is_stale": false,
  "content": { "schema_version": 1, "views": { "container": { "nodes": [...], "edges": [...] } } },
  "provenance": { "run_id": "run_01H...", "source": "agent", "model": "claude-sonnet-5",
                  "requirements_version": 4 } }
```

## Authorization Matrix (enforced in application layer + RLS backstop)

| Endpoint group | viewer | member | admin | owner |
|---|---|---|---|---|
| Read projects/artifacts | ✅ | ✅ | ✅ | ✅ |
| Create/edit projects, runs, edits | — | ✅ | ✅ | ✅ |
| MCP servers, LLM settings, members | — | — | ✅ | ✅ |
| Approve provisioning plans | — | ✅* | ✅ | ✅ |
| Billing, delete workspace | — | — | — | ✅ |

\* member approval allowed only for servers the admin marked member-approvable; default admin-only.
