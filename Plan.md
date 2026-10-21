# Roadmap

[Home](README.md) · [Decisions](Decisions.md) · [Validation](evaluation/VALIDATION.md)

Improve the complete harness as an engineering project that a hiring manager can
understand quickly and a technical interviewer can inspect in depth. Keep the
reader's path clear: problem → architecture → workflows → decisions → evidence.

## Execution progress

| Area | Source state | Next acceptance result |
| --- | --- | --- |
| Portfolio-wide review | Two improvement passes cover documentation, diagrams, code, UI, tests and public/private boundaries | Integrated locally into main; checks and independent review pass; no push or deployment |
| Question answering | One runtime, MCP entrance, bounded retrieval/model calls and PostgreSQL checkpoints implemented | Representative multi-turn quality and failure-slice evaluation |
| Knowledge ingestion | Conversion, preparation, embedding and import/verification are separate jobs | Operator-selected corpus refresh and deployment acceptance remain separately owned |
| Artifact review | Saved-response validation, exact-response decisions and synthetic two-version cycle implemented | External runner/provider execution and live-review acceptance are separate work |
| Documentation and visuals | Reader route, Atlas example and evaluation diagram updated in local commits | Map the accepted source material to the separate website before editing it |
| Deployment and recovery | Dated bounded results retained in the deployment record | Broader recovery and clean-target acceptance beyond existing checks |

## Documentation and diagram consistency

The six requested documentation/design changes are complete locally: source and
deployment descriptions have separate owners, processing claims match the
current output, all three workflows appear in the index, diagram labels are
larger, existing visual conventions replace the invented design concept, and
the diagram catalog starts with three main views. Application defects remain
separate implementation work.

The reader pass is complete locally: README opens with the Atlas question and
names Michael's application work; the artifact-review guide leads with owner
decisions and a before/after example; its diagram shows concrete feedback.
The latest documentation commit is `ed25a04`. The next documentation step is
mapping this accepted material to the separate website.

## Current review

1. Audited the repository; dated findings and evidence are in the validation record.
2. Improved the engineering narrative, diagrams, examples and document ownership.
3. Fixed confirmed local defects with regression coverage and verified the UI.
4. Source/release checks and independent review pass; changes are committed locally.

The [validation record](evaluation/VALIDATION.md) owns dated outcomes. The source
review does not activate ingestion, change services or publish the website.

## Later work

- Fix two confirmed ingestion defects in a separate code pass: converted file
  names can collide, and a failed source conversion does not stop release
  preparation. Add regression coverage before changing either behavior.
- Build a representative held-out set for retrieval and answer quality; preserve
  earlier diagnostic results rather than comparing unlike corpora as a benchmark.
- Calibrate model-judge recommendations against owner decisions and useful edits.
- Add an external artifact-review runner only with explicit task, provider,
  budget and evidence contracts.
- Revalidate selected deployment targets, recovery and provider compatibility
  when their source or configuration changes.
- Align the separate website with accepted source documentation, then handle
  publication as a separate step.

Historical experiments remain in Git history and the dated evaluation/deployment
records. Current operational ownership remains in the private Operations Guidance.
