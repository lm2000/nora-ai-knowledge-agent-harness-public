import importlib.util
import json
import sys
import tarfile
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "build_release", Path(__file__).resolve().parents[1] / "scripts/build_release.py"
)
release = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = release
spec.loader.exec_module(release)


@pytest.fixture
def source(tmp_path):
    (tmp_path / "README.md").write_text("# Synthetic project\n")
    (tmp_path / "public-docs.json").write_text(json.dumps({"documents": ["README.md"]}))
    (tmp_path / "release-manifest.json").write_text(
        json.dumps({"files": ["README.md", "public-docs.json"]})
    )
    return tmp_path


def test_archive_is_deterministic_and_contains_no_history(source):
    (source / ".private").mkdir()
    (source / ".private/original").write_text("Excluded original")
    first = release.build(source, source / "first.tar.gz")
    second = release.build(source, source / "second.tar.gz")
    assert first["sha256"] == second["sha256"]
    with tarfile.open(source / "first.tar.gz") as archive:
        names = archive.getnames()
        assert len(names) == 3
        assert not any(".private" in name for name in names)
        receipt = json.load(archive.extractfile("nora-0.1.0/SOURCE-CHECKSUMS.json"))
        assert set(receipt["files"]) == {"README.md", "public-docs.json"}


@pytest.mark.parametrize("name", [".private/original", "../outside", "/absolute", "token.key"])
def test_nonpublic_paths_fail(source, name):
    (source / "release-manifest.json").write_text(json.dumps({"files": ["README.md", name]}))
    with pytest.raises(ValueError):
        release.sources(source)


def test_symlink_and_owner_address_are_rejected(source):
    path = source / "README.md"
    path.unlink()
    path.symlink_to(source / "public-docs.json")
    with pytest.raises(ValueError, match="symlink"):
        release.sources(source)
    path.unlink()
    path.write_text("operator" + "@" + "real-domain.invalid")
    with pytest.raises(ValueError, match="account"):
        release.sources(source)


def test_case_insensitive_collision_is_rejected(source):
    (source / "release-manifest.json").write_text(json.dumps({"files": ["README.md", "readme.md"]}))
    with pytest.raises(ValueError, match="case-insensitive"):
        release.sources(source)
