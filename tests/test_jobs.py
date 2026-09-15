"""Tests for the manual ingestion job pipeline, release activation and rollback."""

import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from doubles import DeterministicEncoderDouble as DeterministicEncoder
from qdrant_client import QdrantClient

from nora.config import Settings
from nora.documents import LocalDocumentStore
from nora.jobs import (
    activate,
    activate_cloud,
    active_release,
    knowledge_update,
    rollback_cloud,
    run_embed,
    run_import_verify,
)
from nora.retrieval import RetrievalService, create_app


@pytest.fixture
def encoder():
    return DeterministicEncoder()


@pytest.fixture
def qdrant():
    client = QdrantClient(":memory:")
    yield client


@pytest.fixture(autouse=True)
def patch_qdrant_connect(qdrant, monkeypatch):
    """One shared in-memory Qdrant per test; ingestion jobs must not close it."""

    class _NoCloseWrapper:
        def __init__(self, client):
            self._client = client

        def __getattr__(self, name):
            if name == "close":
                raise AttributeError(name)
            return getattr(self._client, name)

        def close(self):
            pass

    monkeypatch.setattr(
        "nora.jobs.connect",
        lambda settings, **kwargs: _NoCloseWrapper(qdrant),
    )


def make_source(tmp_path, name, content: str) -> Path:
    source = tmp_path / name
    source.mkdir(parents=True)
    (source / "doc.md").write_text(content, encoding="utf-8")
    return source


def test_stage_handoffs_require_completed_previous_stages(tmp_path, encoder):
    release = tmp_path / "release"
    with pytest.raises(ValueError, match="Prepare stage did not complete"):
        run_embed(release, encoder)
    with pytest.raises(ValueError, match="Embed stage did not complete"):
        run_import_verify(release, Settings())


def test_knowledge_update_creates_release_activates_and_searches(tmp_path, encoder, qdrant):
    source = make_source(tmp_path, "source", "# Atlas\nAtlas ships on October 12, 2026.\n")
    releases = tmp_path / "releases"
    result = knowledge_update(source, releases, Settings(), encoder)
    assert result["activated"]
    assert (Path(result["release"]) / "job-import.json").exists()
    assert active_release(releases) == Path(result["release"]).resolve()

    # Retrieval reads the active release for both documents and the index.
    active = active_release(releases)
    # Re-import is idempotent for the same point set in the same collection.
    from nora.jobs import run_import_verify as _import

    _import(active, Settings())
    service = RetrievalService(
        qdrant,
        encoder,
        LocalDocumentStore(active / "docs"),
        collection=result["collection"],
        data_dir=active,
    )
    hits = service.search("Atlas ship date", 5)["results"]
    assert any("October 12" in hit["text"] for hit in hits)


def test_failed_import_leaves_active_release_unchanged(tmp_path, encoder, qdrant, monkeypatch):
    source = make_source(tmp_path, "source", "# Atlas\nAtlas ships on October 12, 2026.\n")
    releases = tmp_path / "releases"
    knowledge_update(source, releases, Settings(), encoder)
    first_release = active_release(releases)

    # Break Qdrant connectivity for the second run.
    def broken_connect(settings, **kwargs):
        raise RuntimeError("Qdrant unavailable")

    monkeypatch.setattr("nora.jobs.connect", broken_connect)
    source2 = make_source(tmp_path, "source2", "# Cedar\nCedar support is 24x7.\n")
    with pytest.raises(RuntimeError, match="Qdrant unavailable"):
        knowledge_update(source2, releases, Settings(), encoder)
    assert active_release(releases) == first_release


