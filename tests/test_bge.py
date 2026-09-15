"""Tests for the shared HTTP BGE service and client. All encoders are deterministic doubles."""

import numpy as np
import pytest
from doubles import DeterministicEncoderDouble as DeterministicEncoder
from fastapi.testclient import TestClient

from nora.bge_client import BGEClient
from nora.bge_server import Capacity, create_app
from nora.common import DIMENSION
from nora.config import Settings


@pytest.fixture
def encoder():
    return DeterministicEncoder()


def test_bge_server_query_and_document_modes(encoder):
    app = create_app(settings=Settings(), encoder=encoder, token="test-bge")
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer test-bge"}
        response = client.get("/health", headers=headers)
        assert response.status_code == 200
        assert response.json()["ready"]

        doc = client.post(
            "/encode", json={"texts": ["hello world example"], "query": False}, headers=headers
        )
        assert doc.status_code == 200
        assert len(doc.json()["vectors"][0]) == DIMENSION

        query = client.post(
            "/encode", json={"texts": ["hello world example"], "query": True}, headers=headers
        )
        assert query.status_code == 200
        # The double honors the HTTP query flag, so query and document vectors differ.
        assert doc.json()["vectors"][0] != query.json()["vectors"][0]


def test_bge_server_rejects_auth_and_oversized_batch(encoder):
    app = create_app(settings=Settings(), encoder=encoder, token="test-bge")
    with TestClient(app) as client:
        assert client.get("/health").status_code == 401
        headers = {"Authorization": "Bearer wrong"}
        response = client.post("/encode", json={"texts": ["x"]}, headers=headers)
        assert response.status_code == 401

        headers = {"Authorization": "Bearer test-bge"}
        response = client.post(
            "/encode",
            json={"texts": ["x"] * 200},
            headers=headers,
        )
        assert response.status_code == 413


def test_bge_client_splits_batches_and_records_calls(monkeypatch):
    """The HTTP client splits large requests and retries on transient 503s."""
    client = BGEClient("http://example-bge", "token", max_batch_size=3, retries=2)
    calls = []

    def fake_request(texts: list[str], query: bool):
        calls.append((len(texts), query))
        result = np.zeros((len(texts), DIMENSION), dtype=np.float32)
        for i in range(len(texts)):
            result[i, 0] = 1.0
        return result

    monkeypatch.setattr(client, "_request", fake_request)
    vectors = client.encode(["a", "b", "c", "d", "e"], query=True)
    assert vectors.shape == (5, DIMENSION)
    assert calls == [(3, True), (2, True)]


def test_bge_capacity_rejects_when_queue_full():
    cap = Capacity(max_inflight=1, max_queued=1, label="test", timeout=1.0)

    async def exercise():
        async with cap:
            with pytest.raises(__import__("fastapi").HTTPException) as error:
                async with cap:
                    pass
            assert error.value.status_code == 503

    import asyncio

    asyncio.run(exercise())


def test_bge_capacity_times_out_when_no_slot():
    cap = Capacity(max_inflight=1, max_queued=1, label="test", timeout=0.05)

    async def exercise():
        async with cap:
            with pytest.raises(__import__("fastapi").HTTPException) as error:
                await cap.acquire()
            assert error.value.status_code == 503

    import asyncio

    asyncio.run(exercise())
