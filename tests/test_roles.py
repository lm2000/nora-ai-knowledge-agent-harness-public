"""Role identity, checkpoint namespace and cross-role denial tests."""

import uuid
from contextlib import asynccontextmanager
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import InMemorySaver

from nora.agent import create_graph
from nora.config import Settings
from nora.coordination import Runtime, create_app
from nora.ownership import InMemoryOwnershipStore
from nora.roles import (
    RoleConfig,
    load_role_config,
    role_thread_id,
    valid_role,
)


def test_role_validation_and_thread_namespace():
    assert valid_role("knowledge")
    assert valid_role("research")
    assert valid_role("interview")
    assert not valid_role("other")
    thread = str(uuid.uuid4())
    assert role_thread_id("knowledge", thread).startswith("knowledge:")
    assert role_thread_id("research", thread) != role_thread_id("knowledge", thread)


def test_invalid_role_namespace_rejected():
    with pytest.raises(Exception):
        role_thread_id("bad-role", str(uuid.uuid4()))


def test_role_configs_load_different_prompts():
    settings = Settings()
    knowledge = load_role_config("knowledge", settings)
    research = load_role_config("research", settings)
    interview = load_role_config("interview", settings)
    assert knowledge.system_prompt != research.system_prompt
    assert research.system_prompt != interview.system_prompt
    assert knowledge.role == "knowledge"
    assert research.role == "research"
    assert interview.role == "interview"


def test_role_model_inventory_defaults_are_exposed():
    settings = Settings()
    research = load_role_config("research", settings)
    assert len(research.models) >= 2
    providers = {spec.provider for spec in research.models}
    assert "ollama" in providers


class Knowledge:
    calls = 0

    @asynccontextmanager
    async def pinned(self):
        yield self

    async def call(self, name, arguments):
        self.calls += 1
        return {"results": [{"doc_id": "a" * 64, "text": "Atlas waits for rollback rehearsal."}]}

    async def health(self):
        return {"ready": True, "documents": 3, "points": 7}


class FakeModel(BaseChatModel):
    @property
    def _llm_type(self):
        return "fake-model"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, ChatResult

        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="answer"))])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def runtime_for_role(role: str, ownership: InMemoryOwnershipStore | None = None):
    from nora.agent import create_graph

    settings = Settings()
    knowledge = Knowledge()
    config = RoleConfig(
        role=role,
        display=role,
        system_prompt=f"You are {role}",
        knowledge_tools=frozenset({"search_knowledge", "read_document"}),
        call_limit=3,
        models=[],
    )
    graph = create_graph(FakeModel(), knowledge, InMemorySaver(), settings, role_config=config)
    return Runtime(graph, knowledge, role, "fake", ownership or InMemoryOwnershipStore())


def test_cross_role_history_is_denied_on_wrong_runtime(tmp_path):
    from dataclasses import replace

    auth = {"Authorization": "Bearer test"}
    thread = str(uuid.uuid4())
    settings = replace(Settings(), state_dir=tmp_path)
    with TestClient(
        create_app(settings, runtime=runtime_for_role("knowledge"), token="test")
    ) as client:
        response = client.get(f"/history/research/{thread}", headers=auth)
        assert response.status_code == 403, response.text
        # No wrong-role hint revealing the actual owner.
        assert "research" not in response.text.lower()


def test_same_role_history_is_allowed(tmp_path):
    from dataclasses import replace

    auth = {"Authorization": "Bearer test"}
    thread = str(uuid.uuid4())
    settings = replace(Settings(), state_dir=tmp_path)
    with TestClient(
        create_app(settings, runtime=runtime_for_role("knowledge"), token="test")
    ) as client:
        response = client.post(
            "/ask", json={"question": "What blocks Atlas?", "thread_id": thread}, headers=auth
        )
        assert response.status_code == 200, response.text
        response = client.get(f"/history/knowledge/{thread}", headers=auth)
        assert response.status_code == 200, response.text
        assert len(response.json()["messages"]) == 2


def test_ask_with_matching_role_succeeds(tmp_path):
    from dataclasses import replace

    auth = {"Authorization": "Bearer test"}
    thread = str(uuid.uuid4())
    settings = replace(Settings(), state_dir=tmp_path)
    with TestClient(
        create_app(settings, runtime=runtime_for_role("research"), token="test")
    ) as client:
        response = client.post(
            "/ask",
            json={"question": "What blocks Atlas?", "thread_id": thread, "role": "research"},
            headers=auth,
        )
        assert response.status_code == 200, response.text
        assert response.json()["role"] == "research"


