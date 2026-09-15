# Text-cleanup results

[Collection history](README.md) · [Data contract](../data/Source%20Inventory.md)

The September 5, 2026 private run completed all 100 extraction tasks and a separate finalizer. Independent download checks covered eleven resulting archives: ZIP CRC, SHA-256, UTF-8 text and manifest accounting. Thirteen separate raw archives retained their recorded generations, sizes and hashes.

## Aggregate accounting

| Measure | Before | After |
| --- | ---: | ---: |
| Source references | 22,853 | 22,302 retained |
| Excluded references | — | 551 |
| Globally unique text objects after extraction | — | 21,508 |
| Physically stored text objects across independent archives | — | 21,521 |
| Compressed archive bytes | 556,823,130 | 55,173,782 |
| Globally unique payload bytes | 775,748,059 | 163,160,865 |

Compressed size fell about 90.1%. Thirteen cross-archive repeated objects remain so each archive is independently usable. Reference count, unique text count and stored object count measure different things.

## Exclusions and OCR

| Exclusion reason | References |
| --- | ---: |
| Audio/video | 66 |
| Binary NUL content | 1 |
| Empty or low-confidence raster extraction | 353 |
| No meaningful text | 20 |
| Recorded unreadable or unsupported input | 98 |
| SVG without meaningful text | 13 |

Raster OCR retained 944 references; SVG extraction retained 77. These are reference counts, not unique-image counts. Structural checks did not measure transcription accuracy across the corpus.

## Method

The earlier cleanup converted private source archives into readable UTF-8 text. It preserved originals, decoded supported exports, rejected unusable content and compared output bindings before delivery. Cloud workers and a finalizer performed that particular batch.

The original staging, deployment, execution, finalization and verification scripts are retained with private inputs and receipts in the preservation archive. They are not a public cloud job or a second production ingestion implementation.

The current shared package provides [optional Docling conversion](../src/nora/conversion.py) and [deterministic preparation](../src/nora/preparation.py). It produces a new local bundle and leaves inputs unchanged. Supported formats, exclusions and explicit commands are described in [setup](../setup/README.md).

## Execution and limits

The full extraction job recorded 100 successes with observed peak concurrency 100. Extraction start through finalizer terminal status took about 5 minutes 22 seconds. An earlier sample failed because staging folders were absent; the recorded retry succeeded after those folders were prepared.

The reviewed final receipt records completion at `2026-09-05T13:52:42.747068Z`. The original receipts preserve object identities, checksums, exclusions and rollback bindings privately. This public summary does not include the underlying source text or grant redistribution rights to it.

These results establish a completed cleanup job and its accounting. They do not establish OCR accuracy, an embedded/indexed corpus, retrieval relevance or application acceptance. Historical aggregate measurements belong to the original batch; the new synthetic source checks do not imply the private archives were reprocessed or a cloud batch rerun.
