"""Real PostgreSQL checkpointer restart tests for role runtimes.

Uses the coordinator-provided fixture from ../POSTGRES-FIXTURE.json and
synthetic model/retrieval doubles.  Each test gets a uniquely named database.
"""

import json
import os
import uuid
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from nora.agent import create_graph
from nora.config import Settings
from nora.coordination import Runtime, create_app
from nora.ownership import PostgresOwnershipStore
from nora.roles import RoleConfig

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "POSTGRES-FIXTURE.json"


def _fixture_dsn() -> str | None:
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


def _require_fixture():
    dsn = _fixture_dsn()
    if not dsn:
        pytest.skip("No PostgreSQL test fixture DSN configured")
    return dsn


class _KnowledgeDouble:
    @staticmethod
    async def call(name, arguments):
        return {"results": [{"doc_id": "a" * 64, "text": "Prepared answer."}]}

    @staticmethod
    async def health():
        return {"ready": True, "documents": 1, "points": 1}

    @staticmethod
    @__import__("contextlib").asynccontextmanager
    async def pinned():
        yield _KnowledgeDouble


class _FakeModel(BaseChatModel):
    @property
    def _llm_type(self):
        return "fake-model"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, ChatResult

        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="synthetic"))])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


@pytest.fixture
async def pg_runtime(tmp_path):
    """Build a Knowledge runtime backed by a fresh Postgres checkpointer."""
    fixture_dsn = _require_fixture()
    if not await _pg_available(fixture_dsn):
        pytest.skip(
            "PostgreSQL fixture is present but this sandbox cannot reach it; "
            "run tests/test_coordination_postgres.py from an environment with fixture network access."
        )
    db_name = f"nora_test_{uuid.uuid4().hex[:12]}"
    import psycopg

    async with await psycopg.AsyncConnection.connect(fixture_dsn, autocommit=True) as conn:
        await conn.execute(f"CREATE DATABASE {db_name}")

    parsed = psycopg.conninfo.conninfo_to_dict(fixture_dsn)
    parsed["dbname"] = db_name
    conninfo = psycopg.conninfo.make_conninfo(**parsed)

    settings = replace(Settings(), state_dir=tmp_path, role="knowledge")
    config = RoleConfig(
        role="knowledge",
        display="Knowledge Assistant",
        system_prompt="You are knowledge",
        knowledge_tools=frozenset({"search_knowledge", "read_document"}),
        call_limit=3,
        models=[],
    )
    async with AsyncPostgresSaver.from_conn_string(conninfo) as saver:
        await saver.setup()
        graph = create_graph(_FakeModel(), _KnowledgeDouble(), saver, settings, role_config=config)
        ownership = PostgresOwnershipStore(conninfo)
        await ownership.setup()
        runtime = Runtime(graph, _KnowledgeDouble(), "knowledge", "fake", ownership)
        yield runtime, conninfo, settings

    async with await psycopg.AsyncConnection.connect(fixture_dsn, autocommit=True) as conn:
        await conn.execute(f"DROP DATABASE IF EXISTS {db_name} WITH (FORCE)")


async def test_checkpointer_state_survives_process_restart(pg_runtime):
    """A new runtime reconnecting to the same Postgres DB resumes the thread."""
    runtime, conninfo, settings = pg_runtime
    auth = {"Authorization": "Bearer test"}
    thread = str(uuid.uuid4())

    with TestClient(create_app(settings, runtime=runtime, token="test")) as client:
        response = client.post(
            "/ask", json={"question": "First turn", "thread_id": thread}, headers=auth
        )
        assert response.status_code == 200, response.text
        assert response.json()["answer"] == "synthetic"

    # Rebuild the graph with a fresh saver connection pointing at the same DB.
    config = RoleConfig(
        role="knowledge",
        display="Knowledge Assistant",
        system_prompt="You are knowledge",
        knowledge_tools=frozenset({"search_knowledge", "read_document"}),
        call_limit=3,
        models=[],
    )
    async with AsyncPostgresSaver.from_conn_string(conninfo) as saver:
        await saver.setup()
        graph = create_graph(_FakeModel(), _KnowledgeDouble(), saver, settings, role_config=config)
        ownership = PostgresOwnershipStore(conninfo)
        await ownership.setup()
        runtime2 = Runtime(graph, _KnowledgeDouble(), "knowledge", "fake", ownership)

        with TestClient(create_app(settings, runtime=runtime2, token="test")) as client:
            history = client.get(f"/history/knowledge/{thread}", headers=auth)
            assert history.status_code == 200, history.text
            messages = history.json()["messages"]
            assert any("First turn" in m["content"] for m in messages)

            # A second turn resumes from the persisted checkpoint.
            response = client.post(
                "/ask", json={"question": "Second turn", "thread_id": thread}, headers=auth
            )
            assert response.status_code == 200, response.text


async def test_postgres_ownership_survives_runtime_restart(pg_runtime):
    """Ownership claimed by one runtime is enforced by a restarted runtime."""
    runtime, conninfo, settings = pg_runtime
    auth = {"Authorization": "Bearer test"}
    thread = str(uuid.uuid4())

    with TestClient(create_app(settings, runtime=runtime, token="test")) as client:
        response = client.post(
            "/ask", json={"question": "Knowledge question", "thread_id": thread}, headers=auth
        )
        assert response.status_code == 200, response.text

    # A new runtime with a fresh connection still denies Research the same UUID.
    config = RoleConfig(
        role="research",
        display="Research Assistant",
        system_prompt="You are research",
        knowledge_tools=frozenset({"search_knowledge", "read_document"}),
        call_limit=3,
        models=[],
    )
    async with AsyncPostgresSaver.from_conn_string(conninfo) as saver:
        await saver.setup()
        graph = create_graph(_FakeModel(), _KnowledgeDouble(), saver, settings, role_config=config)
        ownership = PostgresOwnershipStore(conninfo)
        await ownership.setup()
        research_runtime = Runtime(graph, _KnowledgeDouble(), "research", "fake", ownership)
        research_settings = replace(settings, role="research")

        with TestClient(
            create_app(research_settings, runtime=research_runtime, token="test")
        ) as client:
            denied = client.post(
                "/ask",
                json={"question": "Research question", "thread_id": thread, "role": "research"},
                headers=auth,
            )
            assert denied.status_code == 403, denied.text
            body = denied.text.lower()
            assert "knowledge" not in body
            assert "owned by" not in body
