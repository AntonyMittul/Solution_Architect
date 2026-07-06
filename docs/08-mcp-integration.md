# 08 — MCP Integration Architecture

## 1. Position: We Are an MCP Host

The platform is an **MCP host/client**: our agents consume tools from external MCP servers
(GitHub, Terraform runners, cloud pricing, docs generators, etc.). We deliberately do **not**
build bespoke per-vendor integrations — MCP is the single integration seam, which is what makes
the tool ecosystem extensible without code changes.

(Exposing *our* capabilities as an MCP server for other hosts is a noted future opportunity,
out of scope for v1.)

## 2. Components (`integrations` module)

```
integrations/
├── domain/          # McpServer, ToolDescriptor, ToolInvocation, ProvisioningPlan, TrustLevel
├── application/
│   ├── registry.py      # register/test/discover servers; cache tool catalogs
│   ├── governor.py      # allowlist check, trust check, approval workflow, rate limits
│   └── executor.py      # session lifecycle, invoke, timeout, result normalization
└── infrastructure/
    ├── mcp_client.py    # official `mcp` Python SDK; streamable-HTTP + stdio transports
    └── sandbox.py       # stdio servers run in locked-down containers (see §5)
```

### Registry
- Workspace admins register servers (FS-9). `POST /mcp-servers/{id}/test` performs `initialize`
  + `tools/list`; the discovered catalog is stored and shown to the admin, who then builds the
  **tool allowlist** (default: empty — nothing callable until explicitly allowed).
- Catalog re-discovery on demand and daily; **tool schema changes flag the tool for re-approval**
  (defends against rug-pull attacks where a benign tool's description/behavior changes).

### Governor — every invocation passes through it, no exceptions
1. Server active? Tool on allowlist? Workspace within MCP rate limits?
2. Side-effect classification: tools are classified `read` / `write` at allowlist time by the
   admin (defaulting to `write` = requires approval). `write` tools **always** require a fresh
   per-action human approval (`tool_invocations.status: proposed → approved`). Approvals are
   argument-specific: if the agent changes an argument, re-approval is required.
3. Full audit record for every call (arguments, result, actor, timestamps).

### Executor
- Maintains MCP sessions per (workspace, server) with idle teardown.
- Per-call timeout (default 60s), result size cap, structured error normalization.
- Results are wrapped in provenance envelopes before entering agent context (see §4).

## 3. Provisioning Flow (two-phase, human-gated)

```
user goal ("create repo + CI for this blueprint")
      │
      ▼
provisioner agent  ──►  ProvisioningPlan: ordered list of {server, tool, arguments, rationale}
      │                 (agent has NO execution capability — planning only)
      ▼
plan preview UI  ──►  user approves / rejects (per action or whole plan)
      │
      ▼
executor runs approved actions sequentially; each result recorded;
failure stops the sequence; completed actions reported (no automatic rollback — 
rollback guidance is included in the plan for destructive-capable actions)
      │
      ▼
results (repo URL, issue links, logs) attached to project + audit log
```

The separation "agent plans / governor gates / executor acts" means a prompt-injected agent can
at worst *propose* a malicious action, which lands in front of a human with full arguments shown.

## 4. Security Posture for Tool Results (prompt-injection defense)

Tool results are **untrusted input**. Before entering any agent context they are:
- wrapped in delimited provenance blocks (`<tool_result server="github" trust="untrusted">`),
  with agent system prompts instructing that content inside such blocks is data, never instructions;
- size-capped and stripped of control/invisible characters;
- forbidden from triggering `write` tool calls in the same run step without human approval
  (the governor enforces this structurally — it does not rely on the model behaving).

## 5. Transports & Sandboxing

- **Preferred: streamable HTTP** servers (remote, credentialed) — no local execution.
- **stdio servers** (community servers, local tools) never run on the worker host. They run in
  per-invocation sandbox containers: no network egress by default (explicit egress allowlist per
  server), read-only rootfs, CPU/memory limits, 5-min max lifetime. This contains malicious or
  compromised community servers.
- First-party launch integration: **GitHub MCP server** (streamable HTTP, OAuth). Terraform/IaC
  server in M5 (roadmap).

## 6. Credentials

- Stored in `credentials` (doc 05), envelope-encrypted (per-workspace DEK wrapped by KMS master
  key). Decrypted only in the executor process at call time; never logged, never enters agent
  context or LLM prompts.
- OAuth-based servers use the OAuth flow with refresh-token rotation; PAT-style secrets are
  write-only in the API (can be replaced, never read back).
- Scope guidance surfaced in UI at registration (e.g., "grant repo-scope only").

## 7. Extensibility Contract

Adding a new integration = registering an MCP server + allowlisting tools. Zero backend code.
Platform-bundled "first-party" servers ship as pre-configured registry entries (curated
endpoint, recommended allowlist, scope docs) — still ordinary registry rows, no special-case code.
