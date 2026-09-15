# Coordination

[Services](README.md) · [Knowledge Assistant](../../agents/README.md#knowledge-assistant)

Coordination turns a question and retrieved passages into an answer. For example, “Which of those risks affects the deadline?” continues the same saved thread and performs another knowledge search.

## Selected target: one runtime per role

Each enabled role has its own container containing Coordination and the Deep Agent. Execution, model/tool calls and conversation lifecycle stay together; there is no separate outer coordinator. All roles use shared Retrieval MCP and PostgreSQL. Each role runtime performs automatic balanced routing across the configured inference providers (Ollama Cloud and Fireworks.ai). BGE stays behind Retrieval for conversational knowledge queries.

The existing `coordination` service serves the Knowledge Assistant role directly; Research and Interview runtimes are implemented with their own system prompts and model inventories. UI role routing, per-role configuration, PostgreSQL checkpoint namespacing and a global thread ownership table are implemented. A shared PostgreSQL database namespaces checkpoints; the ownership table additionally rejects the same client-visible thread id being reused across roles. See [role status](../../agents/README.md) and [the target inventory](README.md#selected-target).

[Conversation sequence](../../architecture/diagrams/02-question-to-answer.excalidraw.md) · [SVG preview](../../architecture/diagrams/02-question-to-answer.svg).

## Current request path

1. Accept an authenticated `/ask` request or an AG-UI `/agent` stream.
2. Reserve the process execution slot and atomically count the accepted request before streaming headers.
3. Search Retrieval MCP for the latest user question.
4. Run the Deep Agent with a bounded model view, search/read tools and the configured Ollama model.
5. Store checkpoints and return plain answer content. `/history/{thread_id}` returns user and assistant messages.

[Agent construction](../../src/nora/agent.py), [HTTP adapters](../../src/nora/coordination.py) and [MCP client](../../src/nora/mcp_client.py) are shared across targets. Filesystem, shell and delegation tools are excluded. Manual ingestion is separate.

[Configuration](../configuration.md#request-bounds) owns timeouts, history and request limits. The official async PostgreSQL checkpointer is used in production; framework tests use an in-memory checkpointer and an in-memory ownership store. Request accounting is atomic, but execution concurrency is local to one process. Each role runtime has its own semaphore.

The `coordination` (Knowledge), `role-research` and `role-interview` runtimes each perform automatic quality-first model routing across their configured inventory (Ollama Cloud and Fireworks.ai). Tool binding and fallback-once-before-stream contracts are tested with doubles. The legacy optional keyword router remains available for the backward-compatible `coordination` path. Eight real PostgreSQL ownership/restart checks and live text/auth smoke calls through Ollama Cloud and Fireworks passed for the candidate. Live tool/stream behavior and target-host resource costs/latencies have not been measured.


## Deployment, migration and rollback

- **Secret-file interfaces.** Each Coordination/role runtime reads `NORA_INTERNAL_TOKEN_FILE`, `NORA_POSTGRES_PASSWORD_FILE`, `NORA_MCP_TOKEN_FILE` and optional provider files (`NORA_OLLAMA_TOKEN_FILE`, `NORA_FIREWORKS_TOKEN_FILE`). `nora init` creates these files under `.runtime/secrets`; Compose mounts them via `secrets:` and never embeds values in environment variables.
- **Health and readiness.** `deploy/health.py` calls `/health` on the service with the internal token. The endpoint returns 503 while Retrieval is not ready and 200 when Retrieval reports ready. Compose `healthcheck` uses this script; the UI waits for the three role services to be healthy.
- **Migration and rollback preserving old chats.** Activation changes the `current` release symlink or GCS pointer; conversation checkpoints are stored separately in PostgreSQL and are unaffected by release activation/rollback. The ownership table is created by each role runtime at startup if it does not exist. Rollback restores the previous release pointer; old chats remain readable through their role runtime.
- **Application downgrade.** Downgrade to an older single-role application has not been exercised. Preserve the PostgreSQL volume; Research/Interview histories require a role-aware application. Corpus-pointer rollback is separate from application rollback.
- **Startup and restart.** Each role runtime initializes the Postgres checkpointer schema and the ownership table on startup. A restart reconnects to the same PostgreSQL database and resumes existing conversations; ownership claims persist because they live in PostgreSQL. Run one Coordination/role worker per role for the current ownership model.
- **Timeouts and concurrency.** `NORA_REQUEST_TIMEOUT` bounds the whole answer turn, `NORA_TOOL_TIMEOUT` bounds Retrieval MCP calls, and `NORA_DAILY_LIMIT` plus `NORA_CONCURRENCY` throttle accepted requests locally. The selector passes the request timeout to each provider model.
- **Resource observations.** No real resource measurements were taken in this sandbox; CPU, memory and latency observations must be recorded on the target host under load.
