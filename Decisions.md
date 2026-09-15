# Architecture decisions

[Home](README.md) · [Architecture](architecture/Architecture%20Concept.md) · [Roadmap](Plan.md)

This is the public summary of Nora's accepted architecture. It describes choices and rationale, not deployment proof. The complete owner-specific decision history is preserved separately; historical record numbers below provide continuity with implementation comments.

## Current inference providers

**Recorded 2026-09-14T16:32:06-04:00.** The owner removed Hermes from the Nora delivery plan. Use Ollama Cloud and Fireworks.ai as model providers; optional local Ollama remains supported by the selected design. Nora keeps model routing, tool execution and conversation checkpoints inside each role runtime.

Hermes is not an active provider, delivery blocker or deferred requirement. This supersedes the Hermes portions of D169–D171 and the later clarification proposing Hermes as a model provider. Earlier records below preserve the decision history; the provider set in this section is authoritative for the current plan.

## Per-role runtime containers, checkpoint ownership and automatic provider routing

**D172, recorded 2026-09-14T14:59:41-04:00.** Implement the accepted D169/D170 role-runtime slice in the frozen base: Research Assistant and Interview Analyst runtimes, role-owned chats, PostgreSQL checkpoint namespacing, explicit user-reviewed context transfer, and automatic quality-first model routing across Ollama Cloud and Fireworks.ai. Keep the existing `coordination` service as a backward-compatible Knowledge Assistant alias.

- **Role construction and ownership:** `nora.roles` defines Knowledge, Research and Interview configurations with distinct system prompts and a shared tool set. Each runtime loads its role from `NORA_ROLE`. `role_thread_id(role, uuid)` namespaces checkpoints inside PostgreSQL, and `nora.ownership` maintains a global thread-ownership table so a client-visible UUID claimed by one role is rejected by other roles on ask, read, resume and transfer.
- **Checkpoint compatibility and migration:** Existing un-namespaced Knowledge checkpoints are recognized as `knowledge:<uuid>` for compatibility. No destructive schema migration is required.
- **UI selector, history and resume:** The UI stores a selected role and per-role thread IDs. AG-UI and history endpoints include the role. Cross-role requests are denied at the runtime. A `/transfer` endpoint returns a deterministic, user-reviewable summary of selected source messages; the target chat only receives the summary when the user posts it.
- **Automatic provider routing:** Each runtime builds a role-specific model inventory from conservative defaults or `NORA_<ROLE>_MODELS`. The selector filters by required quality/capability, then sorts by weighted cost/latency assumptions. Fallback occurs once, only before any output chunk is emitted, and decision logs contain SHA-256 query hashes only.
- **Provider adapters:** Ollama Cloud uses the native protocol via `ChatOllama`. Fireworks.ai uses the verified OpenAI-compatible endpoint via `langchain-openai`. Optional local Ollama uses the same native protocol via `ChatOllama` against a configurable endpoint.
- **Shared contracts preserved:** `KnowledgeClient.pinned()`, `X-Nora-Release`, shared BGE, Retrieval MCP, ingestion jobs and activation remain unchanged. Role patches are Compose additions against the frozen base.

## Current priority: cleanup first, then implementation, then rollout

**D170, recorded 2026-09-14T10:39:31-04:00.** The owner ordered the remaining work in three stages:

1. **GitHub-ready cleanup and review first.** Complete publishable documentation, diagrams and source checks before starting implementation.
2. **Accepted implementation second.** Build the selected target architecture: per-role runtime containers, shared BGE server, four manual ingestion job containers, dedicated GCS prepared-document bucket, automatic balanced routing across Ollama Cloud / Hermes Cloud Gateway / Fireworks.ai, and role/thread checkpoint isolation.
3. **Controlled rollout third.** Verify a clean installation, exercise representative answer quality, and roll out only after implementation evidence supports it.

This ordering intentionally separates publication readiness from build work and from live deployment.

