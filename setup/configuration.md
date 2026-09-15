# Application configuration

[Setup](README.md) · [Settings source](../src/nora/config.py) · [Compose](../compose.yaml)

For example, a host can change its answer provider and collection through environment variables while running the same application package. Nora reads settings when a service or CLI command starts; importing a module does not load weights, credentials or clients.

## Paths and endpoints

| Variable | Default outside Compose | Purpose |
| --- | --- | --- |
| `NORA_DATA_DIR` | `.runtime/releases/current` | Active prepared release, including `docs/`, `import/` and `coverage.json` |
| `NORA_STATE_DIR` | `.runtime/state` | SQLite daily request counter |
| `NORA_MODEL_PATH` | `.runtime/models/bge` | Verified local BGE cache |
| `NORA_COLLECTION` | `nora_prepared_bge_v1` | Explicit Qdrant collection (fallback when no active release names one) |
| `NORA_QDRANT_URL` | `http://localhost:6333` | Index endpoint |
| `NORA_RETRIEVAL_URL` | `http://localhost:8001/mcp` | MCP endpoint |
| `NORA_BGE_URL` | `http://localhost:8002` | Shared BGE HTTP service |
| `NORA_BGE_TIMEOUT` | `60` | Batch embedding request timeout (seconds) |
| `NORA_BGE_MAX_BATCH_SIZE` | `64` | Maximum texts per `/encode` request |
| `NORA_OLLAMA_URL` | `https://ollama.com` | Answer provider |
| `NORA_OLLAMA_MODEL` | `gpt-oss:20b` | Configurable model example; availability depends on the provider |
| `NORA_RELEASES_ROOT` | `.runtime/releases` | Parent directory for versioned release bundles and the `current` symlink/pointer |
| `NORA_GCS_MANIFEST` | Unset | Optional local manifest for generation-pinned GCS reads |
| `NORA_GCS_POINTER` | Unset | Authoritative `gs://bucket/object` cloud activation pointer consumed by Retrieval |
| `NORA_GCS_PROJECT` | Unset | GCP project for the cloud storage client |
| `NORA_GCS_BUCKET` | Unset | Bucket used for both release publication and the activation pointer (must match the pointer bucket) |
| `NORA_GCS_PREFIX` | Unset | Prefix under which release documents and manifests are published |
| `NORA_GCS_PUBLISHER_CREDENTIALS_FILE` | Unset | Path to the publisher's explicit ADC credential file; required for GCS activation |
| `NORA_MCP_ALLOWED_HOSTS` | `localhost:*,127.0.0.1:*,retrieval:*` | HTTP Host values accepted by MCP |

The operator command `nora knowledge-update` writes releases under the parent of `NORA_DATA_DIR` and updates the `current` symlink there. Retrieval resolves `current` on each request, so activation takes effect without restarting the service.

Compose sets container paths and service DNS names. Host addresses and resource names are configuration, not embedded in application code. Only UI port 8080 and Retrieval port 8001 are published, both on loopback.

## Roles and model routing

| Variable | Default | Purpose |
| --- | --- | --- |
| `NORA_ROLE` | `knowledge` | Role served by this runtime (`knowledge`, `research`, `interview`) |
| `NORA_KNOWLEDGE_MODELS` | built-in defaults | JSON array of candidate models for Knowledge Assistant |
| `NORA_RESEARCH_MODELS` | built-in defaults | JSON array of candidate models for Research Assistant |
| `NORA_INTERVIEW_MODELS` | built-in defaults | JSON array of candidate models for Interview Analyst |
| `NORA_FIREWORKS_URL` | `https://api.fireworks.ai/inference/v1` | Fireworks OpenAI-compatible endpoint |
| `NORA_FIREWORKS_MODEL` | `accounts/fireworks/models/kimi-k3` | Example Fireworks model slug |
| `NORA_SELECTOR_COST_WEIGHT` | `1.0` | Relative weight for cost in routing decisions |
| `NORA_SELECTOR_LATENCY_WEIGHT` | `1.0` | Relative weight for latency in routing decisions |
| `NORA_SELECTOR_LOG` | unset | Optional path for routing decision logs |

The default model inventory exposes conservative quality/cost/latency assumptions, not measured values. Override `NORA_<ROLE>_MODELS` with a JSON array to change the candidate models, their capability tags and relative weights. The selector filters out models below the task's required quality tier, then sorts by weighted cost and latency.


## Credentials and PostgreSQL

Use `NORA_<NAME>` or `NORA_<NAME>_FILE`, with one source per credential. Names are `QDRANT_KEY`, `MCP_TOKEN`, `INTERNAL_TOKEN`, `POSTGRES_PASSWORD`, `OLLAMA_TOKEN`, `BGE_TOKEN` and optional `FIREWORKS_TOKEN`. Service credentials are required; a provider token may be empty for a local endpoint. Errors identify the setting without printing its value.

`nora init` creates owner-only files under `.runtime/secrets`. Compose mounts those files into the services that need them. PostgreSQL's wrapper reads its file before the official entrypoint changes user. UI credentials are read on the server at request time, never during browser compilation.

