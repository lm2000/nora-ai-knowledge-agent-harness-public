# Roadmap

[Home](README.md) · [Decisions](Decisions.md) · [Validation](evaluation/VALIDATION.md)

Improve the complete harness as an engineering project that a hiring manager can
understand quickly and a technical interviewer can inspect in depth. Keep the
reader's path clear: problem → architecture → workflows → decisions → evidence.

![The three workflows tracked by this roadmap.](architecture/diagrams/harness-workflows.gif)

[Local browser version](architecture/diagrams/harness-workflows.html)

## Execution progress

| Area | Source state | Next acceptance result |
| --- | --- | --- |
| Portfolio-wide review | Two improvement passes are integrated into `main`; source checks and independent review are recorded below | Representative quality and deployment acceptance remain separate work |
| Question answering | One runtime, MCP entrance, bounded retrieval/model calls and PostgreSQL checkpoints implemented | Representative multi-turn quality and failure-slice evaluation |
| Knowledge ingestion | Conversion, preparation, embedding and import/verification are separate jobs | Operator-selected corpus refresh and deployment acceptance remain separately owned |
| Artifact review | Saved-response validation, exact-response decisions and synthetic two-version cycle implemented | External runner/provider execution and live-review acceptance are separate work |
| Documentation and visuals | Reader route and Atlas example are in `main`; the compact README system view and clearer review boundary pass local documentation checks | Map accepted source material to the separate website before editing it |
| Deployment and recovery | Dated bounded results retained in the deployment record | Broader recovery and clean-target acceptance beyond existing checks |

## Documentation and diagram consistency

The six requested documentation/design changes are complete locally: source and
deployment descriptions have separate owners, processing claims match the
current output, all three workflows appear in the index, diagram labels are
larger, existing visual conventions replace the invented design concept, and
the diagram catalog starts with three main views. Application defects remain
separate implementation work.

The reader pass brings Michael's application work above the compact architecture
view, keeps the detailed view one link away, and leads the artifact-review guide
with owner decisions and a before/after example. The next documentation step is
mapping this source material to the separate website.

## Current review

1. Audited the repository; dated findings and evidence are in the validation record.
2. Improved the engineering narrative, diagrams, examples and document ownership.
3. Fixed confirmed local defects with regression coverage and verified the UI.
4. Source/release checks and independent review passed for the two earlier
   improvement cycles. This reader-pass edit has its own validation record.

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
