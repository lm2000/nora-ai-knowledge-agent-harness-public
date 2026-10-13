"""Source-category metadata remains valid for retained and newly prepared bundles."""

import json

import pytest

from nora.common import digest
from nora.indexing import import_bundle, verify_bundle


def categories(bundle, value):
    path = bundle / "import/chunks.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["categories"] = value
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    coverage = json.loads((bundle / "coverage.json").read_text())
    coverage["chunks_sha256"] = digest(path.read_bytes())
    (bundle / "coverage.json").write_text(json.dumps(coverage))
    return rows


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
