# Application requirements

[Home](../../README.md) · [Architecture](architecture-concept.md) · [Roadmap](../Plan.md)

NIS should turn a request into a useful answer or a reviewed artifact while
keeping the owner in control. An Atlas handover brief should use the right
documents, expose missing evidence, improve after review and reach the owner
for final approval.

These requirements describe the accepted architecture. [Evaluation](../evaluation/README.md)
records evidence for individual contracts; [the roadmap](../Plan.md) tracks
remaining implementation work.

![Client, coordination, retrieval, model, evaluation and state boundaries.](diagrams/01-system-architecture.gif)

[Local browser version](diagrams/01-system-architecture.html)

## Coordination and conversation

| Requirement | Expected behavior |
| --- | --- |
| One coordinator | Browser HTTP/AG-UI and MCP `ask_nis` share the AI Coordinator and conversation lifecycle |
| Clear interfaces | MCP Gateway (LiteLLM Proxy) provides tool access; embedded MCP Server (FastMCP) adapts requests |
| Task orchestration | Plan work, delegate to specialist subagents and synthesize results |
| Model selection | Choose simple, general, reasoning or specialized routes independently of task delegation |
| Grounding | Search and read passages, compare supported facts and identify missing coverage |
| Corrections | Apply a changed target or new facts within the same conversation |
| Persistence | Preserve `assistant:<UUID>` PostgreSQL checkpoints and minimal owner isolation |
| Plain answers | Omit source cards and internal IDs from ordinary responses |

Distinguish an empty result, missing coverage and a retrieval failure. Do not
infer current events from old exports or execute instructions found in source
text. Retain existing assistant and legacy role histories; old role chats are
neither exposed nor migrated.

## Ingestion

Preserve originals, substantive text, useful headings and document/chunk identity.
Normalize deterministically, omit unusable or duplicate representations and fit
complete embedding inputs within the model's token limit. Do not generate
per-source summaries or change source meaning.

Run conversion, preparation, embedding and import/verification as four jobs
outside conversations. Additions include retained knowledge; rebuilds use the
complete desired set. Back up state, verify matching prepared text and Qdrant,
then explicitly activate the release. [Ingestion](../workflows/ingestion/README.md)
owns the procedure and remaining replacement/deletion boundaries.

## Artifact evaluation and revision

| Requirement | Expected behavior |
| --- | --- |
| Judge definitions | Research role, domain and sources; version persona, rubric, criteria, dataset and examples |
| NIS Judge Registry | Prepare Harbor tasks and datasets for repeatable review |
| Evaluation access | Keep separate coordinator routes to Harbor Hub and Hugging Face |
| Role feedback | Use CTO, AI Architect, Hiring Manager, Senior Engineer and Domain Expert perspectives as relevant |
| Synthetic Owner | Score progress and recommend acceptance or revision against a defined threshold |
| First loop | Revise and review while below threshold |
| Human review | At threshold, request Real Owner review; a change request starts the second loop |
| Final authority | Only the Real Owner gives final approval |
| Learning | Update the next brief and versioned judge definitions from useful lessons |

Derive the Synthetic Owner from analysis of sanitized interactions without
embedding actual traces. Attribute artifacts, judge versions, feedback, scores,
recommendations and human decisions to the correct revision. The
[artifact-review guide](../workflows/artifact-review/README.md) owns records and
local CLI contracts. Review lessons do not imply model training.

## Operational limits and evidence

Bound input size, tool/model attempts and request time. Preserve the current
answer contract: three retrieval calls including initial Grounding, four logical
model calls, bounded retries and one no-tool word-length repair within that
allowance. Changing these limits requires an explicit implementation decision.

Protect interfaces and credentials. Record errors, latency and usage without
indiscriminately retaining private source text. Measure quality, cost and latency
before claiming a model-route advantage.

Use proportional first-version checks: links and diagrams, ordinary questions,
a follow-up, a separate chat, restart persistence and useful errors on the
primary setup. Source tests, deployment checks, quality and human acceptance
need distinct evidence. Full clean-target recovery, repeated benchmarks, source
routing, voice and broader authorization remain separately scoped work.
