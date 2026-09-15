import base64
import json
from unittest.mock import MagicMock

import numpy as np
import pytest
from qdrant_client import models

from nora.common import digest
from nora.documents import GCSDocumentStore, LocalDocumentStore, passage
from nora.embedding import BGEEncoder
from nora.indexing import import_bundle, point_ids, verify_bundle
from nora.preparation import chunks_for, prepare, searchable_text
from nora.retrieval import RetrievalService


def test_preparation_preserves_originals_and_accounts_for_exclusions(tmp_path, encoder):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    original = b"# Plan\nAtlas ships after its rollback rehearsal.\n"
    (inputs / "one.md").write_bytes(original)
    (inputs / "duplicate.txt").write_bytes(original)
    (inputs / "empty.txt").write_text(" ")
    (inputs / "bad.txt").write_bytes(b"\xff")
    (inputs / ".DS_Store").write_text("metadata")
    (inputs / "image.png").write_bytes(b"image")
    (inputs / "link.md").symlink_to(inputs / "one.md")
    output = tmp_path / "output"
    result = prepare(inputs, output, encoder)
    assert result["documents"] == result["chunks"] == result["exact_duplicates"] == 1
    assert {row["reason"] for row in result["excluded"]} == {
        "empty_or_binary",
        "unreadable",
        "metadata",
        "unsupported_format",
        "symlink",
    }
    assert (output / "docs" / (digest(original) + ".txt")).read_bytes() == original
    assert (inputs / "one.md").read_bytes() == original
    with pytest.raises(FileExistsError):
        prepare(inputs, output, encoder)
    with pytest.raises(ValueError, match="outside"):
        prepare(inputs, inputs / "nested", encoder)


def test_chunk_boundaries_are_complete_and_stable(encoder):
    text = "# Section\n" + " ".join(f"word{i}" for i in range(1000))
    rows = list(chunks_for(text, "a" * 64, encoder.tokenizer))
    assert len(rows) == 3
    assert "word999" in rows[-1]["text"]
    assert all(
        len(encoder.tokenizer(row["text"], add_special_tokens=True)["input_ids"]) <= 512
        for row in rows
    )
    assert rows == list(chunks_for(text, "a" * 64, encoder.tokenizer))


def test_mail_decoding_prefers_plain_text_and_drops_script():
    def data(text):
        return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")

    mail = {
        "payload": {
            "headers": [{"name": "Subject", "value": "Release"}],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": data("Rollback is required.")}},
                {
                    "mimeType": "text/html",
                    "body": {"data": data("<script>hidden</script><p>Other body</p>")},
                },
            ],
        }
    }
    assert searchable_text(json.dumps(mail)) == "Release\n\nRollback is required."
    del mail["payload"]["parts"][0]
    assert searchable_text(json.dumps(mail)) == "Release\n\nOther body"


def test_empty_or_failed_preparation_leaves_no_partial_output(tmp_path, encoder):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    with pytest.raises(ValueError, match="No readable"):
        prepare(inputs, tmp_path / "output", encoder)
    (inputs / "one.txt").write_text("Content")
    encoder.encode = lambda texts: np.zeros((len(texts), 768))
    with pytest.raises(ValueError, match="normalized"):
        prepare(inputs, tmp_path / "output", encoder)
    assert not (tmp_path / "output").exists()


def test_index_roundtrip_and_hybrid_search(bundle, qdrant, encoder):
    assert import_bundle(qdrant, "test", bundle)["documents"] == 3
    assert import_bundle(qdrant, "test", bundle)["documents"] == 3
    assert verify_bundle(qdrant, "test", bundle)["verified"]
    service = RetrievalService(
        qdrant, encoder, LocalDocumentStore(bundle / "docs"), collection="test", data_dir=bundle
    )
    hits = service.search("Cedar priority incident support", 5)["results"]
    assert "Cedar" in hits[0]["text"]
    assert len({r["doc_id"] for r in hits}) == len(hits) == 3
    assert service.health()["ready"]
    assert service.read(hits[0]["doc_id"], limit=10)["next_offset"] == 10