PostgreSQL uses `NORA_POSTGRES_HOST`, `NORA_POSTGRES_PORT`, `NORA_POSTGRES_DB` and `NORA_POSTGRES_USER`; defaults are `localhost`, `5432`, `nora`, `nora`. The official async LangGraph checkpointer initializes its schema at service startup. Credentials stay outside database URLs in source files.

## Request bounds

| Variable | Default |
| --- | ---: |
| `NORA_DAILY_LIMIT` | 60 accepted requests per UTC day |
| `NORA_CONCURRENCY` | 1 active run in the Coordination process |
| `NORA_REQUEST_TIMEOUT` | 180 seconds |
| `NORA_TOOL_TIMEOUT` | 45 seconds |
| `NORA_QUESTION_LIMIT` | 4,000 characters |
| `NORA_HISTORY_TURNS` | 4 user turns in model context |
| `NORA_KNOWLEDGE_CALL_LIMIT` | 3 searches/reads per run, including initial search |

The counter is atomic across local SQLite connections. It counts requests, including failed attempts, rather than tokens or provider calls. A model retry and optional routing fallback can make multiple inference calls.

Conversation ownership is enforced by a `nora_thread_ownership` table in the shared PostgreSQL database. The first `/ask`, `/agent`, `/history/{role}/{thread_id}` or `/transfer` call for a client-visible thread id atomically claims the id for that role; later attempts from a different role receive 403. Legacy un-namespaced Knowledge checkpoints are treated as Knowledge-owned on first access. The ownership table provides cross-role rejection; PostgreSQL checkpoint namespacing provides data isolation. Distributed locks and provider spending caps are not implemented.

HTTP bodies are limited to 70 KB before Coordination JSON parsing. The model view is bounded to 48,000 characters, with old turns removed as groups and tool/result pairs retained. Checkpoints keep the complete conversation.

## Optional routing and GCS

Routing is disabled by default. [Routing reference](model-routing.md) owns its settings and limitations.

For local filesystem mode, Retrieval reads full documents from the active release directory under `NORA_RELEASES_ROOT`.

For GCS mode, set `NORA_GCS_POINTER` to an authoritative `gs://bucket/object` URL, `NORA_GCS_BUCKET` to the bucket used for both release publication and the pointer, and `NORA_GCS_PREFIX` to the release-artifact prefix. Activation publishes prepared documents plus a generation-pinned manifest and atomically updates the pointer with a compare-and-swap generation precondition; Retrieval reads the pointer on each request to discover the active manifest and documents. The storage client uses normal Application Default Credentials. Every document read verifies the content hash against its SHA-256 ID. `NORA_GCS_MANIFEST` is a legacy local manifest path used only for explicit local reads; the cloud pointer is the production activation mechanism.

`NORA_GCS_PUBLISHER_CREDENTIALS_FILE` is the explicit boundary between the ordinary reader identity and the authorized publisher identity. It must point to a Google Cloud ADC credential file using keyless federation or service-account impersonation; long-lived service-account key files are rejected that has permission to upload objects and to perform the conditional pointer write. The launcher rejects GCS mode when this file is missing or unreadable, before any upload side effects. Retrieval and the reader path continue to use normal ADC and are not granted publisher permissions by this configuration.

Compose passes `NORA_GCS_POINTER` and `NORA_GCS_PROJECT` to Retrieval and the `admin` service. These values select storage, not a credential identity. GCP deployment must supply and verify keyless Application Default Credentials separately for the runtime reader and the authorized publisher; no publisher credentials are baked into source.

The four-container `scripts/knowledge-update` launcher chooses the activation mode from its environment. In local mode it atomically replaces the `current` symlink under the releases root. In GCS mode it runs the four jobs, then invokes `nora activate` inside the `admin` container with the publisher credential mounted at `/run/secrets/gcs-publisher`, updating the cloud pointer, then the local `current` symlink and history (these are separate writes). Keep the pointer and release-publication bucket aligned with the single-bucket activation interface.

The UI accepts its loopback origin and the loopback 8080 origins by default. Set `NORA_UI_ALLOWED_ORIGINS` to a comma-separated list that includes an intended additional origin, including its HTTPS scheme and port. Compose forwards this variable to the UI and `NORA_MCP_ALLOWED_HOSTS` to Retrieval; both can be set in `.env`. [Tailscale setup](README.md#private-access-with-tailscale) uses these settings for the selected private access path. They configure origin/host checks, not user login or tenant isolation.

Compose forwards each role’s own `NORA_KNOWLEDGE_MODELS`, `NORA_RESEARCH_MODELS` or `NORA_INTERVIEW_MODELS` inventory, and `NORA_SELECTOR_COST_WEIGHT` / `NORA_SELECTOR_LATENCY_WEIGHT` (both default to 1.0). Nonempty per-role inventory replaces defaults; otherwise `NORA_OLLAMA_URL` / `NORA_OLLAMA_MODEL` and `NORA_FIREWORKS_URL` / `NORA_FIREWORKS_MODEL` select the default endpoints and models.
