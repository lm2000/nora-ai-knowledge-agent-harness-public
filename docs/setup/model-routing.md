# Application model selection and client routes

[Setup](README.md) · [Coordination](containers/coordination.md) · [Configuration](configuration.md#model-routing)

Model routing selects an inference route for a task or subtask. For example,
a comparison can require a higher quality tier than a saved-fact question.
The AI Coordinator plans and delegates the work; model selection meets the
required quality tier, then compares configured cost and latency assumptions.

![The AI Coordinator selects model routes separately from workflow orchestration.](../architecture/diagrams/model-routing.gif)

[Local browser version](../architecture/diagrams/model-routing.html)

## Two configuration layers

Coordination's model adapters and selector belong to the application. A client
such as Codex separately chooses native inference or a saved NIS route. The
[architecture](../architecture/architecture-concept.md) owns the design; the
settings below describe the existing selector and dated client configuration.
An adapter's presence does not establish an enabled credential or fallback.

The dated [configuration record](private-deployment/STATUS.md#configuration-reference--2026-10-21)
owns the installation. The gateway reference below retains its October 15
scope: NIS RAG Cloud was the default, with native OpenAI, Ollama Cloud and
Ollama Local as explicit alternatives; Fireworks was legacy and disabled.

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

Endpoint/model defaults use `NORA_OLLAMA_*` and `NORA_FIREWORKS_*`.
`NORA_SELECTOR_COST_WEIGHT` and `NORA_SELECTOR_LATENCY_WEIGHT` tune relative
weights; both default to `1.0`. `NORA_SELECTOR_LOG` optionally records decisions.

## Model inventory reference

Set `NORA_ASSISTANT_MODELS` to a JSON array to replace the built-in candidate
inventory. An unset or blank value uses the defaults; `[]` is an empty override
and fails because the selector needs at least one candidate. The
[minimal environment example](../../.env.example) shows the required fields.
The [inventory loader](../../src/nora/assistant.py) owns JSON keys and defaults;
[ProviderSpec and the adapters](../../src/nora/providers.py) own provider behavior.
Defaults below apply to custom array entries; the built-in inventory has its own
assumptions in the loader.

| JSON key | Default when omitted | Meaning |
| --- | --- | --- |
| `provider` | Required | Adapter name: `ollama` or `fireworks` |
| `model` | Required | Model name understood by that provider |
| `base_url` | Required | HTTP(S) endpoint without embedded credentials, query or fragment; Fireworks requires its inference endpoint |
| `tools` | `true` | Declared tool support, stored as `supports_tools` |
| `streaming` | `true` | Declared streaming support, stored as `supports_streaming` |
| `context_length` | `16000` | Passed to Ollama as `num_ctx`; the Fireworks adapter does not use this field |
| `quality_tier` | `3` | Assumed quality tier; the convention is 1–5, with higher tiers stronger |
| `relative_cost` | `1.0` | Relative cost assumption used in ranking, not a measured price |
| `relative_latency` | `1.0` | Relative latency assumption used in ranking, not measured request time |
| `capability_tags` | `[]` | Declared tags used for eligibility: `knowledge`, `reasoning`, `coding` and `interview` |

The loader infers `OLLAMA_TOKEN` or `FIREWORKS_TOKEN` from `provider`; do not put
a token in the array. The current selector does not filter or disable tool
binding/streaming based on the `tools` and `streaming` flags. They record declared
support, so an operator must still choose a model that supports the required
operation. `context_length` likewise does not establish a verified provider
window or replace the application's request/history bounds.

The [selector](../../src/nora/selector.py) uses the latest real user question to
derive a minimum tier and required tags; it ignores `nora_answer_repair` when
finding that question. Ordinary questions require tier 2 and `knowledge`.
Reasoning, code and interview hints raise the tier to 3 and add the corresponding
tag. A question longer than 800 characters also raises the tier to 3.

Candidates whose required credential is unavailable are skipped without logging
secret values. Ollama permits an empty token for local use; this check does not
prove that a hosted endpoint will accept an unauthenticated request. Remaining
candidates must meet the tier and all required tags. If none match, the selector
uses the viable inventory instead, so this degradation does not guarantee the
requested quality or capability. Construction failures are skipped. If no usable
candidate remains, the request fails.

Eligible candidates are ranked by a score, with lower values preferred:

```text
0.5 × max(quality_tier − required_tier, 0)
+ relative_cost × cost_weight
+ relative_latency × latency_weight
− 0.2 × number_of_matched_required_tags
```

This favors a candidate near the required tier after eligibility filtering.
The scores compare configured assumptions, not observed quality, spending or
latency. Equal scores retain inventory order.

### Synthetic selection example

This illustrative array uses fictional model names. Replace them with available
models before using it; reading the example makes no provider request.

```json
[
  {
    "provider": "ollama",
    "model": "example-general",
    "base_url": "http://localhost:11434",
    "quality_tier": 2,
    "relative_cost": 1.0,
    "relative_latency": 1.0,
    "capability_tags": ["knowledge"]
  },
  {
    "provider": "ollama",
    "model": "example-reasoning",
    "base_url": "http://localhost:11434",
    "quality_tier": 3,
    "relative_cost": 1.5,
    "relative_latency": 1.2,
    "capability_tags": ["knowledge", "reasoning"]
  }
]
```

With both candidates viable and both weights at `1.0`:

| Question | Eligibility and ranking |
| --- | --- |
| “Who owns Atlas?” | Both meet tier 2 and `knowledge`. General scores `1.8`; reasoning scores `3.0`. General is first. |
| “Compare Atlas options.” | Tier 3 and `knowledge`/`reasoning` leave only the reasoning candidate eligible; its score is `2.3`. |
| “Debug Atlas code.” | Neither has `coding`. The selector degrades to both viable candidates; general scores `1.8` versus `2.5` and is first despite being below the requested tier and lacking `coding`. |

This capability degradation is separate from provider-failure fallback. A failed
invocation may try one other ranked candidate, if one remains, only before any
streaming chunk has been emitted. A partial response does not restart as another
answer. The synthetic example illustrates ordering; it is not an inference test.

## Limits and evidence

Quality, cost and latency scores are conservative configuration assumptions, not measured parity or savings. Logs contain query hashes and routing outcomes rather than raw questions. The three-retrieval/four-logical-model-call bounds remain independent of provider retries.

Deterministic adapter tests establish tool binding, invocation, streaming and
error behavior. Fresh-session gateway checks cover completed and incremental
responses, independent function arguments, saved Retrieval and public web search;
see the dated [status](private-deployment/STATUS.md) for outcomes and limitations.
These are bounded integration checks, not representative quality, embeddings,
provider parity or a latency benchmark. LiteLLM's inference alias does not replace
the NIS selector inside Coordination.
