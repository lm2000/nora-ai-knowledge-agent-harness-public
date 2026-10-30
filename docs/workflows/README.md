# Workflows

[Home](../../README.md) · [Evaluation](../evaluation/README.md)

The NIS AI agent harness has three workflows. For example, answering an Atlas
release question uses saved knowledge; reviewing its release briefing evaluates
an artifact. The AI Coordinator selects the workflow, plans the work, delegates
bounded tasks and combines the results.

| Workflow | Example | Result |
| --- | --- | --- |
| [Question answering](../agents/README.md) | Ask about Atlas and continue the conversation | A supported answer and retained conversation |
| [Knowledge ingestion](ingestion/README.md) | Add a revised project guide while retaining the corpus | A prepared knowledge release |
| [Artifact evaluation and revision](artifact-review/README.md) | Review a draft briefing before delivery | Feedback, owner decisions and a retained or revised artifact |

![Knowledge ingestion, question answering and artifact review use the harness for different tasks.](../architecture/diagrams/harness-workflows.gif)

[Local browser version](../architecture/diagrams/harness-workflows.html)

The [Coordination Layer](../architecture/architecture-concept.md) owns task
orchestration. [Model routing](../setup/model-routing.md) selects inference
routes for the work. Ingestion remains operator-triggered, outside conversations.
