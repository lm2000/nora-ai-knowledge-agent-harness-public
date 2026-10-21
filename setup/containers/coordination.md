# Coordination and the NIS assistant

[Services](README.md) · [Assistant behavior](../../agents/README.md)

Coordination owns the conversation: it selects an answer model, runs the OSS Deep Agent and persists history. For example, a question about Atlas and its UUID follow-up use the same assistant and checkpoints, regardless of client transport.

![How Coordination serves one question.](../../architecture/diagrams/architecture-request-path.gif)

[Local browser version](../../architecture/diagrams/architecture-request-path.html)

## Selected one-assistant target — 2026-10-02

FastMCP is embedded in the existing FastAPI process. `ask_nis(question, thread_id=None)` returns a plain answer and conversation UUID. Omitting the UUID starts a new topic; supplying it continues that assistant conversation. LiteLLM runs as a separate gateway to the same tool. HTTP and MCP invoke the same operation in process, and their lifespans share startup/shutdown.

The dated private candidate has direct/gateway transport, normal-restart continuity and bounded Codex/OpenClaw conversational evidence. [Deployment status](../private-deployment/STATUS.md) owns those results and remaining quality gaps. MCP streaming, extra tools and other gateway integrations remain future work.

## Interfaces and state

Run `nora serve coordination --host 0.0.0.0` in the backend container. `/ask` accepts `question` and an optional UUID `thread_id`; `/history/{thread_id}` returns that assistant's history; `/agent` supplies AG-UI. Role-selection fields, role-specific history and `/transfer` are removed.

Public thread identifiers remain UUIDs. PostgreSQL checkpoints use `assistant:<UUID>` internally. There is no fallback to raw legacy checkpoints. The existing ownership table rejects IDs belonging to old roles while retaining their stored records. No old-chat migration or destructive schema change is part of this cleanup.

[Configuration](../configuration.md) owns model inventory, credentials, endpoints and request limits. `NORA_ASSISTANT_MODELS` configures the incumbent selector. Shared Retrieval MCP pins the prepared release for a turn; BGE stays behind Retrieval for knowledge queries.

## Execution bounds

The default turn allows three retrieval calls including initial Grounding, and four logical model calls. Provider retry/output-token limits remain unchanged. The graph-step bound permits middleware bookkeeping after a final answer. One explicit numeric word-cap repair may run without tools within the same model allowance; it does not truncate or loop. Failed or still-oversized repairs return an error. Streaming can expose drafts, so capped streaming presentation is not accepted merely because the final saved answer complies.

The official async PostgreSQL checkpointer initializes its schema at startup. Request accounting is atomic; execution concurrency is local to one Coordination process. A normal restart reconnects to the same database and retains assistant history.

## Packaging and secrets

Coordination uses the shared backend image while owning its own process and state mounts. Compose mounts internal/MCP credentials, PostgreSQL password and configured provider credentials as secret files. `nora init` creates local owner-only files; values do not belong in source or logs.

Conversation checkpoints are independent from ingestion state and corpus activation. Back up PostgreSQL, Qdrant, prepared documents and configuration before deployment changes. [Operations reference](../private-deployment/ROLLOUT.md#operate-and-recover) and the canonical maintainer guide own host-specific procedures.
