# 05 — Database Schema

PostgreSQL 16 + pgvector. Conventions: ULID primary keys (`CHAR(26)`), `TIMESTAMPTZ` UTC,
soft delete via `deleted_at`, every tenant-owned table carries `workspace_id` (denormalized on
purpose — it is the RLS isolation key), `created_at/updated_at` on all tables (triggers omitted
below for brevity).

**Multi-tenancy:** shared schema + **Row-Level Security**. Application sets
`SET LOCAL app.workspace_id = ...` per transaction; RLS policies filter every tenant table.
Application-level scoping remains as the first line of defense; RLS is the backstop.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- ===== identity =====================================================

CREATE TABLE users (
    id              CHAR(26) PRIMARY KEY,
    email           CITEXT UNIQUE NOT NULL,
    password_hash   TEXT,                      -- NULL for OAuth-only users
    name            TEXT NOT NULL,
    avatar_url      TEXT,
    email_verified  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE oauth_identities (
    id           CHAR(26) PRIMARY KEY,
    user_id      CHAR(26) NOT NULL REFERENCES users(id),
    provider     TEXT NOT NULL CHECK (provider IN ('github','google')),
    provider_uid TEXT NOT NULL,
    UNIQUE (provider, provider_uid)
);

CREATE TABLE workspaces (
    id          CHAR(26) PRIMARY KEY,
    slug        CITEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('personal','team')),
    plan        TEXT NOT NULL DEFAULT 'free' CHECK (plan IN ('free','pro','team')),
    region      TEXT NOT NULL DEFAULT 'us',            -- future data residency
    settings    JSONB NOT NULL DEFAULT '{}',           -- model tier, defaults
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ
);

CREATE TABLE memberships (
    id           CHAR(26) PRIMARY KEY,
    workspace_id CHAR(26) NOT NULL REFERENCES workspaces(id),
    user_id      CHAR(26) NOT NULL REFERENCES users(id),
    role         TEXT NOT NULL CHECK (role IN ('owner','admin','member','viewer')),
    UNIQUE (workspace_id, user_id)
);

CREATE TABLE api_keys (                                 -- programmatic access (later)
    id           CHAR(26) PRIMARY KEY,
    workspace_id CHAR(26) NOT NULL REFERENCES workspaces(id),
    name         TEXT NOT NULL,
    key_hash     TEXT NOT NULL,                         -- sha256; plaintext shown once
    scopes       TEXT[] NOT NULL,
    last_used_at TIMESTAMPTZ,
    expires_at   TIMESTAMPTZ,
    revoked_at   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ===== projects & requirements ======================================

CREATE TABLE projects (
    id           CHAR(26) PRIMARY KEY,
    workspace_id CHAR(26) NOT NULL REFERENCES workspaces(id),
    name         TEXT NOT NULL,
    description  TEXT,
    status       TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
    settings     JSONB NOT NULL DEFAULT '{}',   -- target cloud, budget, team, compliance flags
    created_by   CHAR(26) NOT NULL REFERENCES users(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at   TIMESTAMPTZ
);
CREATE INDEX idx_projects_ws ON projects (workspace_id, status);

CREATE TABLE requirement_docs (                 -- versioned structured requirements
    id           CHAR(26) PRIMARY KEY,
    workspace_id CHAR(26) NOT NULL REFERENCES workspaces(id),
    project_id   CHAR(26) NOT NULL REFERENCES projects(id),
    version      INT NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('draft','confirmed')),
    content      JSONB NOT NULL,                -- structured: goals, actors, FRs, NFRs, assumptions
    created_by   TEXT NOT NULL,                 -- 'user:<id>' | 'agent:<name>'
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, version)
);

-- ===== conversations ================================================