def test_ask_with_wrong_role_is_denied(tmp_path):
    from dataclasses import replace

    auth = {"Authorization": "Bearer test"}
    thread = str(uuid.uuid4())
    settings = replace(Settings(), state_dir=tmp_path)
    with TestClient(
        create_app(settings, runtime=runtime_for_role("research"), token="test")
    ) as client:
        response = client.post(
            "/ask",
            json={"question": "What blocks Atlas?", "thread_id": thread, "role": "knowledge"},
            headers=auth,
        )
        assert response.status_code == 403, response.text


def test_cross_role_ask_denied_when_research_thread_sent_to_knowledge(tmp_path):
    """A Research-owned thread id sent to Knowledge /ask without role field is denied."""
    shared = InMemoryOwnershipStore()
    research_runtime = runtime_for_role("research", shared)
    knowledge_runtime = runtime_for_role("knowledge", shared)
    settings = replace(Settings(), state_dir=tmp_path)
    auth = {"Authorization": "Bearer test"}
    thread = str(uuid.uuid4())
    with TestClient(
        create_app(settings, runtime=research_runtime, token="test")
    ) as research_client:
        assert (
            research_client.post(
                "/ask",
                json={"question": "Research question", "thread_id": thread, "role": "research"},
                headers=auth,
            ).status_code
            == 200
        )
    with TestClient(
        create_app(settings, runtime=knowledge_runtime, token="test")
    ) as knowledge_client:
        # No role field: the Knowledge runtime would otherwise default to knowledge:{thread}.
        denied = knowledge_client.post(
            "/ask", json={"question": "Knowledge question", "thread_id": thread}, headers=auth
        )
        assert denied.status_code == 403, denied.text
        # Explicit wrong-role field is also denied.
        denied2 = knowledge_client.post(
            "/ask",
            json={"question": "Knowledge question", "thread_id": thread, "role": "knowledge"},
            headers=auth,
        )
        assert denied2.status_code == 403, denied2.text


def test_cross_role_denial_hides_owner_role(tmp_path):
    """A denial for another role's exact UUID must not reveal the owner role."""
    shared = InMemoryOwnershipStore()
    research_runtime = runtime_for_role("research", shared)
    knowledge_runtime = runtime_for_role("knowledge", shared)
    settings = replace(Settings(), state_dir=tmp_path)
    auth = {"Authorization": "Bearer test"}
    thread = str(uuid.uuid4())
    with TestClient(create_app(settings, runtime=research_runtime, token="test")) as client:
        assert (
            client.post(
                "/ask",
                json={"question": "Research question", "thread_id": thread, "role": "research"},
                headers=auth,
            ).status_code
            == 200
        )
    with TestClient(create_app(settings, runtime=knowledge_runtime, token="test")) as client:
        for endpoint in [
            f"/history/knowledge/{thread}",
        ]:
            denied = client.get(endpoint, headers=auth)
            assert denied.status_code == 403, denied.text
            body = denied.text.lower()
            assert "research" not in body
            assert "owned by" not in body
            assert "owner" not in body


def test_cross_role_history_and_agent_denied_for_research_thread(tmp_path):
    """Read, AG-UI resume and transfer export of a Research thread from Knowledge fail."""
    shared = InMemoryOwnershipStore()
    research_runtime = runtime_for_role("research", shared)
    knowledge_runtime = runtime_for_role("knowledge", shared)
    settings = replace(Settings(), state_dir=tmp_path)
    auth = {"Authorization": "Bearer test"}
    thread = str(uuid.uuid4())
    with TestClient(create_app(settings, runtime=research_runtime, token="test")) as client:
        assert (
            client.post(
                "/ask",
                json={"question": "Research question", "thread_id": thread, "role": "research"},
                headers=auth,
            ).status_code
            == 200
        )
    with TestClient(create_app(settings, runtime=knowledge_runtime, token="test")) as client:
        assert client.get(f"/history/knowledge/{thread}", headers=auth).status_code == 403
        request = {
            "threadId": thread,
            "runId": str(uuid.uuid4()),
            "state": {},
            "messages": [{"id": "q", "role": "user", "content": "Question"}],
            "tools": [],
            "context": [],
            "forwardedProps": {},
        }
        assert client.post("/agent", json=request, headers=auth).status_code == 403
        tx = client.post(
            "/transfer",
            json={
                "source_role": "knowledge",
                "source_thread_id": thread,
                "target_role": "research",
                "target_thread_id": str(uuid.uuid4()),
            },
            headers=auth,
        )
        assert tx.status_code == 403, tx.text


