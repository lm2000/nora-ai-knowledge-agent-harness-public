# Contributor instructions

## Project context

Read [README.md](README.md), [Decisions.md](Decisions.md), [Plan.md](Plan.md) and the guide for the area being changed. Follow any separately supplied operator instructions and task-specific model or execution preferences.

Nora is a self-hosted knowledge assistant. Coordination contains an OSS Deep Agent with LangChain/LangGraph underneath. Retrieval is a separate MCP service over BGE, Qdrant and prepared text. PostgreSQL stores conversation checkpoints. Ingestion is a separate manual workflow. D167 selects one Coordination/Deep Agent container per role, a shared BGE server and four separate manual ingestion job containers; current Compose still needs that refactor. Keep target diagrams and implementation status distinct.

D169 records the accepted review choices for implementation: a dedicated GCS prepared-document bucket; one manual command automating four ingestion jobs, validation and version activation; separate role chats; and automatic model selection inside each role runtime. The routing objective meets required quality before comparing cost and latency. Application model access includes Ollama and Fireworks.ai. Preserve the distinction between selected requirements and implemented adapters.

D170 orders the work: finish documentation and source cleanup for GitHub, implement the accepted target, then roll it out. Publication or documentation work does not itself change a running deployment. Follow the operator's chosen executor and model preferences for each task.

## Working conventions

- Keep changes focused on the requested scope and preserve other contributors' work.
- Put implementation details in their owning guide; link to that guide from overview pages.
- Describe implemented, experimental, planned and historical work accurately.
- Keep normal answer behavior consistent with the plain-answer contract.
- Preserve source identity needed for maintenance and evaluation; preprocessing does not rewrite source meaning.
- Use explicit configuration for operator and deployment differences across supported targets.
- Keep credentials, private corpus material, conversation state and raw private traces out of contributions.

## Documentation

Write in English. Start with purpose and an example, then give the procedure or technical reference. Commands should name their execution location and expected result. Use relative repository links.

Keep editable Excalidraw sources under `architecture/diagrams/` as Obsidian-native `.excalidraw.md` files so they open with full plugin functionality. Embed matching SVG exports with standard Markdown image links, and refresh each SVG when its source changes. Existing Mermaid diagrams remain in their owning Markdown documents. Keep labels short, separate conversation and ingestion paths, and use tables for detailed contracts. Archived private drawings and operating history remain outside the public documentation set.

Update the relevant public architecture decision or roadmap when an accepted change alters them. Owner-specific operational decisions and approvals belong in the separately maintained private operating record.

## Validation

Keep `public-docs.json` aligned with public pages and diagram counts. For documentation changes, run `make linkcheck` and `make diagrams`. Visually inspect changed diagrams. Check examples against the actual file names and interfaces; do not present a host-specific reference bundle as a portable installer.

Run relevant application checks when application code changes. Offline mock tests, integration tests and deployment evidence establish different things; name what was actually tested.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [PUBLISHING.md](PUBLISHING.md).
