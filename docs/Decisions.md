# Architecture decisions

[Home](../README.md) · [Architecture](architecture/architecture-concept.md) · [Roadmap](Plan.md)

This page records accepted design choices and the contracts they preserve.
For example, an Atlas briefing can be drafted, reviewed by role-based judges,
revised and sent to its owner for approval. The dated
[deployment record](setup/private-deployment/STATUS.md) owns installation facts.

![NIS component boundaries behind the accepted design.](architecture/diagrams/01-system-architecture.gif)

[Local browser version](architecture/diagrams/01-system-architecture.html)

## Problems, choices and consequences

The design starts with two constraints: useful knowledge outlives a conversation,
and each model request has a finite context window. A larger prompt alone does
not provide a maintained knowledge store. The Knowledge Backbone preserves
prepared source text and a searchable index outside model context; Retrieval MCP
selects and reads relevant passages for the current task. Each request still
uses a bounded context, while the retained knowledge can grow independently.

| Problem / constraint | Choice and mechanism | Alternative and consequence |
| --- | --- | --- |
| Knowledge must survive chats and exceed what fits in one request | Keep prepared full text and a searchable Qdrant index in the Knowledge Backbone; Retrieval MCP searches and reads selected passages | Reattaching the corpus or relying on chat history consumes the context window and makes reuse depend on each client. Retrieval adds preparation, indexing and relevance evaluation, and can miss useful evidence |
| A task can require retrieval, model calls, specialist work and result synthesis | One AI Coordinator owns the task lifecycle, delegates work and combines results behind shared browser/MCP operations | Independent client or specialist runtimes duplicate state and orchestration rules. Shared coordination needs explicit budgets, checkpoint ownership and failure handling |
| Clients need knowledge tools without owning storage and embedding details | Retrieval MCP exposes bounded search/read operations and owns query encoding plus index/source access | Direct storage access couples every client to Qdrant, model configuration and release selection. The service boundary adds a hop and requires coordinated source/index activation |
| Ingestion and search must use compatible embeddings | Share BGE and its pinned configuration for document and query encoding | Separately managed encoders can drift. A shared service needs admission control so batch work leaves capacity for interactive queries |
| Knowledge changes must be inspectable and activated as a matching text/index release | Run ingestion outside conversations as four jobs; verify before activation | Query-triggered updates mix long-running writes with answer latency. Controlled ingestion leaves an explicit freshness and activation procedure for the operator |
| Agent work needs a bounded failure and resource envelope | Limit retrieval/model calls, retries and answer repair | An open-ended loop can keep searching or revising. Strict limits can leave an answer incomplete, so missing evidence and failures must remain explicit |
| Judge feedback must improve an artifact while preserving owner authority | Aggregate judge feedback, use Synthetic Owner scoring to qualify review, then require Real Owner approval | Automatic final acceptance removes the owner's decision. Human approval adds review latency; synthetic scores need calibration and can disagree with the owner |

The alternatives explain the design choices; measured quality, latency and cost
belong in the owning evaluation records. Detailed contracts remain below and in
the linked workflow/service guides.

## One coordinator and clear interfaces

**Accepted 2026-10-02; cleanup expanded 2026-10-06; design expanded 2026-10-25.**
NIS is one AI agent harness with one AI Coordinator and separate topic
conversations. The Coordination Layer is the logical grouping of that
coordinator and its interfaces. The Coordination service is the concrete
process that hosts Deep Agents/LangGraph and the embedded MCP Server.

The AI Coordinator plans, routes and delegates focused work to specialist
subagents, selects model routes and synthesizes results. Specialist and judge
roles describe work within the harness; they do not restore obsolete
role-specific chat runtimes or context-transfer machinery. There is no second
custom outer agent loop.

Browser CopilotKit HTTP/AG-UI and MCP reach the same operation. The MCP client
path is `client → MCP Gateway (LiteLLM Proxy) → MCP Server (FastMCP) → AI Coordinator`.
The gateway provides tool access; the embedded server exposes
`ask_nis(question, thread_id=None)`, returning a plain answer and its UUID.
Direct MCP clients use the same server without a loopback inference request.
The selected installation path belongs to the deployment record.

