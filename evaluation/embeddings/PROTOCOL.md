# Comparison method

[Run instructions](README.md) · [Results](RESULTS.md)

## 1. Freeze the inputs

Compare both models on the same 17 English excerpts and three queries. Keep source paths, hashes and offsets. The original run corrected one invalid query/source reference before execution; its relevance labels remain provisional.

## 2. Use the pinned models

| Model | Revision | Pooling | Dimensions |
| --- | --- | --- | --- |
| Qwen3 Embedding 0.6B | `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3` | Last nonpadding token | 1024 |
| BGE base en v1.5 | `a5beb1e3e68b9ab74eb54cfd186867f64f240e1a` | CLS token | 768 |

Apply each model’s query instruction, no document instruction, and L2 normalization. Validate the complete tokenized input—including special tokens/prompts—against 512 tokens. Reject oversized inputs rather than truncating them.

## 3. Keep execution comparable

Use separate processes in BGE/Qwen/Qwen/BGE order: CPU float32, four intra-op threads, one inter-op thread, fixed seed, document batches of four and single-query batches. Exclude one document and one query warmup, then take three repeats.

## 4. Record measurements

Time tokenization, inference, pooling and normalization; document timing includes concatenation. Keep loading and warmup separate. Sample process RSS every 20 ms after imports through loading, encoding and retrieval; call it a sampled peak, not an exact allocation maximum.

Retain hardware/software versions, input/model hashes, timestamps, load averages and raw samples. Do not stop unrelated workloads; disclose their possible influence.

## 5. Calculate diagnostic retrieval scores

Use exact in-memory cosine search. Recall@1/3/5 averages the fraction of relevant documents retrieved. MRR@10 averages the reciprocal first-relevant rank within ten. Count/exclude unlabelled queries and store scores as `diagnostic_not_validated`.

## 6. Interpret the limits

Keep inputs and outputs unchanged after a run. Three unreviewed judgments cannot select a quality winner. A broader evaluation needs reviewed labels, varied questions and hard negatives. Long-context behavior and target-server capacity are not measured here.

Model references: [Qwen](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) · [BGE](https://huggingface.co/BAAI/bge-base-en-v1.5).
