import json
import uuid
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any

from fastapi.testclient import TestClient
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import Field

from nora.agent import bounded_messages, create_graph
from nora.config import Settings
from nora.coordination import Runtime, create_app
from nora.documents import LocalDocumentStore
from nora.indexing import import_bundle
from nora.ownership import InMemoryOwnershipStore
from nora.retrieval import RetrievalService
from nora.retrieval import create_app as retrieval_app


class Knowledge:
    failure = False
    calls = []

    @asynccontextmanager
    async def pinned(self):
        yield self

    async def call(self, name, arguments):
        if self.failure:
            raise RuntimeError("Synthetic retrieval outage")
        return {"results": [{"doc_id": "a" * 64, "text": "Atlas waits for rollback rehearsal."}]}

    async def health(self):
        return {"ready": not self.failure, "documents": 3, "points": 7}


class Model(BaseChatModel):
    observed: Any = Field(default_factory=list, exclude=True)
    bound: Any = Field(default_factory=list, exclude=True)

    @property
    def _llm_type(self):
        return "nora-test-model"

    def bind_tools(self, tools, **kwargs):
        self.bound.append([tool.name for tool in tools])
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.observed.append(messages)
        humans = [m for m in messages if isinstance(m, HumanMessage)]
        assert isinstance(messages[-1], ToolMessage)
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=f"Grounded turn {len(humans)}"))]
        )


def runtime(settings):
    model, knowledge = Model(), Knowledge()
    graph = create_graph(model, knowledge, InMemorySaver(), settings)
    return Runtime(graph, knowledge, "knowledge", "synthetic", InMemoryOwnershipStore()), model


def test_real_graph_grounding_followup_checkpoint_and_current_turn_counts(tmp_path):
    settings = replace(Settings(), state_dir=tmp_path, history_turns=2)
    state, model = runtime(settings)
    thread = str(uuid.uuid4())
    with TestClient(create_app(settings, state, token="test")) as client:
        auth = {"Authorization": "Bearer test"}
        assert client.get("/health").status_code == 401
        assert client.get("/health", headers=auth).json()["documents"] == 3
        for n in range(1, 4):
            response = client.post(
                "/ask", json={"question": f"Question {n}", "thread_id": thread}, headers=auth
            )
            assert response.status_code == 200, response.text
            assert response.json()["knowledge_calls"] == 1
            assert response.json()["answer"] == f"Grounded turn {min(n, 2)}"
        saved = client.get("/history/" + thread, headers=auth).json()["messages"]
        assert len(saved) == 6
        assert all(message["role"] in {"user", "assistant"} for message in saved)
    assert all(set(tools) == {"search_knowledge", "read_document"} for tools in model.bound)


def test_agent_budget_is_http_429_before_sse_and_outages_are_explicit(tmp_path):
    settings = replace(Settings(), state_dir=tmp_path, daily_limit=1)
    state, _ = runtime(settings)
    auth = {"Authorization": "Bearer test"}
    with TestClient(create_app(settings, state, token="test")) as client:
        response = client.post("/ask", json={"question": "Question"}, headers=auth)
        assert response.status_code == 200, response.text
        request = {
            "threadId": str(uuid.uuid4()),
            "runId": str(uuid.uuid4()),
            "state": {},
            "messages": [{"id": "q", "role": "user", "content": "Question"}],
            "tools": [],
            "context": [],
            "forwardedProps": {},
        }
        blocked = client.post("/agent", json=request, headers=auth)
        assert blocked.status_code == 429
        assert blocked.headers["content-type"].startswith("application/json")
        state.knowledge.failure = True
        assert client.get("/health", headers=auth).status_code == 503


def test_retrieval_failure_releases_slot_and_next_request_recovers(tmp_path):
    settings = replace(Settings(), state_dir=tmp_path, request_timeout=3)
    state, _ = runtime(settings)
    auth = {"Authorization": "Bearer test"}
    with TestClient(create_app(settings, state, token="test")) as client:
        state.knowledge.failure = True
        assert client.post("/ask", json={"question": "Question"}, headers=auth).status_code == 503
        state.knowledge.failure = False
        assert client.post("/ask", json={"question": "Question"}, headers=auth).status_code == 200
        assert client.get("/history/bad-id", headers=auth).status_code == 422
        assert client.post("/ask", content=b"x" * 70001, headers=auth).status_code == 413


def test_ag_ui_stream_uses_real_adapter(tmp_path):
    settings = replace(Settings(), state_dir=tmp_path)
    state, _ = runtime(settings)
    request = {
        "threadId": str(uuid.uuid4()),
        "runId": str(uuid.uuid4()),
        "state": {},
        "messages": [{"id": "q", "role": "user", "content": "Question"}],
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }
    with TestClient(create_app(settings, state, token="test")) as client:
        response = client.post(
            "/agent",
            json=request,
            headers={"Authorization": "Bearer test", "Accept": "text/event-stream"},
        )
        assert response.status_code == 200
        events = [
            json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
        ]
        assert events[0]["type"] == "RUN_STARTED"
        assert events[-1]["type"] == "RUN_FINISHED", events
        assert any("Grounded turn 1" in str(event) for event in events)