def test_activation_rollback_switches_releases(tmp_path, encoder, qdrant):
    settings = Settings()
    releases = tmp_path / "releases"
    releases.mkdir()

    source_a = make_source(tmp_path, "source_a", "# Atlas\nAtlas ships on October 12, 2026.\n")
    source_b = make_source(tmp_path, "source_b", "# Cedar\nCedar support is 24x7.\n")

    res_a = knowledge_update(source_a, releases, settings, encoder)
    res_b = knowledge_update(source_b, releases, settings, encoder)

    active_a = active_release(releases)
    assert active_a == Path(res_b["release"]).resolve()

    # Rollback to the previous release atomically.
    activate(releases, Path(res_a["release"]))
    assert active_release(releases) == Path(res_a["release"]).resolve()

    # Import the rolled-back release and search it.
    from nora.jobs import run_import_verify as _import

    _import(active_release(releases), settings)
    service = RetrievalService(
        qdrant,
        encoder,
        LocalDocumentStore(active_release(releases) / "docs"),
        collection=res_a["collection"],
        data_dir=active_release(releases),
    )
    hits = service.search("Atlas ship date", 5)["results"]
    assert any("October 12" in hit["text"] for hit in hits)


class _RetrievalKnowledge:
    """Adapter that exposes a RetrievalService as the Knowledge client contract."""

    def __init__(self, service):
        self.service = service

    @asynccontextmanager
    async def pinned(self):
        yield self

    async def call(self, name: str, arguments: dict) -> dict:
        if name == "search":
            return self.service.search(arguments["query"], arguments.get("limit", 5))
        if name == "read":
            return self.service.read(
                arguments["doc_id"], arguments.get("offset", 0), arguments.get("limit", 8000)
            )
        raise ValueError(f"Unknown operation {name}")

    async def health(self) -> dict:
        return {**self.service.health(), "ready": True}


def test_knowledge_assistant_answers_from_new_release(tmp_path, encoder, qdrant):
    """The existing Deep Agent uses the newly ingested release through the retrieval boundary."""
    from langgraph.checkpoint.memory import InMemorySaver

    from nora.agent import create_graph
    from nora.config import Settings

    source = make_source(tmp_path, "source", "# Atlas\nAtlas ships on October 12, 2026.\n")
    releases = tmp_path / "releases"
    result = knowledge_update(source, releases, Settings(), encoder)
    active = active_release(releases)

    service = RetrievalService(
        qdrant,
        encoder,
        LocalDocumentStore(active / "docs"),
        collection=result["collection"],
        data_dir=active,
    )
    from tests.test_services import Model

    model = Model()
    graph = create_graph(model, _RetrievalKnowledge(service), InMemorySaver(), Settings())
    output = __import__("asyncio").run(
        graph.ainvoke(
            {
                "messages": [
                    __import__("langchain_core.messages", fromlist=["HumanMessage"]).HumanMessage(
                        content="When does Atlas ship?"
                    )
                ]
            },
            {"configurable": {"thread_id": "test-thread"}},
        )
    )
    answer = output["messages"][-1].content
    assert answer
    assert any(
        "search_knowledge" in str(getattr(m, "tool_calls", []))
        for messages in model.observed
        for m in messages
    )


def test_rollback_uses_activation_history(tmp_path, encoder, qdrant):
    settings = Settings()
    releases = tmp_path / "releases"
    releases.mkdir()
    source_a = make_source(tmp_path, "source_a", "# Atlas\nAtlas ships on October 12, 2026.\n")
    source_b = make_source(tmp_path, "source_b", "# Cedar\nCedar support is 24x7.\n")
    res_a = knowledge_update(source_a, releases, settings, encoder)
    res_b = knowledge_update(source_b, releases, settings, encoder)
    assert active_release(releases) == Path(res_b["release"]).resolve()

    from nora.jobs import rollback

    rollback(releases)
    assert active_release(releases) == Path(res_a["release"]).resolve()


def test_activate_requires_import_and_collection(tmp_path, encoder, qdrant):
    from nora.jobs import activate

    releases = tmp_path / "releases"
    releases.mkdir()
    bad_release = tmp_path / "bad"
    bad_release.mkdir()
    with pytest.raises(ValueError, match="Release has not passed import/verify"):
        activate(releases, bad_release)
    (bad_release / "job-import.json").write_text("{}")
    (bad_release / "coverage.json").write_text('{"phase": "embedded"}')
    with pytest.raises(ValueError, match="Qdrant collection"):
        activate(releases, bad_release)


