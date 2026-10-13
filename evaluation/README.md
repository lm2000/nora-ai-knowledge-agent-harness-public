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


## One-assistant integration checks planned

The single-assistant candidate has bounded direct/gateway, UUID continuity, restart and Codex/OpenClaw conversational evidence in [deployment status](../setup/private-deployment/STATUS.md). Those passes establish the exercised client paths, not representative answer quality. The October 6 preparation answer passed its dated acceptance check, but a later exact-question repeat omitted requested preservation fields. The eight-case quality pilot recorded four passes after correcting four cloud-judge false positives; source freshness, source selection, answer coverage and generation completeness need improvement. These development questions and an uncalibrated model-assisted review do not estimate production accuracy. Owner review remains pending. See [execution progress](../Plan.md#execution-progress). Repeat affected client checks after interface changes, and retain passing historical evidence when behavior is unchanged. Repeated benchmarks and clean-server restoration remain later work in [the roadmap](../Plan.md).

The focused completion/shared-repair/owning-guide correction is implemented locally on October 6: 44 service/selector tests passed, with existing retrieval and logical model-call budgets. This is fixture verification; rollout and repeated live Q2/P4/follow-up acceptance remain pending. See the current [execution progress](../Plan.md#execution-progress).

The subsequent October 6 Coordination-only rollout failed the four-turn quality sample: Q2a/follow-up returned 503; Q2b passed at 83 words and P4 at 99 words. Empty repair generations hit the existing token cap and were rejected; untitled owning-passage identification and model-configuration synonyms need correction. This quality delta remains unaccepted and unpublished. See [deployment evidence](../setup/private-deployment/STATUS.md#focused-quality-correction-rollout-acceptance-failed--2026-10-06).

A subsequent local-only refinement recognizes distinctive untitled preservation contracts without treating broader ingestion headings as the owning guide, requests a returned-ID read for missing attribution/fields, and accepts pinned revision/dimensions/normalization with vectors. 56 focused service/selector tests passed; this refinement is not deployed or accepted through inference. See [current execution progress](../Plan.md#execution-progress).


Quality refinement rollout (2026-10-06): Coordination image `quality-refinement-20261006` / `sha256:920485192ed9cd35fc49b745458793055203c1271b3f188d4a4315b58fb7b5a4` is healthy; existing history/corpus/other services and limits retained. Three preparation turns produced one pass (78/100 words) and two HTTP 503 failures. Failed-turn checks exposed substantive-content synonym rejection and a follow-up repair missing deterministic/no-rewrite and explicit source identity. Quality remains unaccepted; publication and primary synchronization remain pending. No extra trials; prior passing storage comparison retained. Canonical Operations Guidance contains the dated receipt/report reference.


Local preparation follow-up correction (2026-10-06): 67 focused tests and saved failed-draft replay pass. Supported substantive-content/boilerplate-aside wording is accepted; related restatement guidance retains all six facts. Genuine omissions remain rejected. This correction is undeployed and unpublished; running image 92048519 remains healthy but unaccepted. Real-model follow-up compliance and publication/primary synchronization remain pending. See canonical Operations Guidance for the dated result.


Preparation follow-up rollout (2026-10-06): Coordination image `preparation-followup-20261006` / `sha256:ffed46272d5e0798a6308410c8e7cc8f9dcdc29f7fb22346a8da146ecb02684f` is healthy; history/corpus/other services/settings retained. Both fresh Q2 calls failed with HTTP 503; follow-up returned all six facts/attribution at 87/100 words with an unsupported exhaustive opening. Initial first generation exhausted its token limit before repair. Second failure remains undiagnosed after a latest-turn diagnostic mistakenly read the successful follow-up; that boundary deviation is recorded in canonical Operations Guidance. Repeated preparation quality remains unaccepted; no publication or primary sync occurred.


Isolated GPT-OSS:20b pilot (2026-10-06) stopped on its first failed preparation turn. Three searches exhausted retrieval before an owning-guide read; draft/source attribution were deficient and the repair returned empty with a normal stop. No production route change; remaining turns not run. Four distinct provider responses reported 18,949 prompt / 508 generated tokens, 10.291 seconds; billing unmeasured. Candidate quality is unaccepted. See current execution progress and canonical Operations Guidance for the private result reference.
