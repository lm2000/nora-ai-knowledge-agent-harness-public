# Document Processing packaging

[Services](README.md) · [Manual workflow](../../workflows/ingestion/README.md)

Document Processing is a manually invoked batch. For example, an operator prepares a new set of project notes, imports them into a new collection, verifies it and then activates the new release atomically so Retrieval uses both the new prepared documents and the matching Qdrant collection. The previous release remains available for rollback.

## Selected target packaging

Use four separate, temporary job containers: **Docling conversion**, **deterministic preparation/chunking**, **batch embedding**, and **index import/update**. Each has a distinct entrypoint and input/output contract. They may share base images or libraries without sharing a running container. Job order, stage artifacts and failure behavior belong to the [manual workflow](../../workflows/ingestion/README.md#selected-target-workflow).

Mount originals read only into conversion. Persist extracted artifacts, full documents, chunks, vectors and reports outside worker lifetimes. Preparation writes full documents to the dedicated GCS bucket in the selected target; local filesystem storage is used for development and tests. The conversion stage is packaged in a separate image (`nora-conversion:local`) that installs the Docling extra; the other three job stages share the backend image. The batch worker calls the shared BGE server with bounded concurrency; the import worker owns writes to Qdrant and verifies before activation. Conversation runtimes do not own or schedule these jobs.

This packaging is selected in [D167](../../Decisions.md#selected-target-separate-runtime-and-job-containers) and refined by [D169](../../Decisions.md#accepted-implementation-choices-from-the-architecture-review); it has not been implemented in root Compose. Images, entrypoints, resource limits and mounts still need changes. The [service inventory](README.md) owns the complete container list.

## Current implementation

| Command / Service | Owner |
| --- | --- |
| `scripts/knowledge-update` | Host-side launcher that runs the four distinct job containers in order and activates the release |
| `nora knowledge-update` | Host-only operator command that runs the four jobs and activates the release ([jobs.py](../../src/nora/jobs.py)) |
| `nora job convert` / `job-convert` | [Docling adapter](../../src/nora/conversion.py) wrapper for selected originals |
| `nora job prepare` / `job-prepare` | Deterministic [normalization and chunking](../../src/nora/preparation.py) |
| `nora job embed` / `job-embed` | Batch embedding through the shared [BGE HTTP client](../../src/nora/bge_client.py) |
| `nora job import` / `job-import` | Shared [index import/validation](../../src/nora/indexing.py) |
| `nora cache-model` | Pinned [model cache](../../src/nora/embedding.py) |
| `nora prepare` | Legacy combined preparation and embedding (still available) |

Root Compose provides four distinct temporary job services under the `ingestion` profile. `job-convert` uses the dedicated `nora-conversion:local` image; the other three jobs use the shared backend image. The host-side `scripts/knowledge-update` launcher runs them in order, verifies each stage manifest, stops before activation on any failure, and activates the new release only after import/verify succeeds. Each job container exits after its stage; no persistent orchestrator is added. Preparation and embedding are split: `nora job prepare` produces chunks, `nora job embed` calls the shared BGE service, and `nora job import` writes and verifies the Qdrant collection.

When `NORA_GCS_POINTER` is configured, the launcher additionally performs the GCS publication and pointer activation step by running `nora activate` inside the existing `admin` container. The publisher credential file (`NORA_GCS_PUBLISHER_CREDENTIALS_FILE`) is mounted read-only into that single activation container and is not shared with Retrieval or the job containers. Without `NORA_GCS_POINTER` the launcher behaves exactly as before, writing only the local `current` symlink.

Input originals, prepared bundles, model caches and database volumes have distinct ownership. A batch never starts because a question arrived or a folder changed. [Setup](../README.md) owns commands; the [workflow](../../workflows/ingestion/README.md) owns lifecycle behavior.
