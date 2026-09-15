# Container packaging status

[Services](README.md) · [Setup](../README.md) · [Validation](../../evaluation/VALIDATION.md)

The September 14 source refactor replaces separate local/cloud Compose bundles and the earlier partial drafts with [one application configuration](../../compose.yaml), [one backend image](../../deploy/Dockerfile) and [one UI image](../../ui/Dockerfile).

Both application images built successfully on ARM Linux using Python 3.12.12 and Node.js 22.22.0. The five-service stack imported and verified three fictional documents, answered four requests through Ollama Cloud, preserved conversation history after restart and restored it into a separate PostgreSQL instance with a fresh volume. The installed backend's 18 Python modules matched the reviewed source.

UI origins and MCP allowed hosts now pass through Compose configuration. The live services accepted configured values, rejected unconfigured values and required the MCP credential. [Validation](../../evaluation/VALIDATION.md) records the scope; other architectures, Tailscale access from another device and general answer quality remain to test.

The isolated browser acceptance harness (`scripts/ui_acceptance.py`) now passes all 11 checks against synthetic model/retrieval doubles: role-specific answers, new conversation, current-thread reload, prior-thread resume, rendered research history after reload, explicit selected/reviewed transfer to a new target chat, in-flight delayed interview response without leaking into another role, and resuming the interview thread after switching back. It exercises the actual Next.js UI, three real role API runtimes and Playwright Chromium; it does not replace a live deployment with real corpus and providers.

The earlier drafts and deployment-specific copies remain in the local preservation archive. They are not additional supported installation paths. Follow [the shared setup procedure](../README.md#run-the-application) on the intended deployment target.


D167 and D169 are now reflected in current Compose: the existing `coordination` service serves the Knowledge Assistant role directly, with dedicated `role-research` and `role-interview` runtimes. There is no separate `role-knowledge` container and no additional outer coordinator. Per-role model selection, thread ownership enforcement and PostgreSQL-backed checkpoint persistence are implemented and tested with synthetic doubles. Ollama Cloud and Fireworks.ai retain working adapters resolved against the actual installed dependencies (langchain-openai 0.3.34, openai 2.54.0, httpx 0.28.1). The combined candidate passed 165 Python tests (including eight real PostgreSQL ownership/restart checks), 11 subtests and eight UI unit tests. Live text/auth smoke calls succeeded through Ollama Cloud and Fireworks; tool/stream contracts use test doubles. The database fixture used PostgreSQL 16 and has been stopped after testing; the deployment Compose file pins PostgreSQL 17.9. Target-host deployment and resource measurements remain the GCP workstream.
