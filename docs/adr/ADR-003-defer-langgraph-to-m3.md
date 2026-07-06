# ADR-003 — Defer LangGraph to the M3 blueprint graph; intake uses a hand-rolled orchestrator

**Status:** Accepted (M2)
**Relates to:** doc 07 (agent architecture), doc 04 §4.2 (human-in-the-loop pause/resume)

## Context

Doc 07 specifies LangGraph for orchestration control flow, including the intake graph. The M2
intake flow is, in practice, a **linear loop with one agent and a human pause**: analyst →
(needs_input) → resume → … → complete, capped at N rounds.

We already have, from M0/M1, the run machinery LangGraph would otherwise provide the glue for:
a run state machine (`queued → running → needs_input → completed`), a durable event log with
SSE + `Last-Event-ID` replay, an at-least-once job queue with idempotent redelivery, and a
kind-dispatched executor registry.

## Decision

Implement M2 intake with a **hand-rolled `IntakeExecutor`** over the existing run machinery
rather than adopting LangGraph now. Introduce **LangGraph in M3**, where the blueprint run needs
what LangGraph is actually good at: parallel fan-out (diagram / tech-stack / api→db in parallel),
conditional routing (the design-reviewer repair loop), and checkpointed graph state.

## Rationale

- The intake flow has no parallelism and one branch point; a graph framework would add
  indirection without removing complexity.
- Fewer moving parts in M2 means the flow is fully unit- and component-testable (it is: the
  executor is driven directly in tests, and end-to-end through the real worker in a smoke test).
- The `RunExecutor` seam means M3 can add a `LangGraphBlueprintExecutor` as just another
  registered executor — intake and ping are unaffected.
- Resumability, the main thing LangGraph checkpointing buys, is already handled: the run pauses
  at `needs_input`, persists, and any worker resumes it.

## Consequences

- **M3 must introduce LangGraph** for the blueprint graph; that is where checkpointing of
  in-graph state (mid-fan-out) genuinely matters and where `run_checkpoints` (doc 05) gets built.
- If intake later grows parallel steps (e.g. retrieval + analysis concurrently), revisit and
  fold it into the LangGraph runtime too.
