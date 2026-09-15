# Knowledge Retrieval

[Services](README.md) · [Data contract](../../data/Source%20Inventory.md)

Retrieval exposes two tools: search for passages and read more of a selected document. Coordination uses this boundary rather than accessing the index or prepared store directly.

## Selected target: shared Retrieval and BGE

Retrieval remains a separate shared MCP container for all agent roles and intended clients. It calls the **shared BGE server container** for query encoding, queries Qdrant for passages and reads full prepared documents through the local/GCS document-store interface. Agent roles use MCP rather than calling BGE or Qdrant directly.

The separate batch embedding worker is BGE's other caller. Preserve the pinned model revision, normalized vector dimensions and complete input limit, with query instructions applied only in query mode. Implement bounded batch concurrency and backpressure so imports cannot consume all interactive encoding capacity. [The inventory](README.md#shared-bge-capacity) owns the capacity policy.

The current encoder below is a real local model implementation, not a network service. A BGE server API and a Retrieval client adapter are required for D167.

## Current implementation

### Search

The shared [BGE HTTP service](../../src/nora/bge_server.py) loads the pinned `BAAI/bge-base-en-v1.5` revision once and exposes `/encode` for query and document modes. It applies bounded batch size, per-mode concurrency limits and a small queue with backpressure so batch imports cannot starve interactive queries. The Retrieval MCP service calls the BGE service through the [HTTP client](../../src/nora/bge_client.py) instead of loading the model itself.

Qdrant fuses dense search and a hashed lexical term-frequency representation with reciprocal-rank fusion. This lexical path is not full BM25. Results are distinct by document, limited to six documents and 2,600 characters per returned passage. [Shared representation](../../src/nora/common.py).

### Read and access

A SHA-256 document ID resolves local prepared text or a generation-pinned GCS object. Both stores verify content hashes. A read returns at most 8,000 characters with a bounded offset; internal IDs support maintenance and are not normal citation cards.

The [MCP server](../../src/nora/retrieval.py) serves streamable HTTP at `/mcp`. Tool calls and `/health` require a bearer credential. MCP also checks allowed HTTP Host values and request size. Readiness compares the active release's collection point count with its prepared coverage; it does not measure relevance. Activation advances the `current` release symlink atomically in local mode, or updates a generation-conditional `gs://bucket/object` cloud pointer in GCS mode; Retrieval resolves the active release on each request. Search and read within one answer turn pin the same release via the `X-Nora-Release` header so a concurrent activation cannot split search from read.

[Document stores](../../src/nora/documents.py) share one read contract. Retrieval does not run ingestion or write conversation checkpoints. [The real synthetic smoke test](../../scripts/synthetic_smoke.py) exercises BGE, Qdrant and MCP together. Per-client credentials, source-level authorization and deployment of the dedicated GCS prepared-document bucket with real credentials remain future work.
