#!/usr/bin/env python3
"""Check public Mermaid inventory and Markdown fences without a renderer.

This structural check is dependency-free. It does not parse Mermaid grammar
or prove visual quality; render changed diagrams separately before review.
"""

import re
import sys

from docs_common import ROOT, load_manifest, split_fences


def check(root=ROOT):
    manifest = load_manifest(root)
    expected = manifest["mermaid_blocks"]
    errors, actual = [], {}
    for name in manifest["documents"]:
        text = (root / name).read_text(encoding="utf-8")
        _, blocks, fence_errors = split_fences(text)
        errors.extend(f"{name}: {error}" for error in fence_errors)
        if re.search(r"!\[\[|excalidraw-plugin:|```(?:excalidraw|compressed-json)", text):
            errors.append(f"{name}: unsupported private-editor diagram markup")
        diagrams = [(body, line) for lang, body, line in blocks if lang == "mermaid"]
        if diagrams:
            actual[name] = len(diagrams)
        for body, line in diagrams:
            if not re.match(r"\s*(flowchart\s+(?:LR|RL|TB|TD|BT)|sequenceDiagram)\b", body):
                errors.append(f"{name}:{line}: empty or unsupported diagram type")
            if len(body.splitlines()) < 2:
                errors.append(f"{name}:{line}: diagram has insufficient content")
            if "%%{init:" in body or "<script" in body.lower():
                errors.append(f"{name}:{line}: custom executable diagram content")
    if not actual or actual != expected:
        errors.append(f"Mermaid inventory differs from public-docs.json: actual={actual}")
    return errors, actual


def main():
    try:
        errors, diagrams = check()
    except (ValueError, KeyError, OSError) as exc:
        print(f"Document manifest error: {exc}")
        return 1
    if errors:
        print("\n".join(errors))
        return 1
    print(
        f"Diagram structure OK: {sum(diagrams.values())} Mermaid blocks in {len(diagrams)} public documents. Render validation is separate."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
