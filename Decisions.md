# Architecture decisions

[Home](README.md) · [Architecture](architecture/architecture-concept.md) · [Roadmap](Plan.md)

This page owns the current accepted design. For example, a client asks about the Atlas release and continues with the returned conversation UUID. Dated deployment evidence lives in [deployment status](setup/private-deployment/STATUS.md); superseded choices remain in Git history.

![The system boundaries behind these decisions.](architecture/diagrams/01-system-architecture.gif)

[Local browser version](architecture/diagrams/01-system-architecture.html)

## Selected target: one assistant with a gateway-backed MCP entrance

**Accepted 2026-10-02; cleanup expanded 2026-10-06.** One NIS assistant handles separate topic conversations. Research, knowledge questions and interview analysis are tasks for that assistant, not separately selectable runtimes. Remove obsolete role configuration, role-specific interfaces and context-transfer machinery.

The source gateway reference path is `client → LiteLLM MCP Gateway → embedded FastMCP → NIS runtime`. The dated deployment record owns the enabled installation path. Direct clients use the same FastMCP server. The tool contract remains `ask_nis(question, thread_id=None)`, returning a plain answer and its UUID. HTTP, AG-UI and MCP share the same operation and application lifecycle; the embedded adapter adds no loopback model request. LiteLLM supplies the gateway rather than replacing the incumbent model selector.

NIS retains OSS Deep Agents/LangGraph, automatic model selection and PostgreSQL checkpoints. New topic chats use `assistant:<UUID>` internally and public UUIDs externally. Existing assistant chats continue; old role chats are neither migrated nor exposed through the assistant. Stored history is retained, with minimal ownership checks preventing old role UUIDs from being reused as assistant UUIDs. No destructive database migration is selected.

This is a private single-user system. One Coordination process owns execution and conversation lifecycle; there is no additional custom outer coordinator. The gateway adds a process and network hop, so no measured cost or latency saving is claimed. History/status MCP tools, streaming MCP and other gateway integrations remain future work.

## Inference routing boundaries

The configured NIS RAG Cloud route supplies the answer-inference default. Explicit client alternatives are native OpenAI, Ollama Cloud, and Ollama Local. Fireworks is a legacy, credential-empty option; Hermes is excluded from harness application inference, execution and review. The selector meets the task's required quality before comparing configured cost/latency assumptions. These assumptions require measurement; selecting a route does not establish answer quality.

The private LiteLLM gateway also supplies an explicit client inference alias and
read-only Retrieval/public-web MCP namespaces. Public web lookup reuses the
existing Ollama credential; it does not add a tool to the NIS conversation graph
or alter that graph's request bounds. The pinned gateway compatibility adapter
retains mixed reasoning/text channels and independent Ollama function-call IDs
and indexes. Gateway restarts never synchronize a LiteLLM schema against the
shared NIS database. The [routing guide](setup/model-routing.md) owns this client
configuration, and [deployment status](setup/private-deployment/STATUS.md) owns
fresh-session/default-selection evidence.

Keep the accepted request bounds: three retrieval calls including initial Grounding, four logical model calls, bounded provider retries, and one no-tool word-length repair within that model allowance. Source text remains reference material rather than executable instructions.

## Manual ingestion outside conversations

Knowledge updates are explicitly operator-triggered and independent of conversations. Four temporary jobs perform conversion, deterministic preparation, embedding, and import/verification. Shared BGE serves both query and document encoding. Original documents and substantive text survive preparation; no per-source LLM summaries or meaning rewrites are generated.

Additions require assembly with the retained corpus before import. A full rebuild requires the complete desired source set. Prepared full text and the matching Qdrant collection form one release; search and read within an answer pin that release together. A literal Retrieval release pin requires an explicit deployment change; advancing a pointer alone does not change it.

The ordinary operator procedure starts with PostgreSQL and Qdrant backups plus a matching prepared-document/configuration copy, then prepares, imports/verifies, activates and checks answers. No routine rollback branch is required. A failed acceptance check leaves the update incomplete for investigation. See [the checklist](workflows/ingestion/knowledge-base-update-checklist.md) and [technical contracts](workflows/ingestion/README.md).

Prepared documents currently use the local retained-release deployment. A dedicated GCS bucket and generation-conditional activation pointer remain the selected future cutover, not a verified live refresh.

## Service and storage boundaries

UI, Coordination, LiteLLM gateway, Retrieval MCP, shared BGE, Qdrant and PostgreSQL are separate persistent services. The four ingestion workers are temporary jobs. Qdrant stores a rebuildable search index; PostgreSQL stores conversations; prepared full text lives outside both databases. Database volumes are not object-storage mounts. [Container guidance](setup/containers/README.md) owns images, mounts and entrypoints.

## Documentation, verification and publication

Maintain each diagram as editable HTML with inline SVG plus its derived GIF. Keep detailed explanations in interactive nodes and visible labels understandable without interaction. Publish only allowlisted source, synthetic examples and portable guidance; credentials, corpus data and private traces remain outside publication.

Validate source and diagrams before rollout. Back up state before changing the running candidate and verify existing assistant continuity, new conversations and affected client behavior afterward. Keep source checks, live deployment and final conversational acceptance distinct. Representative quality measurement, full clean-target restoration and other host variants remain later work in the roadmap.

## Artifact review as a separate workflow

[Artifact evaluation and revision](workflows/artifact-review/README.md) is an
owner-directed workflow alongside knowledge ingestion. Frozen artifacts and
task-specific criteria feed reviews; owner decisions determine revisions and
delivery. Retrieval relevance and artifact quality remain separate measures.
This adds no background review loop or conversation/ingestion trigger.