## Accepted implementation choices from the architecture review

**D169, recorded 2026-09-14T10:05:16-04:00.** The owner selected implementation of the reviewed target, including the role runtimes and automatic model routing. These are accepted requirements; this record does not establish completed implementation or deployment.

- **Prepared documents:** use a dedicated GCS bucket. This selects the GCS branch of D167; original source files remain unchanged.
- **Knowledge releases:** prepare a new logical dataset version containing full documents, chunks, vector/model metadata and its Qdrant collection. Validate the complete version before switching retrieval to it, and retain the previous version for rollback. A failure before activation leaves the active version unchanged. Documents and the search index must advance together as one selected dataset version.
- **Ingestion trigger:** one explicit operator command starts all four job containers in order and automatically performs validation and activation. The manual trigger is retained; the operator does not have to launch each stage separately. Job execution and recovery remain outside conversational Coordination.
- **Conversation isolation:** each role owns separate chats and history. Shared PostgreSQL must preserve role-aware conversation identity and ownership. Necessary context is transferred explicitly rather than exposing one shared conversation to all roles.
- **Model access:** support Ollama, models accessed through Hermes Cloud Gateway, and Fireworks.ai. These are accepted application routes; the owner's access report is not an adapter integration test. Optional local Ollama keeps its own container.
- **Model selection:** automatic routing inside each agent's Coordination/Deep Agent runtime is selected. Assigning one fixed model to each role was not selected. Do not add a separate outer coordinator or assume that routing requires a new container.
- **Routing objective:** balance quality, cost and latency. Meet the task's required quality first, then consider cost and speed among eligible models. Concrete model eligibility, thresholds and evaluation still require implementation and measurement; a keyword heuristic alone does not establish that objective.

This refines D167 and the earlier experimental routing direction. The existing implementation and its tests remain evidence for their exercised behavior only. The [container inventory](setup/containers/README.md), [ingestion workflow](workflows/ingestion/README.md), [role runtime](setup/containers/coordination.md) and [technology choices](architecture/Technology%20Options.md) remain the owning design and implementation references.

## Selected target: separate runtime and job containers

**D167, recorded 2026-09-14T09:35:40-04:00.** Each agent role has its own Docker container containing Coordination and the Deep Agent, including execution and conversation lifecycle. Keep the UI, shared Retrieval MCP, shared BGE server, Qdrant and PostgreSQL in separate containers. Do not add a separate custom outer coordinator.

Knowledge Assistant behavior is implemented in the current Coordination service. Its per-role packaging is the reference for future roles; Research Assistant and Interview Analyst remain planned. All roles use shared MCP search/read and PostgreSQL conversation checkpoints. Role routing and checkpoint isolation still need implementation.

Split manual ingestion into four temporary job containers, in order: Docling conversion; deterministic normalization/chunking; batch embedding; index import/update. Retain intermediate artifacts and independent job results outside the containers. Preserve original documents and substantive text; preparation does not use LLM summaries or rewriting.

Retrieval and the batch embedding worker both call the shared BGE server. Bound batch size and concurrency, apply backpressure, and retain capacity for interactive query encoding. Exact limits and admission-control mechanics require measurement and implementation.

Prepared full documents use GCS through its API or shared filesystem storage. They remain separate from the Qdrant search index and PostgreSQL conversation state. Managed storage and mounted volumes are not containers. Ollama Cloud is the external inference provider; optional local Ollama has its own container.

This supersedes the earlier single global Coordination, inline BGE and combined ingestion packaging as the **target design**. D133's rule against an outer coordinator and D123/D145's manual, deterministic preparation remain. D165's Obsidian-native sources and matching SVG previews also apply to the four architecture diagrams. The [service inventory](setup/containers/README.md) owns boundaries and current gaps; [diagrams](architecture/diagrams/README.md) illustrate them. This decision changes documentation, not application code or deployment.

