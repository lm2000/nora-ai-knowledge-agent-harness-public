# Artifact evaluation and revision

[Workflows](../README.md) · [Evaluation](../../evaluation/README.md)

Improve an artifact through review, revision and owner approval. For example,
check an Atlas release briefing against its source plan, correct a missing
prerequisite and use that lesson in the next review brief.

## Atlas before and after

The fictional Atlas source requires a passing load test and a completed
rollback rehearsal. The draft mentions only the load test.

| Feedback | Owner decision | Result |
| --- | --- | --- |
| Include the rollback rehearsal | Accept: required by the source | Add it in v2 |
| Promise release will take five minutes | Reject: no source supports the timing | Keep timing unknown |
| Add an existing open-questions section | Already resolved | Keep one section |

**Before**

> Atlas release requires a passing payment-service load test.

**After**

> Atlas release requires a passing payment-service load test and a completed rollback rehearsal.

Release duration remains unknown; the existing open-questions section is retained.
The [local example](#local-example) replays saved synthetic reviews and records
explicit decisions. The design below separates judge preparation from review
execution; external execution and score-based revision are later implementation
work in the [roadmap](../../Plan.md).

## Prepare the judges

Research the review's role, domain and relevant sources before defining a judge.
Turn that research into a versioned persona, rubric, criteria, dataset and
examples. Keep source references and the reason for each criterion so a later
review can explain what changed.

Harbor tasks and datasets form the NIS Judge Registry. A registry entry defines
what a judge evaluates; it is separate from the model and execution route used
for a particular run.

![Research informs versioned judge definitions in the NIS Judge Registry.](../../architecture/diagrams/judge-registry.gif)

[Local browser version](../../architecture/diagrams/judge-registry.html)

| Example judge | Review perspective |
| --- | --- |
| CTO | Business value, constraints and technical risk |
| AI Architect | System boundaries, AI behavior and evidence |
| Hiring Manager | Role fit, clarity and supported claims |
| Senior Engineer | Correctness, implementation detail and maintainability |
| Domain Expert | Domain facts and task-specific standards |
| Synthetic Owner | Fit to the owner's documented needs and preferences |

These are role definitions, not claims that independent human experts performed
the review. Several roles using one model can produce correlated opinions.
Build the Synthetic Owner from sanitized analysis of relevant owner interactions
and preferences. Its recommendation supports the Real Owner's decision.

## Review and revise

The AI Coordinator selects judges and routes, gathers their feedback and manages
two feedback loops.

![The AI Coordinator aggregates judge feedback, uses the Synthetic Owner recommendation for revision, and brings qualifying work to the Real Owner for final approval.](../../architecture/diagrams/artifact-review-flow.gif)

[Local browser version](../../architecture/diagrams/artifact-review-flow.html)

1. Freeze the artifact, source evidence and task brief. Record the selected judge,
   rubric, criteria, dataset and example versions, along with each model route.
2. Execute the selected reviews. Keep each judge's findings, scores and supporting
   references separate, then let the coordinator aggregate them.
3. Ask the Synthetic Owner to score the result and recommend accept or reject.
   Below a configurable threshold, revise the artifact and evaluate it again.
4. When the score qualifies, bring the result and feedback to the Real Owner.
   The Real Owner gives final approval or requests changes. Requested changes start a
   second revision and re-evaluation loop.
5. Retain useful lessons for the next brief and judge definitions. Record their
   new versions; this does not train a model automatically.

Harbor Hub provides a task/results route; Hugging Face Inference Providers
provides judge-model access. The coordinator selects these routes separately.
Harbor does not forward requests to Hugging Face. Task orchestration, model
routing and final owner approval have different responsibilities.

Check every finding against the source and current artifact. A valid report or
higher score does not establish an improvement. Missing personal evidence stays
a question for the person concerned.

## Compare versions and carry lessons forward

Keep the artifact inputs, evidence and rubric versions comparable across a
revision. A changed rubric starts a new comparison; keep earlier results with
their original versions. Review the revised artifact as well as the scores.

For Atlas, the next brief can add this owner-authored lesson:

> Check every release prerequisite against the source plan. Do not infer release
> duration; flag missing timing as unknown.

The supplied Atlas v1/v2 packets keep the same task, criteria and rubric. They
illustrate a comparable revision; they do not store or apply this next brief.

Retrieval quality asks whether search and read found the right evidence.
Artifact quality asks whether the output uses that evidence accurately and
serves its task. Keep those evaluations separate.

## Local example

The CLI validates captured responses and records owner decisions. Its Atlas
packet uses one Evidence reviewer, `scripted-reviewer` and `synthetic-fixture`.
It makes no model or external-service requests and has no automatic acceptance
threshold or revision loop. Earlier external-provider and Harbor pilots in
separate preparation projects do not establish live execution for this harness.

Run commands from the repository root with a new output directory. For the
complete two-version example:

```bash
nora review-example --output .private/atlas-review-cycle
```

Expected result: saved reviews, decisions, both artifact versions and a summary.
The accepted prerequisite is added; unsupported timing is rejected; the existing
section is not duplicated.

To inspect the same cycle step by step:

```bash
nora review-replay --packet examples/artifact-review/packet.json \
  --response examples/artifact-review/response.json --http-status 200 \
  --output .private/atlas-review
```

Expected result: frozen inputs, readable feedback and `requires_owner_review`.
Then record the decisions and explicitly authored next version:

```bash
nora review-revision --review .private/atlas-review \
  --decisions examples/artifact-review/decisions.json \
  --next-packet examples/artifact-review/packet-v2.json \
  --output .private/atlas-revision
```

Expected result: decisions, the supplied artifact and `revision_recorded`.

### Saved-review contract

- **Frozen packet:** task, criteria, rubric version, artifact text/hash and
  anchors, source excerpts/hashes, judge perspective, provider and model.
  Exact packet bytes identify the reviewed input. Configuration and observed
  model identity are recorded separately; reasoning cannot replace final content.
- **Owner decisions:** include `packet_sha256` and `response_sha256` from the
  reviewed run's `state.json`, with every finding named once, a reason and one of
  `accept`, `reject`, `already_resolved` or `needs_input`. Files without the
  response hash are rejected; review the feedback before supplying that hash.
  Saved input hashes and feedback are checked against the original response.
- **Revision:** accepted changes require changed content and a new version.
  Retaining the artifact requires no accepted changes. Sources, task, criteria
  and reviewer configuration remain fixed for this comparison. The command
  records the supplied artifact; it does not edit it or verify semantic quality.
- **Scores and limits:** scores are ordinal model opinions from 1–4 or `null`,
  not acceptance thresholds. Failed reviews have no score. At most 20 findings
  and 1 MiB per input are accepted. A serialized report above that limit fails
  before replay reports success. Historical scores belong to their reviewed
  version. Existing output directories, including pending runs, are not overwritten.
- **Private storage:** supply credential-free captured responses and keep outputs
  private. Commands make no automatic retries and do not change conversations,
  corpus data, publication or deployment.
