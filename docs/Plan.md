# Roadmap

[Home](../README.md) · [Decisions](Decisions.md) · [Validation](evaluation/VALIDATION.md)

Make NIS easy to understand and useful to operate: explain the architecture,
implement the accepted workflows, then evaluate the results. For example, an
Atlas briefing should move from grounded draft through judge feedback to a
human acceptance decision.

![Question answering, Ingestion, and artifact evaluation and revision.](architecture/diagrams/harness-workflows.gif)

[Local browser version](architecture/diagrams/harness-workflows.html)

## Current work: documentation alignment

**2026-10-25 — local review complete.** Rewrite the existing harness documentation and
diagrams around the accepted design before changing the application. Preserve
unrelated worktree changes, executable contracts, runtime state and dated
evidence.

| Scope | State | Remaining acceptance |
| --- | --- | --- |
| Main entry points | Local edits and independent review complete | Owner read-through |
| Workflow, setup and evaluation guides | Refreshed and reviewed; existing commands preserved | Owner read-through |
| Diagrams and public inventory | 13 pairs updated; 16 pairs in the catalog; rendering and independent review complete | Owner review of the diagrams |
| Documentation validation | Links, diagrams, release manifest and whitespace checks passed | Results in the dated validation record |

The accepted design uses a Coordination Layer with one AI Coordinator,
specialist subagents, separate model routes and shared browser/MCP access.
Artifact review uses versioned judge definitions, a NIS Judge Registry,
Synthetic Owner recommendations and Real Owner approval. [Decisions](Decisions.md)
owns the choices; [architecture](architecture/architecture-concept.md) owns
their explanation.

## Documentation layout

**2026-10-25 — consolidated locally.** Product guides, decisions, requirements,
workflow/evaluation material and all HTML/GIF pairs now live under `docs/`.
The [documentation index](README.md) replaces the former root repository map.
Root README, contributor/AI instructions, security and license notices remain
standard entry points. Executable helpers stay under root `setup/`; application
code, examples, runtime data and local agent material keep their original paths.

Local navigation and publication inventories are rebased. Font-license build
references follow their moved notice. Structural checks pass; scoped migration
review and packaging verification are recorded before owner acceptance.

The knowledge-refresh source list keeps its existing logical names. A physical
path map reads the moved guides without renaming archive/state identities; this
does not run ingestion or change active knowledge.

**2026-10-29 — application-test collection restored.** Corrected the indentation
in `src/nora/coordination.py:113`. The full configured pytest suite completed:
323 passed, 8 skipped and 11 subtests passed, with three dependency deprecation
warnings. See the [validation record](evaluation/VALIDATION.md#coordination-indentation-repair--2026-10-29).
Owner review remains pending.

## Delivery after documentation acceptance

**2026-10-29 — public snapshot preparation.** The owner requested preparation of
the existing public repository update. The isolated candidate contains the 203
allowlisted source files and a checksum receipt. Full contributor checks passed
in the source tree and the candidate; the candidate Python wheel also built.
The owner subsequently authorized publication. Public `main` now points to
`5df4b0ffc3c7dddfc656aa21575db9fdb881997e`; anonymous HTTPS readback of the README,
documentation index and checksum receipt matched the published snapshot.
GitHub Actions was running at readback. Website deployment remains a later step.

| Step | Dependency and result | Completion boundary |
| --- | --- | --- |
| Finalize the private Harness documentation | Resolve the current Architect/Technical Writer findings, simplify repeated material and verify changed HTML/GIF pairs | Documentation checks and scoped re-review complete; owner accepts the result |
| Generate the public Harness repository | Use the accepted private tree and the [publication allowlist/procedure](PUBLISHING.md) to prepare the clean public snapshot; update the existing public target when present | Inspect the public diff and exclusions; obtain explicit authorization before pushing or publishing |
| Update the website from the accepted public material | Map the architecture, terminology and diagrams into the existing website; use the accepted resume/CL for any Founder profile update | Build, link and visual checks complete; website deployment is a separate authorized step |

The public snapshot follows documentation acceptance, and the website follows
the reviewed public material. Source publication and website deployment do not
change running Harness services. The separate Career plan owns resume/CL review.

## Application implementation sequence

| Area | Starting point | Next result |
| --- | --- | --- |
| Coordination | One coordinator, bounded retrieval/model calls and PostgreSQL checkpoints | Map planning and specialist delegation onto Deep Agents/LangGraph while preserving conversation contracts |
| Model routes | Application adapters, selector and bounded fallback | Map simple/general/reasoning/specialized routes to configured models; measure quality, cost and latency |
| Question answering | Grounded answer path and topic conversations | Representative multi-turn quality and failure-slice evaluation |
| Ingestion | Separate jobs; local collision, failed-conversion and host-tokenizer repairs with regression coverage | Revalidate installed job images and the host route before a separately authorized corpus update |
| Artifact review | Saved-response validation, exact-response decisions and a synthetic two-version cycle | Add separate Harbor Hub/Hugging Face execution routes and versioned judge definitions/registry |
| Owner review | Explicit saved human decisions | Calibrate Synthetic Owner scores/thresholds against real decisions; verify both revision loops |
| Deployment and recovery | Bounded dated checks in the deployment record | Revalidate affected targets and recovery after implementation changes |

The answer path retains three retrieval calls including Grounding and four
logical model calls, with bounded retries and repair. Any change needed for
specialist execution requires an explicit implementation decision and relevant
checks. The local review example continues to replay saved responses.

## Execution progress

**2026-10-29 — ingestion reliability and documentation cleanup.** The three
ingestion repairs have regression coverage, and the remaining legacy document
copies/local skill mirrors have been archived outside the public source tree.
Full contributor checks now pass in the actual checkout; the ten logical
refresh source identities retain their mapped paths. The owner authorized
committing and pushing the source repairs. See the
[cleanup validation](evaluation/VALIDATION.md#duplicate-documentation-cleanup--2026-10-29).
Runtime deployment and corpus updates remain separate.

Two earlier improvement cycles integrated engineering narrative, diagrams,
examples, application fixes and source/release checks. Their dated outcomes,
including the later reader pass, remain in the
[validation record](evaluation/VALIDATION.md). The current documentation refresh
has a separate integration check.

Carry forward the existing engineering work:

- Ingestion reliability repairs are local: source-path-derived extraction names,
  failed-conversion rejection and separate host tokenizer/HTTP embedding inputs.
  The [validation record](evaluation/VALIDATION.md#ingestion-reliability-repair--2026-10-29)
  owns test evidence; deployment and corpus updates remain separate actions.
- Build a representative held-out retrieval and answer set. Keep earlier
  diagnostic results tied to their original corpora and methods.
- Define external-review task, provider, budget and evidence contracts before
  connecting a live runner.
- Recheck deployment compatibility and persistence when source/configuration
  changes; broader recovery and clean-target acceptance remain separate work.
- Map accepted source documentation to the separate website, then handle
  publication as its own step.

Historical experiments remain in Git history and dated evaluation/deployment
records. Private Operations Guidance owns operational coordination. Editing or
validating documentation does not activate ingestion, change services or
publish the website.
