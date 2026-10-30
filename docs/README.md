# Documentation

[Home](../README.md) · [Contributing](../CONTRIBUTING.md)

Start with this short review route:

1. [Project overview](../README.md): purpose, example and the whole harness.
2. [Architecture](architecture/architecture-concept.md): why components exist and
   how knowledge, coordination and review fit together.
3. [Decisions](Decisions.md): constraints, alternatives and consequences.

The topic map below points to the owning guide for deeper questions. For
example, architecture explains why Ingestion runs outside conversations; the
ingestion guide owns its procedure. Superseded plans remain in Git history.

| Location | Owns |
| --- | --- |
| [README](../README.md) | Purpose, example and reader route |
| [Architecture](architecture/architecture-concept.md) | Coordination Layer, model routes, three workflows and storage boundaries |
| [Requirements](architecture/Requirements.md) | Expected behavior and protected contracts |
| [Decisions](Decisions.md) | Accepted choices and dated rationale |
| [Roadmap](Plan.md) | Active work, implementation sequence and acceptance results |
| [AGENTS](../AGENTS.md) | Contributor and AI-tool instructions |
| [src/nora/](../src/nora/__init__.py) | Preparation, retrieval, agent runtime, configuration and CLI |
| [ui/](../ui/package.json) | Next.js, CopilotKit and AG-UI browser application |
| [tests/](../tests/test_services.py) | Application contracts and framework integration tests |
| [examples/](../examples/queries.json) | Fictional documents and labeled questions |
| [deploy/](../deploy/Dockerfile) and [Compose](../compose.yaml) | Container packaging and service definitions |
| [setup/](../setup/google-cloud/03-cloud-setup.py) | Executable host/cloud helpers; their documentation is under `docs/setup/` |
| [Setup](setup/README.md) | Installation and executable configuration |
| [Model routing](setup/model-routing.md) | Model adapters, selector configuration, fallback and route evidence |
| [Services](setup/containers/README.md) | Concrete process boundaries, network and state ownership |
| [Deployment record](setup/private-deployment/STATUS.md) | Dated private installation evidence |
| [Diagrams](architecture/diagrams/README.md) | Interactive HTML sources and matching GIF views |
| [Assistant behavior](agents/README.md) | Question-answering contracts, budgets, repair and persistence |
| [Workflows](workflows/README.md) | Entry points for all three workflows |
| [Ingestion](workflows/ingestion/README.md) | Knowledge releases, artifacts and canonical operator checklist |
| [Artifact review](workflows/artifact-review/README.md) | Judge Registry, feedback, Synthetic Owner/Real Owner loops and saved-response CLI |
| [Data contract](data/Data%20Contract.md) | Source types, preparation artifacts and identity rules |
| [Evaluation](evaluation/README.md) | Quality protocols, results and known limits |
| [Scripts](../scripts/build_release.py) | Validation, smoke and source-release utilities |
| `operations/` | Private runbooks and recovery evidence; excluded from public releases |
| [Publishing](PUBLISHING.md) | Public source snapshot procedure |

Reusable custom skills are maintained in the separate Agentic Tools project.

## Generated and private state

| Location | Purpose |
| --- | --- |
| `.private/` | Private records, originals and local operational material |
| `.runtime/` | Rebuildable runtime state |
| `.release/` | Generated release artifacts |
| `.private/public-sync/` | Generated public-repository synchronization output |
| `.smart-env/` | Rebuildable local index used by Obsidian Smart plugins |

`public-docs.json` inventories publishable documentation.
`release-manifest.json` is the exact public source allowlist. Each diagram lives
as editable HTML with inline SVG and its derived GIF under
`docs/architecture/diagrams/`.
