# Changelog

## Documentation and diagram consistency — 2026-10-21

- Separate source architecture, client routes and recorded deployment configuration.
- Match JSON and chunk-metadata descriptions to the current processing outputs.
- Align three workflow names, simplify diagram navigation and enlarge small labels.
- Retain the existing visual style and remove the invented design concept.

[Home](README.md) · [Roadmap](docs/Plan.md)

This page records project milestones. Detailed private operating history and execution receipts are maintained separately.

## 2026-10-21 — Whole-project engineering review

Reorganized the overview around the problem, project contribution, architecture,
trade-offs and evidence. Restored the full roadmap, consolidated historical
quality entries and documented visual conventions and workspace-only skill
ownership. Updated diagram typography and export compatibility. Added a large
review-to-revision regression and mobile/unavailable-state browser checks.

## 2026-10-21 — Artifact evaluation and revision workflow

Added a workflow guide, configuration example and two HTML/GIF diagrams covering
judge feedback, owner decisions, artifact revisions and lessons for the next
review brief. Offline CLI commands validate saved reviews and record decisions
bound to the exact response; a synthetic two-version example exercises the cycle.
Retrieval quality and generated-output quality remain separate. See the
[workflow guide](docs/workflows/artifact-review/README.md) and
[local validation](docs/evaluation/VALIDATION.md#artifact-review-workflow--checked-2026-10-21).

## 2026-10-06 — Single-assistant cleanup in progress

Current source guidance is being aligned around one assistant, separate topic chats and backup-first ingestion. Obsolete role interfaces and material are removed without migrating or deleting stored conversations. [The roadmap](docs/Plan.md) owns integration and rollout progress; October 6 bounded client/browser/restart acceptance and the preparation answer passed after verified backups and Coordination/UI deployment.

## 2026-10-03 — Conversational client slice accepted

Bounded Codex and ordinary OpenClaw gateway question/follow-up checks passed. Direct/gateway transport and normal-restart continuity also have dated evidence. These results establish the exercised client paths rather than representative answer quality. [Deployment status](docs/setup/private-deployment/STATUS.md) retains the acceptance limits.

## 2026-10-02 — One-assistant architecture accepted

Selected one assistant, OSS Deep Agents/LangGraph, the incumbent model selector and PostgreSQL topic checkpoints. Embedded FastMCP and a separate LiteLLM gateway share one question/optional-UUID contract. Editable HTML diagrams supply derived GIF previews.

## Earlier milestones

The shared package, browser UI, deterministic preparation, shared BGE and Retrieval MCP, four ingestion jobs and container packaging were consolidated in September 2026. Historical architecture and execution detail remains in Git history and the dated deployment/evaluation records. Licenses and upstream notices remain part of the source.
