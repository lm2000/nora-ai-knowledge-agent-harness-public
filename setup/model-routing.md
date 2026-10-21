# Application model selection and client routes

[Setup](README.md) · [Coordination](containers/coordination.md) · [Configuration](configuration.md#model-routing)

Client inference defaults to the configured NIS RAG Cloud route. Explicit alternatives are native OpenAI, Ollama Cloud, and Ollama Local; Fireworks is legacy and not enabled. For example, a comparison can require a higher quality tier than a simple saved-fact question. Selection meets the required quality tier first, then compares configured cost and latency assumptions.

## Two configuration layers

Coordination's model adapters and selector belong to the application. A client such as Codex separately chooses native inference or a saved NIS route. An available source adapter does not imply an enabled deployment credential or fallback. The dated [configuration record](private-deployment/STATUS.md#configuration-reference--2026-10-21) owns the installation; the gateway reference below retains its October 15 verification scope.

## Gateway routes and client configuration

The October 15 reference candidate used LiteLLM as its client-facing inference
and MCP boundary. Secrets are mounted by name; their values are never part of source
or logs.

| Alias / interface | Backend and base URL | Verified capabilities | Priority and fallback |
| --- | --- | --- | --- |
| `nora-ollama` / NIS RAG Cloud (default) | Ollama Cloud, `https://ollama.com`, model `glm-5.3-flash` | `/v1/models`, streamed `/v1/responses`, single and multiple function calls | Primary inference route; no gateway model fallback is enabled yet |
| `retrieval-search`, `retrieval-read` | NIS Retrieval MCP, internal `http://retrieval:8001/mcp`, exposed at `/mcp/retrieval` | MCP search and bounded document read | Knowledge-search route; it does not generate answers |
| `web-search` | Ollama public web search, gateway `/mcp/web` | Public titles, URLs and bounded excerpts; existing Ollama credential | Read-only web lookup; no native search dependency |
| `nis-ask_nis` | NIS Coordination MCP, exposed at `/mcp/nis` | MCP answer operation and conversation UUID continuation | Application fallback/complete answer path; it retains NIS's own selector |
| Fireworks legacy | `https://api.fireworks.ai/inference/v1`, secret `fireworks` | Not enabled in the candidate gateway | No fallback until a nonempty credential and smoke test exist |
| Local Ollama | `http://ollama:11434` when the optional profile is enabled | Not enabled in the candidate gateway | Development-only alternative; explicit profile required |
| OpenAI managed Codex | Codex-managed backend | Not a LiteLLM route; no user key is copied into NIS | Retained explicit fallback; separate from the NIS provider |
| Hermes | Hermes Cloud/Desktop control plane | Explicitly excluded from NIS harness inference | Not a fallback for this project |
| Llama / LlamaIndex | No configured inference backend; LlamaIndex references are retrieval terminology | No route to validate | Not a provider; do not add a speculative alias |
| Harbor | Evaluation catalog/runner, not an inference provider | No runtime model endpoint | Evaluation-only; no gateway route |

The current verified fallback boundary is therefore transport-level: a client
can use `nis-ask_nis` or direct NIS MCP if model inference through LiteLLM is
unavailable. LiteLLM does not silently switch to Fireworks or local Ollama.
Provider and request timing appear in the gateway logs; this change does not
claim a benchmark or measured latency advantage.

Codex uses the `nis-litellm` Responses provider and `nora-ollama` alias. Its
command-backed bearer helper reads the existing application-owned credential;
launching the desktop app does not require an inherited shell environment key.
Saved `nis_retrieval` and `nis_web` MCP entries use the existing header helper
and explicit read-only tool approvals. No credential value belongs in source.
The dated [deployment record](private-deployment/STATUS.md) owns the current
default-selection outcome and exact verification boundary.

Use reasoning effort `high` for this GLM route. A bounded upstream check found
that `think=false` returned reasoning inside ordinary content with a closing
think tag; `think=true` separated its thinking and answer channels. The custom
client catalog uses a conservative 262,144-token window and 220,000-token
compaction threshold; provider metadata reports a larger 1,048,576-token context.
This is capacity metadata, not a quality or long-context acceptance result.

The pinned LiteLLM 1.103.2 compatibility module separates mixed reasoning, text
and tool deltas before Responses conversion and retains Ollama's per-call stream
indexes and IDs. It never synthesizes text deltas from the final answer. Both
sync and async regression checks exercise the real converter; version changes
require revalidation. Public web search is a bearer-authenticated MCP adapter
inside the gateway, bounded to ten results and a fixed Ollama API endpoint.

Codex-native search, built-in app connectors and managed OpenAI inference remain
separate services. Only inference and MCP calls explicitly directed to the NIS
provider/namespaces use LiteLLM; enabling a default provider does not proxy every
connector through it.

## Configuration

`NORA_ASSISTANT_MODELS` is a JSON array overriding the built-in model inventory. Endpoint/model defaults use `NORA_OLLAMA_*` and `NORA_FIREWORKS_*`. `NORA_SELECTOR_COST_WEIGHT` and `NORA_SELECTOR_LATENCY_WEIGHT` tune relative weights; `NORA_SELECTOR_LOG` optionally records decisions.

Candidates lacking configured credentials are skipped without logging secret values. If no capability-matched candidate survives, the selector uses the viable inventory. A request fails when no credentialed candidate remains. A provider failure may use one fallback only before any streaming output; a partial response does not restart as another answer.

## Limits and evidence

Quality, cost and latency scores are conservative configuration assumptions, not measured parity or savings. Logs contain query hashes and routing outcomes rather than raw questions. The three-retrieval/four-logical-model-call bounds remain independent of provider retries.

Deterministic adapter tests establish tool binding, invocation, streaming and
error behavior. Fresh-session gateway checks cover completed and incremental
responses, independent function arguments, saved Retrieval and public web search;
see the dated [status](private-deployment/STATUS.md) for outcomes and limitations.
These are bounded integration checks, not representative quality, embeddings,
provider parity or a latency benchmark. LiteLLM's inference alias does not replace
the NIS selector inside Coordination.
