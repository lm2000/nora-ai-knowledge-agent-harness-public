import json
from unittest.mock import MagicMock

import pytest
from qdrant_client import QdrantClient

from nora.cli import main
from nora.common import digest
from nora.conversion import convert


def test_cli_import_and_verify_close_real_disk_client(bundle, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        "nora.indexing.connect", lambda settings: QdrantClient(path=str(tmp_path / "qdrant"))
    )
    assert main(["import", str(bundle), "--collection", "test"]) == 0
    assert json.loads(capsys.readouterr().out)["documents"] == 3
    # Reopening the same local store would fail if the previous client retained its lock.
    assert main(["verify", str(bundle), "--collection", "test"]) == 0
    assert json.loads(capsys.readouterr().out)["verified"]


def test_conversion_adapter_preserves_source_and_refuses_overwrite(tmp_path):
    source = tmp_path / "document.pdf"
    source.write_bytes(b"Synthetic adapter input")
    adapter = MagicMock()
    document = adapter.convert.return_value.document
    document.export_to_markdown.return_value = "# Extracted text\n"
    document.export_to_dict.return_value = {"text": "Extracted text"}
    result = convert(source, tmp_path / "output", adapter)
    assert result["source_sha256"] == digest(source.read_bytes())
    assert (tmp_path / "output/document.md").read_text() == "# Extracted text\n"
    with pytest.raises(FileExistsError):
        convert(source, tmp_path / "output", adapter)
    assert adapter.convert.call_count == 1


def test_serve_role_sets_nora_role_env(monkeypatch):
    """The --role argument must reach the factory app via NORA_ROLE."""
    captured = {}

    def fake_uvicorn_run(app, factory, host, port):
        captured["app"] = app
        captured["host"] = host
        captured["port"] = port
        captured["role_env"] = __import__("os").environ.get("NORA_ROLE")

    monkeypatch.setattr("uvicorn.run", fake_uvicorn_run)
    monkeypatch.delenv("NORA_ROLE", raising=False)
    assert main(["serve", "role", "--role", "research"]) == 0
    assert captured["port"] == 8003
    assert captured["role_env"] == "research"
    assert captured["app"] == "nora.coordination:create_app"


def test_serve_role_defaults_to_nora_role_env(monkeypatch):
    """Without --role, the runtime uses NORA_ROLE from the environment."""
    captured = {}

    def fake_uvicorn_run(app, factory, host, port):
        captured["port"] = port
        captured["role_env"] = __import__("os").environ.get("NORA_ROLE")

    monkeypatch.setattr("uvicorn.run", fake_uvicorn_run)
    monkeypatch.setenv("NORA_ROLE", "interview")
    assert main(["serve", "role"]) == 0
    assert captured["port"] == 8004
    assert captured["role_env"] == "interview"
