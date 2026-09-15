"""Stable representation shared by preparation, indexing and retrieval."""

import collections
import hashlib
import re
import uuid

from qdrant_client import models

MODEL = "BAAI/bge-base-en-v1.5"
REVISION = "a5beb1e3e68b9ab74eb54cfd186867f64f240e1a"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
DIMENSION = 768
MAX_TOKENS = 512
CHUNK_NAMESPACE = uuid.UUID("f227de5e-d2b8-4ab7-8457-6714b9de317e")
REPRESENTATION = {
    "model": MODEL,
    "revision": REVISION,
    "dimension": DIMENSION,
    "pooling": "cls",
    "normalized": True,
    "lexical": "hashed-tf-v1",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def valid_document_id(value: str) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def sparse(text: str, *, document: bool = False) -> models.SparseVector:
    """Hashed lexical term frequency; this is not a complete BM25 scorer."""
    counts = collections.Counter(re.findall(r"[^\W_]+", text.lower(), re.UNICODE))
    hashed: dict[int, float] = collections.defaultdict(float)
    length = sum(counts.values())
    for term, count in counts.items():
        if len(term) < 2:
            continue
        index = int.from_bytes(hashlib.blake2b(term.encode(), digest_size=4).digest(), "big")
        hashed[index] += (
            count * 2.5 / (count + 1.5 * (0.25 + 0.75 * length / 350)) if document else 1.0
        )
    indices = sorted(hashed)
    return models.SparseVector(indices=indices, values=[hashed[index] for index in indices])
