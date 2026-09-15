# Repository map

[Home](README.md) · [Contributing](CONTRIBUTING.md)

| Location | Owns |
| --- | --- |
| [README](README.md) | Purpose, example, maturity and reading routes |
| [Roadmap](Plan.md) and [Decisions](Decisions.md) | Current priorities and accepted architecture |
| [src/nora/](src/nora/__init__.py) | Shared preparation, retrieval, agent, configuration and CLI |
| [ui/](ui/package.json) | The Next.js / CopilotKit browser application and server proxy |
| [tests/](tests/test_services.py) | Synthetic contracts and real framework adapters |
| [examples/](examples/queries.json) | Fictional documents and labeled questions |
| [deploy/](deploy/Dockerfile) and [Compose](compose.yaml) | Container packaging, health checks and credential wrappers |
| [setup/](setup/README.md) | Installation, configuration and target considerations |
| [setup/containers/](setup/containers/README.md) | Service responsibilities and state ownership |
| [architecture/](architecture/Architecture%20Concept.md) | Design, requirements and future technology choices |
| [agents/](agents/README.md) | Implemented role and proposed specialist roles |
| [workflows/ingestion/](workflows/ingestion/README.md) | Manual knowledge updates |
| [data/](data/Source%20Inventory.md) | Document identity and source handling |
| [evaluation/](evaluation/README.md) | Reproduction, scoped results and planned answer tests |
| [categorization/](categorization/README.md) | Historical collection and normalization context |
| [Templates/](Templates/Project%20Template.md) | Project/agent documentation template |
| [scripts/](scripts/build_release.py) | Documentation checks, synthetic smoke and source packaging |
| [Publishing](PUBLISHING.md) | Clean source snapshot procedure and remaining publication steps |

The README uses SVG previews with editable Excalidraw sources under `architecture/diagrams/`. Other public diagrams remain Mermaid blocks.

The public release contains one backend and one UI. Legacy deployment copies, raw private receipts, original diagrams and operating diaries are preserved locally outside the distribution. The old Git history remains separate from the generated source archive.
