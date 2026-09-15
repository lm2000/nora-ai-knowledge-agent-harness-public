"""Content-addressed prepared-document stores used by either deployment target."""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from nora.common import digest, valid_document_id


class DocumentStore(Protocol):
    def read(self, doc_id: str) -> str: ...


class LocalDocumentStore:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()

    def read(self, doc_id: str) -> str:
        if not valid_document_id(doc_id):
            raise ValueError("Invalid document ID")
        path = self.directory / f"{doc_id}.txt"
        if path.is_symlink() or not path.resolve().is_relative_to(self.directory):
            raise ValueError("Prepared document must remain inside its store")
        raw = path.read_bytes()
        if digest(raw) != doc_id:
            raise ValueError("Prepared document checksum mismatch")
        return raw.decode("utf-8")


class GCSDocumentStore:
    """Reads exact object generations; cloud credentials use the normal ADC chain."""

    def __init__(self, manifest, client=None):
        if isinstance(manifest, Path):
            self.manifest = json.loads(manifest.read_text(encoding="utf-8"))
            self._loaded_from = str(manifest)
        elif isinstance(manifest, dict):
            self.manifest = manifest
            self._loaded_from = None
        else:
            raise TypeError("manifest must be a Path or dict")
        self.client = client

    def _client(self):
        if self.client is None:
            from google.cloud import storage

            self.client = storage.Client(project=self.manifest.get("project"))
        return self.client

    def read(self, doc_id: str) -> str:
        if not valid_document_id(doc_id):
            raise ValueError("Invalid document ID")
        entry = self.manifest["documents"].get(doc_id)
        if not entry:
            raise FileNotFoundError("Document is absent from the prepared manifest")
        generation = int(entry["generation"])
        if generation <= 0 or not isinstance(entry["object"], str) or not entry["object"]:
            raise ValueError("Invalid prepared object binding")
        raw = (
            self._client()
            .bucket(self.manifest["bucket"])
            .blob(entry["object"], generation=generation)
            .download_as_bytes(timeout=30)
        )
        if digest(raw) != doc_id:
            raise ValueError("Prepared document checksum mismatch")
        return raw.decode("utf-8")


def publish_release(
    release_dir: Path,
    bucket: str,
    prefix: str,
    client,
    *,
    collection: str | None = None,
) -> dict:
    """Upload full prepared documents and write a generation-pinned release manifest."""
    release_dir = release_dir.resolve()
    docs_dir = release_dir / "docs"
    coverage_path = release_dir / "coverage.json"
    if not docs_dir.is_dir():
        raise ValueError("Release has no prepared documents")
    if not coverage_path.exists():
        raise ValueError("Release coverage missing")
    coverage = json.loads(coverage_path.read_text())
    if coverage.get("phase") != "embedded":
        raise ValueError("Release must be embedded before publishing")
    release_tag = uuid.uuid4().hex[:12]
    documents = {}
    for path in sorted(docs_dir.glob("*.txt")):
        doc_id = path.stem
        if not valid_document_id(doc_id):
            raise ValueError(f"Invalid document filename: {path.name}")
        object_name = f"{prefix}/{release_tag}/docs/{doc_id}.txt".lstrip("/")
        blob = client.bucket(bucket).blob(object_name)
        blob.upload_from_filename(path)
        raw = path.read_bytes()
        if digest(raw) != doc_id:
            raise ValueError(f"Document content does not match its ID: {doc_id}")
        documents[doc_id] = {"object": object_name, "generation": blob.generation}
    manifest = {
        "schema_version": 1,
        "bucket": bucket,
        "prefix": prefix,
        "release_tag": release_tag,
        "representation": coverage.get("representation", {}),
        "collection": collection or coverage.get("qdrant_collection", ""),
        "documents": documents,
        "coverage": {"documents": coverage.get("documents"), "chunks": coverage.get("chunks")},
    }
    manifest_name = f"{prefix}/{release_tag}/manifest.json".lstrip("/")
    manifest_blob = client.bucket(bucket).blob(manifest_name)
    manifest_blob.upload_from_string(json.dumps(manifest, indent=2))
    manifest["manifest_object"] = manifest_name
    manifest["manifest_generation"] = manifest_blob.generation
    return manifest


