# Preparing a public source release

[Home](README.md) · [Contributing](CONTRIBUTING.md) · [Validation](evaluation/VALIDATION.md)

The source candidate is a clean snapshot built from an explicit file list. It contains the shared application, portable configuration, synthetic examples, tests, Mermaid diagrams, editable Excalidraw files with README previews, and license notices. It does not carry the private repository's commit history.

## Build and inspect

From a configured development checkout:

```bash
make validate
make release
```

[release-manifest.json](release-manifest.json) owns the source file list; [public-docs.json](public-docs.json) owns Markdown coverage and diagrams. The builder rejects unsafe paths, symlinks, missing files, unlisted public documents and common private key, home-directory and account-address markers. This targeted scan is useful evidence, not a guarantee that every possible sensitive string can be recognized.

The result is `.release/nora-0.1.0-source.tar.gz`. Its top-level `nora-0.1.0/` directory includes `SOURCE-CHECKSUMS.json` with each source file's SHA-256. The archive is deterministic for unchanged inputs and records no host user, group or source timestamp. It excludes `.git`, private history, credentials, model weights, caches and runtime state.

Extract it into a new directory, inspect the exact contents, then repeat the contributor checks there. The current five-service stack has passed an isolated ARM Linux trial, including Ollama Cloud answers and conversation restoration. That evidence is separate from implementing and rolling out the selected target architecture; see the [validation record](evaluation/VALIDATION.md).

## Publication steps still separate

1. Review the exact source candidate and the [validation limits](evaluation/VALIDATION.md).
2. Select the public repository name and use the extracted snapshot for a fresh history. Changing the old private repository's visibility would expose its earlier commits.
3. Preserve [LICENSE](LICENSE), [NOTICE.md](NOTICE.md) and [Templates/LICENSE](Templates/LICENSE).
4. Publish only after the intended destination is chosen. This local preparation does not create a repository, push a branch or change visibility.

Private originals and prior evaluation evidence remain in the maintainer's local archive. The three included example documents are fictional; they replace private material in the public reproduction route, not in historical measurements.
