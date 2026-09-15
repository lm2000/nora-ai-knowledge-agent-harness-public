# Fixed-query retrieval improvement

[Original pilot](../README.md) · [Evaluation](../../README.md)

This September 5, 2026 experiment added lexical ranking to the same 91-document, 481-point pilot. Questions, expected labels, sources and embeddings remained fixed.

| Variant | Hit@1 | Hit@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| Original dense, five chunks | 3/6 | 3/6 | 0.5000 |
| Dense, five distinct documents | 3/6 | 3/6 | 0.5000 |
| Dense + BM25 fusion, distinct documents | 4/6 | 5/6 | 0.7222 |

## What changed

Exact dense ranking used the existing normalized BGE vectors. BM25 used `k1=1.5` and `b=0.75`; reciprocal-rank fusion used `k=60`. Zero-score lexical matches contributed nothing. Each document was represented by its best fused chunk. Ranking did not use expected IDs or supporting answer excerpts.

One named-role question improved from expected-document rank 9 to 3. One cross-language statistic question improved from rank 14 to 1. A broadly worded hiring question remained outside the top five; several documents could plausibly match its wording. The other three expected documents remained first.

These observations establish changed rankings on the fixed set, not their complete causal explanation. They do not prove that English BGE generally fails on Russian, that a source was missing, or that the ambiguous label should silently be changed.

## Limits

The six questions are development diagnostics. Keep their original result when adding reviewed labels or held-out examples. The current cloud server uses a hashed lexical representation, not this complete BM25 scorer, so this score is not a production benchmark.

## Reproduction scope

The original runner, private chunks, cached vectors and question fixtures are preserved outside the public release. Aggregate measurements above describe that historical experiment. They are not a result for the current shared source.

Use the [current synthetic smoke test](../../../setup/README.md#test-real-retrieval) to exercise the shared BGE/Qdrant/MCP path. It uses three fictional questions and does not reproduce the earlier pilot or its BM25 comparison.
