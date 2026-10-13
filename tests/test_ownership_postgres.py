"""Real PostgreSQL ownership tests using the coordinator-provided fixture.

The fixture DSN is read from ../POSTGRES-FIXTURE.json.  Tests create and drop
uniquely named databases under that fixture so they do not touch shared state.
All model/retrieval dependencies are synthetic doubles.
"""

import asyncio
import json
import os
import uuid
from pathlib import Path

import pytest

from nora.ownership import PostgresOwnershipStore

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "POSTGRES-FIXTURE.json"


def _fixture_dsn() -> str | None:
    """Return the coordinator-provided fixture DSN, or None if absent."""
    if FIXTURE_PATH.exists():
        data = json.loads(FIXTURE_PATH.read_text())
        return data.get("dsn")
    return os.environ.get("NORA_POSTGRES_TEST_DSN")


async def _pg_available(conninfo: str) -> bool:
    try:
        import psycopg

        async with await psycopg.AsyncConnection.connect(conninfo, autocommit=True) as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception:
        return False


@pytest.fixture
async def pg_store(tmp_path):
    """Create a PostgresOwnershipStore backed by a fresh test database."""
    fixture_dsn = _fixture_dsn()
    if not fixture_dsn:
        pytest.skip("No PostgreSQL test fixture DSN configured")
    if not await _pg_available(fixture_dsn):
        pytest.skip(
            "PostgreSQL fixture is present but this sandbox cannot reach it; "
            "run tests/test_ownership_postgres.py from an environment with fixture network access."
        )
    db_name = f"nora_test_{uuid.uuid4().hex[:12]}"
    import psycopg

    async with await psycopg.AsyncConnection.connect(fixture_dsn, autocommit=True) as conn:
        await conn.execute(f"CREATE DATABASE {db_name}")

    parsed = psycopg.conninfo.conninfo_to_dict(fixture_dsn)
    parsed["dbname"] = db_name
    conninfo = psycopg.conninfo.make_conninfo(**parsed)

    store = PostgresOwnershipStore(conninfo)
    await store.setup()
    yield store

    async with await psycopg.AsyncConnection.connect(fixture_dsn, autocommit=True) as conn:
        await conn.execute(f"DROP DATABASE IF EXISTS {db_name} WITH (FORCE)")


async def test_postgres_ownership_claim_and_persistence(pg_store):
    thread = str(uuid.uuid4())
    assert await pg_store.claim(thread) == (True, "assistant")
    fresh = PostgresOwnershipStore(pg_store.conninfo)
    assert await fresh.owner(thread) == "assistant"
    assert await fresh.claim(thread) == (True, "assistant")


async def test_concurrent_assistant_claims_are_atomic(pg_store):
    thread = str(uuid.uuid4())
    results = await asyncio.gather(*(pg_store.claim(thread) for _ in range(3)))
    assert results == [(True, "assistant")] * 3


async def test_historical_owner_is_not_reassigned(pg_store):
    import psycopg

    thread = str(uuid.uuid4())
    async with await psycopg.AsyncConnection.connect(pg_store.conninfo) as conn:
        await conn.execute(
            "INSERT INTO nora_thread_ownership (thread_id, role) VALUES (%s, %s)",
            (thread, "research"),
        )
        await conn.commit()
    assert await pg_store.claim(thread) == (False, "research")
    assert await pg_store.owner(thread) == "research"


async def test_owner_returns_none_and_setup_is_idempotent(pg_store):
    await pg_store.setup()
    assert await pg_store.owner(str(uuid.uuid4())) is None
