# Manual ingestion

[Run an update](knowledge-base-update-checklist.md) · [Job containers](../../setup/containers/ingestion.md) · [Data contract](../../data/Data%20Contract.md)

Ingestion prepares selected documents for retrieval when an operator starts a run. For example, add a revised project decision while preserving its original bytes and the retained knowledge corpus. Questions and folder changes do not start ingestion jobs.

Use the [operator checklist](knowledge-base-update-checklist.md) to select the installation's activation procedure. This guide explains artifacts, assembly and activation mechanisms; the [container guide](../../setup/containers/ingestion.md) owns images, entrypoints and mounts.

## Ingestion stages

![Selected sources pass through conversion, preparation, embedding, import and verification before activation.](../../architecture/diagrams/manual-ingestion.gif)

[Local browser version](../../architecture/diagrams/manual-ingestion.html)

| Stage | Input | Durable output |
| --- | --- | --- |
| Conversion | Read-only selected originals | `extracted/manifest.json`, extracted text/assets and source metadata |
| Preparation | Completed extraction | Full documents with content hashes, manifest, `coverage.json` and chunks with stable IDs, headings, text and categories |
| Embedding | Completed prepared chunks | Vectors, pinned model/encoding metadata and `job-embed.json` |
| Import and verification | Complete embedded bundle | Fresh Qdrant collection and `job-import.json` |

