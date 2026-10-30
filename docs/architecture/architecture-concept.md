# Architecture

[Home](../../README.md) · [Requirements](Requirements.md) · [Decisions](../Decisions.md) · [References](Research%20and%20Design%20Inputs.md)

Nora Intelligence System (NIS) is a personal AI agent harness for work that needs
saved knowledge, several execution steps and review. Its architecture separates
knowledge retention, task coordination and model inference so each can evolve
without making a conversation carry the whole system.

**Example:** “Prepare an Atlas handover brief.” NIS finds the release plan and
decisions, drafts a briefing, collects specialist feedback and revises it before
the owner approves it. The next conversation can use the same retained sources.

This page explains the accepted design. [Decisions](../Decisions.md#problems-choices-and-consequences)
owns alternatives and trade-offs; [the roadmap](../Plan.md) tracks implementation.
[Setup](../setup/README.md) and the dated [deployment record](../setup/private-deployment/STATUS.md)
own commands and observed installation state.

## Why a Knowledge Backbone

A model request has a finite context window. Projects accumulate documents and
lessons across many conversations, so attaching everything to each prompt does
not provide a maintainable knowledge source. Chat history also ties useful
information to a particular conversation and client.

The **Knowledge Backbone** retains prepared source text and a searchable index
outside model context. Ingestion prepares and verifies a knowledge release;
Retrieval MCP finds and reads relevant passages from that release for the current
task. The corpus can grow independently of the prompt. Each model request still
has a bounded context, and retrieval quality determines which evidence reaches it.

![Ingestion prepares retained knowledge; Retrieval selects evidence for a bounded model request.](diagrams/02-question-to-answer.gif)

[Local browser version](diagrams/02-question-to-answer.html) · [Ingestion contract](../workflows/ingestion/README.md)

Prepared full text preserves the material available to read. Qdrant provides a
rebuildable search index. Shared BGE encodes documents and queries with the same
pinned configuration. Matching text and index releases keep search results tied
to the source being read. This adds preparation, activation and relevance checks;
keeping data outside context does not guarantee that every answer finds it.

## System boundaries

![One Coordination Layer connects clients, specialist work, model routes, knowledge, evaluation and state.](diagrams/01-system-architecture.gif)

[Local browser version](diagrams/01-system-architecture.html) · [All diagrams](diagrams/README.md)

| Component | Why it exists / responsibility |
| --- | --- |
| AI Coordinator | Own a task across retrieval, planning, specialist delegation and model calls; combine results into an answer or artifact |
| Retrieval MCP | Give agents bounded search/read tools while owning query encoding, index access and source-release selection |
| MCP Gateway (LiteLLM Proxy) | Give MCP clients access to NIS tools and forward their calls to the coordinator's MCP interface |
| MCP Server (FastMCP, `ask_nis`) | Publish the coordinator operation as an MCP tool and invoke it in process; shown as Coordinator API in the conversation view |
| Browser UI | Provide the interactive CopilotKit interface over HTTP/AG-UI to the same coordination operation |
| Model backends | Execute selected inference calls; Ollama and Fireworks are serving backends, DeepSeek is a model family |
| Evaluation routes | Reach prepared Harbor Hub tasks/results or Hugging Face judge models as separate coordinator-selected paths |
| PostgreSQL | Retain conversation checkpoints independently of browser and MCP transport sessions |

The **Coordination Layer** groups the coordinator and its interfaces logically.
The **Coordination service** is the process hosting Deep Agents/LangGraph and
FastMCP. Frameworks provide execution, model/tool abstractions and state;
NIS connects them through its task, knowledge and conversation contracts.

A shared coordinator keeps browser and MCP clients from implementing separate
planning and history rules. The gateway supplies tool access; the MCP Server
exposes `ask_nis`; the coordinator performs the work. The browser uses its
HTTP/AG-UI interface directly. [Service guidance](../setup/containers/README.md)
owns packaging, network and mounts.

## Three workflows

![The harness separates question answering, knowledge updates and artifact review.](diagrams/harness-workflows.gif)

[Local browser version](diagrams/harness-workflows.html)

| Workflow | Purpose and boundary | Owning guide |
| --- | --- | --- |
| Question answering | Retrieve evidence, generate and check an answer, retain the conversation | [Assistant behavior](../agents/README.md) |
| Ingestion | Convert → prepare → embed → import/verify → activate a matching knowledge release | [Ingestion](../workflows/ingestion/README.md) |
| Artifact evaluation and revision | Collect judge feedback, revise under Synthetic Owner scoring, then seek Real Owner approval | [Artifact review](../workflows/artifact-review/README.md) |

Ingestion runs outside conversations so long-running writes and activation have
an inspectable lifecycle. Four jobs preserve originals and substantive source
text. Additions assemble with retained knowledge; rebuilds use the complete
desired set. This leaves freshness and activation as explicit operator work.
The [checklist](../workflows/ingestion/knowledge-base-update-checklist.md) owns it.

## One question

![The same AI Coordinator plans the request and combines the result.](diagrams/architecture-request-path.gif)

[Local browser version](diagrams/architecture-request-path.html) · [Conversation detail](diagrams/conversation.html)

For “What blocks the Atlas release?”, the coordinator identifies the task and
asks Retrieval MCP for relevant knowledge. Retrieval calls BGE for query encoding,
combines dense and hashed lexical search with reciprocal-rank fusion, and
deduplicates results by document. A bounded read supplies source passages to the
selected model. The coordinator checks grounding and returns the answer.

Source text is evidence, not instructions. A dated export cannot establish a
current event. Ordinary answers omit citation cards and internal IDs; requested
source titles/headings can appear in prose. PostgreSQL retains conversation
content; browser storage keeps the current conversation UUID. The behavior guide
owns the three-retrieval/four-logical-model-call bounds, request-only repair and
ownership checks. The [data contract](../data/Data%20Contract.md) owns source
identity and artifacts.

## Task orchestration and model routing

![The coordinator assigns work, selects inference routes and combines returned results.](diagrams/model-routing.gif)

[Local browser version](diagrams/model-routing.html)

A multi-step task needs more than model selection. The AI Coordinator chooses
the workflow, delegates bounded work to specialist subagents and synthesizes
their results. Model routing selects suitable inference for each step; a
specialist can use different routes while completing its task.

| Route | Typical use |
| --- | --- |
| Simple | Extraction, classification and short factual tasks |
| General | Conversation and drafting |
| Reasoning | Analysis, planning and difficult comparisons |
| Specialized | Task-specific models or capabilities, for example through Fireworks |

Capabilities and required quality determine eligibility before configured cost
and latency rank candidates. Categories do not permanently assign providers.
Client model choice remains separate from NIS application selection.
[Model routing](../setup/model-routing.md) owns adapters, fallback and route evidence.

## Judges and owner review

![Research produces reusable role definitions and prepared Harbor tasks in the NIS Judge Registry.](diagrams/judge-registry.gif)

[Local browser version](diagrams/judge-registry.html)

Reusable judges make review criteria explicit across revisions. Role, domain and
source research produces versioned persona, rubric, criteria, dataset and
examples. Prepared Harbor tasks/datasets form the **NIS Judge Registry**. Roles
include CTO, AI Architect, Hiring Manager, Senior Engineer, Domain Expert and
Synthetic Owner. The last uses sanitized analysis of relevant owner interactions.

![Judge feedback and Synthetic Owner scoring feed revision before Real Owner approval.](diagrams/artifact-review-flow.gif)

[Local browser version](diagrams/artifact-review-flow.html)

The coordinator selects separate Harbor Hub task/results and Hugging Face
judge-model routes; Harbor does not call Hugging Face in this design. It
aggregates feedback, then the Synthetic Owner scores progress and recommends
acceptance or revision. Below threshold, revise and evaluate again. A qualifying
result reaches the Real Owner, whose change requests form the second loop and
whose approval is final. Scores require calibration against real decisions.
Lessons improve the next brief and judge definitions. The
[artifact-review guide](../workflows/artifact-review/README.md) owns both loops and records.

## Storage, deployment and evidence

Originals remain in operator-controlled storage. Prepared full text uses local
release storage or generation-pinned GCS objects. Qdrant stores the derived
index; PostgreSQL stores checkpoints. Database volumes remain separate from
object-storage artifacts. The deployment record owns installation selection.

One `src/nora/` package supplies services and ingestion jobs; `ui/` owns the
browser application. Host placement can change while preserving these boundaries.
[Evaluation](../evaluation/README.md) distinguishes source checks, dated live
results and owner acceptance. Operational commands and historical experiments
stay in their owning guides rather than being repeated here.
