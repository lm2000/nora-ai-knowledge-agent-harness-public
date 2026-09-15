"""Validate, import and independently verify a prepared index bundle."""

import json
import uuid
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient, models

from nora.common import DIMENSION, REPRESENTATION, digest, sparse, valid_document_id
from nora.config import Settings, credential
from nora.documents import LocalDocumentStore


def connect(settings: Settings, *, timeout: int = 60) -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, api_key=credential("QDRANT_KEY"), timeout=timeout)


def valid_categories(value) -> bool:
    """Preserve nonempty, unique source labels without accepting malformed payloads."""
    return (
        isinstance(value, list)
        and bool(value)
        and all(
            isinstance(label, str)
            and label.strip() == label
            and bool(label)
            and label.isprintable()
            for label in value
        )
        and len(set(value)) == len(value)
    )


def load_bundle(directory: Path):
    coverage = json.loads((directory / "coverage.json").read_text())
    if coverage.get("representation") != REPRESENTATION:
        raise ValueError("Bundle representation does not match this application")
    root = directory / "import"
    for name, field in [("chunks.jsonl", "chunks_sha256"), ("vectors.npy", "vectors_sha256")]:
        if digest((root / name).read_bytes()) != coverage.get(field):
            raise ValueError(f"Bundle checksum mismatch: {name}")
    rows = [json.loads(line) for line in (root / "chunks.jsonl").read_text().splitlines()]
    for row in rows:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("text"), str)
            or not row["text"].strip()
            or not isinstance(row.get("heading"), str)
            or not isinstance(row.get("doc_id"), str)
            or not valid_categories(row.get("categories"))
        ):
            raise ValueError("Invalid chunk metadata")
        try:
            if str(uuid.UUID(row["chunk_id"])) != row["chunk_id"]:
                raise ValueError("Noncanonical point ID")
        except (KeyError, TypeError, AttributeError, ValueError) as error:
            raise ValueError("Invalid point ID") from error
    vectors = np.load(root / "vectors.npy", mmap_mode="r", allow_pickle=False)
    if not rows or len(rows) != coverage["chunks"] or vectors.shape != (len(rows), DIMENSION):
        raise ValueError("Bundle count or vector dimension mismatch")
    if not np.isfinite(vectors).all() or not np.allclose(
        np.linalg.norm(vectors, axis=1), 1, atol=0.001
    ):
        raise ValueError("Bundle vectors must be finite and normalized")
    ids, documents = {r["chunk_id"] for r in rows}, {r["doc_id"] for r in rows}
    if len(ids) != len(rows) or len(documents) != coverage["documents"]:
        raise ValueError("Duplicate point IDs or incorrect document count")
    if any(not valid_document_id(doc) for doc in documents):
        raise ValueError("Invalid document ID")
    if documents != {p.stem for p in (directory / "docs").glob("*.txt")}:
        raise ValueError("Prepared document inventory mismatch")
    store = LocalDocumentStore(directory / "docs")
    for doc_id in documents:
        store.read(doc_id)
    return coverage, rows, vectors


def point_ids(client, collection: str) -> set[str]:
    ids, offset = set(), None
    while True:
        points, offset = client.scroll(
            collection, limit=512, offset=offset, with_payload=False, with_vectors=False
        )
        ids.update(str(p.id) for p in points)
        if offset is None:
            return ids


def import_bundle(client, collection: str, directory: Path) -> dict:
    coverage, rows, vectors = load_bundle(directory)
    expected = {row["chunk_id"] for row in rows}
    if client.collection_exists(collection):
        info = client.get_collection(collection)
        config = info.config.params.vectors
        dense = config.get("dense") if isinstance(config, dict) else None
        if not dense or dense.size != DIMENSION or dense.distance != models.Distance.COSINE:
            raise ValueError("Existing collection uses a different dense representation")
        lexical = (info.config.params.sparse_vectors or {}).get("lexical")
        if not lexical or lexical.modifier != models.Modifier.IDF:
            raise ValueError("Existing collection uses a different lexical representation")
        existing = point_ids(client, collection)
        if existing and existing != expected:
            raise ValueError(
                "Use a new collection for a changed dataset; existing points are preserved"
            )
    else:
        client.create_collection(
            collection,
            vectors_config={
                "dense": models.VectorParams(
                    size=DIMENSION, distance=models.Distance.COSINE, on_disk=True
                )
            },
            sparse_vectors_config={
                "lexical": models.SparseVectorParams(
                    index=models.SparseIndexParams(on_disk=True), modifier=models.Modifier.IDF
                )
            },
            on_disk_payload=True,
        )
    for start in range(0, len(rows), 128):
        points = [
            models.PointStruct(
                id=row["chunk_id"],
                payload=row,
                vector={
                    "dense": vectors[index].tolist(),
                    "lexical": sparse(row["text"], document=True),
                },
            )
            for index, row in enumerate(rows[start : start + 128], start)
        ]
        client.upsert(collection, points=points, wait=True)
    if point_ids(client, collection) != expected:
        raise ValueError("Index point IDs differ after import")
    return {"imported": len(rows), "documents": coverage["documents"], "collection": collection}


def verify_bundle(client, collection: str, directory: Path) -> dict:
    coverage, rows, vectors = load_bundle(directory)
    expected = {row["chunk_id"]: row for row in rows}
    if point_ids(client, collection) != set(expected):
        raise ValueError("Stored point IDs differ from the prepared bundle")
    offset = None
    while True:
        points, offset = client.scroll(
            collection, limit=512, offset=offset, with_payload=True, with_vectors=False
        )
        for point in points:
            if point.payload != expected[str(point.id)]:
                raise ValueError("Stored text or metadata differs from the prepared bundle")
        if offset is None:
            break
    samples = {rows[i]["chunk_id"]: vectors[i] for i in {0, len(rows) // 2, len(rows) - 1}}
    stored = client.retrieve(collection, ids=list(samples), with_vectors=True, with_payload=False)
    if len(stored) != len(samples):
        raise ValueError("Stored vector sample is incomplete")
    for point in stored:
        if not np.allclose(point.vector["dense"], samples[str(point.id)], atol=0.00001):
            raise ValueError("Stored vector differs from the prepared bundle")
    return {
        "verified": True,
        "points": len(rows),
        "documents": coverage["documents"],
        "vector_samples": len(samples),
    }