Each temporary worker consumes completed artifacts and exits. Artifacts survive the workers; ingestion owns its job reports independently of PostgreSQL conversation checkpoints. [The accepted decision](../../Decisions.md#ingestion-and-state) records this boundary.

## Processing contract

Preserve original bytes, substantive text, headings and provenance. The conversion job accepts PDF, DOCX, HTML, PPTX, XLSX, Markdown and TXT. Markdown and TXT use direct readers; the other formats use Docling. Preparation can read JSON text directly, but JSON is not accepted by the four-job conversion entrypoint. Deterministic preparation accounts for unsupported, empty and unreadable inputs, omits exact duplicates and obvious metadata/boilerplate, and does not use LLM summaries or rewrite source meaning.

Chunk within the embedding model's complete input limit. The current bundle retains document content hashes, chunk IDs and model configuration with the vectors. Token offsets are used internally for splitting; persisted chunk offsets and individual chunk-content hashes are not part of the current output. Embedding and interactive Retrieval use the same shared BGE service, with matching revision, dimensions and normalization and the appropriate document/query encoding modes. Bound batch load to preserve interactive capacity; see [shared BGE capacity](../../setup/containers/README.md#shared-bge-capacity).

Conversion names each extracted Markdown file by the SHA-256 of its complete
relative source path, including the extension. The extraction manifest maps
that filename back to the original path and source checksum. This keeps
`report.md` and `report.txt`, or `team/report.md` and `team__report.md`, distinct.
Prepared document IDs remain content-based; exact duplicate text is still
deduplicated by preparation.

Any failed conversion stops the batch with a nonzero exit status after saving
its manifest, including when every source fails. Preparation independently
rejects failed-source reports, missing converted files and duplicate targets,
including in older manifests. Correct the failed input and rerun into a new
extraction directory; do not remove failure records to accept a partial batch.
Unsupported formats remain explicitly reported skips. Conversion failure does
not import a collection or advance the active release.

A vector file alone is not an imported index. Import independently verifies point identity/counts and the matching document manifest. Each stage validates its input artifacts. Interrupted-run recovery and concurrent writers remain unverified.

## Add documents while retaining an existing bundle

The Docker `scripts/knowledge-update` launcher creates a complete release from
its selected input. To add documents without losing retained knowledge, prepare
and embed a delta first, then assemble it with an immutable complete base. The
[checklist](knowledge-base-update-checklist.md#2-prepare-the-complete-release)
gives the ordered commands.

From the repository root, using complete embedded bundles:

```bash
nora assemble ./retained/prepared ./delta/prepared ./merged/prepared \
  --collection nora_merged_v2
nora job import ./merged/prepared
```

Assembly produces a new self-contained bundle and `job-assemble.json`; it does not encode, connect to Qdrant, import or activate. The following import creates and verifies the merged collection. Activation is a separate step.

Assembly preserves base documents, chunk rows/order, categories and associated vectors, then appends delta content. Identical documents are retained once only if their chunks, metadata and vectors agree exactly. Conflicting identities, corrupt inputs, differing representations/vector dtypes, output inside an input and existing output directories are rejected. Use immutable inputs and one writer.

Coverage and available job records remain under `provenance/base/` and `provenance/delta/`. Counts/checksums are recalculated and the merged output is validated; assembly does not invent historical prepare/embed reports.

**Version behavior:** this is additive, not replacement or deletion. Older and newer content-addressed versions can both appear in retrieval. Preserve source dates and identity. For replacement or removal, prepare a fresh bundle from the complete desired source set and import into a fresh collection.

## Backups and activation

Before changing the active release, take database backups using the installation's tools: Qdrant for the index and PostgreSQL for conversations. Save the matching prepared-document bundle and effective deployment configuration as well; the full document text is outside the databases. Record completed backup locations and checksums in the private run record. Retaining the base bundle is also required for additive assembly.

Prepared documents and their matching search collection advance together. Import does not change the running service's active selection.

| Retrieval configuration | Activation |
| --- | --- |
| Literal local release-directory pin | Explicit deployment overlay; recreate only Retrieval |
| Local `current` symlink | Atomically replace the symlink after verification |
| Generation-pinned GCS pointer | Publish the release, then conditionally update the pointer |

A literal-pin installation does not follow `current`. Its [activation procedure](knowledge-base-update-checklist.md#4-activate-retrieval) requires the complete installation Compose file set, including applicable Coordination repair overlays. Database backups do not change the activation mechanism.

For pointer-following installations, Retrieval resolves the selection per request and honors `X-Nora-Release` so search and read within a turn use the same release. GCS/Qdrant writes are not transactional: advance the pointer only after import verification. A failure after a cloud pointer write may leave local history/symlink records stale and requires reconciliation. Record failed acceptance as incomplete and investigate the failed check.

## Operator commands

For a complete source set, run the Docker launcher from the repository root.
Use the application's existing Compose project and complete file set. For the
fresh source installation in [setup](../../setup/README.md#run-the-application):

```bash
export NORA_COMPOSE_PROJECT=nora
scripts/knowledge-update ./complete-source-set .runtime/releases nora_complete_v2
```

The launcher uses four temporary job containers, then activates the verified
release selection. Local mode replaces `current` under the supplied releases
root; GCS mode adds publication/activation through `admin`. Keep the root mounted
where Retrieval expects its releases. A literal deployment pin is not rewritten.
Originals remain unchanged; use a fresh collection name for each changed dataset.

**Host alternative:** `nora knowledge-update <source> <releases> --collection
<new-collection>` runs the same stages in one host process. Preparation uses
the pinned local BGE tokenizer from `NORA_MODEL_PATH`; embedding uses the
shared BGE HTTP service. It does not initialize local model weights for
inference. Install the embedding extra and create the verified cache as shown
in [development setup](../../setup/README.md#test-real-retrieval); add the
conversion extra for Docling formats. A missing or invalid tokenizer cache
stops the command before release artifacts are created.

The host must reach the configured BGE and Qdrant endpoints and supply their
credentials; Compose-internal service names are not automatically host routes.
Use the same complete-source, backup and activation requirements as the Docker
launcher. Local regression coverage uses synthetic embeddings and an in-memory
index; it does not establish a live host update or deploy this repair. See the
[validation record](../../evaluation/VALIDATION.md#ingestion-reliability-repair--2026-10-29).

## GCS publication reference

This reference describes GCS-pointer activation. The dated deployment record owns the installation's selected mode. Originals are retained in the installation's source bucket; prepared documents and the pointer belong in the dedicated prepared-data bucket. Bucket/IAM setup and live cutover are separate from ordinary content updates.

Before cutover, verify a keyless publisher can create releases and conditionally update the intended pointer, while Retrieval has read-only access. The pointer bucket must match `NORA_GCS_BUCKET`; the prefix must be nonempty. Configure Retrieval to follow the cloud pointer and save the effective deployment configuration with the backups.

From the deployment-host repository checkout, with a complete desired source set:

```bash
export NORA_COMPOSE_PROJECT=<deployment-compose-project>
export NORA_COMPOSE_FILES='<complete current -f file set from the private operating record>'
export NORA_GCS_PROJECT=<gcp-project>
export NORA_GCS_BUCKET=<prepared-bucket>
export NORA_GCS_PREFIX=<prepared-release-prefix>
export NORA_GCS_POINTER=gs://<prepared-bucket>/<pointer-object>
export NORA_GCS_PUBLISHER_CREDENTIALS_FILE=<keyless-adc-file>

scripts/knowledge-update \
  <complete-source-staging-directory> \
  <local-release-staging-root> \
  <new-qdrant-collection>
```

Expected result: four completed job stages, a published release and generation-pinned manifest, then a conditional pointer update. The keyless ADC file is mounted read-only into the activation container only. A service-account private key is rejected. The launcher also supports a configured publisher service-account identity; see its [source](../../../scripts/knowledge-update).

Publication writes `<prefix>/<release-tag>/docs/<sha256>.txt` and `<prefix>/<release-tag>/manifest.json` in the selected bucket. Read the pointer back with its generation and pinned manifest; compare identities/counts and check Qdrant, search, a direct read, an answer and conversation reload before acceptance. Save actual results in the private run record.

## Verification commands

These are development checks, not a production knowledge update. From the repository root in the configured environment:

```bash
PYTHONPATH=src python scripts/verify_conversion_image.py
NORA_PYTHON="$(command -v python)" scripts/docker_acceptance.sh
```

The first checks conversion against a synthetic DOCX. The second builds and runs an isolated Docker project with a deterministic BGE double, exercises the four-job launcher, search/read and agent answer across MCP, and exercises its existing test-only rollback path before cleaning up its own resources. Neither establishes current production quality or live GCS cutover.

## Incremental behavior still to complete

Identical imports and additive assembly are supported. Replacement/deletion, interrupted-batch recovery and concurrent writers remain unverified. A changed point inventory needs a new collection without overwriting the running index. A full rebuild handles a complete desired dataset; it does not establish resumability or safe concurrent writes. See [deployment evidence](../../setup/private-deployment/STATUS.md) for dated live results.
