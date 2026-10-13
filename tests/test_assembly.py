"""Additive assembly must preserve source identity and chunk/vector associations."""

import json
import shutil
from contextlib import closing

import numpy as np
import pytest
from doubles import DeterministicEncoderDouble
from qdrant_client import QdrantClient

from nora.cli import main
from nora.common import digest
from nora.config import Settings
from nora.indexing import import_bundle, load_bundle, verify_bundle
from nora.jobs import assemble_bundle, run_import_verify
from nora.preparation import prepare


def make_bundle(tmp_path, name, documents):
    source = tmp_path / f"{name}-source"
    source.mkdir()
    for filename, text in documents.items():
        (source / filename).write_text(text)
    bundle = tmp_path / name
    prepare(source, bundle, DeterministicEncoderDouble())
    return bundle


def inventory(root):
    return {
        str(p.relative_to(root)): digest(p.read_bytes()) for p in root.rglob("*") if p.is_file()
    }


def rewrite_rows(bundle, mutate):
    path = bundle / "import/chunks.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    mutate(rows)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    coverage = json.loads((bundle / "coverage.json").read_text())
    coverage["chunks_sha256"] = digest(path.read_bytes())
    (bundle / "coverage.json").write_text(json.dumps(coverage))


@pytest.fixture
def pair(tmp_path):
    base = make_bundle(tmp_path, "base", {"a.md": "# Atlas\nShips in October.\n"})
    delta = make_bundle(tmp_path, "delta", {"b.md": "# Borealis\nShips in November.\n"})
    return base, delta


def test_preserves_base_and_appends_delta_without_changing_inputs(pair, tmp_path):
    base, delta = pair
    # Exercise a retained legacy coverage record without a prepare-job manifest.
    (base / "provenance").mkdir()
    (base / "provenance/coverage.json").write_text('{"historical": true}')
    rewrite_rows(base, lambda rows: rows[0].update(categories=["Project Knowledge"], legacy="kept"))
    before = [inventory(p) for p in pair]
    _, base_rows, base_vectors = load_bundle(base)
    _, delta_rows, delta_vectors = load_bundle(delta)
    output = tmp_path / "merged"
    report = assemble_bundle(base, delta, output, collection="merged-inactive")
    coverage, rows, vectors = load_bundle(output)
    assert rows == base_rows + delta_rows
    np.testing.assert_array_equal(vectors, np.concatenate([base_vectors, delta_vectors]))
    assert (
        (output / "import/chunks.jsonl")
        .read_bytes()
        .startswith((base / "import/chunks.jsonl").read_bytes())
    )
    for source in pair:
        for document in (source / "docs").glob("*.txt"):
            assert (output / "docs" / document.name).read_bytes() == document.read_bytes()
    assert coverage["documents"] == 2 and report["added_documents"] == 1
    assert report["encoded_chunks"] == 0 and report["activated"] is False
    assert (output / "provenance/base/provenance/coverage.json").is_file()
    assert not (output / "job-embed.json").exists()
    assert not (output / "job-prepare.json").exists()
    assert not (tmp_path / "current").exists()
    assert before == [inventory(p) for p in pair]


def test_identical_document_is_retained_once(pair, tmp_path):
    base, _ = pair
    delta = tmp_path / "duplicate"
    shutil.copytree(base, delta)
    report = assemble_bundle(base, delta, tmp_path / "merged", collection="new")
    coverage, rows, vectors = load_bundle(tmp_path / "merged")
    _, old_rows, old_vectors = load_bundle(base)
    assert report["duplicate_documents"] == 1 and report["added_chunks"] == 0
    assert coverage["documents"] == 1 and rows == old_rows
    np.testing.assert_array_equal(vectors, old_vectors)


def test_multiple_chunks_and_partial_duplicate_keep_vector_alignment(tmp_path):
    shared = "# Shared\nRetained unchanged.\n"
    base = make_bundle(
        tmp_path, "base", {"a.md": shared, "b.md": "# One\nFirst.\n# Two\nSecond.\n"}
    )
    delta = make_bundle(
        tmp_path, "delta", {"a.md": shared, "b.md": "# Three\nThird.\n# Four\nFourth.\n"}
    )
    _, old_rows, old_vectors = load_bundle(base)
    _, delta_rows, delta_vectors = load_bundle(delta)
    old_ids = {r["chunk_id"] for r in old_rows}
    new_indices = [i for i, row in enumerate(delta_rows) if row["chunk_id"] not in old_ids]
    report = assemble_bundle(base, delta, tmp_path / "merged", collection="new")
    _, rows, vectors = load_bundle(tmp_path / "merged")
    assert len(old_rows) == 3 and len(new_indices) == 2
    assert rows == old_rows + [delta_rows[i] for i in new_indices]
    np.testing.assert_array_equal(vectors[:3], old_vectors)
    np.testing.assert_array_equal(vectors[3:], delta_vectors[new_indices])
    assert report["duplicate_documents"] == 1 and report["added_documents"] == 1


