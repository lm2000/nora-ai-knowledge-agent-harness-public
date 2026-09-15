# Data contract

[Home](../README.md) · [Manual ingestion](../workflows/ingestion/README.md)

Nora's public documentation does not enumerate a user's private archive paths, accounts or document titles. Each installation maintains its own source inventory and access records.

## Source families

Different source families can inform the same question. For a project handover, useful material might include project decisions, meeting notes, saved research and the user's correction. Source families are neither separate agents nor evidence that a particular installation has coverage.

| Family | Useful context | Interpretation |
| --- | --- | --- |
| Project documents | Decisions, designs and progress | Keep version and project identity |
| Meetings and correspondence | Agreements, requests and follow-ups | Distinguish event time from export time |
| Saved research | Technical or organizational background | Retain publication date and source context |
| Guides and playbooks | Reusable procedures | Separate reference instructions from commands to the agent |
| User guidance | Goals, preferences and corrections | Distinguish accepted guidance from quoted text |
| Reviews and generated analysis | Feedback and prior conclusions | Retain whether the result was accepted and its supporting evidence |

An inventory records what is actually available. This list is a conceptual map, not a source-collection request or an exhaustive coverage claim.

## Data stages

| Stage | Contents | Owner |
| --- | --- | --- |
| Originals | Selected files or exports in their original form | Operator-controlled source storage |
| Prepared documents | Readable text, document identity and minimal provenance | Manual preparation workflow |
| Chunks and vectors | Retrieval text units, stable IDs, embedding revision and vectors | Embedding/import workflow |
| Search index | Dense and lexical representations plus internal metadata | Qdrant |
| Conversation state | Thread messages and execution checkpoints | PostgreSQL |

Originals remain unchanged. Derived data can be rebuilt, but rebuilding must preserve the connection to the selected source version.

## Current prepared-document layout

The shared package uses SHA-256 identities and `docs/<doc_id>.txt` files. The ID hashes preserved source bytes, while deterministic normalized text is used for search chunks. Both local reads and optional generation-pinned GCS reads verify the content hash. `coverage.json` records exclusions, counts and representation; `import/` contains chunk rows and normalized vectors.

Chunks retain their text, document ID and stable point identity. The selected BGE model produces 768-dimensional normalized vectors. Embedding revision, tokenization and pooling settings must agree between indexing and querying.

Operational identities stay internal to the system. Omitting them from normal answers does not remove their maintenance or evaluation role.

## Installation inventory

Record source version, document count, exclusions, prepared-document hashes, chunk count and embedding configuration. Report unavailable or unreadable inputs separately from intentionally excluded material. Keep raw private locations and access details in operator-controlled records.

A completed private preparation run recorded 21,508 unique documents. This is a case-study measurement, not a dataset distributed with Nora. The [cleanup summary](../categorization/RESULTS.md) gives its method and limits.

## Public examples

Use synthetic project notes, decisions and meeting records for shareable fixtures. Preserve dates and clearly identify fictional content. Do not publish real mail, calendars, transcripts or private source inventories as sample data.
