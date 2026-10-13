#!/usr/bin/env python3
"""Check public diagram pairs, Mermaid inventory and Markdown fences.

This structural check is dependency-free. It does not parse Mermaid grammar
or prove visual quality; render changed diagrams separately before review.
"""

import re
import struct
import sys
from pathlib import Path

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
    if actual != expected:
        errors.append(f"Mermaid inventory differs from public-docs.json: actual={actual}")
    supporting = set(manifest.get("supporting_files", []))
    pairs = manifest.get("diagram_pairs", [])
    listed = []
    for pair in pairs:
        source, preview = pair["source"], pair["preview"]
        listed.extend((source, preview))
        if source not in supporting or preview not in supporting:
            errors.append(f"Diagram pair outside supporting inventory: {pair}")
            continue
        if (
            Path(source).suffix != ".html"
            or Path(preview).suffix != ".gif"
            or Path(source).with_suffix(".gif").as_posix() != preview
        ):
            errors.append(f"Diagram source/preview names differ: {pair}")
            continue
        html = (root / source).read_text(encoding="utf-8")
        if not re.search(r"<svg\b", html, re.I) or not re.search(r"<title\b", html, re.I):
            errors.append(f"{source}: missing inline SVG or title")
        if re.search(r'(?:src|href)\s*=\s*["\'](?:https?:)?//', html, re.I):
            errors.append(f"{source}: external asset dependency")
        raw = (root / preview).read_bytes()
        if len(raw) < 14 or raw[:6] not in (b"GIF87a", b"GIF89a") or raw[-1:] != b";":
            errors.append(f"{preview}: invalid GIF header or trailer")
        elif not all(struct.unpack("<HH", raw[6:10])):
            errors.append(f"{preview}: empty GIF dimensions")
    if len(listed) != len(set(listed)):
        errors.append("Duplicate diagram source or preview")
    assets = {name for name in supporting if name.endswith((".html", ".gif"))}
    if set(listed) != assets:
        errors.append("HTML/GIF assets differ from diagram_pairs inventory")
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
        f"Diagram structure OK: {len(load_manifest().get('diagram_pairs', []))} HTML/GIF pairs; {sum(diagrams.values())} Mermaid blocks. Render validation is separate."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
