# Optional model routing

[Setup](README.md) · [Coordination](containers/coordination.md) · [Roadmap](../Plan.md)

The [shared adapter](../src/nora/routing.py) chooses between two Ollama-compatible models using question length and English complexity keywords. For example, a short factual question may use the cheaper model while a comparison uses the stronger model. Routing is disabled by default and has no measured quality parity.

## Settings

| Variable | Meaning |
| --- | --- |
| `NORA_ROUTER_ENABLED` | Enable explicitly with `true` |
| `NORA_ROUTER_CHEAP_MODEL` | Required model name when routing is enabled |
| `NORA_ROUTER_CHEAP_URL` | Optional endpoint; defaults to the main Ollama URL |
| `NORA_ROUTER_CHEAP_TOKEN` or `_FILE` | Optional separate credential |
| `NORA_ROUTER_THRESHOLD` | Nonnegative score threshold; default 40 |
| `NORA_ROUTER_LOG` | Optional local JSONL decision log |

The stronger model uses normal `NORA_OLLAMA_*` settings. A primary credential is reused only when endpoint URLs match; it is not forwarded to a different cheap endpoint. Add these variables explicitly to the Coordination environment when using Compose.

## Behavior and tests

The adapter uses public LangChain invocation, tool-binding and streaming interfaces. It preserves message histories and tool calls. A provider failure can try the other tier once before any stream output; after partial output it raises instead of starting another answer. A logging failure never triggers another model request.

Decision records include a query hash, tier, score, threshold, fallback, outcome and latency. They do not measure actual token usage or cost. Coordination's model retry can add inference attempts, so a daily request count is not a model-call budget.

[Contract tests](../tests/test_routing.py) cover sync/async calls, tool binding, failures, partial streams and credential separation. These are deterministic doubles. Compare real models on reviewed retrieval and answer fixtures before choosing a threshold or claiming savings.

The old standalone router and boolean quality-parity helper were retired with their original evidence. No judge or quality gate is implemented here. LiteLLM and RouteLLM remain [technology candidates](../architecture/Technology%20Options.md).
