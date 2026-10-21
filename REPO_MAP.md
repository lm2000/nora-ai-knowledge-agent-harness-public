# Repository map

[Home](README.md) · [Contributing](CONTRIBUTING.md)

Each topic has one current owner. Superseded material remains available through Git history.

![Runtime components referenced by this repository map.](architecture/diagrams/01-system-architecture.gif)

[Local browser version](architecture/diagrams/01-system-architecture.html)

| Location | Owns |
| --- | --- |
| [README](README.md) | Product overview, example, current state and reading route |
| [Roadmap](Plan.md) | Current priorities and completion criteria |
| [Decisions](Decisions.md) | Accepted architecture and historical rationale |
| [AGENTS](AGENTS.md) | Contributor and AI-tool instructions |
| [src/nora/](src/nora/__init__.py) | Preparation, retrieval, agent runtime, configuration and CLI |
| [ui/](ui/package.json) | Next.js, CopilotKit and AG-UI browser application |
| [tests/](tests/test_services.py) | Application contracts and framework integration tests |
| [examples/](examples/queries.json) | Fictional documents and labeled questions |
| [deploy/](deploy/Dockerfile) and [Compose](compose.yaml) | Container packaging and service definitions |
| [setup/](setup/README.md) | Installation and configuration |
| [setup/containers/](setup/containers/README.md) | Runtime service boundaries and state ownership |
| [setup/private-deployment/](setup/private-deployment/STATUS.md) | Dated private deployment evidence |
| [architecture/](architecture/architecture-concept.md) | Current design, requirements and diagrams |
| [agents/](agents/README.md) | Single-assistant behavior and evaluation expectations |
| [Workflows](workflows/README.md) | Task-specific procedures, including artifact evaluation and revision |
| [workflows/ingestion/](workflows/ingestion/README.md) | Knowledge update design and canonical checklist |
| [data/](data/Data%20Contract.md) | Public source types and document identity rules |
| [evaluation/](evaluation/README.md) | Quality protocols, results and known limits |
| [scripts/](scripts/build_release.py) | Validation, smoke and source-release utilities |
| `skills/` | Workspace-installed reference copies, identified by their source-origin records; excluded from public releases |
| `operations/` | Private tracked runbooks and recovery evidence; excluded from public releases |
| [Publishing](PUBLISHING.md) | Public source snapshot procedure |

## Generated and private state

| Location | Purpose |
| --- | --- |
| `.private/` | Private records, originals and local-only operational material |
| `.runtime/` | Rebuildable runtime state |
| `.release/` | Generated release artifacts |
| `.private/public-sync/` | Generated public-repository synchronization output |
| `.smart-env/` | Rebuildable local index used by Obsidian Smart plugins |

`public-docs.json` inventories publishable documentation. `release-manifest.json` is the exact public source allowlist. Editable HTML diagrams with inline SVG and matching derived GIF previews live together under `architecture/diagrams/`.
