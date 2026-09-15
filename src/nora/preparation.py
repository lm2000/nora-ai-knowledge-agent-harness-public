"""Deterministic, manually invoked preparation into a new self-contained bundle."""

import base64
import html
import json
import os
import re
import tempfile
import unicodedata
import uuid
from pathlib import Path

import numpy as np

from nora.common import CHUNK_NAMESPACE, DIMENSION, MAX_TOKENS, REPRESENTATION, digest


def _decode_body(value: str) -> str:
    try:
        return base64.b64decode(
            value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
        ).decode("utf-8")
    except (ValueError, UnicodeError):
        return ""


def _html_text(value: str) -> str:
    value = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", value)
    value = re.sub(r"(?i)<br\s*/?>|</(?:p|div|li|tr|h[1-6])>", "\n", value)
    return html.unescape(re.sub(r"(?s)<[^>]+>", " ", value)).strip()


def searchable_text(text: str) -> str:
    """Decode recognizable mail exports; leave ordinary text's substance intact."""
    clean = text
    if text.lstrip().startswith("{"):
        try:
            item = json.loads(text)
        except json.JSONDecodeError:
            item = None
        if isinstance(item, dict) and isinstance(item.get("payload"), dict):
            bodies: list[tuple[str, str]] = []

            def visit(part):
                mime = part.get("mimeType", "")
                data = part.get("body", {}).get("data", "")
                if mime in {"text/plain", "text/html"} and data:
                    decoded = _decode_body(data)
                    if decoded.strip():
                        bodies.append((mime, decoded))
                for child in part.get("parts", []):
                    visit(child)

            visit(item["payload"])
            plain = [body for mime, body in bodies if mime == "text/plain"]
            selected = plain or [_html_text(body) for _, body in bodies]
            subject = next(
                (
                    h.get("value", "")
                    for h in item["payload"].get("headers", [])
                    if h.get("name", "").lower() == "subject"
                ),
                "",
            )
            if selected:
                clean = (subject + "\n\n" + "\n\n".join(dict.fromkeys(selected))).strip()
    elif re.match(r"\s*(?:id|threadId|labelIds):", text):
        bodies = [
            _decode_body(m[1])
            for m in re.finditer(r"(?m)^\s*data:\s*([A-Za-z0-9+/_=-]{20,})\s*$", text)
        ]
        bodies = [body for body in bodies if body.strip()]
        plain = [
            body for body in bodies if not re.search(r"(?i)<(?:html|body|div|table)", body[:2000])
        ]
        if bodies:
            clean = max(plain, key=len) if plain else _html_text(max(bodies, key=len))
    clean = re.sub(r"(?m)^\s*(?:data|value):\s*[A-Za-z0-9+/_=-]{512,}\s*$", "", clean)
    return "".join(c for c in clean if unicodedata.category(c) != "Cf")


def chunks_for(text: str, doc_id: str, tokenizer):
    clean = searchable_text(text)
    starts = (
        [0] + [m.start() for m in re.finditer(r"(?m)^#{1,6} ", clean) if m.start()] + [len(clean)]
    )
    for section, (begin, end) in enumerate(zip(starts, starts[1:])):
        part = clean[begin:end]
        offsets = tokenizer(part, add_special_tokens=False, return_offsets_mapping=True)[
            "offset_mapping"
        ]
        heading = part.splitlines()[0][:180] if part.startswith("#") else ""
        for first in range(0, len(offsets), 332):
            last = min(first + 380, len(offsets))
            body = part[offsets[first][0] : offsets[last - 1][1]]
            if not body.strip():
                continue
            if len(tokenizer(body, add_special_tokens=True)["input_ids"]) > MAX_TOKENS:
                raise ValueError("Chunk exceeds the complete token limit")
            yield {
                "chunk_id": str(uuid.uuid5(CHUNK_NAMESPACE, f"{doc_id}:{section}:{first}")),
                "doc_id": doc_id,
                "heading": heading,
                "text": body,
                "categories": ["documents"],
            }
            if last == len(offsets):
                break