def test_gcs_publish_and_activation_pointer(tmp_path, encoder, qdrant):
    from fake_gcs import FakeGCSClient

    from nora.documents import GCSDocumentStore, publish_release
    from nora.jobs import activate

    settings = Settings()
    releases = tmp_path / "releases"
    source = make_source(tmp_path, "source", "# Atlas\nAtlas ships on October 12, 2026.\n")
    result = knowledge_update(source, releases, settings, encoder)
    release_dir = Path(result["release"])

    client = FakeGCSClient()
    manifest = publish_release(release_dir, "nora-prepared-test", "dev", client)
    assert manifest["bucket"] == "nora-prepared-test"
    assert manifest["collection"] == result["collection"]
    assert "manifest_object" in manifest

    active_pointer = tmp_path / "active-gcs-manifest.json"
    activate(releases, release_dir, gcs_manifest_path=active_pointer, gcs_client=client)
    assert active_pointer.exists()

    store = GCSDocumentStore(active_pointer, client=client)
    doc_id = next(iter(manifest["documents"]))
    text = store.read(doc_id)
    assert "October 12" in text


def test_release_pin_header_overrides_current_symlink(tmp_path, encoder, qdrant):
    from fastapi.testclient import TestClient

    settings = Settings(
        releases_root=tmp_path / "releases", data_dir=tmp_path / "releases" / "current"
    )
    source_a = make_source(tmp_path, "source_a", "# Atlas\nAtlas ships on October 12, 2026.\n")
    source_b = make_source(tmp_path, "source_b", "# Atlas\nAtlas ships on October 19, 2026.\n")
    res_a = knowledge_update(source_a, settings.releases_root, settings, encoder)
    knowledge_update(source_b, settings.releases_root, settings, encoder)

    # Build a retrieval service over the active (B) release.
    active = active_release(settings.releases_root)
    service = RetrievalService(
        qdrant,
        encoder,
        LocalDocumentStore(active / "docs"),
        collection=settings.collection,
        data_dir=active,
        settings=settings,
    )
    app = create_app(settings, service, token="test")
    with TestClient(app, base_url="http://localhost:8001") as client:
        headers = {
            "Authorization": "Bearer test",
            "X-Nora-Release": str(res_a["release"]),
        }
        response = client.get("/release", headers=headers)
        assert response.status_code == 200
        assert response.json()["release"] == str(res_a["release"])


def test_search_and_read_pin_pinned_release_across_symlink_change(tmp_path, encoder, qdrant):
    from fastapi.testclient import TestClient

    releases = tmp_path / "releases"
    settings = Settings(releases_root=releases, data_dir=releases / "current")
    source_a = make_source(tmp_path, "source_a", "# Atlas\nAtlas ships on October 12, 2026.\n")
    source_b = make_source(tmp_path, "source_b", "# Cedar\nCedar support is 24x7.\n")
    res_a = knowledge_update(source_a, releases, settings, encoder)
    knowledge_update(source_b, releases, settings, encoder)

    # Build retrieval with settings so it resolves the active release (B).
    service = RetrievalService(
        qdrant,
        encoder,
        None,
        collection=settings.collection,
        data_dir=settings.data_dir,
        settings=settings,
    )
    app = create_app(settings, service, token="test")
    with TestClient(app, base_url="http://localhost:8001") as client:
        headers = {
            "Authorization": "Bearer test",
            "Accept": "application/json, text/event-stream",
            "X-Nora-Release": str(res_a["release"]),
        }

        def rpc(method, params):
            response = client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                headers=headers,
            )
            assert response.status_code == 200, response.text
            return response.json()["result"]

        initialized = rpc(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        )
        headers["MCP-Protocol-Version"] = initialized["protocolVersion"]
        found = rpc("tools/call", {"name": "search", "arguments": {"query": "Atlas ship date"}})
        results = found.get("structuredContent", json.loads(found["content"][0]["text"]))["results"]
        assert any("October 12" in hit["text"] for hit in results)
        doc_id = results[0]["doc_id"]
        read = rpc("tools/call", {"name": "read", "arguments": {"doc_id": doc_id, "limit": 200}})
        text = read.get("structuredContent", json.loads(read["content"][0]["text"]))["text"]
        assert "October 12" in text


