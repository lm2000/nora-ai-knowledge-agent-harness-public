# Contributing to Nora

[Home](README.md) · [Roadmap](Plan.md) · [Architecture decisions](Decisions.md)

Useful contributions improve the shared knowledge path, its tests, or its documentation. Start with a concrete behavior: for example, a corrupted bundle should fail before creating an index collection.

## Development

Follow [development setup](setup/README.md#install-for-development), then run `make validate`. This runs Python contracts and cloud-planning tests, lint, UI tests, TypeScript, the production UI build, shell syntax and documentation checks. It needs no private data or answer-model credential.

Use `make test`, `make lint` or `make ui-check` while iterating. Run the [real retrieval smoke test](setup/README.md#test-real-retrieval) when changing representation, preparation, search or MCP behavior. The optional Docling extra and complete container startup have separate validation needs.

## Source organization

[The repository map](REPO_MAP.md) identifies each owner. Keep shared behavior in `src/nora/`, browser code in `ui/`, synthetic fixtures in `examples/`, and packaging in `deploy/` plus root Compose. Target guides refer to this source instead of creating deployment-specific copies.

Use explicit configuration and dependency injection at service boundaries. Module imports must not read credentials, download a model or open a network connection. Keep credentials and runtime state under ignored application-owned directories.

## Documentation and diagrams

Explain purpose and give an example before technical reference. Put a procedure in one owning guide and link to it elsewhere. State the scope of a measured result, including the use of doubles or synthetic data.

List public Markdown and diagram counts in [public-docs.json](public-docs.json). The README uses native Excalidraw sources and matching SVG previews under `architecture/diagrams/`; include both in a change and refresh the preview when its source changes. Other Mermaid blocks render directly on GitHub. Local checks cover links, headings, fences and diagram inventory; inspect a real Mermaid render when changing a diagram.

The [release manifest](release-manifest.json) lists every public source file explicitly. Add intended source files there. `make release-check` checks paths, document coverage and common private credential/path markers; `make release` builds a snapshot with per-file hashes. It never includes Git history or runtime data.

## Pull requests

Describe the problem, resulting behavior, validation and material limitations. Include a synthetic reproduction where useful. Preserve prior experiment results when revising labels or metrics. Propose material architecture changes with their tradeoff; routine repairs need no separate design document.

For design reviews, state the reviewed revision, scope, method and limitations. Number findings, cite the relevant file, and explain the concrete trigger and impact. Preserve measured evidence, mark untested hypotheses, and use synthetic reproductions instead of private source material.

Keep private source documents, transcripts and operator receipts out of patches. Preserve the [MIT license](LICENSE) and [upstream notices](NOTICE.md). [Security reporting](SECURITY.md) describes the private reporting route.