D169 refines this decision: it selects a dedicated GCS bucket for prepared documents, adds Hermes Cloud Gateway and Fireworks.ai as external inference routes, and accepts Research Assistant and Interview Analyst as implementation scope. The D169 choice is authoritative.



## First complete knowledge-update-to-answer slice

**D171, recorded 2026-09-14T14:23:44-04:00.** In this isolated checkout implement and independently review the first end-to-end slice of the D169 architecture: a persistent shared HTTP BGE service, four distinct temporary manual-ingestion job containers, one host-side launcher, one operator command, coherent activation/rollback and source-level GCS support. This slice deliberately keeps Coordination and the Deep Agent in the existing `coordination` service, does not add a separate outer coordinator, and does not implement per-role runtimes or automatic balanced model routing. Prepared full documents use the local filesystem in development and test; the dedicated GCS bucket remains the selected production storage target and is supported at the source level with a local verification double.

Scope included and verified in this slice (container acceptance completed and source checks recorded at 2026-09-14T14:23:44-04:00; the earlier 14:14:50 and 16:32 timestamps were planning/verification artifacts, not the actual America/New_York recording time of this pass):

1. **Shared HTTP BGE server** (`nora serve bge`): loads the pinned `BAAI/bge-base-en-v1.5` revision once, exposes `/encode` for query and document modes, and applies bounded batch size, outstanding-request concurrency and a small queue with backpressure so batch ingestion cannot starve interactive queries.
2. **Four job entrypoints and distinct containers**: `convert`, `prepare-standalone`, `embed`, and `import-verify`, each with its own Compose service (`job-convert`, `job-prepare`, `job-embed`, `job-import`). Each reads a manifest, validates its inputs, writes completed artifacts to an explicit release directory and records its own job report.
3. **Host-side launcher** (`scripts/knowledge-update`): runs the four containers in order, verifies completed artifacts between stages, stops before activation on any failure and atomically activates the new release by writing a `current` symlink.
4. **One operator command** (`nora knowledge-update <source> <release>`): host-only equivalent that runs the four jobs in order, validates the bundle and atomically activates the new release. In local mode activation writes the `current` symlink; in GCS mode it updates a generation-conditional `gs://bucket/object` cloud pointer. A failed or interrupted run leaves the active pointer/symlink unchanged; the previous release remains readable for rollback through the activation history log or cloud pointer history.
5. **Coherent activation and release pinning**: Retrieval pins both its Qdrant collection and prepared-document directory to the active release. Activation advances documents and the search index together; switching only the index is not allowed. Search and read within one answer turn pin one release via the `X-Nora-Release` header so activation during an answer does not split search from read. In GCS mode Retrieval consumes the authoritative cloud pointer to discover the active manifest and documents.
6. **Source-level GCS support**: publishing release artifacts and generation-conditional cloud pointer activation/rollback reuse the existing document-store interface and Google client dependency. A `FakeGCSClient` double supports local verification; real bucket creation, credentials and upload are not exercised here.
7. **Compose/build updates**: add the `bge` service and four job profiles, wire the BGE URL into Retrieval, add health checks and `NORA_RELEASES_ROOT`, and keep Coordination and the Deep Agent together.

Honest status of remaining target items (the first slice is now source-implemented and container-accepted; the following remain accepted implementation scope, not newly deferred future candidates):

- Per-role runtime containers and UI routing for Research Assistant and Interview Analyst.
- Role/thread checkpoint isolation in PostgreSQL.
- Automatic balanced model routing across Ollama Cloud, Hermes Cloud Gateway and Fireworks.ai (the existing optional keyword/length router remains experimental).
- Real deployment of the dedicated GCS prepared-document bucket and a controlled clean-install rollout.
## 1. One agent inside Coordination

**D128, D133.** Use OSS Deep Agents with LangChain and LangGraph underneath. Coordination hosts that agent and its conversation lifecycle. Avoid adding a second custom outer agent loop.