def test_concurrent_activations_leave_one_valid_current(tmp_path, encoder, qdrant):
    """Concurrent activations are serialized by the atomic rename; history records both."""
    import threading

    settings = Settings()
    releases = tmp_path / "releases"
    releases.mkdir()
    source_a = make_source(tmp_path, "source_a", "# Atlas\nAtlas ships on October 12, 2026.\n")
    source_b = make_source(tmp_path, "source_b", "# Atlas\nAtlas ships on October 19, 2026.\n")
    res_a = knowledge_update(source_a, releases, settings, encoder)
    res_b = knowledge_update(source_b, releases, settings, encoder)
    release_a = Path(res_a["release"])
    release_b = Path(res_b["release"])

    results = []

    def activate_release(release_dir):
        try:
            results.append(activate(releases, release_dir))
        except Exception as error:
            results.append(error)

    threads = [
        threading.Thread(target=activate_release, args=(release_a,)),
        threading.Thread(target=activate_release, args=(release_b,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    currents = [r.resolve() for r in results if isinstance(r, Path)]
    assert len(currents) == 2
    # Both threads reported success; the filesystem symlink is the last atomic rename.
    current = active_release(releases)
    assert current in {release_a, release_b}
    history = (releases / ".history").read_text(encoding="utf-8").splitlines()
    assert any(release_a.name in line for line in history)
    assert any(release_b.name in line for line in history)


def test_invalid_release_pin_is_ignored(tmp_path, encoder, qdrant):
    """A pinned release outside the releases root or without job-import is ignored."""
    from fastapi.testclient import TestClient

    releases = tmp_path / "releases"
    settings = Settings(releases_root=releases, data_dir=releases / "current")
    source = make_source(tmp_path, "source", "# Atlas\nAtlas ships on October 12, 2026.\n")
    knowledge_update(source, releases, settings, encoder)

    service = RetrievalService(
        qdrant,
        encoder,
        None,
        collection=settings.collection,
        data_dir=settings.data_dir,
        settings=settings,
    )
    app = create_app(settings, service, token="test")
    with TestClient(app, base_url="http://localhost:8001") as client:
        # Outside root: should fall back to current.
        response = client.get(
            "/release",
            headers={
                "Authorization": "Bearer test",
                "X-Nora-Release": "/tmp/outside",
            },
        )
        assert response.status_code == 200
        assert response.json()["release"] == str(active_release(releases))

        # Missing job-import.json: should fall back to current.
        empty = tmp_path / "empty_release"
        empty.mkdir()
        response = client.get(
            "/release",
            headers={"Authorization": "Bearer test", "X-Nora-Release": str(empty)},
        )
        assert response.status_code == 200
        assert response.json()["release"] == str(active_release(releases))


def test_cloud_pointer_activation_and_retrieval(tmp_path, encoder, qdrant):
    """Activation writes a GCS pointer; Retrieval reads it to serve documents."""
    from fake_gcs import FakeGCSClient
    from fastapi.testclient import TestClient

    from nora.retrieval import create_app

    settings = Settings(
        releases_root=tmp_path / "releases",
        data_dir=tmp_path / "releases" / "current",
    )
    source = make_source(tmp_path, "source", "# Atlas\nAtlas ships on October 12, 2026.\n")
    result = knowledge_update(source, settings.releases_root, settings, encoder)
    release_dir = Path(result["release"])

    client = FakeGCSClient()
    pointer = activate_cloud(
        settings.releases_root,
        release_dir,
        "nora-test-bucket",
        "releases",
        "releases/current.json",
        client,
        collection=result["collection"],
    )

    pointer_settings = Settings(
        releases_root=settings.releases_root,
        data_dir=settings.data_dir,
        gcs_pointer="gs://nora-test-bucket/releases/current.json",
    )
    service = RetrievalService(
        qdrant,
        encoder,
        None,
        collection=settings.collection,
        data_dir=settings.data_dir,
        settings=pointer_settings,
        gcs_client=client,
    )
    app = create_app(pointer_settings, service, token="test")
    with TestClient(app, base_url="http://localhost:8001") as client_test:
        release_info = client_test.get("/release", headers={"Authorization": "Bearer test"}).json()
        assert release_info["release"] == pointer["active_manifest"]["object"] + "#" + str(
            pointer["active_manifest"]["generation"]
        )

        headers = {
            "Authorization": "Bearer test",
            "Accept": "application/json, text/event-stream",
        }

        def rpc(method, params):
            response = client_test.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                headers=headers,
            )
            assert response.status_code == 200, response.text
            return response.json()["result"]

        initialized = rpc(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        )
        headers["MCP-Protocol-Version"] = initialized["protocolVersion"]
        found = rpc("tools/call", {"name": "search", "arguments": {"query": "Atlas ship date"}})
        results = found.get("structuredContent", json.loads(found["content"][0]["text"]))["results"]
        assert any("October 12" in hit["text"] for hit in results)
        doc_id = results[0]["doc_id"]
        read = rpc("tools/call", {"name": "read", "arguments": {"doc_id": doc_id, "limit": 200}})
        text = read.get("structuredContent", json.loads(read["content"][0]["text"]))["text"]
        assert "October 12" in text


def test_cloud_pointer_rollback(tmp_path, encoder, qdrant):
    """Rollback rewinds the authoritative cloud pointer to the previous manifest."""
    from fake_gcs import FakeGCSClient

    settings = Settings(
        releases_root=tmp_path / "releases",
        data_dir=tmp_path / "releases" / "current",
    )
    source_a = make_source(tmp_path, "source_a", "# Atlas\nAtlas ships on October 12, 2026.\n")
    source_b = make_source(tmp_path, "source_b", "# Cedar\nCedar support is 24x7.\n")
    res_a = knowledge_update(source_a, settings.releases_root, settings, encoder)
    res_b = knowledge_update(source_b, settings.releases_root, settings, encoder)

    client = FakeGCSClient()
    activate_cloud(
        settings.releases_root,
        Path(res_a["release"]),
        "nora-test-bucket",
        "releases",
        "releases/current.json",
        client,
        collection=res_a["collection"],
    )
    pointer_b = activate_cloud(
        settings.releases_root,
        Path(res_b["release"]),
        "nora-test-bucket",
        "releases",
        "releases/current.json",
        client,
        collection=res_b["collection"],
    )

    rolled = rollback_cloud(settings.releases_root, "nora-test-bucket", "current.json", client)
    assert rolled["active_manifest"]["object"] != pointer_b["active_manifest"]["object"]
    assert rolled["active_manifest"]["object"].endswith("/manifest.json")


def test_cloud_pointer_conditional_write_rejects_stale_generation(tmp_path, encoder, qdrant):
    """A conditional cloud pointer write fails when the expected generation is stale."""
    from fake_gcs import FakeGCSClient

    from nora.documents import publish_release, write_cloud_pointer

    settings = Settings(
        releases_root=tmp_path / "releases",
    )
    source = make_source(tmp_path, "source", "# Atlas\nAtlas ships on October 12, 2026.\n")
    result = knowledge_update(source, settings.releases_root, settings, encoder)
    release_dir = Path(result["release"])

    client = FakeGCSClient()
    manifest = publish_release(release_dir, "nora-test-bucket", "releases", client)
    write_cloud_pointer("nora-test-bucket", "current.json", manifest, client, expected_generation=0)
    with pytest.raises(ValueError, match="Generation precondition failed"):
        write_cloud_pointer(
            "nora-test-bucket", "current.json", manifest, client, expected_generation=0
        )


def test_knowledge_update_gcs_mode_activates_cloud_pointer(tmp_path, encoder, qdrant):
    """When GCS is explicitly configured, knowledge_update publishes and points."""
    from fake_gcs import FakeGCSClient

    source = make_source(tmp_path, "source", "# Atlas\nAtlas ships on October 12, 2026.\n")
    releases = tmp_path / "releases"
    creds = tmp_path / "publisher-creds.json"
    creds.write_text("{}")

    settings = Settings(
        gcs_pointer="gs://nora-test-bucket/releases/current.json",
        gcs_bucket="nora-test-bucket",
        gcs_prefix="releases",
        gcs_publisher_credentials=creds,
    )
    client = FakeGCSClient()
    result = knowledge_update(source, releases, settings, encoder, gcs_client=client)
    assert result["activated"]
    assert "pointer" in result
    assert (releases / "current").resolve() == Path(result["release"]).resolve()


def test_knowledge_update_gcs_mode_rejects_missing_publisher_credentials(tmp_path, encoder, qdrant):
    """Missing publisher credentials are rejected before any job side effects."""
    from nora.config import ConfigurationError

    source = make_source(tmp_path, "source", "# Atlas\nAtlas ships on October 12, 2026.\n")
    releases = tmp_path / "releases"
    settings = Settings(
        gcs_pointer="gs://nora-test-bucket/releases/current.json",
        gcs_bucket="nora-test-bucket",
        gcs_prefix="releases",
    )
    with pytest.raises(ConfigurationError, match="NORA_GCS_PUBLISHER_CREDENTIALS_FILE"):
        knowledge_update(source, releases, settings, encoder)
    assert not any(releases.iterdir())


def test_rollback_cloud_pointer_rewinds_local_and_authoritative(tmp_path, encoder, qdrant):
    """Cloud rollback restores the previous manifest pointer and local current."""
    from fake_gcs import FakeGCSClient

    from nora.jobs import rollback

    releases = tmp_path / "releases"
    creds = tmp_path / "publisher-creds.json"
    creds.write_text("{}")
    settings = Settings(
        releases_root=releases,
        gcs_pointer="gs://nora-test-bucket/releases/current.json",
        gcs_bucket="nora-test-bucket",
        gcs_prefix="releases",
        gcs_publisher_credentials=creds,
    )
    source_a = make_source(tmp_path, "source_a", "# Atlas\nAtlas ships on October 12, 2026.\n")
    source_b = make_source(tmp_path, "source_b", "# Cedar\nCedar support is 24x7.\n")

    client = FakeGCSClient()
    res_a = knowledge_update(source_a, releases, settings, encoder, gcs_client=client)
    res_b = knowledge_update(source_b, releases, settings, encoder, gcs_client=client)
    assert active_release(releases) == Path(res_b["release"]).resolve()

    rolled = rollback(
        releases,
        gcs_pointer=("nora-test-bucket", "releases/current.json"),
        gcs_client=client,
    )
    assert rolled["active_manifest"]["object"].endswith("/manifest.json")
    assert active_release(releases) == Path(res_a["release"]).resolve()


def test_publisher_gcs_client_rejects_missing_credential_file(tmp_path):
    """The publisher client helper rejects a missing credential file before SDK calls."""
    from nora.config import ConfigurationError, Settings
    from nora.jobs import _publisher_gcs_client

    missing = tmp_path / "missing.json"
    settings = Settings(gcs_publisher_credentials=missing)
    with pytest.raises(ConfigurationError, match="credentials file not found"):
        _publisher_gcs_client(settings)