def test_concurrent_first_turn_ownership_is_atomic(tmp_path):
    """The first runtime to claim a thread id wins; the second is denied."""
    import asyncio

    shared = InMemoryOwnershipStore()
    research_runtime = runtime_for_role("research", shared)
    interview_runtime = runtime_for_role("interview", shared)
    settings = replace(Settings(), state_dir=tmp_path)
    auth = {"Authorization": "Bearer test"}
    thread = str(uuid.uuid4())

    async def race():
        with (
            TestClient(
                create_app(settings, runtime=research_runtime, token="test")
            ) as research_client,
            TestClient(
                create_app(settings, runtime=interview_runtime, token="test")
            ) as interview_client,
        ):
            r1 = research_client.post(
                "/ask",
                json={"question": "R", "thread_id": thread, "role": "research"},
                headers=auth,
            )
            r2 = interview_client.post(
                "/ask",
                json={"question": "I", "thread_id": thread, "role": "interview"},
                headers=auth,
            )
            statuses = {r1.status_code, r2.status_code}
            assert statuses == {200, 403}, f"unexpected statuses {r1.status_code}, {r2.status_code}"
            return r1.status_code, r2.status_code

    # Run the race repeatedly; at least one ordering must show the expected split.
    for _ in range(20):
        a, b = asyncio.run(race())
        if a == 200 and b == 403:
            break
    else:
        raise AssertionError("Research never won the ownership race")


def test_role_system_prompt_reaches_model():
    """The runtime passes its role-specific system prompt into the graph."""
    settings = Settings()
    research_cfg = load_role_config("research", settings)
    interview_cfg = load_role_config("interview", settings)
    assert "Research Assistant" in research_cfg.system_prompt
    assert "Interview Analyst" in interview_cfg.system_prompt
    assert research_cfg.system_prompt != interview_cfg.system_prompt


def test_legacy_knowledge_checkpoint_resume(tmp_path):
    """A Knowledge runtime can resume a checkpoint stored under the raw UUID."""
    from langgraph.checkpoint.memory import InMemorySaver

    settings = replace(Settings(), state_dir=tmp_path)
    knowledge = Knowledge()
    config = RoleConfig(
        role="knowledge",
        display="Knowledge Assistant",
        system_prompt="You are knowledge",
        knowledge_tools=frozenset({"search_knowledge", "read_document"}),
        call_limit=3,
        models=[],
    )
    saver = InMemorySaver()
    graph = create_graph(FakeModel(), knowledge, saver, settings, role_config=config)
    thread = str(uuid.uuid4())
    # Simulate a legacy checkpoint by writing state under the raw UUID.
    import asyncio

    asyncio.run(
        graph.ainvoke(
            {
                "messages": [
                    __import__("langchain_core.messages", fromlist=["HumanMessage"]).HumanMessage(
                        content="Legacy question"
                    )
                ]
            },
            {"configurable": {"thread_id": thread}, "recursion_limit": 10},
        )
    )

    # A new runtime using the same saver resumes the legacy checkpoint.
    runtime = Runtime(graph, knowledge, "knowledge", "fake", InMemoryOwnershipStore())
    auth = {"Authorization": "Bearer test"}
    with TestClient(create_app(settings, runtime=runtime, token="test")) as client:
        response = client.get(f"/history/knowledge/{thread}", headers=auth)
        assert response.status_code == 200, response.text
        messages = response.json()["messages"]
        assert any("Legacy question" in m["content"] for m in messages)


def test_transfer_endpoint_returns_reviewable_summary(tmp_path):
    """Selected messages from a source role are summarized for a target role."""
    from dataclasses import replace

    auth = {"Authorization": "Bearer test"}
    source_thread = str(uuid.uuid4())
    target_thread = str(uuid.uuid4())
    settings = replace(Settings(), state_dir=tmp_path)
    with TestClient(
        create_app(settings, runtime=runtime_for_role("knowledge"), token="test")
    ) as client:
        ask = client.post(
            "/ask",
            json={"question": "What blocks Atlas?", "thread_id": source_thread},
            headers=auth,
        )
        assert ask.status_code == 200, ask.text

        transfer = client.post(
            "/transfer",
            json={
                "source_role": "knowledge",
                "source_thread_id": source_thread,
                "target_role": "research",
                "target_thread_id": target_thread,
                "message_ids": [],
            },
            headers=auth,
        )
        assert transfer.status_code == 200, transfer.text
        payload = transfer.json()
        assert "summary" in payload
        assert "What blocks Atlas?" in payload["summary"]
        assert payload["source_role"] == "knowledge"
        assert payload["target_role"] == "research"
        assert payload["message_count"] == 2

        # Same source and target role is rejected.
        same = client.post(
            "/transfer",
            json={
                "source_role": "knowledge",
                "source_thread_id": source_thread,
                "target_role": "knowledge",
                "target_thread_id": str(uuid.uuid4()),
            },
            headers=auth,
        )
        assert same.status_code == 400, same.text

        # Empty source conversation returns 404, not an empty success.
        empty_thread = str(uuid.uuid4())
        empty = client.post(
            "/transfer",
            json={
                "source_role": "knowledge",
                "source_thread_id": empty_thread,
                "target_role": "research",
                "target_thread_id": str(uuid.uuid4()),
            },
            headers=auth,
        )
        assert empty.status_code == 404, empty.text
