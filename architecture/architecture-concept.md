# Architecture

[Home](../README.md) · [Requirements](Requirements.md) · [References](Research%20and%20Design%20Inputs.md) · [Services](../setup/containers/README.md)

Nora separates conversation handling from knowledge retrieval and document preparation. A user asks one question; a shared retrieval service finds passages; an agent produces a plain answer and retains the conversation.

## Worked example

“Prepare a brief for the Atlas project handover.” The assistant should establish which project or handover the user means, retrieve relevant decisions and notes, and explain supported points and gaps. Exported documents are dated snapshots, so a saved calendar item alone cannot establish a current meeting.

## Single-assistant architecture

One NIS assistant handles separate topic chats. Browser AG-UI and the embedded FastMCP tool reach the same Coordination operation. The source includes a separate LiteLLM gateway and a direct FastMCP entrance. The deployment record owns the enabled client path. Model selection, OSS Deep Agents/LangGraph and PostgreSQL checkpoints stay inside NIS. [Decisions](../Decisions.md) owns the accepted choices; [deployment status](../setup/private-deployment/STATUS.md) owns dated acceptance and open quality checks.

## Accepted target view

![One-assistant NIS architecture](diagrams/01-system-architecture.gif)

[Local browser version](diagrams/01-system-architecture.html) · [All diagrams](diagrams/README.md)

UI, Coordination, gateway, Retrieval, shared BGE, Qdrant and PostgreSQL have separate service boundaries. Conversion, preparation, embedding and import are temporary operator-triggered jobs. Prepared text can use a local release or generation-pinned GCS objects; the deployment guide owns the selected installation.

Knowledge updates do not run inside conversations. Additions are assembled with retained knowledge; rebuilds use the complete desired inputs. Back up state, import and verify the complete release, explicitly activate Retrieval, then check answers. The [operator checklist](../workflows/ingestion/knowledge-base-update-checklist.md) owns that procedure and the [technical guide](../workflows/ingestion/README.md) owns artifacts and activation contracts.

## Artifact evaluation and revision

