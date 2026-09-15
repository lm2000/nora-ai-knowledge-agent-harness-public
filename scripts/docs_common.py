"""Shared, dependency-free checks for the manifest-listed public documentation."""

import json
import re
import subprocess
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_manifest(root=ROOT):
    data = json.loads((root / "public-docs.json").read_text(encoding="utf-8"))
    docs = data["documents"]
    supporting = data.get("supporting_files", [])
    if not docs or len(docs + supporting) != len(set(docs + supporting)):
        raise ValueError("Manifest must list a nonempty, unique set of files")
    for name in docs + supporting:
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or any(p.startswith(".") for p in path.parts):
            raise ValueError(f"Nonpublic or nonrelative manifest path: {name}")
        target = root / path
        if not target.is_file() or target.is_symlink():
            raise ValueError(f"Missing file or symlink: {name}")
        if not target.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"File resolves outside repository: {name}")
    if any(not name.endswith(".md") for name in docs):
        raise ValueError("The documents list must contain Markdown files")
    # Catch a newly added public Markdown page accidentally omitted from checks.
    inventory = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        capture_output=True,
        text=True,
        check=False,
    )
    if inventory.returncode == 0:
        active = {
            name
            for name in inventory.stdout.split("\0")
            if name.endswith(".md") and (root / name).is_file()
        }
        drawings = {name for name in supporting if name.endswith(".excalidraw.md")}
        unlisted = active - set(docs) - drawings
        if unlisted:
            raise ValueError(f"Markdown files outside public manifest: {sorted(unlisted)}")
    return data


def split_fences(text):
    """Return prose, (language, body, starting line) blocks and fence errors."""
    prose, blocks, errors = [], [], []
    opened, body = None, []
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if opened:
            if (
                marker
                and marker[1][0] == opened[0][0]
                and len(marker[1]) >= len(opened[0])
                and not marker[2].strip()
            ):
                blocks.append((opened[1], "\n".join(body), opened[2]))
                opened, body = None, []
            else:
                body.append(line)
            prose.append("")
        elif marker:
            opened = (marker[1], marker[2].strip(), number)
            prose.append("")
        else:
            prose.append(line)
    if opened:
        errors.append(f"Unclosed code fence at line {opened[2]}")
    return "\n".join(prose), blocks, errors


def heading_ids(text):
    """GitHub-style IDs for the ATX headings used by this documentation set."""
    prose, _, _ = split_fences(text)
    ids, seen = set(), {}
    for line in prose.splitlines():
        match = re.match(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        heading = re.sub(r"<[^>]*>", "", match[1]).lower()
        heading = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", heading)
        slug = "".join(c for c in heading if c in "-_ " or unicodedata.category(c)[0] in "LN")
        slug = slug.replace(" ", "-")
        base = slug
        suffix = seen.get(base, 0)
        while slug in ids:
            suffix += 1
            slug = f"{base}-{suffix}"
        seen[base] = suffix
        ids.add(slug)
    ids.update(re.findall(r'<a\s+(?:id|name)=["\']([^"\']+)', prose))
    return ids


def markdown_links(prose):
    # Inline links/images and reference definitions. Code fences are removed by callers.
    for match in re.finditer(
        r'!?\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+["\'][^\n]*?["\'])?\)', prose
    ):
        yield match[1].strip("<>"), prose[: match.start()].count("\n") + 1
    for match in re.finditer(r"^ {0,3}\[[^\]]+\]:\s*(<[^>]+>|\S+)", prose, re.M):
        yield match[1].strip("<>"), prose[: match.start()].count("\n") + 1
