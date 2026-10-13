# Model selection

[Setup](README.md) · [Coordination](containers/coordination.md) · [Configuration](configuration.md#model-routing)

The NIS assistant selects among configured tool-capable Ollama Cloud and Fireworks.ai models. For example, a comparison can require a higher quality tier than a simple saved-fact question. Selection meets the required quality tier first, then compares configured cost and latency assumptions.

## Configuration

`NORA_ASSISTANT_MODELS` is a JSON array overriding the built-in model inventory. Endpoint/model defaults use `NORA_OLLAMA_*` and `NORA_FIREWORKS_*`. `NORA_SELECTOR_COST_WEIGHT` and `NORA_SELECTOR_LATENCY_WEIGHT` tune relative weights; `NORA_SELECTOR_LOG` optionally records decisions.

Candidates lacking configured credentials are skipped without logging secret values. If no capability-matched candidate survives, the selector uses the viable inventory. A request fails when no credentialed candidate remains. A provider failure may use one fallback only before any streaming output; a partial response does not restart as another answer.

## Limits and evidence

Quality, cost and latency scores are conservative configuration assumptions, not measured parity or savings. Logs contain query hashes and routing outcomes rather than raw questions. The three-retrieval/four-logical-model-call bounds remain independent of provider retries.

Deterministic adapter tests establish tool binding, invocation, streaming and error behavior. Representative answer quality and provider cost/latency still require reviewed fixtures and measurements. LiteLLM serves as the MCP gateway; its built-in inference router is not selected. The obsolete keyword/length router is removed from the supported assistant path.
