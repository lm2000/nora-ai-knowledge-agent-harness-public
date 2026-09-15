#!/usr/bin/env python3
"""Check manifest-listed Markdown links, local assets, anchors and boundaries.

External URLs are counted but not fetched. Private archives are intentionally
outside this public-document check; non-Markdown local targets must still exist.
"""

import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

from docs_common import ROOT, heading_ids, load_manifest, markdown_links, split_fences


def check(root=ROOT):
    manifest = load_manifest(root)
    docs = set(manifest["documents"])
    drawings = {
        name for name in manifest.get("supporting_files", []) if name.endswith(".excalidraw.md")
    }
    errors, checked, external = [], 0, 0
    for name in sorted(docs):
        source = root / name
        text = source.read_text(encoding="utf-8")
        prose, _, fence_errors = split_fences(text)
        errors.extend(f"{name}: {error}" for error in fence_errors)
        if "[[" in prose or "]]" in prose:
            errors.append(f"{name}: Obsidian-only link/embed in public prose")
        for link, line in markdown_links(prose):
            parts = urlsplit(link)
            if parts.scheme in {"http", "https", "mailto"}:
                external += 1
                continue
            if parts.scheme or parts.netloc or parts.path.startswith("/"):
                errors.append(f"{name}:{line}: nonportable link {link}")
                continue
            target = (
                (source.parent / unquote(parts.path)).resolve() if parts.path else source.resolve()
            )
            if not target.is_relative_to(root.resolve()):
                errors.append(f"{name}:{line}: link escapes repository: {link}")
                continue
            relative = target.relative_to(root.resolve()).as_posix()
            if any(part.startswith(".") for part in Path(relative).parts) and not relative.endswith(
                ".env.example"
            ):
                errors.append(f"{name}:{line}: link into private/hidden files: {link}")
                continue
            if not target.exists():
                errors.append(f"{name}:{line}: missing target: {link}")
                continue
            if target.suffix == ".md" and relative not in docs | drawings:
                errors.append(f"{name}:{line}: Markdown target outside public manifest: {link}")
            if parts.fragment and target.suffix == ".md":
                if unquote(parts.fragment) not in heading_ids(target.read_text(encoding="utf-8")):
                    errors.append(f"{name}:{line}: missing heading: {link}")
            checked += 1
    return errors, len(docs), checked, external


def main():
    try:
        errors, count, links, external = check()
    except (ValueError, KeyError, OSError) as exc:
        print(f"Document manifest error: {exc}")
        return 1
    if errors:
        print("\n".join(errors))
        return 1
    print(
        f"Links OK: {count} public documents, {links} local links/assets/anchors; {external} external links not fetched."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