def test_context_trimming_keeps_pairs_and_does_not_mutate_checkpoints():
    call = AIMessage(content="", tool_calls=[{"name": "read_document", "args": {}, "id": "r"}])
    tool = ToolMessage(content="x" * 10000, tool_call_id="r")
    source = [
        HumanMessage(content="Old"),
        AIMessage(content="Old answer"),
        HumanMessage(content="New"),
        call,
        tool,
    ]
    trimmed = bounded_messages(source, 1, 1000)
    assert len(trimmed) == 3 and trimmed[1].tool_calls[0]["id"] == trimmed[2].tool_call_id
    assert len(tool.content) == 10000 and len(trimmed[2].content) < 1000


def test_mcp_initialize_tools_search_read_and_auth(bundle, encoder, qdrant):
    import_bundle(qdrant, "test", bundle)
    service = RetrievalService(
        qdrant, encoder, LocalDocumentStore(bundle / "docs"), collection="test", data_dir=bundle
    )
    app = retrieval_app(Settings(), service, token="test")
    with TestClient(app, base_url="http://localhost:8001") as client:
        assert client.get("/health").status_code == 401
        headers = {"Authorization": "Bearer test", "Accept": "application/json, text/event-stream"}

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
        assert {tool["name"] for tool in rpc("tools/list", {})["tools"]} == {"search", "read"}
        found = rpc("tools/call", {"name": "search", "arguments": {"query": "Cedar support"}})
        assert not found.get("isError"), found
        results = found.get("structuredContent", json.loads(found["content"][0]["text"]))["results"]
        read = rpc(
            "tools/call",
            {"name": "read", "arguments": {"doc_id": results[0]["doc_id"], "limit": 50}},
        )
        assert not read.get("isError"), read
        assert (
            len(read.get("structuredContent", json.loads(read["content"][0]["text"]))["text"]) == 50
        )
        invalid = rpc("tools/call", {"name": "search", "arguments": {"query": " "}})
        assert invalid["isError"]
        assert (
            client.post(
                "/mcp", headers={**headers, "Host": "untrusted.example"}, json={}
            ).status_code
            == 421
        )


async def test_router_runs_inside_the_real_deep_agent_graph():
    from nora.routing import RoutingChatModel

    cheap, strong = Model(), Model()
    router = RoutingChatModel(cheap_model=cheap, strong_model=strong)
    graph = create_graph(router, Knowledge(), InMemorySaver(), Settings())
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="Atlas status")]},
        {"configurable": {"thread_id": str(uuid.uuid4())}},
    )
    assert result["messages"][-1].content == "Grounded turn 1"
    assert len(cheap.observed) == 1 and not strong.observed
    assert set(cheap.bound[-1]) == {"search_knowledge", "read_document"}


def test_explicit_transfer_returns_reviewable_summary_not_raw_history(tmp_path):
    """Transfer returns a deterministic summary; target history is not auto-populated."""
    from dataclasses import replace

    settings = replace(Settings(), state_dir=tmp_path)
    state, _ = runtime(settings)
    auth = {"Authorization": "Bearer test"}
    source = str(uuid.uuid4())
    target = str(uuid.uuid4())
    with TestClient(create_app(settings, state, token="test")) as client:
        # Create a Knowledge conversation.
        r1 = client.post(
            "/ask",
            json={"question": "What blocks Atlas?", "thread_id": source, "role": "knowledge"},
            headers=auth,
        )
        assert r1.status_code == 200
        # Request transfer summary.
        tx = client.post(
            "/transfer",
            json={
                "source_role": "knowledge",
                "source_thread_id": source,
                "target_role": "research",
                "target_thread_id": target,
            },
            headers=auth,
        )
        assert tx.status_code == 200, tx.text
        body = tx.json()
        assert "Summary from knowledge conversation" in body["summary"]
        assert body["source_role"] == "knowledge"
        assert body["target_role"] == "research"
        # The target thread remains empty until the user explicitly posts the summary.
        target_history = client.get(f"/history/knowledge/{target}", headers=auth)
        assert target_history.status_code == 200
        assert target_history.json()["messages"] == []


def test_cross_role_resume_is_denied_on_knowledge_runtime(tmp_path):
    """A client-visible thread id used for Research cannot be read from Knowledge."""
    from dataclasses import replace

    settings = replace(Settings(), state_dir=tmp_path)
    state, _ = runtime(settings)
    auth = {"Authorization": "Bearer test"}
    thread = str(uuid.uuid4())
    with TestClient(create_app(settings, state, token="test")) as client:
        assert client.get(f"/history/research/{thread}", headers=auth).status_code == 403
