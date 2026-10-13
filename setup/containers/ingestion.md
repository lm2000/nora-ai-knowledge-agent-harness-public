# Document Processing packaging

[Services](README.md) · [Ingestion contracts](../../workflows/ingestion/README.md) · [Run an update](../../workflows/ingestion/knowledge-base-update-checklist.md)

Package an operator-run ingestion batch as temporary jobs. **Example:** conversion reads selected notes, preparation and embedding produce a complete bundle, and import verifies a new Qdrant collection before the operator selects it for Retrieval.

## Selected target packaging

Root Compose implements four separate job services under the `ingestion` profile. Each has its own entrypoint and completed input/output contract; each exits after its stage. [D167](../../Decisions.md#manual-ingestion-outside-conversations) and [D169](../../Decisions.md#manual-ingestion-outside-conversations) record the design. The [manual workflow](../../workflows/ingestion/README.md#selected-target-workflow) owns ordering and artifact semantics.

## Current implementation

| Service | Image | Entrypoint | Storage and service access |
| --- | --- | --- | --- |
| `job-convert` | `nora-conversion:local` with Docling extra | `nora job convert` | Originals read only; extracted artifacts persisted |
| `job-prepare` | Shared backend | `nora job prepare` | Extraction in; full documents and chunks out |
| `job-embed` | Shared backend | `nora job embed` | Prepared chunks in; shared BGE document encoding; vectors/reports out |
| `job-import` | Shared backend | `nora job import` | Complete bundle in; writes and independently verifies Qdrant |
| `admin` activation step | Shared backend | `nora activate` | In GCS mode, publisher access and retained local release storage |

Use the deployment's effective image overrides rather than assuming source defaults are its running image. See [Compose source](../../compose.yaml) and the installation's private operating record.

## Mounts and ownership

- Mount selected originals read only into conversion.
- Persist extraction, prepared full documents, chunks, vectors and job reports outside worker lifetimes. Local release storage and Qdrant are distinct; the full text is not reconstructed from the index.
- Keep model caches and PostgreSQL volumes separate from source/release storage. Ingestion owns job reports; conversation checkpoints do not own or schedule ingestion.
- Give embedding access to shared BGE and bound batch load; import owns Qdrant writes.
- For GCS publication, mount `NORA_GCS_PUBLISHER_CREDENTIALS_FILE` read only into `admin` only. Retrieval has reader access; job workers do not receive the publisher file. Keyless publisher identity configuration is separate from source data.

## Launchers and deployment selection

`scripts/knowledge-update` runs the four job containers, checks completed artifacts and stops on failure. `nora knowledge-update` is the host-only alternative. Both create a complete release from their input, so additions must use separate jobs and `nora assemble` to retain the base corpus. Assembly is a separate operator CLI step, not a fifth ingestion job service.

Without `NORA_GCS_POINTER`, the Docker launcher selects the release through local `current`. With it, the launcher uses `admin` to publish and conditionally advance the cloud pointer. The current private deployment pins Retrieval to a literal local directory and therefore needs a separate deployment overlay/recreation; follow the [operator checklist](../../workflows/ingestion/knowledge-base-update-checklist.md#4-activate-retrieval).

Set the installation's Compose project, complete file set, mounted paths and service configuration before running jobs. Preserve all current repair overlays during deployment operations. Questions and folder changes never trigger a batch. GCS cutover and its publisher/IAM setup remain separate deployment work.

`nora cache-model` manages the pinned embedding model cache. The split job entrypoints above define this workflow.
