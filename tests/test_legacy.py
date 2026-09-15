"""Synthetic compatibility tests; no private corpus, network or real model calls."""

import json

import pytest

from nora.common import REPRESENTATION, digest
from nora.indexing import import_bundle, load_bundle, verify_bundle
from nora.legacy import adapt_legacy


def categories(bundle, value):
    path = bundle / "import/chunks.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["categories"] = value
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    coverage = json.loads((bundle / "coverage.json").read_text())
    coverage["chunks_sha256"] = digest(path.read_bytes())
    (bundle / "coverage.json").write_text(json.dumps(coverage))
    return rows


def legacy(bundle):
    categories(bundle, ["Projects", "User Guidance"])
    modern = json.loads((bundle / "coverage.json").read_text())
    old = {
        "phase": "full",
        "documents": modern["documents"],
        "chunks": modern["chunks"],
        "model": REPRESENTATION["model"],
        "revision": REPRESENTATION["revision"],
        "dimension": 768,
        "vector_sha256": modern["vectors_sha256"],
        "failed_documents": 0,
        "omitted_documents": 0,
        "original_provenance": {"keep": True},
    }
    for path in [bundle / "coverage.json", bundle / "import/coverage.json"]:
        path.write_text(json.dumps(old))
    manifest = {
        "bucket": "fixture-bucket",
        "project": "fixture-project",
        "documents": {
            p.stem: {"object": "documents/" + p.name, "generation": "7", "bytes": p.stat().st_size}
            for p in (bundle / "docs").glob("*.txt")
        },
    }
    (bundle / "gcs-documents.json").write_text(json.dumps(manifest))
    return old


def snapshot(root):
    return {
        str(p.relative_to(root)): digest(p.read_bytes()) for p in root.rglob("*") if p.is_file()
    }


def adapt(source, dest, **kw):
    return adapt_legacy(
        source,
        dest,
        collection="fixture_full_r1",
        document_bucket=kw.get("bucket", "fixture-bucket"),
    )


def test_multicategory_payload_survives_index_roundtrip(bundle, qdrant):
    rows = categories(bundle, ["Projects", "User Guidance"])
    import_bundle(qdrant, "categories", bundle)
    assert verify_bundle(qdrant, "categories", bundle)["verified"]
    stored = qdrant.retrieve("categories", ids=[rows[0]["chunk_id"]], with_payload=True)[0]
    assert stored.payload == rows[0]


@pytest.mark.parametrize(
    "value", [None, [], "documents", {}, [1], [["x"]], [""], [" x"], ["x\n"], ["x", "x"]]
)
def test_malformed_categories_never_create_collection(bundle, qdrant, value):
    categories(bundle, value)
    with pytest.raises(ValueError, match="metadata"):
        import_bundle(qdrant, "malformed", bundle)
    assert not qdrant.collection_exists("malformed")


def test_adapter_preserves_bytes_provenance_and_categories(bundle, tmp_path, qdrant):
    old = legacy(bundle)
    before = snapshot(bundle)
    destination = tmp_path / "adapted"
    receipt = adapt(bundle, destination)
    assert snapshot(bundle) == before
    assert not receipt["activated"] and not receipt["imported"] and not receipt["dense_reembedded"]
    for name in ["import/chunks.jsonl", "import/vectors.npy"]:
        assert (destination / name).read_bytes() == (bundle / name).read_bytes()
        assert (destination / name).stat().st_ino != (bundle / name).stat().st_ino
    for path in (bundle / "docs").glob("*.txt"):
        assert (destination / "docs" / path.name).read_bytes() == path.read_bytes()
    coverage, rows, vectors = load_bundle(destination)
    assert coverage["phase"] == "embedded" and coverage["schema_version"] == 1
    assert coverage["representation"] == REPRESENTATION
    assert coverage["qdrant_collection"] == "fixture_full_r1"
    assert rows[0]["categories"] == ["Projects", "User Guidance"]
    assert json.loads((destination / "provenance/coverage.json").read_text()) == old
    assert (destination / "coverage.json").read_bytes() == (
        destination / "import/coverage.json"
    ).read_bytes()
    manifest = json.loads((destination / "release-manifest.json").read_text())
    assert (
        manifest["documents"]
        == json.loads((bundle / "gcs-documents.json").read_text())["documents"]
    )
    assert manifest["collection"] == coverage["qdrant_collection"]
    assert "active_manifest" not in manifest and "manifest_generation" not in manifest
    assert not (destination / "job-import.json").exists()
    assert (
        json.loads((destination / "job-embed.json").read_text())["method"]
        == "verified-legacy-reuse"
    )
    import_bundle(qdrant, "adapted", destination)
    assert verify_bundle(qdrant, "adapted", destination)["verified"]


@pytest.mark.parametrize(
    "fault",
    [
        "vector_hash",
        "document",
        "manifest_size",
        "generation",
        "categories",
        "coverage",
        "revision",
    ],
)
def test_invalid_legacy_input_leaves_no_output(bundle, tmp_path, fault):
    legacy(bundle)
    if fault == "document":
        next((bundle / "docs").glob("*.txt")).write_text("tampered")
    elif fault in {"manifest_size", "generation"}:
        path = bundle / "gcs-documents.json"
        manifest = json.loads(path.read_text())
        next(iter(manifest["documents"].values()))[
            "bytes" if fault == "manifest_size" else "generation"
        ] = 0
        path.write_text(json.dumps(manifest))
    elif fault == "categories":
        categories(bundle, ["bad", "bad"])
    else:
        for path in [bundle / "coverage.json", bundle / "import/coverage.json"]:
            cov = json.loads(path.read_text())
            cov[
                {"vector_hash": "vector_sha256", "coverage": "documents", "revision": "revision"}[
                    fault
                ]
            ] = "wrong"
            path.write_text(json.dumps(cov))
    destination = tmp_path / "invalid"
    with pytest.raises((ValueError, TypeError)):
        adapt(bundle, destination)
    assert not destination.exists()
    assert not list(tmp_path.glob(".invalid-*"))


def test_refuses_overwrite_nested_destination_and_wrong_bucket(bundle, tmp_path):
    legacy(bundle)
    destination = tmp_path / "existing"
    destination.mkdir()
    (destination / "keep").write_text("keep")
    with pytest.raises(FileExistsError):
        adapt(bundle, destination)
    assert (destination / "keep").read_text() == "keep"
    with pytest.raises(ValueError, match="outside"):
        adapt(bundle, bundle / "nested")
    with pytest.raises(ValueError, match="bucket"):
        adapt(bundle, tmp_path / "other", bucket="another-bucket")


def test_symlinked_source_file_rejected(bundle, tmp_path):
    legacy(bundle)
    path = bundle / "import/vectors.npy"
    outside = tmp_path / "vectors.npy"
    path.rename(outside)
    path.symlink_to(outside)
    with pytest.raises(ValueError, match="regular file"):
        adapt(bundle, tmp_path / "adapted")
