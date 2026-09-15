# Cloud reference status

**Historical deployment evidence.** The shared-source refactor has not been deployed to this instance. See [source validation](../../evaluation/VALIDATION.md) for the separate candidate checks.


[Cloud guide](README.md) · [Evaluation](../../evaluation/README.md) · [Roadmap](../../Plan.md)

**Snapshot: September 14, 2026.** The private reference was running, but answer quality and several earlier acceptance claims still need work. This snapshot is not a continuous monitor or a claim about a new installation.

| Area | Available evidence | Meaning |
| --- | --- | --- |
| Infrastructure | VM readback: running, no external IP | Private reference exists |
| Service health | Coordination, Retrieval and PostgreSQL reported healthy; Qdrant and UI reported running | Service availability at the check time |
| Index | Authenticated Retrieval health reported 143,071 points | Point count; not a fresh full vector-integrity audit |
| MCP access | Unauthenticated health and MCP requests returned HTTP 401 | Tested unauthenticated requests were rejected |
| Relevance | Six-query suite scored 1/6 for hit@1, hit@5 and MRR@5 against thresholds of 0.5 | Suite failed; fixture applicability still needs review |
| Earlier full-corpus browser and recovery checks | Historical completion claims exist; supporting deployment receipts were unavailable in the reviewed checkout | Not independently reproduced in this review |
| Public portability | Bundle contains host, project, image and corpus assumptions | Requires source/configuration work before a general installation |

The reference corpus was historically reported as 21,508 unique documents across 143,071 chunks. Separate cleanup receipts support the prepared-text counts in [cleanup results](../../categorization/RESULTS.md). They do not substitute for a current index-to-source comparison.

Local conversion and mocked router tests passed during the assessment. They do not establish browser behavior, hosted inference quality or successful backup restoration.

Next: inspect the six regression labels and current retrieval output, retain a reproducible evaluation packet, then validate end-to-end behavior and recovery. These execution tasks remain in the roadmap; the current refactor changes documentation only.
