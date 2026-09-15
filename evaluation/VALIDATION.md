# Source and container validation

[Evaluation](README.md) · [Setup](../setup/README.md) · [Roadmap](../Plan.md)

The September 14, 2026 checks exercise the shared source locally and in an isolated ARM Linux Compose project. Synthetic fixtures contain no private corpus material. This page describes what each check establishes.

## Checked locally

- Python contract tests cover deterministic preparation, exclusions, document hashes, generation-pinned GCS reads through a double, incompatible and corrupted imports, Qdrant round trips, atomic request accounting, routing failures and model-cache validation.
- The real Deep Agents/LangGraph and AG-UI adapters run with a deterministic model double and an in-memory checkpointer. Tests cover grounding, bounded follow-up context, history, request limits and recovery after retrieval failure.
- The real MCP server handles initialization, tool discovery, search/read, authentication and invalid requests.
- The separate real-BGE smoke test downloads the pinned public model, verifies its cache receipt, encodes three fictional documents, imports an embedded Qdrant index and uses the MCP SDK over loopback HTTP. Each of three labeled questions ranks its expected document first: Hit@1, Hit@5 and MRR@5 are 1.0.
- The retained Google Cloud foundation tests exercise configuration, offline plans and mocked resource checks; they create no cloud resources.
- The UI has server-boundary tests, a TypeScript check and a production build without a credential file. Browser interaction is checked against a synthetic backend.
- Documentation links, anchors, diagram inventory, rendered Mermaid and source-release paths are checked. Python wheel/source distributions and the explicit public source archive are inspected for their intended contents.

The source-refactor pass completed 80 Python tests, 11 cloud-planning subtests and three UI tests, including validation from a freshly extracted source archive and installed wheel. The public tests and [smoke script](../scripts/synthetic_smoke.py) are the reproduction entrypoints.

The subsequent publication cleanup repeated the source checks, built the Python distributions in an isolated environment, and passed UI tests, type checking and the production build on CI's Node.js 22.22.0. Visual review covered all six editable Excalidraw drawings and nine Mermaid diagrams. Four target drawings received corrected text spacing and matching browser-rendered SVG previews; the service inventory diagram was rearranged to separate the BGE connection labels. These documentation changes do not implement or deploy the selected target architecture.

## Isolated container trial

The separate VM task records the earlier five-service 0.1.0 baseline as already deployed, with three example documents, Atlas answers/follow-up and history after browser refresh. Its deployed source archive SHA-256 is `40d1d121e173523492f50b70096fb2cf1ad08400b6b8107d015199503e98a8dc`. That is a recorded result from that task, not an independent host probe here; the new candidate in this checkout is distinct and not deployed. The next deployment is a controlled upgrade of that existing baseline, not a new VM or initial deployment. VM reboot recovery, full-corpus operation and the new architecture were not proven by browser refresh.

The trial built both application images and started the five default services on Linux aarch64 under Colima, with four CPUs and about 8 GiB RAM. Containers used Python 3.12.12, Node.js 22.22.0, the pinned PostgreSQL/Qdrant images and Ollama Cloud `gpt-oss:20b`. All 18 installed backend modules matched the reviewed source. The container dependency check found no broken requirements.

| Check | Observed result |
| --- | --- |
| Preparation and server import | Three fictional documents and three points imported; document payloads and all three vector samples verified |
| Question | Correct Atlas release date, October 12, 2026, and owner, Jordan |
| Same-conversation follow-up | Correct payment-service load test and rollback prerequisites |
| Missing evidence | Correctly stated that Cedar promises no resolution-time guarantee |
| PostgreSQL and Coordination restart | All four existing message IDs, roles and contents preserved exactly |
| Backup and fresh storage | Custom-format dump restored into a separate PostgreSQL instance with a new volume; the same four messages matched exactly |
| Post-restore follow-up | Correct owner and date; conversation grew to six messages |
| Containerized browser UI | All six messages returned through the UI history proxy; the final restored turn rendered after reload; mobile width and new-conversation checks passed without browser errors |
| Access configuration | Compose forwarded a configured UI origin and MCP hostname; accepted requests returned 200, unconfigured values returned 403/421, and missing MCP credentials returned 401 |

These are four application question requests, each with one recorded knowledge call. They are not provider billing or token measurements. The trial uses generated service credentials and isolated volumes; the existing deployment was not changed.

The first database image pull needed one retry after a registry connection failure. A host-only temporary path was then moved under an existing Colima-shared directory so bind mounts could resolve. The application fix made UI origins and MCP allowed hosts configurable through Compose. No Docker or Colima settings were changed.

## Not established by this pass

Representative answer quality, correction behavior, other CPU/host targets, resource and failure limits, real GCS access, optional Docling conversion and additional client identities remain unverified. Tailscale is the selected private communication path; this trial does not establish a working connection from another device.

