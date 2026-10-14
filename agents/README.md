# NIS assistant

[Home](../README.md) · [Architecture](../architecture/Architecture%20Concept.md) · [Coordination](../setup/containers/coordination.md)

One assistant answers questions about saved material, compares documents and applies follow-up corrections in separate topic conversations. For example, ask for an Atlas handover brief, then ask which decisions still need an owner. Research and interview analysis are tasks rather than separately selectable roles.

## Runtime boundary

Coordination contains the OSS Deep Agent, model selector, tools and conversation lifecycle. It uses shared Retrieval MCP for search/read and PostgreSQL for checkpoints. The browser and `ask_nis(question, thread_id=None)` reach the same assistant through AG-UI or embedded FastMCP, directly or through LiteLLM.

A missing UUID starts a new topic; the returned UUID continues it. Checkpoints use `assistant:<UUID>`. Current assistant history survives normal restart. Legacy role history is retained in storage but is not exposed or migrated into this interface.

## Answer behavior

Search for relevant saved material, read the matching source when needed, then give a concise answer or clarification. State missing evidence and distinguish a dated export from present state. Normal answers omit citation cards and internal IDs; requested source titles/headings can be named in prose.

Three retrieval calls cover automatic Grounding and model-requested search/read calls together. Most turns start with one search, leaving at most two model-requested calls. Scoped preparation-preservation questions and related follow-ups use a targeted search and automatically read one matching returned document ID at offset zero before generation, leaving at most one call. Candidate selection permits inspection; only retrieved content/metadata can verify the title and supported facts. No candidate leaves the two remaining calls available; missing evidence must be stated rather than invented. Counts reset on each turn, and excess requests receive tool errors without executing retrieval. Four logical model calls bound the turn. A requested numeric word cap can use one no-tool repair within that allowance. The repair instruction is sent as a request-only `HumanMessage` named `nora_answer_repair` ending the repair model request, preserving the original system message and retrieved evidence/draft, and is never appended to graph state or checkpoints. The selector ignores this internal message when identifying the actual user question, and context bounds count its characters while ignoring it as a genuine user turn. For scoped preparation-preservation repairs, recheck all six supported requested fields, including those already present in the draft; keep the model configuration explicitly associated with vectors. This guidance does not broaden the acceptance matcher or add a repair/model call. Source-heading attribution compares case and collapsed Unicode whitespace; it does not alter returned answer text or relax required facts. This does not establish general instruction-following reliability.

For example, a question explicitly naming the Manual ingestion guide and asking about an SLA uses the same targeted search and returned-ID read when a candidate is available. This source-selection scope uses only the current question and stays separate from the six-field preparation check. Generic ingestion questions keep their ordinary search route. Automatic search/read calls share the existing retrieval budget.

Preparation follow-ups should restate the supported preservation fields and include requested derived artifacts named in retrieved passages, without claiming an exhaustive inventory. Missing-information statements should describe the passages inspected; if the requested guide was not obtained, say so rather than assigning a broader excerpt to it or generalizing to deployment knowledge. This local source correction passed the six-case isolated production-model check; deployment remains separate.

## Evaluation

Check target selection, relevant evidence, omissions, user corrections, conversation continuation and explicit answer limits. [Deployment status](../setup/private-deployment/STATUS.md) records the bounded Codex/OpenClaw conversational passes and their limits; [evaluation](../evaluation/README.md) owns representative quality work. The [2026-10-13 isolated acceptance](../Plan.md#latest-isolated-acceptance--2026-10-13) passed two fresh preparation questions and one follow-up on gpt-oss:20b; deployment acceptance and representative quality evaluation remain separate.