@pytest.mark.parametrize("corruption", ["checksum", "metadata", "point", "source"])
def test_invalid_bundle_never_creates_collection(bundle, qdrant, corruption):
    chunks = bundle / "import/chunks.jsonl"
    if corruption == "source":
        next((bundle / "docs").glob("*.txt")).write_text("Changed")
    else:
        rows = [json.loads(line) for line in chunks.read_text().splitlines()]
        if corruption == "metadata":
            rows[0]["text"] = None
        elif corruption == "point":
            rows[0]["chunk_id"] = "bad-point"
        elif corruption == "checksum":
            rows[0]["text"] += " changed"
        chunks.write_text("".join(json.dumps(row) + "\n" for row in rows))
        if corruption != "checksum":
            coverage = json.loads((bundle / "coverage.json").read_text())
            coverage["chunks_sha256"] = digest(chunks.read_bytes())
            (bundle / "coverage.json").write_text(json.dumps(coverage))
    with pytest.raises(ValueError):
        import_bundle(qdrant, "test", bundle)
    assert not qdrant.collection_exists("test")


def test_changed_dataset_preserves_existing_index(bundle, tmp_path, encoder, qdrant):
    import_bundle(qdrant, "test", bundle)
    original_ids = point_ids(qdrant, "test")
    inputs = tmp_path / "new"
    inputs.mkdir()
    (inputs / "new.md").write_text("# Separate dataset\nA different document.")
    prepare(inputs, tmp_path / "changed", encoder)
    with pytest.raises(ValueError, match="new collection"):
        import_bundle(qdrant, "test", tmp_path / "changed")
    assert point_ids(qdrant, "test") == original_ids
    assert verify_bundle(qdrant, "test", bundle)["verified"]


def test_wrong_lexical_representation_rejected(bundle, qdrant):
    qdrant.create_collection(
        "test",
        vectors_config={"dense": models.VectorParams(size=768, distance=models.Distance.COSINE)},
    )
    with pytest.raises(ValueError, match="lexical"):
        import_bundle(qdrant, "test", bundle)
    assert qdrant.count("test").count == 0


def test_verification_detects_payload_tampering(bundle, qdrant):
    import_bundle(qdrant, "test", bundle)
    point = next(iter(point_ids(qdrant, "test")))
    qdrant.set_payload("test", {"text": "changed"}, points=[point])
    with pytest.raises(ValueError, match="metadata"):
        verify_bundle(qdrant, "test", bundle)


def test_document_store_checks_hash_and_path(bundle):
    store = LocalDocumentStore(bundle / "docs")
    doc = next((bundle / "docs").glob("*.txt"))
    assert passage(store, doc.stem, offset=-10, limit=5)["next_offset"] == 5
    assert passage(store, "../elsewhere")["error"] == "invalid document ID"
    original = doc.read_bytes()
    doc.write_text("tampered")
    with pytest.raises(ValueError, match="checksum"):
        store.read(digest(original))


def test_gcs_binds_generation_and_content_hash(tmp_path):
    content = b"Synthetic cloud document"
    doc = digest(content)
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "bucket": "example-prepared",
                "documents": {doc: {"object": "docs/one.txt", "generation": 17}},
            }
        )
    )
    client = MagicMock()
    blob = client.bucket.return_value.blob.return_value
    blob.download_as_bytes.return_value = content
    store = GCSDocumentStore(path, client)
    assert store.read(doc) == content.decode()
    client.bucket.return_value.blob.assert_called_with("docs/one.txt", generation=17)
    blob.download_as_bytes.return_value = b"tampered"
    with pytest.raises(ValueError, match="checksum"):
        store.read(doc)


def test_model_cache_rejects_wrong_revision_without_loading_weights(tmp_path):
    (tmp_path / "nora-model.json").write_text(
        json.dumps({"model": "wrong", "revision": "wrong", "files": {"config.json": "bad"}})
    )
    with pytest.raises(ValueError, match="pinned"):
        BGEEncoder(str(tmp_path)).initialize()