The public implementation is in `src/nora/agent.py` and `src/nora/coordination.py`. Specialist role implementations are accepted implementation scope after repository preparation; D167 selects a separate runtime container for each role.

## 2. Shared knowledge through MCP

**D136.** Expose `search` and `read` through an independent Retrieval service. The agent and future clients share that boundary instead of maintaining duplicate indexes. Per-client authorization and cross-client integration still need validation.

MCP is a tool interface. It does not replace a scheduler, queue, ingestion transport or conversation checkpoint store.

## 3. Manual ingestion outside conversations

**D123, D126–D127.** An operator selects and runs knowledge updates. User questions do not trigger ingestion, and Coordination does not own ingestion job state.

**D145.** Prepare sources deterministically. Preserve originals and substantive text; omit unusable content, exact duplicates and obvious boilerplate from prepared data. Do not generate one summary or context document per source.

## 4. Separate storage responsibilities

**D108, D134–D135, D154.** Original archives, prepared text, the search index and conversation checkpoints have different lifecycles.

- Original files remain in operator-controlled storage.
- The shared document-store interface reads local prepared files or generation-pinned GCS objects.
- Qdrant holds the rebuildable dense and lexical index.
- PostgreSQL holds LangGraph conversation checkpoints.

## 5. Plain answers with internal evidence

**D145.** Normal answers omit citation cards, source links and internal IDs. Retrieval still retains text and document identity for evaluation, debugging, updates and deletion handling. Missing evidence should lead to an explained gap or clarification.

## 6. Selected runtime components

**D67, D117, D128, D154.** Docling handles supported document conversion; BGE base English v1.5 supplies embeddings; Qdrant supplies retrieval; CopilotKit/AG-UI supplies the browser interaction; PostgreSQL supplies checkpoints.

Ollama is the implemented answer-provider family. LangSmith is selected for future tracing, evaluation and Studio use, with no connection implied by that selection.

## 7. Model routing is an experimental extension

**D159–D162.** The desired design separates inference access, routing policy and evaluation. The present implementation is a two-tier keyword/length heuristic with one alternate-endpoint fallback. It is disabled by default.

LiteLLM and RouteLLM are design references, not installed implementations in the current dependency set. Adapter contracts are tested with doubles. A judge, actual provider-usage measurement and a quality-based rollout decision remain future work.

## 8. Public documentation and preserved private history

**D163–D164, recorded 2026-09-14.** Prepare the project for an eventual open-source GitHub release. Public documentation uses neutral examples, explicit maturity labels and GitHub-rendered diagrams. Preserve original documents, drawings, private operational decisions and evidence locally.

The documentation refactor does not change application behavior or repository visibility. Review source/configuration, private artifacts and Git history separately before publication. The existing MIT license and upstream notices are retained.

**D165, recorded 2026-09-14.** Keep the README conversation and manual-ingestion diagrams as native Excalidraw sources with matching SVG previews under `architecture/diagrams/`. Other public diagrams remain Mermaid. Refresh previews when their sources change.

**D165 format correction, recorded 2026-09-14T08:56:37-04:00.** Store editable drawings as Obsidian-native `.excalidraw.md` files under `architecture/diagrams/` to enable full Excalidraw plugin functionality. Codex local preview supports this format. Keep existing SVG previews and standard Markdown links; the conversion preserves diagram content.

## Shared public source

**D166, recorded 2026-09-14.** Consolidate the application into `src/nora/` and one `ui/`, with explicit configuration, synthetic examples, tests and a clean source snapshot. Keep target guides as references to the same implementation. Preserve legacy operator code, raw private fixtures and original drawings outside the release. Local source validation is separate from deploying the refactor or publishing GitHub history.

## Private communication

**D168, recorded 2026-09-14.** Use Tailscale as the intended private communication path between Nora's host and its clients. Keep application origin and MCP host settings explicit; network access and application credentials have separate responsibilities. The local container trial validates those settings, while a connection from another Tailscale device remains to test.
