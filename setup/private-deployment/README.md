# Private reference deployment

[Setup](../README.md) · [Historical status](STATUS.md) · [Operations](ROLLOUT.md)

The original five-service private deployment established a browser-to-agent-to-retrieval path with separate knowledge and conversation stores. Its dated evidence is retained as history. A later candidate based on the shared source activated the retained corpus on the main private route; [status](STATUS.md) records the dated acceptance and remaining limits.

![Private service boundaries](../../architecture/diagrams/container-service-inventory.gif)

[Local browser version](../../architecture/diagrams/container-service-inventory.html)

New installations use [one Compose configuration](../../compose.yaml), [one backend](../../src/nora/coordination.py) and [one UI](../../ui/package.json). Prepared text can be local or read from generation-pinned GCS objects. The verified private candidate uses the local release route; real GCS publication remains open. Its working answer route is Ollama Cloud.

The configurable [cloud foundation CLI](../google-cloud/CLI.md) remains available for a separately selected infrastructure stage.

Use [shared setup](../README.md) for a fresh target. Before moving an existing installation to this package, verify its data format, model representation, credentials, collection and PostgreSQL schema on a separate target. Existing runtime receipts do not establish compatibility with a new source candidate.


## Selected one-assistant target — 2026-10-02

One NIS assistant handles separate new topic conversations, retaining the incumbent selector, OSS Deep Agents/LangGraph and PostgreSQL. Clients use a separate LiteLLM MCP Gateway or connect directly to FastMCP embedded in the existing FastAPI process. The [Coordination guide](../containers/coordination.md#selected-one-assistant-target--2026-10-02) owns the implemented `ask_nis` question/optional-UUID contract and shared-operation integration.

The core entrance is implemented and running in the dated private candidate; real MCP calls and normal-restart conversation continuity passed. Bounded Codex and ordinary OpenClaw conversational checks also passed on October 3. OpenClaw required an exact-prompt corrective pair after initial instruction truncation; general reliability and representative quality remain open. See [the dated acceptance record](STATUS.md#ordinary-unrestricted-openclaw-acceptance--2026-10-03). The [roadmap](../../Plan.md) tracks cleanup, rollout and focused quality checks. New-chat persistence is included; old-chat migration/continuation is excluded and existing history is retained. See [the accepted decision](../../Decisions.md#selected-target-one-assistant-with-a-gateway-backed-mcp-entrance).
