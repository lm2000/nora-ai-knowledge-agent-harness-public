# Evaluation

[Home](../README.md) · [Roadmap](../Plan.md) · [Current validation](VALIDATION.md)

Separate application contracts, retrieval relevance and generated-answer quality. For example, a valid MCP response establishes a protocol result; a useful answer also needs the right passages and sound reasoning.

| Work | Result | Scope |
| --- | --- | --- |
| [Shared-source validation](VALIDATION.md) | Local contracts, UI build and real BGE/MCP smoke pass | Synthetic data; model double for agent tests; three real-embedding questions |
| [Embedding comparison](embeddings/README.md) | BGE encoded this CPU workload faster and used less memory than Qwen | Historical: 17 excerpts and three provisional queries |
| [Retrieval pilot](targeted-research-pilot/README.md) | Initial Hit@5 of 3/6 | Historical: 91 documents, 481 points, six development questions |
| [Fixed-query improvement](targeted-research-pilot/improvement/README.md) | Dense + BM25 fusion reached Hit@5 of 5/6 | Historical: same small development set; different lexical implementation |
| [Private regression](regression/README.md) | September 14 repeat: Hit@1, Hit@5 and MRR@5 of 1/6 | Failed baseline; labels and misses still need diagnosis |
| [Routing contracts](../setup/model-routing.md) | Sync/async, tool, stream and failure behavior pass | Deterministic doubles; no quality or spending result |
| [Multi-turn plan](Multi-turn%20Evaluation.md) | Scenarios and component criteria defined | Representative dataset, answer judging and aggregation remain open |

The [synthetic fixture](../examples/queries.json) and [smoke script](../scripts/synthetic_smoke.py) are public reproduction inputs. Private questions, source texts, provider outputs and raw operator receipts are preserved outside the distribution.

The next quality task is to review expected documents alongside returned passages, preserve existing results and build a representative held-out set. Corpus size or a preprocessing edit alone does not diagnose a score change.

LangSmith remains selected for future tracing and evaluation; Harbor is a later task-evaluation candidate. No external trace or dataset connection is required by the local source checks.
