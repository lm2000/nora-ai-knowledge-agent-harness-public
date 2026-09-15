# Embedding runner validation

[Results](RESULTS.md) · [Method](PROTOCOL.md) · [Run instructions](README.md)

The historical September 5, 2026 validation recorded eight passing focused tests and four completed CPU float32 workers. Earlier failed drafts were superseded; their original records remain in the private archive.

Tests covered metric definitions, multiple positives, unlabelled questions, MRR cutoff, pooling with either padding side, token limits, source-quote validation and output preservation. Post-run checks compared pinned revisions, input/code hashes, dimensions, settings and repeated rankings. The 17 excerpt ranges matched their recorded source hashes at that check time.

These checks support consistency of the recorded experiment. They do not validate exhaustive relevance judgments, a running Retrieval MCP service, target-server performance or a deployment decision. BGE was selected later; the historical benchmark's limited evidence remains unchanged.

Use the [runner instructions](README.md) to repeat local checks. Private corpus files and local cache assumptions need adaptation before public reproduction.
