# Contributor instructions

## Project context

Read [README.md](README.md), [Plan.md](Plan.md), [Decisions.md](Decisions.md), [REPO_MAP.md](REPO_MAP.md) and the guide for the area being changed. These are the current shared project entry points for Codex and other AI tools. Use Git history for superseded plans and handovers instead of keeping duplicate current-looking documents. Maintainers also read the separately maintained Nora Intelligence System Operations Guidance when available locally. Follow any separately supplied operator instructions and task-specific model or execution preferences.

NIS is a private single-assistant knowledge service. Coordination contains OSS Deep Agents/LangGraph, the incumbent selector and conversation lifecycle. Retrieval MCP uses shared BGE, Qdrant and prepared text; PostgreSQL stores assistant checkpoints. LiteLLM is a separate MCP gateway to FastMCP embedded in Coordination. The four ingestion jobs run separately on an operator command. The repair instruction is a request-only `HumanMessage` named `nora_answer_repair` ending the repair model request; it is never appended to graph state or checkpoints. The selector ignores this internal message when identifying the actual user question, and context bounds count its characters while ignoring it as a genuine user turn.

Current assistant chats and corpus data must remain intact. Old role interfaces/configuration are removed; stored legacy role chats are retained but not exposed or migrated. Preserve `assistant:<UUID>` checkpoints, minimal owner isolation, graph completion, bounded word-length repair, three retrieval calls including Grounding and four logical model calls. Model inference defaults to the configured NIS RAG Cloud route; explicit alternatives are native OpenAI, Ollama Cloud, and Ollama Local. Fireworks is a legacy, credential-empty option and Hermes is excluded from harness inference, execution and review unless the owner explicitly reverses that choice.

Scoped preparation-preservation grounding searches for the owning guide and reads one matching returned ID before generation when available. Seed both automatic operations into the same per-turn retrieval counter; search plus read leaves at most one model-requested call. Candidate selection permits a read, not source attribution. See [assistant behavior](agents/README.md#answer-behavior).

Use [Decisions](Decisions.md) for accepted design, [Plan](Plan.md) for active progress and [deployment status](setup/private-deployment/STATUS.md) for dated live evidence. Publication does not change running services. The ordinary ingestion procedure is backup-first; additions require retained-corpus assembly, rebuilds require the complete desired set, and a literal Retrieval pin requires explicit deployment activation. The dated deployment record owns the selected local/GCS activation state.

## Working conventions

- Coordinate active harness improvements through the single owner recorded in the private Operations Guidance and the current sequence in Plan.md. Finish worker handoffs before another executor changes shared Codex configuration or the gateway; preserve plan-only ingestion scope and unrelated worktree changes.

- Keep changes focused on the requested scope and preserve other contributors' work.
- Put implementation details in their owning guide; link to that guide from overview pages.
- Describe implemented, experimental, planned and historical work accurately.
- Keep normal answer behavior consistent with the plain-answer contract.
- Preserve source identity needed for maintenance and evaluation; preprocessing does not rewrite source meaning.
- Use explicit configuration for operator and deployment differences across supported targets.
- Keep credentials, private corpus material, conversation state and raw private traces out of contributions.
- Record durable project decisions and current status in the shared repository guides and maintainer operating records, not only in an AI tool's chat or memory. Link to portable personal context instead of copying private preferences into public documentation.

## Documentation

Write in English. Start with purpose and an example, then give the procedure or technical reference. Commands should name their execution location and expected result. Use relative repository links.

Use two maintained files per diagram under `architecture/diagrams/`: editable interactive HTML with inline SVG, and a matching GIF exported from that HTML. Embed the GIF with standard Markdown image links and place the local HTML link directly below it. Regenerate the GIF when HTML changes. Separate Excalidraw, SVG, JSON and Mermaid sources are not required by this convention. Retire old active assets after replacing their links. A repository HTML link opens source; identify it as a local browser version unless a documentation site already exists. Keep labels short and distinguish conversation and manual ingestion paths.

Update the relevant public architecture decision or roadmap when an accepted change alters them. Owner-specific operational decisions and approvals belong in the separately maintained private operating record.

## Validation

Keep `public-docs.json` aligned with public pages and diagram counts. For documentation changes, run `make linkcheck` and `make diagrams`. Visually inspect changed diagrams. Check examples against the actual file names and interfaces; do not present a host-specific reference bundle as a portable installer.

Run relevant application checks when application code changes. Offline mock tests, integration tests and deployment evidence establish different things; name what was actually tested.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [PUBLISHING.md](PUBLISHING.md).
