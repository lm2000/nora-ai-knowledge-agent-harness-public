# Workflows

[Home](../README.md) · [Evaluation](../evaluation/README.md)

The harness supports different tasks using shared knowledge, model access and
bounded execution. Each workflow describes the inputs, steps and owner decisions
for one task.

| Workflow | Example | Result |
| --- | --- | --- |
| [Question answering](../agents/README.md) | Ask about Atlas and continue the conversation | A supported answer and retained conversation |
| [Knowledge ingestion](ingestion/README.md) | Add a revised project guide while retaining the corpus | A prepared knowledge release |
| [Artifact evaluation and revision](artifact-review/README.md) | Review a draft briefing before delivery | Feedback, owner decisions and a retained or revised artifact |

![Knowledge ingestion, question answering and artifact review use the harness for different tasks.](../architecture/diagrams/harness-workflows.gif)

[Local browser version](../architecture/diagrams/harness-workflows.html)

Question answering uses retrieved evidence within the conversation. Ingestion
and artifact review are separate workflows; a question does not start either one.