[Artifact review](../workflows/artifact-review/README.md) is an owner-directed
workflow alongside knowledge ingestion and conversational question answering.
Frozen artifacts, sources and criteria feed judge reviews; owner decisions lead
to a revised artifact or retention, while useful lessons inform the next brief.
Harbor Hub is a task-execution option and Fireworks/Hugging Face are inference
options. The local CLI validates saved responses and records explicit decisions.
See the [workflow map](diagrams/README.md#harness-workflows) for its place in the
harness. It does not run automatically inside a conversation or ingestion job.

## One request

![Architecture request path](diagrams/architecture-request-path.gif)

[Local browser version](diagrams/architecture-request-path.html)

The diagram summarizes the accepted one-assistant request path, with query encoding supplied by shared BGE. The agent can make additional bounded knowledge calls; [the full conversation diagram](diagrams/02-question-to-answer.html) shows document reads and the optional tool cycle. Ingestion is separate and does not run in this sequence.

## Responsibilities

| Component | Owns |
| --- | --- |
| Interaction | CopilotKit browser UI, application-server routes and AG-UI messages/events |
| NIS assistant runtime | Coordination with its OSS Deep Agent, model calls, bounded context, tools and conversation lifecycle |
| Shared Retrieval MCP | MCP `search`/`read`, calls to BGE for query encoding, Qdrant search and prepared-document reads |
| Shared BGE server | Query and document encoding; admission control for interactive and batch callers |
| Four document-processing jobs | Manual conversion, deterministic preparation, batch embedding and index import/update |
| Qdrant | Dense and lexical search index with internal document metadata |
| PostgreSQL | LangGraph conversation checkpoints |

Deep Agents is the harness, LangChain supplies model/tool abstractions, and LangGraph supplies execution and state machinery. These libraries run together inside Coordination. Coordination does not wrap the Deep Agent in a second custom agent loop.

## Technology foundation

| Responsibility | Selected technology |
| --- | --- |
| Agent execution and checkpoints | OSS Deep Agents, LangChain and LangGraph |
| Browser interaction | CopilotKit and AG-UI |
| Document conversion and preparation | Docling plus deterministic readers |
| Embeddings and retrieval | BGE, Qdrant dense search and hashed lexical fusion |
| Conversation persistence | PostgreSQL |
| Answer inference | Configured application model adapters; see model routing |
| Prepared documents | Local directory or generation-pinned GCS objects |

Versions are pinned in the Python and UI lockfiles. The current stack is selected; alternatives and historical rationale remain in [Decisions](../Decisions.md), while external references are listed in [References](Research%20and%20Design%20Inputs.md).

## Deployment boundaries

Coordination contains the assistant and its Deep Agent together. UI, Retrieval MCP, BGE, Qdrant and PostgreSQL are separate services. Four ingestion jobs run only on an operator command and exchange durable artifacts outside conversations. There is no separate custom outer coordinator.

The same source package supplies several independent containers. Host placement can change without changing these ownership boundaries. Qdrant holds the rebuildable search index, PostgreSQL holds conversation state and prepared documents use the configured local/GCS store; database volumes are not object-storage mounts.

## Storage roles

Original files remain in operator-controlled storage. The shared store reads a local document directory or generation-pinned GCS objects. Qdrant is the rebuildable search index, and PostgreSQL holds conversation state. Neither database uses an object-storage mount for live files.

The [data contract](../data/Data%20Contract.md) owns document identity and prepared artifacts. The [service inventory](../setup/containers/README.md) owns packaging and network details.

## Retrieval and answer behavior

The shared implementation combines dense BGE retrieval with a hashed lexical representation and reciprocal-rank fusion. It deduplicates results by document. The earlier local BM25 experiment is a separate implementation and dataset.

Coordination performs an initial knowledge search for each turn. Its tools allow additional search and document reads. Source text is reference material, not instructions to execute. Normal answers omit citation cards and internal IDs; those IDs remain available internally for maintenance and evaluation.

Plain-answer formatting is an application choice, not evidence that an answer is grounded. Correctness, missing-evidence behavior and context selection need their own tests.

## Conversation state and recovery

The implementation uses the official LangGraph PostgreSQL checkpointer and stable thread identifiers. Browser history and checkpoints are different stores. Checkpoint persistence does not by itself demonstrate clean-target restoration, crash behavior or exactly-once effects.

Read the dated [deployment status](../setup/private-deployment/STATUS.md) and [multi-turn evaluation plan](../evaluation/Multi-turn%20Evaluation.md) for what is measured and what remains open.

## Model routing

Coordination selects among its configured application models. A client such as Codex separately selects its own inference route; that choice does not replace the application selector. Supported adapters and enabled deployment routes are different inventories. [Model routing](../setup/model-routing.md) owns the configuration reference; the dated [deployment record](../setup/private-deployment/STATUS.md) owns installation state.

## Additional MCP clients

Nora's Coordination service uses Retrieval MCP today. Another MCP-capable client can reuse the same prepared knowledge after its private route, bearer credential, initialization, `search`, bounded `read`, errors and timeouts are verified. This integration does not grant direct database or ingestion access and does not make the client the owner of Nora's conversation runtime. The current shared bearer boundary does not provide per-user source authorization.

## Future extensions

Source-specific routing, bounded query refinement, richer research loops, voice and broader multi-client authorization remain candidates. Add one only when current evaluation demonstrates a concrete gap and the extension has an explicit tool, state, permission and recovery boundary. LangSmith and Studio may support development and evaluation after their retention and connectivity are configured; they are not application hosting requirements.

## Source layout

Executable application code lives in one `src/nora/` package and one `ui/`. Root Compose and `deploy/` own current packaging, including assistant configuration, the shared BGE API and four job entrypoints with their container definitions.

[Assistant behavior](../agents/README.md) owns conversational expectations. A container is not necessarily an agent.
