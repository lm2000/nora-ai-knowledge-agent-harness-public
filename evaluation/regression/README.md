# Retrieval regression

[Evaluation](../README.md) · [Cloud status](../../setup/private-deployment/STATUS.md)

The suite sends a fixed question set to the live Retrieval MCP `search` tool and scores expected-document rank. It is useful for detecting a changed result; determining why a result changed requires inspecting the fixtures and retrieved text.

## Current baseline

| Metric | September 14, 2026 live repeat | Default threshold |
| --- | ---: | ---: |
| Hit@1 | 1/6 (0.167) | 0.5 |
| Hit@5 | 1/6 (0.167) | 0.5 |
| MRR@5 | 1/6 (0.167) | 0.5 |

The suite failed. The earlier September 9 baseline reported the same scores. These six questions originated in a smaller development pilot; their current expected-document IDs and relevance labels still need review against the full corpus.

The [small pilot](../targeted-research-pilot/improvement/README.md) achieved different scores under a different corpus and retrieval implementation. This is not a controlled measurement of general quality deterioration.

A historical diagnosis identified encoded email bodies and metadata-heavy text, and preparation code was changed. The current score does not establish whether that change was deployed or whether it resolves the misses. Do not infer successful reindexing from a source edit.

## Run against an intended installation

The shared [evaluation command](../../src/nora/evaluation.py) accepts an explicit fixture, endpoint and credential source. The included [fictional questions](../../examples/queries.json) identify expected documents by adjacent source files, whose SHA-256 IDs are computed at load time.

From the repository root, with a running synthetic-data MCP service and `NORA_MCP_TOKEN_FILE` configured:

```bash
nora evaluate --queries examples/queries.json --hit1 1 --hit5 1 --mrr5 1
```

All three thresholds are explicit and independent. Exit codes are `0` for pass, `1` for a scored threshold failure and `2` for an invalid fixture or unavailable service. Invalid tool responses are setup failures, not scored misses. Add `--output` with a new filename to retain the report.

The [self-contained smoke test](../../setup/README.md#test-real-retrieval) creates its own local synthetic index and MCP server. The original six private queries and their runner are preserved outside the release; their earlier result above has not been rerun or replaced.

## Interpret the measures

Hit@k is the fraction of questions whose expected document appears in the first k results. MRR@5 averages the reciprocal rank of the first expected document within five; misses contribute zero. These metrics do not assess the generated answer, conversation continuity or access isolation.

The current thresholds are diagnostic starting points. The script has a pass/fail result, but the application does not automatically enforce it as a release or routing gate.

## Improve the fixture set

1. Verify each expected document exists and that its source content supports the intended answer.
2. Inspect alternative relevant documents and record ambiguous labels explicitly.
3. Version changes and preserve the original six-query result.
4. Add reviewed negative, clarification, cross-language and held-out questions before setting release criteria.

Record corpus/index identity, embedding and retrieval settings, code revision and returned ranks with every comparison.
