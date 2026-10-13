# Application requirements

[Home](../README.md) · [Architecture](Architecture%20Concept.md) · [Roadmap](../Plan.md)

A useful first result is a brief grounded in the selected documents, with the correct target, a clear answer and explicit gaps. This page states desired behavior; the [evaluation index](../evaluation/README.md) identifies the evidence available for it.

The selected 2026-10-02 target is a personal, single-user system with one assistant and new topic chats. Embedded FastMCP exposes one ask tool; LiteLLM provides a gateway to the same interface. Codex is connected first, then OpenClaw. Update all documentation and diagrams before application changes. See [the roadmap](../Plan.md) for progress and later work; source, deployment and conversational acceptance are tracked separately.

## Conversation behavior

| Requirement | Expected outcome | Current boundary |
| --- | --- | --- |
| Search and read | Find and inspect relevant prepared passages | Implemented MCP tools |
| Answer and compare | Explain supported facts, differences and missing evidence | Implemented agent path; quality validation incomplete |
| Clarification and correction | Apply the user's changed target or facts in the same conversation | Multi-turn acceptance remains to validate |
| Persistence | Continue a new thread after ordinary reload or restart | Keep PostgreSQL; old-chat migration is excluded. Full recovery exercises and other hosts are later work |
| Plain answers | Omit source cards and internal IDs from normal answers | Application contract; evaluate independently |
| Shared clients | Codex, then OpenClaw, call the same assistant | One ask tool; direct FastMCP and LiteLLM paths; no enterprise permission model in this single-user slice |

The application should distinguish an empty result, missing source coverage and a failed retrieval request. It should not infer present-day events solely from old exports.

## Knowledge preparation

- Preserve originals and substantive text.
- Normalize deterministically and omit empty, unreadable, duplicate and obvious boilerplate representations from prepared data.
- Keep headings and sections useful for retrieval; do not generate per-source summaries.
- Fit complete embedding inputs within the selected model's token limit.
- Retain document and chunk identity for rebuilding, updates, deletion and debugging.
- Run knowledge updates separately from conversations.

The [manual ingestion workflow](../workflows/ingestion/README.md) defines the intended update behavior. Complete incremental replacement and deletion handling remain work to verify.

## Operational behavior

Bound input size, model/tool attempts and overall request time. Protect service interfaces and distinguish each credential's role. Record errors, latency and model usage without indiscriminately retaining source text in logs.

Use lightweight first-version checks: document links and diagram display, a few ordinary questions, a follow-up, a separate new chat, ordinary restart persistence and a useful error response. Check the primary setup. Full clean-target recovery, repeated benchmarks and other environments remain later work.

## Experimental and future capabilities

Model routing must preserve the model/tool contract and demonstrate acceptable answer quality and cost on the chosen model pool. The present heuristic and report helper do not establish those properties.

Source routing, richer research tools, voice and multi-client authorization remain scoped extensions. Their adoption rationale belongs in [Decisions](../Decisions.md), not in the baseline feature list.