The three synthetic questions are an integration smoke test, not a benchmark or evidence that the private six-query regression improved. Historical aggregate results remain under their original scope in [regression](regression/README.md), [embedding comparison](embeddings/README.md) and the [retrieval pilot](targeted-research-pilot/README.md).

Several dependencies emit upstream deprecation warnings during tests. They do not fail the current checks; upgrades need the same adapter tests.

## First complete knowledge-update-to-answer slice — checked 2026-09-14T14:23:44-04:00

This isolated checkout completes and reviews the first end-to-end slice of the D169 architecture.

### Checked locally

- Added four distinct temporary job services (`job-convert`, `job-prepare`, `job-embed`, `job-import`) under the `ingestion` profile and a host-side `scripts/knowledge-update` launcher that runs them in order, verifies stage manifests, stops before activation on failure and atomically activates the `current` release symlink.
- Added a shared HTTP BGE service (`nora serve bge`) with query/document mode, bounded batch size and per-mode concurrency/backpressure. Tested the endpoint with deterministic encoder doubles via ASGI HTTP (TestClient), including auth rejection, oversized batch rejection and capacity admission.
- Added a BGE HTTP client that splits oversized batches and retries on transient 503s; tested with a recorded request double.
- Split ingestion into four job entrypoints (`nora job convert`, `nora job prepare`, `nora job embed`, `nora job import`) with explicit manifest handoffs.
- Added the operator command `nora knowledge-update` that runs the four jobs, validates the bundle and atomically activates the `current` release symlink. Tested activation, release isolation, rollback through the activation history log and failed-import behavior with a shared in-memory Qdrant double.
- Implemented release pinning so search and read within one answer turn use the same release: the MCP client resolves the active release on the first call and passes it via the `X-Nora-Release` header; Retrieval honors the header per request. Tested via TestClient that a pinned release overrides the active symlink for both `/release`, `/mcp` search and `/mcp` read.
- Added source-level GCS prepared-document publishing and generation-conditional cloud pointer activation/rollback. Retrieval reads the authoritative `gs://bucket/object` pointer to discover the active manifest and documents. Added `FakeGCSClient` for local verification and tests covering publish, conditional pointer writes, rollback, cloud pointer reads, MCP search/read through the pointer and document reads by generation. Real bucket creation, credentials and cloud upload are not exercised.
- Updated service inventory, ingestion workflow, setup commands, architecture diagram labels and this validation page.
- Full backend checks passed from this checkout with `PYTHONPATH=src` so the sibling venv loaded the current source rather than its stale editable install: ruff lint/format, 100 Python tests, shell syntax, link check, diagram structure and release manifest check.

### Acceptance scripts

- `scripts/acceptance_atlas.py` passed: Atlas ships October 12, 2026; a failed update to October 19 leaves the old answer usable; retry activates October 19; rollback returns October 12. Uses the existing application graph with a `DeterministicModelDouble` and a query-sensitive `DeterministicEncoderDouble`; no real BGE or inference provider call. Latencies and availability are recorded without an invented SLO.
- `scripts/bge_real_smoke.py` provides a real-process TCP smoke test for the shared BGE service, now using a query-sensitive deterministic double to assert that the HTTP `query` flag reaches the encoder. In this sandbox it exits with code 2 because loopback socket bind returns `EPERM`; the exact script is provided for a parent escalation run outside the sandbox.
- `scripts/verify_conversion_image.py` creates a synthetic DOCX, runs the `job-convert` container and verifies the real Docling dependency produces the expected Markdown. Passed outside the sandbox; pip check in the conversion image reported no broken requirements.
- `scripts/docker_acceptance.sh` builds the backend and conversion images, starts only `qdrant`, a deterministic-double BGE service and `retrieval` on a checked free loopback port, runs the actual four-job launcher, verifies the live MCP boundary through the real agent graph, exercises rollback and cleans up only its own project resources. Passed outside the sandbox on macOS: Atlas October 12 active, a failed bad-document update leaves it active, October 19 becomes active, rollback returns October 12, source checksums are preserved, **real MCP search/read release pin keeps October 19 accessible while active is October 12**, and the slow BGE double proves query admission during in-flight document work. The pin test uses `scripts/verify_release_pin.py` to capture the October 19 release identity and document ID while that release is active, then after rollback reads the same document with the captured pin, searches again with the same pin, and confirms an unpinned request sees October 12.

### Not exercised

- Docker Compose runtime integration for the four-job/BGE/activation slice was exercised end-to-end on macOS with deterministic doubles; the previously passed ARM Linux five-service trial remains evidence for that stack.
- Real GCS bucket creation, credentials and upload are not exercised; local verification uses the `FakeGCSClient` double.
- Per-role runtime containers and UI routing for Research Assistant and Interview Analyst, automatic balanced provider routing across Ollama Cloud and Fireworks.ai, and role/thread checkpoint isolation remain accepted implementation scope, not newly deferred future candidates.