NIS remains private and single-user. Existing assistant chats continue with
`assistant:<UUID>` internally and public UUIDs externally. Legacy role history
is retained but neither exposed nor migrated; minimal ownership checks prevent
its UUIDs from becoming assistant UUIDs. No destructive database migration is
selected. An extra gateway hop establishes no measured cost or latency benefit.
History/status tools, streaming MCP and broader authorization remain separately
scoped extensions.

## Task orchestration and model routes

**Accepted 2026-10-25.** Orchestration assigns tasks and combines results;
model selection chooses inference for each step. Keep these decisions separate.
Use simple, general, reasoning and specialized routes according to capability.
Ollama and Fireworks are model backends; DeepSeek is a model family, not a fixed
provider. A specialized route may use Fireworks.

Meet required quality before comparing configured cost and latency assumptions.
Do not claim provider parity, savings or quality from route selection alone.
Client inference choice remains separate from application selection. Hermes
remains excluded from harness inference, execution and review.

[Model routing](setup/model-routing.md) owns adapter configuration, credential
availability, fallback and historical gateway evidence. Earlier routing records
describe Fireworks as a credential-empty legacy option; that deployment state
does not restrict the accepted design's specialized route. Preserve mixed
reasoning/text compatibility and independent function-call IDs/indexes when
changing the gateway. Never synchronize a gateway schema against the shared
NIS conversation database.

Preserve the answer contract: three retrieval calls including initial Grounding,
four logical model calls, bounded provider retries and one no-tool word-length
repair within that model allowance. Public-web client tools do not silently
alter the conversation graph or its budgets. Source text is reference material.

## Ingestion and state

Ingestion is operator-triggered and separate from conversations. Four temporary
jobs convert, prepare, embed and import/verify. Shared BGE encodes documents and
queries. Preserve originals and substantive text without generated per-source
summaries or meaning rewrites.

Additions assemble with retained knowledge; rebuilds use the complete desired
set. Prepared full text and the matching Qdrant collection form one release,
pinned together for search and read. A literal Retrieval release pin requires an
explicit deployment change; advancing a pointer alone does not change it.

The ordinary procedure starts with PostgreSQL/Qdrant backups and matching
prepared-document/configuration copies, then prepares, imports/verifies,
activates and checks answers. A failed acceptance check leaves the update
incomplete for investigation; no routine rollback branch is required. The
[checklist](workflows/ingestion/knowledge-base-update-checklist.md) and
[ingestion guide](workflows/ingestion/README.md) own the procedure.

Qdrant stores a rebuildable index, PostgreSQL stores checkpoints, and prepared
full text lives outside both. Database volumes are not object-storage mounts.
Local releases and generation-pinned GCS releases are supported boundaries;
the deployment record owns activation state. The earlier local-release/GCS-future
description is historical. [Container guidance](setup/containers/README.md)
owns images, mounts and entrypoints.

## Role-based evaluation and human approval

**Accepted 2026-10-25.** Artifact evaluation and revision is the third harness
workflow alongside question answering and Ingestion. Research into roles,
domains and sources produces versioned persona, rubric, criteria, dataset and
examples. Prepared Harbor tasks/datasets form the NIS Judge Registry.

The coordinator has separate routes to Harbor Hub and Hugging Face. Harbor does
not call Hugging Face in this design. Review roles are CTO, AI Architect,
Hiring Manager, Senior Engineer, Domain Expert and Synthetic Owner. They produce
feedback rather than final authority.

The Synthetic Owner uses analysis of sanitized owner interactions, without
actual traces in judge definitions. It scores progress and gives an accept/reject
recommendation. Below threshold, revision and review repeat. At threshold, the
Real Owner reviews the artifact and can approve it or request changes, creating
the second loop. Human approval is final. Lessons update the next brief and
judge definitions rather than automatically training models.

The [artifact-review guide](workflows/artifact-review/README.md) owns review
records and the local saved-response CLI. Retrieval relevance and artifact
quality remain separate measures. Invoking this workflow does not create a
background conversation or ingestion trigger.

## Documentation, verification and publication

Maintain editable HTML diagrams with inline SVG and matching GIF exports.
Keep visible labels short and detailed explanations in interactive nodes.
Publish only allowlisted source, synthetic examples and portable guidance;
credentials, corpus data and private traces remain excluded.

Validate source and diagrams before rollout. Back up state before a service
change and check existing assistant continuity, new conversations and affected
clients afterward. Source checks, deployment and owner acceptance are distinct.
Representative quality and full clean-target recovery remain roadmap work.
