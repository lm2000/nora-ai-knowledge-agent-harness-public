# Local retrieval pilot

[Evaluation](../README.md) · [Fixed-query improvement](improvement/README.md)

The September 5, 2026 pilot indexed one private research archive locally to test deterministic chunking, BGE encoding and Qdrant retrieval. It was an embedded database experiment, not a shared MCP service or full agent test.

## Dataset and method

The archive contained 106 manifest references and 91 unique documents. Heading-aware chunking used 400-token windows with 50-token overlap, source character offsets and stable identifiers. It produced 481 points using 474 distinct cached text vectors.

BGE base English v1.5 used pinned revision `a5beb1e3e68b9ab74eb54cfd186867f64f240e1a`, normalized 768-dimensional CLS embeddings and cosine distance. The [embedding protocol](../embeddings/PROTOCOL.md) records the compatible model configuration. The maximum chunk length including special tokens was 403.

## Recorded result

| Measure | Result |
| --- | ---: |
| Initial indexing | 140.79 seconds |
| Cached rerun including six queries | 2.23 seconds |
| Hit@1 | 3/6 |
| Hit@5 | 3/6 |
| MRR@5 | 0.5000 |

The six source-derived questions comprised four English and two Russian queries. Reopened-client checks confirmed point/document counts, cached-vector correspondence and that each chunk was a source substring. These are integrity checks; the six development labels are not a held-out quality benchmark.

A later [dense + BM25 experiment](improvement/README.md) improved the same question set without changing sources, embeddings or labels.

## Reproduction scope

The original runner, private chunks, cached vectors and question fixtures are preserved outside the public release. Aggregate measurements above describe that historical experiment. They are not a result for the current shared source.

Use the [current synthetic smoke test](../../setup/README.md#test-real-retrieval) to exercise the shared BGE/Qdrant/MCP path. It uses three fictional questions and does not reproduce the earlier pilot or its BM25 comparison.
