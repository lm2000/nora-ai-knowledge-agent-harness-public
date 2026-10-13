# Contributing to Nora

[Home](README.md) · [Roadmap](Plan.md) · [Architecture decisions](Decisions.md)

Useful contributions improve the shared knowledge path, its tests, or its documentation. Start with a concrete behavior: for example, a corrupted bundle should fail before creating an index collection.

## Development

Follow [development setup](setup/README.md#install-for-development), then run `make validate`. The repository uses the project-specific `nora-ai` Conda environment. The existing mise shell hook activates it when a terminal enters this directory and restores the previous environment after leaving. This runs Python contracts and cloud-planning tests, lint, UI tests, TypeScript, the production UI build, shell syntax and documentation checks. It needs no private data or answer-model credential.

Use `make test`, `make lint` or `make ui-check` while iterating. Run the [real retrieval smoke test](setup/README.md#test-real-retrieval) when changing representation, preparation, search or MCP behavior. The optional Docling extra and complete container startup have separate validation needs.

## Source organization

[The repository map](REPO_MAP.md) identifies each owner. Keep shared behavior in `src/nora/`, browser code in `ui/`, synthetic fixtures in `examples/`, and packaging in `deploy/` plus root Compose. Target guides refer to this source instead of creating deployment-specific copies.

Use explicit configuration and dependency injection at service boundaries. Module imports must not read credentials, download a model or open a network connection. Keep credentials and runtime state under ignored application-owned directories.

## Documentation and diagrams

Explain purpose and give an example before technical reference. Put a procedure in one owning guide and link to it elsewhere. State the scope of a measured result, including the use of doubles or synthetic data.

List public Markdown and diagram pairs in [public-docs.json](public-docs.json). Maintain one editable HTML file with inline SVG and its matching generated GIF under `architecture/diagrams/`. Embed the GIF with a standard Markdown image and place its HTML link directly below, labeled as a local browser version. Regenerate the GIF whenever its HTML changes and visually inspect it. Separate SVG, Excalidraw and Mermaid sources are not maintained. Run `make linkcheck` and `make diagrams`; structural checks and visual inspection establish different results.

The [release manifest](release-manifest.json) lists every public source file explicitly. Add intended source files there. `make release-check` checks paths, document coverage and common private credential/path markers; `make release` builds a snapshot with per-file hashes. It never includes Git history or runtime data.

## Pull requests

Describe the problem, resulting behavior, validation and material limitations. Include a synthetic reproduction where useful. Preserve prior experiment results when revising labels or metrics. Propose material architecture changes with their tradeoff; routine repairs need no separate design document.

For design reviews, state the reviewed revision, scope, method and limitations. Number findings, cite the relevant file, and explain the concrete trigger and impact. Preserve measured evidence, mark untested hypotheses, and use synthetic reproductions instead of private source material.

Keep private source documents, transcripts and operator receipts out of patches. Preserve the [MIT license](LICENSE) and [upstream notices](NOTICE.md). [Security reporting](SECURITY.md) describes the private reporting route.