CREATE TABLE threads (
    id           CHAR(26) PRIMARY KEY,
    workspace_id CHAR(26) NOT NULL REFERENCES workspaces(id),
    project_id   CHAR(26) NOT NULL REFERENCES projects(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE messages (
    id           CHAR(26) PRIMARY KEY,           -- ULID => chronological order
    workspace_id CHAR(26) NOT NULL REFERENCES workspaces(id),
    thread_id    CHAR(26) NOT NULL REFERENCES threads(id),
    role         TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
    content      JSONB NOT NULL,                 -- text + structured parts (questions, citations)
    run_id       CHAR(26),                       -- assistant messages link to their run
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_messages_thread ON messages (thread_id, id);

-- ===== orchestration ================================================

CREATE TABLE runs (
    id             CHAR(26) PRIMARY KEY,
    workspace_id   CHAR(26) NOT NULL REFERENCES workspaces(id),
    project_id     CHAR(26) NOT NULL REFERENCES projects(id),
    kind           TEXT NOT NULL,                -- 'intake' | 'blueprint' | 'regenerate' | 'provision'
    status         TEXT NOT NULL DEFAULT 'queued'
                   CHECK (status IN ('queued','running','needs_input','completed','failed','cancelled')),
    input          JSONB NOT NULL,               -- requirements version, scope, params
    error          JSONB,
    token_budget   INT NOT NULL,
    tokens_used    INT NOT NULL DEFAULT 0,
    triggered_by   CHAR(26) NOT NULL REFERENCES users(id),
    started_at     TIMESTAMPTZ,
    finished_at    TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_runs_project ON runs (project_id, created_at DESC);
CREATE INDEX idx_runs_status  ON runs (status) WHERE status IN ('queued','running','needs_input');

-- LangGraph checkpoints (graph state for resume); managed by the checkpointer
CREATE TABLE run_checkpoints (
    run_id        CHAR(26) NOT NULL REFERENCES runs(id),
    checkpoint_id TEXT NOT NULL,
    parent_id     TEXT,
    state         BYTEA NOT NULL,                -- serialized graph state
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, checkpoint_id)
);

-- append-only event log; also the SSE replay source. Partitioned by month.
CREATE TABLE agent_events (
    id           CHAR(26) NOT NULL,
    workspace_id CHAR(26) NOT NULL,
    run_id       CHAR(26) NOT NULL,
    seq          INT NOT NULL,                   -- per-run monotonic, = SSE Last-Event-ID
    type         TEXT NOT NULL,                  -- run.status, agent.started, agent.token, ...
    agent        TEXT,
    payload      JSONB NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, seq, created_at)
) PARTITION BY RANGE (created_at);

-- ===== artifacts ====================================================

CREATE TABLE artifacts (                         -- identity of an artifact within a project
    id           CHAR(26) PRIMARY KEY,
    workspace_id CHAR(26) NOT NULL REFERENCES workspaces(id),
    project_id   CHAR(26) NOT NULL REFERENCES projects(id),
    type         TEXT NOT NULL CHECK (type IN
                 ('requirements','architecture_doc','diagram','tech_stack',
                  'cost_estimate','api_spec','db_schema','design_doc')),
    is_stale     BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (project_id, type)
);

CREATE TABLE artifact_versions (
    id            CHAR(26) PRIMARY KEY,
    workspace_id  CHAR(26) NOT NULL REFERENCES workspaces(id),
    artifact_id   CHAR(26) NOT NULL REFERENCES artifacts(id),
    version       INT NOT NULL,
    content       JSONB NOT NULL,               -- canonical structured content
    rendered_uri  TEXT,                         -- S3 key for large/binary renders
    provenance    JSONB NOT NULL,               -- run_id, agent, model, prompt_version,
                                                -- requirements_version, source (agent|user_edit)
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (artifact_id, version)
);

CREATE TABLE artifact_dependencies (             -- edges of the staleness graph
    artifact_id   CHAR(26) NOT NULL REFERENCES artifacts(id),
    depends_on_id CHAR(26) NOT NULL REFERENCES artifacts(id),
    PRIMARY KEY (artifact_id, depends_on_id)
);

-- ===== knowledge (RAG) ==============================================

CREATE TABLE documents (
    id           CHAR(26) PRIMARY KEY,
    workspace_id CHAR(26) NOT NULL REFERENCES workspaces(id),
    project_id   CHAR(26) REFERENCES projects(id),  -- NULL => platform knowledge base
    filename     TEXT NOT NULL,
    mime_type    TEXT NOT NULL,
    storage_uri  TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','processing','ready','failed')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at   TIMESTAMPTZ
);

CREATE TABLE chunks (
    id           CHAR(26) PRIMARY KEY,
    workspace_id CHAR(26) NOT NULL,
    document_id  CHAR(26) NOT NULL REFERENCES documents(id),
    project_id   CHAR(26),
    ordinal      INT NOT NULL,
    text         TEXT NOT NULL,
    embedding    vector(1536) NOT NULL,
    tsv          TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);
CREATE INDEX idx_chunks_vec ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_chunks_tsv ON chunks USING gin (tsv);
CREATE INDEX idx_chunks_scope ON chunks (workspace_id, project_id);

-- ===== integrations (MCP & LLM) =====================================

CREATE TABLE mcp_servers (
    id            CHAR(26) PRIMARY KEY,
    workspace_id  CHAR(26) NOT NULL REFERENCES workspaces(id),
    name          TEXT NOT NULL,
    transport     TEXT NOT NULL CHECK (transport IN ('streamable_http','stdio')),
    endpoint      TEXT,                          -- URL for http; image ref for stdio-in-sandbox
    trust         TEXT NOT NULL DEFAULT 'untrusted'
                  CHECK (trust IN ('untrusted','trusted_read')),
    tool_allowlist TEXT[] NOT NULL DEFAULT '{}', -- empty = nothing allowed
    credential_id CHAR(26),                      -- -> credentials
    status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled')),
    created_by    CHAR(26) NOT NULL REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, name)
);

CREATE TABLE credentials (                       -- envelope-encrypted secrets (MCP, BYOK)
    id            CHAR(26) PRIMARY KEY,
    workspace_id  CHAR(26) NOT NULL REFERENCES workspaces(id),
    kind          TEXT NOT NULL,                 -- 'mcp_token','llm_api_key','oauth_refresh'
    provider      TEXT NOT NULL,
    ciphertext    BYTEA NOT NULL,                -- AES-256-GCM, per-workspace DEK
    key_version   INT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    rotated_at    TIMESTAMPTZ
);

CREATE TABLE tool_invocations (                  -- every MCP tool call, audit-grade
    id            CHAR(26) PRIMARY KEY,
    workspace_id  CHAR(26) NOT NULL,
    run_id        CHAR(26) REFERENCES runs(id),
    mcp_server_id CHAR(26) NOT NULL REFERENCES mcp_servers(id),
    tool_name     TEXT NOT NULL,
    arguments     JSONB NOT NULL,
    result        JSONB,
    status        TEXT NOT NULL CHECK (status IN
                  ('proposed','approved','rejected','executing','succeeded','failed')),
    approved_by   CHAR(26) REFERENCES users(id),
    approved_at   TIMESTAMPTZ,
    executed_at   TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ===== metering & audit =============================================

CREATE TABLE llm_usage (                         -- partitioned by month
    id           CHAR(26) NOT NULL,
    workspace_id CHAR(26) NOT NULL,
    run_id       CHAR(26),
    provider     TEXT NOT NULL,
    model        TEXT NOT NULL,
    input_tokens INT NOT NULL,
    output_tokens INT NOT NULL,
    cached_tokens INT NOT NULL DEFAULT 0,
    cost_usd     NUMERIC(10,6) NOT NULL,
    byok         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

CREATE TABLE audit_log (
    id           CHAR(26) PRIMARY KEY,
    workspace_id CHAR(26) NOT NULL,
    actor        TEXT NOT NULL,                  -- 'user:<id>' | 'system' | 'agent:<name>'
    action       TEXT NOT NULL,                  -- 'project.created','mcp.tool.approved',...
    target       TEXT,
    metadata     JSONB NOT NULL DEFAULT '{}',
    ip           INET,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- transactional outbox for reliable event publication
CREATE TABLE outbox (
    id           CHAR(26) PRIMARY KEY,
    topic        TEXT NOT NULL,
    payload      JSONB NOT NULL,
    published_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_outbox_pending ON outbox (created_at) WHERE published_at IS NULL;
```

## Row-Level Security (pattern, applied to every tenant table)

```sql
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON projects
    USING (workspace_id = current_setting('app.workspace_id', true));
-- app role has no BYPASSRLS; migrations run as a separate role
```

## Design Notes

- **JSONB for artifact/requirements content:** these are agent-produced documents with evolving
  shapes; versioned Pydantic schemas in code (with `schema_version` inside the JSON) give type
  safety without weekly migrations. Relational columns are reserved for what we query/enforce.
- **`agent_events.seq`** doubles as the SSE `Last-Event-ID`, giving cheap reconnect replay.
- **Vector dimension 1536** is the platform default; if a workspace-selected embedding model
  differs, we normalize via a projection or per-model chunk tables (decision deferred; noted
  in risks).
- **Partitioning** only where volume justifies it (`agent_events`, `llm_usage`); everything else
  stays simple.
- **Migrations:** Alembic; expand/contract only (add nullable → backfill → enforce), so deploys
  are zero-downtime (NFR-10).
