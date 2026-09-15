# Agent roles

[Home](../README.md) · [Architecture](../architecture/Architecture%20Concept.md) · [Evaluation](../evaluation/README.md)

A role defines instructions, tools and evaluation expectations. Nora now has three implemented roles, each running Coordination and the Deep Agent in its own container. The folders are referenced by the shared runtime construction in `src/nora/roles.py`; there is no separate outer coordinator. Each role runtime performs automatic balanced routing across Ollama Cloud and Fireworks.ai.

| Role | Example | State |
| --- | --- | --- |
| [Knowledge Assistant](#knowledge-assistant) | Prepare a brief from saved project material | Implemented; backward-compatible alias remains in `coordination` service |
| [Research Assistant](#research-assistant) | Investigate a gap beyond saved knowledge | Implemented role runtime and configuration |
| [Interview Analyst](#interview-analyst) | Compare preparation, transcript and feedback | Implemented role runtime and configuration |

Retrieval, ingestion and databases are services or workflows, not additional agent roles.

## Selected runtime boundary

Each enabled role owns execution and conversation lifecycle inside its container. There is no separate custom outer coordinator. Roles share Retrieval MCP, which calls shared BGE and Qdrant and reads prepared documents. Roles also share PostgreSQL checkpoints; each role namespaces its thread IDs before writing them.

UI role routing, role/thread isolation and runtime configuration are implemented. Research and Interview use the same shared Retrieval tools today; additional research tools remain future work. [D167](../Decisions.md#selected-target-separate-runtime-and-job-containers), [D169](../Decisions.md#accepted-implementation-choices-from-the-architecture-review) and [D172](../Decisions.md#per-role-runtime-containers-checkpoint-ownership-and-automatic-provider-routing) own the packaging and routing decisions.

## Knowledge Assistant

[Architecture](../architecture/Architecture%20Concept.md)

Turn a question about saved material into a concise answer or clarification. For example, prepare a handover brief from project decisions and meeting notes.

The reference behavior is implemented in the shared Coordination service and `src/nora/agent.py`. It searches shared Retrieval MCP, may read additional passages, uses the answer model and stores the conversation. The role directories are referenced by the shared runtime construction in `src/nora/roles.py` rather than a second implementation.

Evaluate correct target selection, relevant evidence, missing information, user corrections and conversation continuation. Do not infer current meeting state from an old export or treat document text as executable instructions.

The selected target runs this role in its own container containing Coordination and the Deep Agent, with shared Retrieval MCP and PostgreSQL checkpoints. Existing behavior remains in the current Coordination implementation; the role runs as `role-knowledge`. See [the service inventory](../setup/containers/README.md).

## Research Assistant

[Future extensions](../architecture/Technology%20Options.md#future-extensions)

**Implemented role runtime.** Investigates a question that the prepared collection cannot answer, such as a technical comparison needing current external evidence.

Start from the existing knowledge through Retrieval MCP. External research tools, provider configuration, investigation limits and result-evaluation criteria remain to choose and implement; this runtime shares the same `search`/`read` tools as Knowledge Assistant today.

Research results do not automatically enter the knowledge index. Adding selected results uses the separate manual ingestion workflow.

The role runs in its own container (`role-research`) containing Coordination and the Deep Agent, with shared Retrieval MCP and PostgreSQL checkpoints. Runtime configuration is in `src/nora/roles.py`. [D172](../Decisions.md#per-role-runtime-containers-checkpoint-ownership-and-automatic-provider-routing) records the implementation status.

## Interview Analyst

[Future extensions](../architecture/Technology%20Options.md#future-extensions)

**Implemented role runtime.** Compares supplied preparation, a transcript and feedback to identify gaps and recommend focused practice.

Use shared Retrieval MCP for relevant saved material. Distinguish transcript observations, feedback and recommendations. Extraction, transcription, analysis criteria and artifact generation remain to integrate; supplying a recording does not mean it has been transcribed.

Evaluate source fidelity, conflicting feedback, missing material and useful comparisons.

The role runs in its own container (`role-interview`) containing Coordination and the Deep Agent, with shared Retrieval MCP and PostgreSQL checkpoints. Runtime configuration is in `src/nora/roles.py`. [D172](../Decisions.md#per-role-runtime-containers-checkpoint-ownership-and-automatic-provider-routing) records the implementation status.

## Proposed package layout

```text
agents/<role>/
  README.md          purpose, example and expected behavior
  agent.py           agent construction, when implemented
  instructions.md    role instructions
  tools/             selected tool wrappers
  middleware/        role-specific extensions, if needed
  evals/             fixtures and evaluation criteria
```

The layout is a design. Implement an entrypoint, dependencies and meaningful tests together. Add connectors, skills or delegation only when the role requires them.

## Shared contract

Use OSS Deep Agents within Coordination and share the Retrieval MCP service. Preserve thread identity and checkpoint behavior. Keep knowledge preparation outside conversations. Normal answers are plain, while internal document IDs remain available for maintenance and evaluation.

Model routing, additional tools and hosted research are separate capabilities with their own compatibility work. A new role directory does not automatically enable any of them.
