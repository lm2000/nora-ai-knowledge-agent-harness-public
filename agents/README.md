# NIS assistant

[Home](../README.md) · [Architecture](../architecture/Architecture%20Concept.md) · [Coordination](../setup/containers/coordination.md)

One assistant answers questions about saved material, compares documents and applies follow-up corrections in separate topic conversations. For example, ask for an Atlas handover brief, then ask which decisions still need an owner. Research and interview analysis are tasks rather than separately selectable roles.

## Runtime boundary

Coordination contains the OSS Deep Agent, model selector, tools and conversation lifecycle. It uses shared Retrieval MCP for search/read and PostgreSQL for checkpoints. The browser and `ask_nis(question, thread_id=None)` reach the same assistant through AG-UI or embedded FastMCP, directly or through LiteLLM.

A missing UUID starts a new topic; the returned UUID continues it. Checkpoints use `assistant:<UUID>`. Current assistant history survives normal restart. Legacy role history is retained in storage but is not exposed or migrated into this interface.

## Answer behavior

Search for relevant saved material, read the matching source when needed, then give a concise answer or clarification. State missing evidence and distinguish a dated export from present state. Normal answers omit citation cards and internal IDs; requested source titles/headings can be named in prose.

Three retrieval calls cover automatic Grounding and model-requested search/read calls together. Most turns start with one search, leaving at most two model-requested calls. Scoped preparation-preservation questions and related follow-ups use a targeted search and automatically read one matching returned document ID at offset zero before generation, leaving at most one call. Candidate selection permits inspection; only retrieved content/metadata can verify the title and supported facts. No candidate leaves the two remaining calls available; missing evidence must be stated rather than invented. Counts reset on each turn, and excess requests receive tool errors without executing retrieval. Four logical model calls bound the turn. A requested numeric word cap can use one no-tool repair within that allowance. This does not establish general instruction-following reliability.

## Evaluation

Check target selection, relevant evidence, omissions, user corrections, conversation continuation and explicit answer limits. [Deployment status](../setup/private-deployment/STATUS.md) records the bounded Codex/OpenClaw conversational passes and their limits; [evaluation](../evaluation/README.md) owns representative quality work. The preparation-preservation answer remains a focused open check until a dated acceptance result records otherwise.
