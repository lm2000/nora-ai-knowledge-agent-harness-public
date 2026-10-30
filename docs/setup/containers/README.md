# Container and service inventory

[Home](../../../README.md) · [Architecture](../../architecture/architecture-concept.md) · [Setup](../README.md)

This page owns the [Compose](../../../compose.yaml) service and storage boundaries.
For example, a browser question and an MCP follow-up use the same Coordination
service and conversation UUID. [Architecture](../../architecture/architecture-concept.md)
owns the Coordination Layer design; [Coordination](coordination.md) owns its
existing client contract.

![Container boundaries](../../architecture/diagrams/container-service-inventory.gif)

[Local browser version](../../architecture/diagrams/container-service-inventory.html)

## Service inventory

| Service | Lifecycle | Owns |
| --- | --- | --- |
| [Browser UI](ui.md) | Persistent | CopilotKit/AG-UI interaction and authenticated server proxy |
| [Coordination service](coordination.md) | Persistent | AI Coordinator, Deep Agents/LangGraph, model selection, embedded FastMCP and conversation lifecycle |
| MCP Gateway | Persistent | LiteLLM Proxy tool access to the FastMCP MCP Server |
| [Retrieval MCP](knowledge-retrieval.md) | Persistent | Search/read over the pinned prepared release |
| Shared BGE | Persistent | Query/document encoding with one pinned model |
| [Qdrant](qdrant.md) | Persistent | Derived dense/lexical search index |
| [PostgreSQL](postgresql.md) | Persistent | Assistant checkpoints and stored ownership records |
| [Four ingestion workers](ingestion.md) | Temporary | Conversion, preparation, embedding and import/verification |
| Admin | On demand | Verification and supported activation operations |
| Local Ollama | Optional profile | Local inference when explicitly configured |

## Shared BGE capacity

Retrieval calls BGE in query mode; the batch worker calls it in document mode. Both use the same pinned model revision, vector dimensions, normalization and compatible input limits. Query instructions remain specific to query encoding.

Bound batch size, outstanding requests and worker concurrency. The shared service needs admission control that preserves interactive capacity and applies backpressure to batch callers; jobs must throttle or pause under load. The exact limits, priority mechanism, timeout and retry policy require measurement. Test query latency during an import before enabling concurrent use.

## Storage and inference outside container boundaries

| Resource | Owner and purpose | Placement |
| --- | --- | --- |
| Original documents | Operator; unchanged source versions | Existing source storage |
| Prepared full documents and manifest | Preparation; full text and source identity for Retrieval `read` | Configured local release or generation-pinned GCS objects |
| Extracted text, chunks, vectors and job reports | Manual ingestion; durable stage handoffs and recovery evidence | Job artifact storage, mounted or accessed by API |
| Search index | Qdrant; derived data rebuildable from prepared artifacts | Qdrant data volume |
| Conversation checkpoints | PostgreSQL; independent from ingestion state | PostgreSQL data volume |
| BGE model files | Shared BGE server; pinned model and receipt | Model cache volume |
| Ollama Cloud | External answer inference route | Provider API outside the Docker host |
| Fireworks.ai | External answer inference route | Provider API outside the Docker host |

GCS and filesystem/database volumes are storage, not Docker containers. Prepared full documents can use a local release or a dedicated GCS bucket; the dated deployment record owns the selected installation. Original documents, prepared full text, vectors and the live search index have distinct lifecycles. No ingestion broker or scheduler is selected.

## Current implementation

Root Compose defines seven default persistent containers: `ui`, `coordination`,
`gateway`, `retrieval`, `bge`, `postgres` and `qdrant`. Four temporary jobs
(`job-convert`, `job-prepare`, `job-embed`, `job-import`) live under the ingestion
profile. The host-side `scripts/knowledge-update` launcher runs them in order,
verifies their manifests and activates the release. The admin profile supports
verification and activation; optional Ollama uses `local-model`.

The source supports local prepared files and a generation-conditional cloud activation pointer (`gs://bucket/object`) that Retrieval consumes. `FakeGCSClient` supports local source tests; those tests do not establish a live bucket or activation. The [deployment record](../private-deployment/STATUS.md#configuration-reference--2026-10-21) owns the recorded installation configuration.

The backend image is shared by Coordination, Retrieval, BGE and admin, while
their containers remain independent. Root Compose mounts `.runtime/releases`
at `/data`, `.runtime/models` at `/models`, `.runtime/state` for the Coordination
request counter, and secrets where needed. Set the launcher's
`NORA_COMPOSE_PROJECT` to the same project used by the application so imports
reach its Qdrant volume. [Setup](../README.md#run-the-application) uses `nora`.
`scripts/docker_acceptance.sh` instead owns an isolated test project and cleans
up its own resources.

Root Compose publishes UI **8080** and Gateway **4000** on host loopback when
those services run. Retrieval, BGE, Coordination and both databases stay internal.
The browser installation can leave Gateway stopped; MCP gateway use has
[separate prerequisites](../README.md#run-the-application). Direct Retrieval
exposure requires an explicit proxy or overlay.
[Setup](../README.md#private-access-with-tailscale) owns Tailscale access.
Automatic provider selection runs inside Coordination. Existing single-user
credentials do not establish multi-user isolation.

[Configuration](../configuration.md) owns settings, [setup](../README.md#run-the-application)
owns commands, and [deployment status](../private-deployment/STATUS.md) owns dated
installation, remote-access and persistence evidence.
