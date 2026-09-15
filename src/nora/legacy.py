"""Adapt retained embeddings into an inactive release without rewriting source data."""

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

from nora.common import REPRESENTATION
from nora.indexing import load_bundle


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def adapt_legacy(source: Path, destination: Path, *, collection: str, document_bucket: str) -> dict:
    """Copy, validate and wrap a legacy bundle; never import or activate anything."""
    source, destination = source.resolve(), destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Destination already exists")
    if destination.resolve().is_relative_to(source):
        raise ValueError("Destination must be outside the legacy bundle")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", collection):
        raise ValueError("Choose an explicit versioned collection name")
    required = [
        "coverage.json",
        "import/coverage.json",
        "import/chunks.jsonl",
        "import/vectors.npy",
        "gcs-documents.json",
    ]
    for name in required:
        path = source / name
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(source):
            raise ValueError("Legacy input must be a regular file within its bundle")
    docs = source / "docs"
    if not docs.is_dir() or docs.is_symlink():
        raise ValueError("Legacy document directory is missing or unsafe")
    for path in docs.iterdir():
        if path.is_symlink() or not path.is_file() or path.suffix != ".txt":
            raise ValueError("Unexpected legacy document entry")
    original = json.loads((source / "coverage.json").read_text())
    imported = json.loads((source / "import/coverage.json").read_text())
    for key in ("documents", "chunks", "model", "revision", "dimension", "vector_sha256"):
        if original.get(key) != imported.get(key):
            raise ValueError("Legacy root and import coverage disagree")
    for key in ("model", "revision", "dimension"):
        if original.get(key) != REPRESENTATION[key]:
            raise ValueError("Legacy dense representation differs")
    if original.get("failed_documents") != 0 or original.get("omitted_documents") != 0:
        raise ValueError("Resolve legacy document exclusions before adapting")
    hashes = {name: file_sha256(source / name) for name in required}
    if hashes["import/vectors.npy"] != original.get("vector_sha256"):
        raise ValueError("Legacy vector checksum mismatch")
    manifest = json.loads((source / "gcs-documents.json").read_text())
    if not document_bucket or document_bucket != manifest.get("bucket"):
        raise ValueError("Explicit document bucket must match the retained generation bindings")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="." + destination.name + "-", dir=destination.parent))
    try:
        (temporary / "import").mkdir()
        (temporary / "provenance").mkdir()
        shutil.copytree(docs, temporary / "docs")
        for name in ("chunks.jsonl", "vectors.npy"):
            shutil.copy2(source / "import" / name, temporary / "import" / name)
        for name in required:
            if name not in ("import/chunks.jsonl", "import/vectors.npy"):
                target = temporary / "provenance" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / name, target)
        coverage = dict(original)
        coverage.update(
            schema_version=1,
            phase="embedded",
            representation=REPRESENTATION,
            chunks_sha256=hashes["import/chunks.jsonl"],
            vectors_sha256=hashes["import/vectors.npy"],
            qdrant_collection=collection,
            legacy_provenance={"coverage": "provenance/coverage.json", "sha256": hashes},
        )
        _json(temporary / "coverage.json", coverage)
        _json(temporary / "import/coverage.json", coverage)
        verified, rows, vectors = load_bundle(temporary)
        document_ids = {row["doc_id"] for row in rows}
        entries = manifest.get("documents", {})
        if set(entries) != document_ids:
            raise ValueError("Legacy GCS manifest inventory differs")
        for doc_id, entry in entries.items():
            if (
                not isinstance(entry, dict)
                or not isinstance(entry.get("object"), str)
                or not entry["object"]
            ):
                raise ValueError("Invalid legacy GCS object binding")
            if not re.fullmatch(r"[1-9][0-9]*", str(entry.get("generation", ""))):
                raise ValueError("Invalid legacy GCS generation")
            if entry.get("bytes") != (temporary / "docs" / f"{doc_id}.txt").stat().st_size:
                raise ValueError("Legacy GCS document size differs")
        # Exact file equality preserves categories, IDs and the physical row-to-vector mapping.
        for name in ("import/chunks.jsonl", "import/vectors.npy"):
            if file_sha256(temporary / name) != hashes[name]:
                raise ValueError("Copied data checksum mismatch")
        # Also detect a source change during the copy; never modify source files.
        if any(file_sha256(source / name) != value for name, value in hashes.items()):
            raise ValueError("Legacy source changed during adaptation")
        if {p.stem for p in docs.glob("*.txt")} != document_ids:
            raise ValueError("Legacy document inventory changed during adaptation")
        for doc_id in document_ids:
            if file_sha256(source / "docs" / f"{doc_id}.txt") != doc_id:
                raise ValueError("Legacy source document changed during adaptation")
        release = {
            "schema_version": 1,
            "bucket": document_bucket,
            "project": manifest.get("project"),
            "prefix": "releases",
            "release_tag": destination.name,
            "representation": REPRESENTATION,
            "collection": collection,
            "documents": entries,
            "coverage": {"documents": verified["documents"], "chunks": verified["chunks"]},
        }
        _json(temporary / "release-manifest.json", release)
        # Completion of reused embedding verification, not a claim of a new model run.
        _json(
            temporary / "job-embed.json",
            {
                "stage": "embed",
                "method": "verified-legacy-reuse",
                "qdrant_collection": collection,
                "vectors_sha256": coverage["vectors_sha256"],
                "shape": list(vectors.shape),
            },
        )
        receipt = {
            "adapted": True,
            "imported": False,
            "activated": False,
            "dense_reembedded": False,
            "documents": verified["documents"],
            "chunks": len(rows),
            "collection": collection,
            "source_files_sha256": hashes,
            "preserved": [
                "documents",
                "chunk_bytes",
                "categories",
                "ids",
                "vector_bytes",
                "row_order",
            ],
            "loader_verified": True,
            "gcs_bindings_validated_offline": True,
            "gcs_read_verified": False,
            "manifest_published": False,
        }
        _json(temporary / "adapter-receipt.json", receipt)
        if destination.exists() or destination.is_symlink():
            raise FileExistsError("Destination appeared during adaptation")
        temporary.rename(destination)
        return receipt
    except BaseException:
        shutil.rmtree(temporary)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--collection", required=True)
    parser.add_argument("--document-bucket", required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            adapt_legacy(
                args.source,
                args.destination,
                collection=args.collection,
                document_bucket=args.document_bucket,
            )
        )
    )


if __name__ == "__main__":
    main()
