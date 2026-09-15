#!/usr/bin/env python3
"""Build a deterministic source snapshot from the explicit public file inventory."""

import argparse
import gzip
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCKED_PARTS = {
    ".git",
    ".private",
    ".runtime",
    ".release",
    "node_modules",
    ".next",
    "__pycache__",
    ".venv",
}
PRIVATE_KEY = re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----")
HOME_PATH = re.compile(r'(?:/Users/|/home/)[A-Za-z0-9][^\s"\'<>]*')
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
TOKEN = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|sk-(?:proj-)?[A-Za-z0-9_-]{30,})\b")


def sources(root: Path) -> dict[str, bytes]:
    manifest = json.loads((root / "release-manifest.json").read_text())
    names = manifest["files"]
    if not names or len(names) != len({name.casefold() for name in names}):
        raise ValueError(
            "Release files must be nonempty and unique, including case-insensitive paths"
        )
    if "source-checksums.json" in {name.casefold() for name in names}:
        raise ValueError("Source checksum filename is reserved")
    docs = json.loads((root / "public-docs.json").read_text())
    if not set(docs["documents"] + docs.get("supporting_files", [])) <= set(names):
        raise ValueError("Release omits public documentation or licenses")
    result = {}
    for name in sorted(names):
        relative = Path(name)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or BLOCKED_PARTS.intersection(relative.parts)
        ):
            raise ValueError("Nonpublic release path: " + name)
        path = root / relative
        if not path.is_file() or any(
            p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(root)
        ):
            raise ValueError("Missing source or symlink: " + name)
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Source resolves outside repository: " + name)
        if path.suffix in {".pem", ".key", ".env"} or name.endswith((".pyc", ".tsbuildinfo")):
            raise ValueError("Runtime artifact in release: " + name)
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        if PRIVATE_KEY.search(text) or HOME_PATH.search(text) or TOKEN.search(text):
            raise ValueError("Private path or credential marker in: " + name)
        if any(
            match[1].lower() not in {"example.com", "example.org", "example.net"}
            for match in EMAIL.finditer(text)
        ):
            raise ValueError("Non-example account address in: " + name)
        result[name] = raw
    return result


def build(root: Path, output: Path) -> dict:
    files = sources(root)
    receipt = {
        "schema_version": 1,
        "version": "0.1.0",
        "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()},
    }
    files["SOURCE-CHECKSUMS.json"] = (json.dumps(receipt, indent=2) + "\n").encode()
    packed = io.BytesIO()
    with gzip.GzipFile(fileobj=packed, mode="wb", filename="", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for name, raw in sorted(files.items()):
                info = tarfile.TarInfo("nora-0.1.0/" + name)
                info.size = len(raw)
                info.mode = (
                    0o755 if (name.endswith(".sh") or name == "scripts/knowledge-update") else 0o644
                )
                info.mtime = info.uid = info.gid = 0
                archive.addfile(info, io.BytesIO(raw))
    raw = packed.getvalue()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        if output.read_bytes() != raw:
            raise FileExistsError("Release output differs; choose a new output path")
    else:
        with output.open("xb") as stream:
            stream.write(raw)
    return {
        "archive": str(output),
        "source_files": len(receipt["files"]),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / ".release/nora-0.1.0-source.tar.gz")
    args = parser.parse_args()
    if args.check:
        print(json.dumps({"checked_public_source_files": len(sources(ROOT))}))
    else:
        print(json.dumps(build(ROOT, args.output), indent=2))
