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
    """Ownership claims survive across separate store instances using the same DB."""
    thread = str(uuid.uuid4())
    accepted, owner = await pg_store.claim(thread, "research")
    assert accepted and owner == "research"

    fresh = PostgresOwnershipStore(pg_store.conninfo)
    assert await fresh.owner(thread) == "research"
    accepted2, owner2 = await fresh.claim(thread, "knowledge")
    assert not accepted2 and owner2 == "research"


async def test_concurrent_first_turn_claims_are_atomic(pg_store):
    """Parallel claims for the same new thread resolve to a single owner."""
    thread = str(uuid.uuid4())

    async def claim(role: str) -> tuple[bool, str]:
        return await pg_store.claim(thread, role)

    results = await asyncio.gather(claim("research"), claim("interview"), claim("knowledge"))
    owners = {owner for accepted, owner in results}
    assert len(owners) == 1
    assert sum(accepted for accepted, _ in results) == 1


async def test_cross_role_claim_is_rejected(pg_store):
    """A thread claimed by one role cannot be claimed by another."""
    thread = str(uuid.uuid4())
    assert (await pg_store.claim(thread, "knowledge")) == (True, "knowledge")
    accepted, owner = await pg_store.claim(thread, "research")
    assert not accepted
    assert owner == "knowledge"


async def test_owner_returns_none_for_unknown_thread(pg_store):
    """Unclaimed threads have no owner."""
    assert await pg_store.owner(str(uuid.uuid4())) is None


async def test_invalid_role_rejected(pg_store):
    """The store validates role names."""
    with pytest.raises(Exception):
        await pg_store.claim(str(uuid.uuid4()), "invalid-role")


async def test_setup_is_idempotent(pg_store):
    """Running setup on an already-initialized store does not fail."""
    await pg_store.setup()
    thread = str(uuid.uuid4())
    assert (await pg_store.claim(thread, "interview")) == (True, "interview")
