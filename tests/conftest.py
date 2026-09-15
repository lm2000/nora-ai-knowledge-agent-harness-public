"""Small deterministic doubles. These test contracts, not model answer quality."""

from pathlib import Path

import pytest
from doubles import DeterministicEncoderDouble as Encoder
from qdrant_client import QdrantClient

from nora.preparation import prepare


@pytest.fixture
def encoder():
    return Encoder()


@pytest.fixture
def bundle(tmp_path, encoder):
    destination = tmp_path / "prepared"
    prepare(Path(__file__).resolve().parents[1] / "examples/documents", destination, encoder)
    return destination


@pytest.fixture
def qdrant():
    client = QdrantClient(":memory:")
    yield client
    client.close()
