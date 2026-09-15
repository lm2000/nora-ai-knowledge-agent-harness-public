# Qdrant

[Services](README.md) · [Retrieval](knowledge-retrieval.md)

Qdrant stores named dense and lexical vectors with chunk text and minimal document metadata. Retrieval queries it; explicit administration commands import prepared bundles.

[Root Compose](../../compose.yaml) pins Qdrant 1.19.1 by manifest digest, mounts a named volume and requires an API key. All application targets share this service; it publishes no host port, and the admin profile imports and verifies prepared data over the internal service network. The [shared importer and verifier](../../src/nora/indexing.py) validate representation, file hashes, point IDs, vector shape/normalization and document integrity before an import. There is no separate host-specific Qdrant bundle.

Repeating an identical point set is supported. An existing collection with different points or a different representation is preserved and rejected; select a new collection for changed data. Verification checks every payload and samples stored dense vectors. Incremental replacement/deletion and atomic collection alias swaps remain future work.

Embedded-Qdrant tests and the real-BGE smoke test pass. An isolated ARM Linux container trial also verified containerized import, payload checks and vector sampling. Rebuilding Qdrant from a prepared bundle remains the intended restore path; Qdrant-specific snapshot/restore and other host architectures were not tested. [Validation](../../evaluation/VALIDATION.md) records the scope.


In the selected target, Qdrant keeps its own container and volume. Shared Retrieval MCP performs searches; the separate manual index import/update worker owns writes. Full prepared documents remain in the dedicated GCS bucket in the selected target (local filesystem in current development), distinct from the search index.
