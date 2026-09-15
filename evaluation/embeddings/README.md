# Embedding comparison

[Evaluation](../README.md) · [Results](RESULTS.md) · [Method](PROTOCOL.md)

This September 2026 CPU experiment compared BGE base English v1.5 with Qwen3 Embedding 0.6B. BGE was faster and used less process memory on the measured workload; it was subsequently selected for Nora. The small provisional relevance set did not establish a quality winner.

## Inspect the result

Read [RESULTS.md](RESULTS.md) for measurements and [PROTOCOL.md](PROTOCOL.md) for model pins, pooling, timing and metric definitions. The 17 excerpts and three diagnostic queries came from private project material. Aggregate results can be read without redistributing those inputs.

## Reproduction scope

The original comparison runner and private fixtures are preserved outside the public release. Its aggregate measurements remain historical. The shared [real retrieval smoke test](../../scripts/synthetic_smoke.py) provides a fictional BGE/Qdrant/MCP reproduction route; it does not reproduce the original BGE-versus-Qwen experiment.
