# Architecture and workflow diagrams

Start with the compact system view, then follow one request and compare the workflows.
They describe source responsibilities. The dated [deployment record](../../setup/private-deployment/STATUS.md#configuration-reference--2026-10-21) owns installation state.

## System architecture

The compact view shows the main responsibilities at reading width.

![NIS source architecture at a glance](system-at-a-glance.gif)

[Local browser version](system-at-a-glance.html)

The detailed view shows component boundaries and both supported MCP entrances.
The gateway is a supported source path; the selected deployment is recorded
separately.

![System architecture](01-system-architecture.gif)

[Local browser version](01-system-architecture.html)

## Request path

Follow one question through retrieval, model inference and conversation state.

![One request through NIS](architecture-request-path.gif)

[Local browser version](architecture-request-path.html)

## Harness workflows

Compare question answering, knowledge ingestion and artifact evaluation and revision.
Ingestion and artifact review run separately from conversations.

![One harness, different workflows](harness-workflows.gif)

[Local browser version](harness-workflows.html)

## Detailed views

### Question to answer

Tool and optional branch detail for the request view. [GIF preview](02-question-to-answer.gif) · [Local browser version](02-question-to-answer.html)

### Conceptual conversation

Client entrances and conversation continuity. [GIF preview](conversation.gif) · [Local browser version](conversation.html)

### Knowledge-update overview

The four manual ingestion jobs and activation boundary. [GIF preview](manual-ingestion.gif) · [Local browser version](manual-ingestion.html)

### Service inventory

Source container responsibilities and storage. [GIF preview](container-service-inventory.gif) · [Local browser version](container-service-inventory.html)

### Selected rollout and later recovery

A reference procedure for a separate target. [GIF preview](private-rollout.gif) · [Local browser version](private-rollout.html)

### Operator knowledge update

The local-pin activation example. [GIF preview](ingestion-workflow.gif) · [Local browser version](ingestion-workflow.html)

### Artifact evaluation and revision

Review configuration, Harbor Hub/direct execution options, judge providers,
owner decisions and retained lessons. The [workflow guide](../../workflows/artifact-review/README.md) owns the local saved-response command boundary.

![Artifact review and revision cycle](artifact-review-flow.gif)

[Local browser version](artifact-review-flow.html)

### Historical CPU embedding comparison

Document throughput and query latency on one small CPU workload. [GIF preview](embedding-cpu-comparison.gif) · [Local browser version](embedding-cpu-comparison.html)

### Embedding comparison method

Shared inputs, pinned models, repeated CPU trials and the evidence boundary. [GIF preview](embedding-comparison-method.gif) · [Local browser version](embedding-comparison-method.html)

### Public source release

The explicit allowlist, clean snapshot and separate public repository. [GIF preview](public-source-release.gif) · [Local browser version](public-source-release.html)

## Refresh a GIF

Maintain one editable HTML file with inline SVG and one matching GIF. A repository
HTML link displays source; open the file locally in a browser for interaction.

From the repository root, with Playwright, Chromium and FFmpeg available:

```bash
node scripts/export_diagrams.cjs 01-system-architecture
```

Expected result: a GIF derived from that HTML, with thirty frames for a legacy
animated view or one frame for a standalone workflow viewer. Omit the stem to
export all pairs. `NODE_PATH`, `NIS_BROWSER_EXECUTABLE` and `NIS_FFMPEG` may select
existing dependencies. Temporary frame directories are separate and removed.
Regenerate and visually inspect previews after changing HTML. Separate SVG,
Excalidraw and Mermaid files are not maintained.

Sources: [architecture](../architecture-concept.md), [assistant](../../agents/README.md), [services](../../setup/containers/README.md), [ingestion](../../workflows/ingestion/README.md) and [roadmap](../../Plan.md).