def prepare_texts(input_dir: Path, output: Path, tokenizer) -> dict:
    """Normalize and chunk documents without embedding. Existing outputs are never overwritten."""
    input_dir, output = input_dir.resolve(), output.resolve()
    if not input_dir.is_dir():
        raise ValueError("Input must be a document directory")
    if output.is_relative_to(input_dir):
        raise ValueError("Output must be outside the input directory")
    if output.exists():
        raise FileExistsError("Choose a new output directory for this preparation run")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".nora-prepare-texts-", dir=output.parent) as tmp:
        stage = Path(tmp) / "bundle"
        (stage / "docs").mkdir(parents=True)
        (stage / "import").mkdir()
        documents, rows, excluded = set(), [], []
        duplicate_count = 0
        for path in sorted(input_dir.rglob("*")):
            if path.is_dir() and not path.is_symlink():
                continue
            relative = path.relative_to(input_dir)
            reason = None
            if path.is_symlink():
                reason = "symlink"
            elif any(p.startswith(".") or p == "__MACOSX" for p in relative.parts):
                reason = "metadata"
            elif path.suffix.lower() not in {".md", ".txt", ".json"}:
                reason = "unsupported_format"
            if reason:
                excluded.append({"path": str(relative), "reason": reason})
                continue
            try:
                raw = path.read_bytes()
                text = raw.decode("utf-8")
            except (OSError, UnicodeError):
                excluded.append({"path": str(relative), "reason": "unreadable"})
                continue
            if not text.strip() or "\0" in text:
                excluded.append({"path": str(relative), "reason": "empty_or_binary"})
                continue
            doc_id = digest(raw)
            if doc_id in documents:
                duplicate_count += 1
                continue
            prepared_rows = list(chunks_for(text, doc_id, tokenizer))
            if not prepared_rows:
                excluded.append({"path": str(relative), "reason": "no_searchable_text"})
                continue
            documents.add(doc_id)
            (stage / "docs" / f"{doc_id}.txt").write_bytes(raw)
            rows.extend(prepared_rows)
        if not rows:
            raise ValueError("No readable, searchable documents were found")
        chunk_path = stage / "import/chunks.jsonl"
        chunk_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
        )
        coverage = {
            "schema_version": 1,
            "phase": "prepared",
            "documents": len(documents),
            "chunks": len(rows),
            "exact_duplicates": duplicate_count,
            "excluded": excluded,
            "representation": REPRESENTATION,
            "chunks_sha256": digest(chunk_path.read_bytes()),
        }
        for path in [stage / "coverage.json", stage / "import/coverage.json"]:
            path.write_text(json.dumps(coverage, indent=2) + "\n", encoding="utf-8")
        if output.exists():
            raise FileExistsError("Output appeared during preparation")
        os.rename(stage, output)
        return coverage


def embed_bundle(
    bundle_dir: Path, encoder, *, batch_size: int = 8, qdrant_collection: str | None = None
) -> dict:
    """Encode chunks in an existing bundle and add vectors to its coverage."""
    bundle_dir = bundle_dir.resolve()
    chunk_path = bundle_dir / "import/chunks.jsonl"
    vector_path = bundle_dir / "import/vectors.npy"
    coverage_path = bundle_dir / "coverage.json"
    if not chunk_path.exists():
        raise ValueError("Bundle has no chunk records")
    if coverage_path.exists():
        coverage = json.loads(coverage_path.read_text())
    else:
        coverage = {}
    rows = [json.loads(line) for line in chunk_path.read_text().splitlines()]
    if not rows:
        raise ValueError("No chunks to encode")
    if batch_size <= 0:
        raise ValueError("Batch size must be positive")
    vector_path.parent.mkdir(parents=True, exist_ok=True)
    vectors = np.lib.format.open_memmap(
        vector_path, mode="w+", dtype="float32", shape=(len(rows), DIMENSION)
    )
    for start in range(0, len(rows), batch_size):
        texts = [row["text"] for row in rows[start : start + batch_size]]
        result = np.asarray(encoder.encode(texts), dtype=np.float32)
        if result.shape != (len(texts), DIMENSION) or not np.isfinite(result).all():
            raise ValueError("Embedding output has invalid shape or values")
        if not np.allclose(np.linalg.norm(result, axis=1), 1, atol=0.001):
            raise ValueError("Embeddings must be normalized")
        vectors[start : start + len(texts)] = result
    vectors.flush()
    del vectors
    update = {
        "phase": "embedded",
        "chunks": len(rows),
        "vectors_sha256": digest(vector_path.read_bytes()),
    }
    if qdrant_collection is not None:
        update["qdrant_collection"] = qdrant_collection
    coverage.update(update)
    for path in [bundle_dir / "coverage.json", bundle_dir / "import/coverage.json"]:
        path.write_text(json.dumps(coverage, indent=2) + "\n", encoding="utf-8")
    return coverage


def prepare(input_dir: Path, output: Path, encoder, *, batch_size: int = 8) -> dict:
    """Create a new bundle including embeddings (legacy combined path)."""
    input_dir, output = input_dir.resolve(), output.resolve()
    if output.exists():
        raise FileExistsError("Choose a new output directory for this preparation run")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".nora-prepare-", dir=output.parent) as tmp:
        stage = Path(tmp) / "bundle"
        prepare_texts(input_dir, stage, encoder.tokenizer)
        coverage = embed_bundle(stage, encoder, batch_size=batch_size)
        if output.exists():
            raise FileExistsError("Output appeared during preparation")
        os.rename(stage, output)
    return coverage