def write_pointer(path: Path, manifest: dict) -> Path:
    """Atomically write a local activation pointer to a generation-pinned GCS manifest."""
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, indent=2) + "\n"
    tmp = path.parent / (path.name + ".tmp." + uuid.uuid4().hex)
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)
    return path


POINTER_SCHEMA_VERSION = 1


def parse_gs_url(url: str) -> tuple[str, str]:
    """Parse gs://bucket/object into (bucket, object_name)."""
    if not isinstance(url, str) or not url.startswith("gs://"):
        raise ValueError("GCS pointer must be a gs:// URL")
    rest = url[5:]
    if "/" not in rest:
        raise ValueError("GCS pointer must include an object path")
    bucket, _, object_name = rest.partition("/")
    if not bucket or not object_name:
        raise ValueError("GCS pointer must include a bucket and an object path")
    return bucket, object_name.lstrip("/")


def read_cloud_pointer(bucket: str, object_name: str, client) -> dict:
    """Download the authoritative cloud activation pointer."""
    data = client.bucket(bucket).blob(object_name).download_as_bytes(timeout=30)
    pointer = json.loads(data.decode("utf-8"))
    if pointer.get("schema_version") != POINTER_SCHEMA_VERSION:
        raise ValueError("Unsupported cloud activation pointer schema")
    active = pointer.get("active_manifest")
    if not isinstance(active, dict) or not active.get("object") or not active.get("generation"):
        raise ValueError("Cloud activation pointer is missing an active manifest")
    return pointer


def load_manifest_from_pointer_entry(entry: dict, client) -> dict:
    """Download a specific generation-pinned manifest object."""
    bucket = entry.get("bucket")
    object_name = entry.get("object")
    generation = entry.get("generation")
    if not bucket or not object_name or not generation:
        raise ValueError("Invalid manifest pointer entry")
    data = (
        client.bucket(bucket)
        .blob(object_name, generation=int(generation))
        .download_as_bytes(timeout=30)
    )
    manifest = json.loads(data.decode("utf-8"))
    manifest.setdefault("bucket", bucket)
    manifest.setdefault("manifest_object", object_name)
    manifest.setdefault("manifest_generation", generation)
    return manifest


def write_cloud_pointer(
    bucket: str,
    object_name: str,
    active_manifest: dict,
    client,
    *,
    expected_generation: int | None = None,
) -> dict:
    """Atomically update the authoritative cloud activation pointer.

    `expected_generation` enables compare-and-swap activation: pass the current
    pointer generation, or 0 when the pointer does not yet exist.
    """
    pointer = {
        "schema_version": POINTER_SCHEMA_VERSION,
        "prefix": active_manifest.get("prefix", ""),
        "active_manifest": {
            "bucket": active_manifest["bucket"],
            "object": active_manifest["manifest_object"],
            "generation": active_manifest["manifest_generation"],
            "release_tag": active_manifest.get("release_tag", ""),
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    blob = client.bucket(bucket).blob(object_name)
    blob.upload_from_string(
        json.dumps(pointer, indent=2) + "\n",
        if_generation_match=expected_generation,
        timeout=30,
    )
    return {
        "bucket": bucket,
        "object": object_name,
        "generation": blob.generation,
        "active_manifest": pointer["active_manifest"],
    }


def passage(store: DocumentStore, doc_id: str, offset: int = 0, limit: int = 8000) -> dict:
    if not valid_document_id(doc_id):
        return {"error": "invalid document ID"}
    try:
        text = store.read(doc_id)
    except FileNotFoundError:
        return {"error": "document not found"}
    offset = max(0, min(offset, len(text)))
    limit = max(1, min(limit, 8000))
    end = min(len(text), offset + limit)
    return {
        "doc_id": doc_id,
        "text": text[offset:end],
        "next_offset": end if end < len(text) else None,
    }