def test_base_collection_cannot_be_reused(pair, tmp_path):
    base, delta = pair
    path = base / "coverage.json"
    coverage = json.loads(path.read_text())
    coverage["qdrant_collection"] = "active"
    path.write_text(json.dumps(coverage))
    with pytest.raises(ValueError, match="separate collection"):
        assemble_bundle(base, delta, tmp_path / "merged", collection="active")
    assert not (tmp_path / "merged").exists()


@pytest.mark.parametrize("conflict", ["point", "shared_document", "shared_vector"])
def test_conflicting_shared_identity_is_rejected_without_output(pair, tmp_path, conflict):
    base, delta = pair
    _, base_rows, _ = load_bundle(base)
    if conflict == "point":
        rewrite_rows(delta, lambda rows: rows[0].update(chunk_id=base_rows[0]["chunk_id"]))
    else:
        delta = tmp_path / "shared"
        shutil.copytree(base, delta)
        if conflict == "shared_document":
            rewrite_rows(
                delta, lambda rows: rows[0].update(chunk_id="00000000-0000-4000-8000-000000000001")
            )
        else:
            path = delta / "import/vectors.npy"
            vectors = np.load(path)
            np.save(path, -vectors)
            coverage = json.loads((delta / "coverage.json").read_text())
            coverage["vectors_sha256"] = digest(path.read_bytes())
            (delta / "coverage.json").write_text(json.dumps(coverage))
    before = [inventory(p) for p in (base, delta)]
    with pytest.raises(ValueError, match="Conflicting|different chunk inventories"):
        assemble_bundle(base, delta, tmp_path / "merged", collection="new")
    assert not (tmp_path / "merged").exists()
    assert before == [inventory(p) for p in (base, delta)]


def test_corrupt_document_fails_before_output(pair, tmp_path):
    base, delta = pair
    next((delta / "docs").glob("*.txt")).write_text("corrupt")
    with pytest.raises(ValueError, match="checksum"):
        assemble_bundle(base, delta, tmp_path / "merged", collection="new")
    assert not (tmp_path / "merged").exists()


def test_existing_output_and_input_path_are_never_overwritten(pair, tmp_path):
    base, delta = pair
    output = tmp_path / "existing"
    output.mkdir()
    (output / "keep").write_text("keep")
    with pytest.raises(FileExistsError):
        assemble_bundle(base, delta, output, collection="new")
    assert (output / "keep").read_text() == "keep"
    with pytest.raises(ValueError, match="separate"):
        assemble_bundle(base, delta, base / "nested", collection="new")


def test_failed_copy_does_not_publish_partial_bundle(pair, tmp_path, monkeypatch):
    base, delta = pair

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr("nora.jobs.shutil.copyfile", fail)
    with pytest.raises(OSError, match="disk full"):
        assemble_bundle(base, delta, tmp_path / "merged", collection="new")
    assert not (tmp_path / "merged").exists()
    assert not list(tmp_path.glob(".nora-assemble-*"))


def test_imports_assembly_into_separate_index_and_preserves_original(pair, tmp_path, monkeypatch):
    base, delta = pair
    output = tmp_path / "merged"
    assemble_bundle(base, delta, output, collection="new")
    database = tmp_path / "qdrant"
    with closing(QdrantClient(path=str(database))) as client:
        import_bundle(client, "original", base)
    monkeypatch.setattr("nora.jobs.connect", lambda settings: QdrantClient(path=str(database)))
    assert run_import_verify(output, Settings())["verified"]["verified"]
    with closing(QdrantClient(path=str(database))) as client:
        assert verify_bundle(client, "original", base)["verified"]
        assert verify_bundle(client, "new", output)["documents"] == 2


def test_modified_assembly_coverage_fails_before_connect(pair, tmp_path, monkeypatch):
    base, delta = pair
    output = tmp_path / "merged"
    assemble_bundle(base, delta, output, collection="new")
    coverage = json.loads((output / "coverage.json").read_text())
    coverage["qdrant_collection"] = "original"
    (output / "coverage.json").write_text(json.dumps(coverage))

    def fail(*args):
        pytest.fail("must not connect before checking assembly report")

    monkeypatch.setattr("nora.jobs.connect", fail)
    with pytest.raises(ValueError, match="Assembly stage report"):
        run_import_verify(output, Settings())


def test_cli_assembly_needs_no_model_or_network(pair, tmp_path, capsys, monkeypatch):
    base, delta = pair

    def fail(*args):
        pytest.fail("assembler must not use model or Qdrant")

    monkeypatch.setattr("nora.jobs.connect", fail)
    monkeypatch.setattr("nora.embedding.BGEEncoder.initialize", fail)
    assert (
        main(["assemble", str(base), str(delta), str(tmp_path / "merged"), "--collection", "new"])
        == 0
    )
    assert json.loads(capsys.readouterr().out)["added_documents"] == 1
