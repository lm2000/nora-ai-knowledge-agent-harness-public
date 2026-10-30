# Private reference deployment

[Setup](../README.md) · [Historical status](STATUS.md) · [Operations](ROLLOUT.md)

Use this guide for private-deployment boundaries and the linked operating
records. For example, moving an installation to a new source candidate requires
separate checks of corpus representation and conversation persistence. The
[dated status](STATUS.md) retains the original five-service history and later
candidate acceptance.

![Private service boundaries](../../architecture/diagrams/container-service-inventory.gif)

[Local browser version](../../architecture/diagrams/container-service-inventory.html)

New installations use [one Compose configuration](../../../compose.yaml), [one backend](../../../src/nora/coordination.py)
and [one Browser UI](../../../ui/package.json). Prepared text can be local or read
from generation-pinned GCS objects. The dated record describes the candidate's
GCS pointer activation and Ollama Cloud answer route.

The configurable [cloud foundation CLI](../google-cloud/CLI.md) remains available for a separately selected infrastructure stage.

Use [shared setup](../README.md) for a fresh target. Before moving an existing installation to this package, verify its data format, model representation, credentials, collection and PostgreSQL schema on a separate target. Existing runtime receipts do not establish compatibility with a new source candidate.

## LiteLLM Admin UI persistence

The LiteLLM Proxy MCP Gateway uses the existing PostgreSQL service for its Admin UI state.
The gateway constructs `DATABASE_URL` at startup from the PostgreSQL secret file;
the database password is not copied into Compose environment values. The gateway
Compose service therefore mounts the `postgres` secret in addition to the gateway
and internal MCP secrets.

The gateway image installs and generates the Prisma client during the image build.
The launcher and gateway configuration disable automatic schema updates; normal
startup only connects an already initialized database.
The build also installs `libatomic1`, which is required by the Prisma query engine
on the slim Debian base image, and stores the generated binaries in the accessible
`/opt/prisma-binaries` directory. A successful build includes these checks:

```text
docker compose -f compose.yaml -f <private overlay>.yaml build gateway
docker compose -p nora-candidate -f compose.yaml -f <candidate overlay>.yaml up -d --no-deps gateway
curl -fsS http://127.0.0.1:4000/health/liveliness
```

Do not run `prisma db push` against the shared NIS PostgreSQL database without a
schema-diff review. LiteLLM's Prisma schema does not include NIS checkpoint and
ownership tables, so an unrestricted sync can drop them. Initialize LiteLLM tables
through a separate database or a reviewed additive migration, and take a current
readable PostgreSQL backup before any schema operation.

## MCP client contract and recorded acceptance

The [Coordination guide](../containers/coordination.md#client-contract) owns
`ask_nis`, its question/optional-UUID contract and the shared HTTP/MCP operation.
The [architecture](../../architecture/architecture-concept.md) owns the accepted
Coordination Layer design.

The dated candidate passed real MCP calls and normal-restart conversation
continuity. Bounded Codex and OpenClaw checks passed on October 3; OpenClaw
required an exact-prompt corrective pair after initial instruction truncation.
The [acceptance record](STATUS.md#ordinary-unrestricted-openclaw-acceptance--2026-10-03)
retains that scope and the remaining quality limits. New-chat persistence was
included; old-chat migration and continuation were excluded while stored history
was retained. The [roadmap](../../Plan.md) owns subsequent work.

The gateway exposes these explicit private namespaces: model inference at
`/v1` with the `nora-ollama` alias, Coordination at `/mcp/nis`, and Retrieval
search/read at `/mcp/retrieval`, and public web search at `/mcp/web`. The web
adapter reuses the Ollama credential and returns bounded source titles, URLs and
excerpts. The [routing guide](../model-routing.md) owns streaming compatibility
and saved-client setup; [status](STATUS.md) owns dated verification. Fireworks and local Ollama remain documented
provider options but are not active gateway routes until separately credentialed
and smoke-tested. Codex-native web search is not proxyable through this service.
