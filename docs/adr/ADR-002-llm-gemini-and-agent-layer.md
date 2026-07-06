# ADR-002 — Single Gemini provider behind an LLMService port; thin typed agents instead of PydanticAI

**Status:** Accepted (M2)
**Supersedes:** the provider/agent choices sketched in doc 07 (which named Anthropic/OpenAI adapters and PydanticAI)

## Context

The product standardized on **Google Gemini (`gemini-3.1-flash-lite`)** as the sole LLM provider;
Anthropic and OpenAI are no longer in scope. Doc 07 also specified PydanticAI for individual
agents, layered above our own `LLMService` port.

## Decision

1. **One provider, behind a port.** We keep the provider abstraction (`LLMProvider` port +
   `StructuredLLM` service) exactly as the architecture intended — the port is what makes
   provider choice a one-adapter concern — and implement a single **Gemini adapter**. The model
   id is config-driven (`AISA_LLM_MODEL_QUALITY` / `_FAST`), so a Gemini version bump or a future
   second provider is a config/adapter change, not a code change in agents.

2. **Drop PydanticAI in favor of a thin in-house typed-agent layer.** Agents (e.g.
   `RequirementsAnalyst`) are plain classes that call `StructuredLLM.complete(schema=...)`, which
   returns a validated Pydantic model and runs the validation-retry loop. With a single provider,
   PydanticAI would be a second abstraction over our own port with no added benefit; the typed
   output + retry it provides, we already provide at the port.

## Consequences

- **Kept:** typed agent I/O (Pydantic schemas), validation-with-retry, token accounting, prompt
  versioning in-repo — the properties doc 07 actually cared about.
- **Simpler dependency graph:** no PydanticAI; `google-genai` is the only LLM dep.
- **Reversible:** if we later want multiple providers or PydanticAI's model router, the port
  boundary means agents don't change — only the adapter/service layer does.
- **Structured output** uses Gemini's native `response_schema` + `response_mime_type=application/json`.
- A deterministic **fake provider** (including a schema-valid auto mode) makes the entire app
  runnable and CI-testable without a key or network.
