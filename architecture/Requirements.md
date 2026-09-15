# Application requirements

[Home](../README.md) · [Architecture](Architecture%20Concept.md) · [Roadmap](../Plan.md)

A useful first result is a brief grounded in the selected documents, with the correct target, a clear answer and explicit gaps. This page states desired behavior; the [evaluation index](../evaluation/README.md) identifies the evidence available for it.

## Conversation behavior

| Requirement | Expected outcome | Current boundary |
| --- | --- | --- |
| Search and read | Find and inspect relevant prepared passages | Implemented MCP tools |
| Answer and compare | Explain supported facts, differences and missing evidence | Implemented agent path; quality validation incomplete |
| Clarification and correction | Apply the user's changed target or facts in the same conversation | Multi-turn acceptance remains to validate |
| Persistence | Continue a thread after reload or restart | Verified in isolated ARM Linux trial: restart and fresh-volume restore preserved exact messages; other hosts and crash behavior remain to test |
| Plain answers | Omit source cards and internal IDs from normal answers | Application contract; evaluate independently |
| Shared clients | Equivalent-permission clients use the same knowledge | Additional-client integration and permission model remain open |

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

Verify recovery using a clean target, including document reads and conversations. Same-host health checks alone do not establish backup restoration or service capacity.

## Experimental and future capabilities

Model routing must preserve the model/tool contract and demonstrate acceptable answer quality and cost on the chosen model pool. The present heuristic and report helper do not establish those properties.

Source routing, richer research, specialist roles, voice and multi-client authorization remain scoped extensions. Their adoption rationale belongs in [Technology Choices](Technology%20Options.md), not in the baseline feature list.
