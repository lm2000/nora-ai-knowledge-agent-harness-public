# Roadmap

[Home](README.md) · [Deployment status](setup/private-deployment/STATUS.md) · [Evaluation](evaluation/README.md)

Nora is a private knowledge assistant with one runtime, shared retrieval services and a four-stage knowledge update workflow. Current work makes that system simpler, reproducible and measurable.

## Current architecture target

Use one NIS assistant with separate topic chats. The default access path is `client → LiteLLM MCP Gateway → NIS FastMCP server → NIS runtime`; the same FastMCP server can also accept direct client connections. NIS retains its selector, LangGraph execution and conversation ownership. See [the accepted target](Decisions.md#selected-target-one-assistant-with-a-gateway-backed-mcp-entrance).

Keep this private single-user integration simple; elaborate access-control and quota systems are outside the slice. Use one ask tool for new conversations, without old-chat migration. Embed FastMCP in the existing FastAPI process, calling shared NIS operations directly.

## Execution progress

### Source refinements awaiting deployment acceptance

- **Scoped preparation grounding:** targeted search and returned-ID read before generation for preservation questions.
- **Conservative text recognizers:** narrow English preparation contract matching for deterministic preparation, originals, headings, source identity, chunk metadata, and model configuration.
- **Unified completion and length repair:** reject empty length-stopped generations; share one tools-disabled repair within the four-logical-call allowance.
- **Shared retrieval accounting:** seed automatic Grounding operations into the per-turn retrieval counter; block parallel/sequential excess calls.
- **Assistant guidance:** prioritize the owning Manual ingestion guide over broader Architecture decisions; require explicit field coverage for preservation questions.

## Unresolved repair outcome

The empty preparation repair remains an acceptance blocker. Offline diagnosis strongly supports a provider-continuation explanation: the installed `langchain-ollama` adapter retains a trailing assistant draft, and the published GPT-OSS template treats this as prefill, suppressing a fresh generation. The repair instruction appears only as a system suffix while messages end with the completed assistant draft. A proposed local correction uses a request-only `HumanMessage` for repair, but no application correction is currently implemented. These source refinements do not establish deployment or real-model acceptance.

## Later work

- Representative retrieval and answer-quality evaluation; bounded conversational checks do not establish general reliability.
- GCS prepared-document publication and pointer cutover, kept separate from ordinary local content updates.
- Incremental source replacement/deletion and concurrent-writer behavior; additions currently retain old source versions.
- Baseline retirement after its own backup and route review; outside this rollout.
- Capped streaming presentation: the JSON/MCP repair is bounded, but a stream may expose a draft before completion.
- Optional calendar/mail integration and additional deployment targets after a concrete need is established.
- Enterprise shared memory across harnesses, Kubernetes/SSO, commercial scale and measured customer AI latency are unimplemented/unverified.

Current decisions live in [Decisions](Decisions.md). Dated runtime and client evidence lives in [Deployment status](setup/private-deployment/STATUS.md). Superseded plans and detailed historical execution entries remain in Git history.