# CPU embedding results

[Method](PROTOCOL.md) · [Runner guide](README.md) · [Validation](VALIDATION.md)

The run completed on September 5, 2026 using 17 English excerpts and three provisional queries. BGE encoded this small document workload about 4.71 times faster than Qwen and used less process memory. This informed Nora's later BGE selection; it did not establish superior retrieval quality.

## Speed and memory

| Measurement | BGE base en v1.5 | Qwen3 Embedding 0.6B |
| --- | ---: | ---: |
| Document throughput | 12.87 excerpts/s | 2.73 excerpts/s |
| Individual-query median | 27.8 ms | 131.0 ms |
| Individual-query p95 | 44.1 ms | 164.5 ms |
| Sampled peak process RSS | 879–890 MiB | 2,998–3,781 MiB |
| Vector dimensions | 768 | 1,024 |

Environment: Apple M4 Pro, macOS, CPU float32, four PyTorch intra-op threads and one inter-op thread; Python 3.12.12, torch 2.6.0 and transformers 5.16.0. Workers ran in BGE/Qwen/Qwen/BGE order in separate processes, with warmup excluded and three repeats per worker.

Throughput divides 17 by the median of six corpus durations per model. Query statistics use 18 samples per model; nearest-rank p95 is imprecise with so few observations. Timings include tokenization, inference, pooling and normalization; document timing also includes concatenation. Downloads, loading and warmup are excluded.

Memory was sampled every 20 ms after imports through loading and encoding. It is process RSS, not weight size or an exact allocation peak. Background workloads were left running. These figures do not establish Linux host or cloud capacity.

## Diagnostic relevance

| Metric over three provisional queries | BGE | Qwen |
| --- | ---: | ---: |
| Recall@1 | 0.667 | 0.667 |
| Recall@3 | 1.000 | 1.000 |
| Recall@5 | 1.000 | 1.000 |
| MRR@10 | 0.778 | 0.833 |

The designated relevant ranks were 1/3/1 for BGE and 1/2/1 for Qwen. One question accounts for the MRR difference. Repeated runs gave the same rankings, but labels were provisional and not an exhaustive human relevance assessment. A supporting excerpt's presence does not make it the only relevant document.

All inputs fit without truncation; maximum tokenized lengths were 183 for BGE and 166 for Qwen, including prompts/special tokens. The experiment did not test long-context behavior or inputs near the 512-token ceiling.

## Reproduction limits

The original private receipts record model/input hashes, raw samples and hardware details. This public summary preserves aggregate results and their method without publishing source excerpts or operator paths. A shareable rerun needs reviewed, redistributable fixtures and the pinned environment. A broader held-out comparison should precede a quality-based model change.
