# Multi-turn evaluation plan

[Evaluation index](README.md) · [Requirements](../architecture/Requirements.md) · [Services](../setup/containers/README.md)

Example: the user asks for an Atlas project handover brief, corrects the project name, then supplies the date. Nora should apply the correction, retain relevant context and continue the same task—not repeat the earlier assumption.

This page plans application evaluation. The completed [retrieval experiments](README.md) test a smaller boundary. LangSmith tracing/evaluation and Studio are selected but not configured; no application dataset upload, trace export or multi-turn run is claimed.

## Nora scenarios and expected criteria

| Scenario | Expected behavior |
| --- | --- |
| Project handover follow-up | Retain the chosen target and filters; replace them when the user changes the target |
| User correction | Apply corrected names, dates or intent without reintroducing the old assumption |
| Clarification/resume | Ask for needed input and continue the same task |
| Correctness/comparison | Use expected facts and relevant text; distinguish disagreements and gaps |
| Partial source failure | Explain unavailable coverage rather than treat failure as empty results |

Normal Nora answers contain no citations, source links/cards or internal IDs. Internal evidence/IDs remain inspectable for maintenance and evaluation. Source preparation does not generate summaries.

## Conversation fixtures

Prepare reviewed examples with ordered `messages`, scenario ID, selected context, bounded source/tool fixtures and expected facts or clarification—not one mandatory exact sentence. Include correction and failure variants.

Record fixture version, model/prompt/tool settings, assessment method and per-criterion results. Select synthetic or explicitly chosen existing material; this plan does not collect or transfer data. Review rubric/coverage before setting thresholds.

## Small end-to-end validation scenario

Later choose three to five available documents with known passages. Record source/version/internal IDs and expected facts. Use working copies for update/deletion variants; keep originals intact.

| Stage | Expected check |
| --- | --- |
| Manual preparation | Separate operator job creates prepared GCS records and Qdrant vectors; no conversational dispatch |
| Filtering | Exclude unusable, duplicate, system and repeated-boilerplate fixture variants; retain headings/substance; generate no context summary |
| First question | UI → Deep Agent in Coordination → MCP Retrieval → evidence → correct plain answer |
| Comparison/gap | Combine supported facts across fixtures; explain an absent fact |
| Client reuse | Equivalent-permission Nora/other MCP client queries use the same knowledge without duplicate indexes; exact wording need not match |
| Correction/failure | Same-task continuation, corrected context, bounded retries and saved state for later resume after unavailability |
| Manual refresh | Add/change working fixtures; replace stale fragments without reprocessing unchanged material |
| Removal/outage | Remove confirmed-deleted fragments from active search; do not treat a temporary outage as deletion |

Capture fixture versions, operation IDs, component outcomes and retry/resume evidence. Test restricted-client access separately. Full reindex is a separate test. Test PostgreSQL crash/restart and clean-target restore against the implemented checkpointer.

## Planned LangSmith Playground workflow

The supplied [multi-turn guide](https://docs.langchain.com/langsmith/multiple-messages) offers three starting points: a traced LLM call, a dataset of message lists, or manual messages. Match the prompt's Messages List variable to the input key, such as `messages`.

Hold examples fixed while varying prompt/tools/output schema. Inspect manually first, then add repeatable checks. This evaluates the selected model call; it does not recreate the distributed application.

## Separate evaluation layers

| Layer | Scope |
| --- | --- |
| LLM call / Playground | Prompt, history, tool configuration and output schema |
| End-to-end Nora | UI, MCP permissions, retrieval, plain answer, checkpoints, clarification/resume, remote failures, cancellation and duplicate/late results |
| Harbor task trial | Complete task outcome through an adapter and explicit test environment |

One layer does not substitute for another. Local retrieval metrics likewise say nothing about UI or persistence.

## Planned Nora composite evaluator

A Nora-specific composite combines independently inspectable criteria. It is a design, not a claim of an implemented/native class.

| Criterion | Assessment |
| --- | --- |
| Answer correctness | Material facts match fixtures/evidence; no prohibited user-facing source metadata |
| Task completion | Required information and gaps are addressed |
| Multi-turn continuity | Relevant context and user corrections survive |
| Retrieval relevance | Evidence relevance/coverage matches reviewed judgments |
| Tool/workflow correctness | Correlation, inputs/results and transitions are correct |
| Recovery | Clarification/resume, retries, partial failures, cancellation and duplicate/late-result behavior |

Retain component scores, evidence and reasons alongside the aggregate. Weights, aggregation, thresholds and missing/not-applicable handling remain open. Track latency/cost separately.

Use deterministic checks for schemas, IDs and observable transitions. Semantic criteria start with human review; optional model judgment must be calibrated against reviewed examples and identified in results. Call-level fixtures assess only what that call exposes; workflow/recovery criteria need end-to-end evidence.

## Future evaluation approaches

- **Summary evaluation:** aggregate across an experiment/dataset, with explicit denominators. This does not mean source-summary generation.
- **Pairwise evaluation:** compare variants for the same input; allow ties, preserve reasons and account for output-order bias.
- **Harbor / Terminal-Bench:** assess suitable task/environment behavior, not a replacement for Nora's evidence and multi-turn criteria. Task version/selection and adapter fit remain open.

[Evaluation approaches](https://docs.langchain.com/langsmith/evaluation-types#summary-evaluators) · [Pairwise guide](https://docs.langchain.com/langsmith/evaluate-pairwise) · [Harbor](https://www.harborframework.com/docs) · [Terminal-Bench](https://www.tbench.ai/).

### Harbor integration options

The [integration guide](https://docs.langchain.com/langsmith/harbor-integrations) describes independent choices:

| Integration | Boundary |
| --- | --- |
| LangSmith results plugin | Records trials, feedback, tokens/cost as experiments; full agent traces need instrumentation |
| Official LangGraph adapter | Candidate for a LangGraph/Deep Agents graph inside a trial; Nora compatibility needs assessment |
| LangSmith sandbox environment | Optional trial hosting, not required merely to record results |

A sandboxed graph does not automatically test Nora's separate workers, external knowledge stores and persistence. Define accessible dependencies and the intended boundary; consider one small local task with a clear verifier before a benchmark. Tutorial providers and sandbox hosting are not Nora selections.

## Next implementation step

Specify a compact handover-conversation fixture and rubric, map each criterion to its evaluation layer, then wire repeatable tests to the existing application entrypoints. Deployment mode/region/plan, judge models, aggregation and thresholds remain open. No integration is configured by this document.
