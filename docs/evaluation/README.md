# Evaluation

[Home](../../README.md) · [Roadmap](../Plan.md) · [Validation index](VALIDATION.md#validation-index)

Evaluate application behavior, retrieval relevance and artifact quality
separately. For example, a valid MCP response establishes a protocol result;
a useful Atlas briefing also needs the right evidence and every release
prerequisite.

![Where question answering, ingestion and artifact review fit.](../architecture/diagrams/harness-workflows.gif)

[Local browser version](../architecture/diagrams/harness-workflows.html)

| Work | Result | Scope |
| --- | --- | --- |
| [Documentation review — 2026-10-25](VALIDATION.md#architect-and-technical-writer-follow-up--2026-10-25) | Recorded link, diagram and release-manifest checks | Documentation-only; no new application behavior or deployment |
| [Shared-source validation](VALIDATION.md#checked-locally) | Local contracts, UI build and real BGE/MCP smoke pass | Synthetic data; model double for agent tests; three real-embedding questions |
| [Embedding comparison](embeddings/README.md) | BGE encoded this CPU workload faster and used less memory than Qwen | Historical: 17 excerpts and three provisional queries |
| [Retrieval pilot](targeted-research-pilot/README.md) | Initial Hit@5 of 3/6 | Historical: 91 documents, 481 points, six development questions |
| [Fixed-query improvement](targeted-research-pilot/improvement/README.md) | Dense + BM25 fusion reached Hit@5 of 5/6 | Historical: same small development set; different lexical implementation |
| [Private regression](regression/README.md) | September 14 repeat: Hit@1, Hit@5 and MRR@5 of 1/6 | Failed baseline; labels and misses still need diagnosis |
| [Routing contracts](../setup/model-routing.md) | Sync/async, tool, stream and failure behavior pass | Deterministic doubles; no quality or spending result |
| [Multi-turn plan](Multi-turn%20Evaluation.md) | Scenarios and component criteria defined | Representative dataset, answer judging and aggregation remain open |

The [synthetic fixture](../../examples/queries.json) and [smoke script](../../scripts/synthetic_smoke.py) are public reproduction inputs. Private questions, source texts, provider outputs and raw operator receipts are preserved outside the distribution.

The next quality task is to review expected documents alongside returned passages, preserve existing results and build a representative held-out set. Corpus size or a preprocessing edit alone does not diagnose a score change.

LangSmith is an optional future tracing route. Local source checks do not require
an external evaluation service.

## Judge preparation and artifact review

[Artifact evaluation and revision](../workflows/artifact-review/README.md) first
prepares versioned judge definitions from role/domain research and relevant
sources. Harbor tasks and datasets form the NIS Judge Registry. The coordinator
then selects judges and execution/model routes for a frozen artifact.

![Judge feedback returns to the coordinator, then Synthetic Owner and Real Owner decisions govern the two revision loops.](../architecture/diagrams/artifact-review-flow.gif)

[Local browser version](../architecture/diagrams/artifact-review-flow.html)

The Synthetic Owner scores the result and recommends accept or reject. Work
below the configured threshold returns for revision; qualifying work goes to
the Real Owner for approval or requested changes. Lessons improve later briefs
and judge definitions. Keep evidence and rubric versions comparable.

The guide owns this design and its [judge preparation](../workflows/artifact-review/README.md#prepare-the-judges),
route boundaries and two feedback loops. Its [Atlas example](../workflows/artifact-review/README.md#local-example)
is the existing saved-response replay, with explicit decisions and ordinal
scores rather than automatic score gating.

## Answer-quality investigations

Dated client and service outcomes live in [deployment status](../setup/private-deployment/STATUS.md).
The October 6 investigation included incomplete preparation answers, failed
repairs and useful local corrections. Those development trials do not estimate
production accuracy. The [historical investigation](VALIDATION.md#historical-answer-quality-investigation--2026-10-06)
retains its original results and limitations.

Current work is to separate source selection, answer completeness, follow-up
behavior and execution failures, then evaluate them on reviewed held-out cases.
See the [roadmap](../Plan.md) for the complete project sequence.
