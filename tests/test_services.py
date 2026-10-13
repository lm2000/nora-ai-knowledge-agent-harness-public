import json
import uuid
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
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


class CountingKnowledge(Knowledge):
    def __init__(self):
        self.calls = []

    async def call(self, name, arguments):
        self.calls.append(name)
        return await super().call(name, arguments)


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


class RepeatedToolModel(Model):
    """Attempt one tool call beyond the run budget, then answer from prior passages."""

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.observed.append(messages)
        blocked = [
            message
            for message in messages
            if isinstance(message, ToolMessage) and getattr(message, "status", None) == "error"
        ]
        if blocked:
            return ChatResult(
                generations=[
                    ChatGeneration(message=AIMessage(content="Answer from prior passages"))
                ]
            )
        searches = sum(
            isinstance(message, ToolMessage) and message.name == "search_knowledge"
            for message in messages
        )
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "search_knowledge",
                                "args": {"query": f"retry {searches}"},
                                "id": f"retry-{searches}",
                            }
                        ],
                    )
                )
            ]
        )


class BatchedToolModel(Model):
    """Read once, request a partially blocked batch, then return a final answer."""

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.observed.append(messages)
        if any(isinstance(m, ToolMessage) and m.status == "error" for m in messages):
            answer = AIMessage(content="Answer from prior passages")
        else:
            read = any(isinstance(m, ToolMessage) and m.name == "read_document" for m in messages)
            calls = (
                [
                    {
                        "name": "search_knowledge",
                        "args": {"query": f"lookup {i}"},
                        "id": f"search-{i}",
                    }
                    for i in range(2)
                ]
                if read
                else [{"name": "read_document", "args": {"doc_id": "a" * 64}, "id": "read"}]
            )
            answer = AIMessage(content="", tool_calls=calls)
        return ChatResult(generations=[ChatGeneration(message=answer)])


class NeverEndingToolModel(RepeatedToolModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        # Ignore tool-limit errors to exercise the separate model-call guard.
        messages = [m for m in messages if not (isinstance(m, ToolMessage) and m.status == "error")]
        return super()._generate(messages, stop, run_manager, **kwargs)


def runtime(settings):
    model, knowledge = Model(), Knowledge()
    graph = create_graph(model, knowledge, InMemorySaver(), settings)
    return Runtime(graph, knowledge, "synthetic", InMemoryOwnershipStore()), model


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


def test_tool_call_limit_returns_answer_from_prior_passages(tmp_path):
    settings = replace(Settings(), state_dir=tmp_path, knowledge_call_limit=2)
    model, knowledge = RepeatedToolModel(), Knowledge()
    graph = create_graph(model, knowledge, InMemorySaver(), settings)
    state = Runtime(graph, knowledge, "synthetic", InMemoryOwnershipStore())
    with TestClient(create_app(settings, state, token="test")) as client:
        response = client.post(
            "/ask",
            json={"question": "Question", "thread_id": str(uuid.uuid4())},
            headers={"Authorization": "Bearer test"},
        )
    assert response.status_code == 200, response.text
    assert response.json()["answer"] == "Answer from prior passages"


@pytest.mark.parametrize("model_type", [RepeatedToolModel, BatchedToolModel])
def test_default_retrieval_budget_delivers_final_answer(tmp_path, model_type):
    settings = replace(Settings(), state_dir=tmp_path)
    model, knowledge = model_type(), CountingKnowledge()
    graph = create_graph(model, knowledge, InMemorySaver(), settings)
    state = Runtime(graph, knowledge, "synthetic", InMemoryOwnershipStore())
    thread = str(uuid.uuid4())
    with TestClient(create_app(settings, state, token="test")) as client:
        auth = {"Authorization": "Bearer test"}
        response = client.post(
            "/ask", json={"question": "Question", "thread_id": thread}, headers=auth
        )
        assert response.status_code == 200, response.text
        assert response.json()["answer"] == "Answer from prior passages"
        assert response.json()["knowledge_calls"] == 4  # Includes one blocked-call result.
        saved = client.get("/history/" + thread, headers=auth).json()["messages"]
        assert saved[-1]["content"] == response.json()["answer"]
    assert len(model.observed) <= settings.knowledge_call_limit + 1
    assert len(knowledge.calls) == settings.knowledge_call_limit


def test_model_call_guard_stops_repeated_blocked_tools_and_releases_slot(tmp_path):
    settings = replace(Settings(), state_dir=tmp_path, concurrency=1, request_timeout=3)
    model, knowledge = NeverEndingToolModel(), CountingKnowledge()
    graph = create_graph(model, knowledge, InMemorySaver(), settings)
    state = Runtime(graph, knowledge, "synthetic", InMemoryOwnershipStore())
    with TestClient(create_app(settings, state, token="test")) as client:
        auth = {"Authorization": "Bearer test"}
        response = client.post("/ask", json={"question": "Question"}, headers=auth)
        assert response.status_code == 503
        assert len(model.observed) == settings.knowledge_call_limit + 1
        assert len(knowledge.calls) == settings.knowledge_call_limit
        before = len(model.observed)
        response = client.post("/ask", json={"question": "Next question"}, headers=auth)
        assert response.status_code == 503
        assert len(model.observed) - before == settings.knowledge_call_limit + 1


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


def test_startup_warns_for_missing_provider_credentials(monkeypatch, caplog):
    """An assistant inventory with half-configured providers warns once at startup."""
    from nora.coordination import _warn_missing_provider_credentials
    from nora.providers import ProviderSpec

    monkeypatch.delenv("NORA_FIREWORKS_TOKEN", raising=False)
    monkeypatch.delenv("NORA_FIREWORKS_TOKEN_FILE", raising=False)
    monkeypatch.delenv("NORA_OLLAMA_TOKEN", raising=False)
    monkeypatch.delenv("NORA_OLLAMA_TOKEN_FILE", raising=False)

    models = [
        ProviderSpec(
            provider="ollama",
            model="gpt-oss:20b",
            base_url="http://localhost:11434",
            token_name="OLLAMA_TOKEN",
        ),
        ProviderSpec(
            provider="fireworks",
            model="accounts/fireworks/models/kimi-k3",
            base_url="https://api.fireworks.ai/inference/v1",
            token_name="FIREWORKS_TOKEN",
        ),
    ]
    import logging

    with caplog.at_level(logging.WARNING, logger="nora.coordination"):
        _warn_missing_provider_credentials(models)
    warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1, warnings
    assert "fireworks/accounts/fireworks/models/kimi-k3" in warnings[0]
    assert "FIREWORKS_TOKEN" in warnings[0]
    assert "ollama" not in warnings[0]  # local endpoint stays routable


def test_startup_warns_when_all_models_lack_credentials(monkeypatch, caplog):
    """An inventory where every candidate lacks a credential warns the assistant will fail."""
    from nora.coordination import _warn_missing_provider_credentials
    from nora.providers import ProviderSpec

    monkeypatch.setenv("NORA_FIREWORKS_TOKEN", "")
    monkeypatch.delenv("NORA_FIREWORKS_TOKEN_FILE", raising=False)

    models = [
        ProviderSpec(
            provider="fireworks",
            model="accounts/fireworks/models/kimi-k3",
            base_url="https://api.fireworks.ai/inference/v1",
            token_name="FIREWORKS_TOKEN",
        )
    ]
    import logging

    with caplog.at_level(logging.WARNING, logger="nora.coordination"):
        _warn_missing_provider_credentials(models)
    warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("has no model with a configured provider credential" in w for w in warnings)


class EmptyFollowupModel(Model):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        humans = sum(isinstance(m, HumanMessage) for m in messages)
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content="Grounded first answer" if humans == 1 else "",
                        response_metadata={"done_reason": "length"} if humans > 1 else {},
                    )
                )
            ]
        )


def test_empty_final_answer_is_failure_and_cannot_reuse_previous_turn(tmp_path):
    settings = replace(Settings(), state_dir=tmp_path)
    model, knowledge = EmptyFollowupModel(), Knowledge()
    graph = create_graph(model, knowledge, InMemorySaver(), settings)
    state = Runtime(graph, knowledge, "synthetic", InMemoryOwnershipStore())
    thread = str(uuid.uuid4())
    with TestClient(create_app(settings, state, token="test")) as client:
        auth = {"Authorization": "Bearer test"}
        first = client.post("/ask", json={"question": "First", "thread_id": thread}, headers=auth)
        assert first.json()["answer"] == "Grounded first answer"
        failed = client.post(
            "/ask", json={"question": "Follow-up", "thread_id": thread}, headers=auth
        )
        assert failed.status_code == 503
        assert "Grounded first answer" not in failed.text
        # A failed turn releases the concurrency slot for a new conversation.
        fresh = client.post("/ask", json={"question": "Fresh"}, headers=auth)
        assert fresh.status_code == 200


class LengthModel(Model):
    replies: Any = Field(default_factory=list)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.observed.append(messages)
        return ChatResult(generations=[ChatGeneration(message=self.replies.pop(0))])


def length_runtime(tmp_path, replies):
    from nora.assistant import load_assistant_config

    settings = replace(Settings(), state_dir=tmp_path)
    assistant = load_assistant_config(settings)
    model, knowledge = LengthModel(replies=replies), CountingKnowledge()
    graph = create_graph(model, knowledge, InMemorySaver(), settings, assistant_config=assistant)
    state = Runtime(graph, knowledge, "synthetic", InMemoryOwnershipStore())
    return settings, state, model, knowledge


@pytest.mark.parametrize("tool_rounds", [0, 2])
def test_length_repair_preserves_source_counts_calls_and_removes_draft(tmp_path, tool_rounds):
    draft = "extra " * 12 + "Source: Record, Recovery, 2026-10-04; live state unverified."
    final = "Restore the saved pin. Source: Record, Recovery, 2026-10-04; live state unverified."
    settings, state, model, knowledge = length_runtime(
        tmp_path,
        [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "search_knowledge", "args": {"query": "lookup"}, "id": f"lookup-{i}"}
                ],
            )
            for i in range(tool_rounds)
        ]
        + [AIMessage(content=draft), AIMessage(content=final), AIMessage(content="Next")],
    )
    thread = str(uuid.uuid4())
    with TestClient(create_app(settings, state, token="test")) as client:
        auth = {"Authorization": "Bearer test"}
        response = client.post(
            "/ask",
            json={"question": "Answer in at most 15 words", "thread_id": thread},
            headers=auth,
        )
        assert response.status_code == 200, response.text
        assert response.json()["answer"] == final
        history = client.get("/history/" + thread, headers=auth).json()["messages"]
        assert [m["content"] for m in history] == ["Answer in at most 15 words", final]
        assert len(model.observed) == 2 + tool_rounds
        assert len(knowledge.calls) == 1 + tool_rounds
        assert len(model.bound) == 1 + tool_rounds
        assert "exact source title and heading" not in str(model.observed[-1][-1].content)
        assert "Preserve supported facts" in str(model.observed[-1][-1].content)
        assert model.observed[-1][-1].name == "nora_answer_repair"
        response = client.post(
            "/ask", json={"question": "Next question", "thread_id": thread}, headers=auth
        )
        assert response.status_code == 200, response.text
        assert response.json()["answer"] == "Next"
    assert len(model.observed) == 3 + tool_rounds
    assert all(m.name != "nora_answer_repair" for msgs in model.observed[-1:] for m in msgs)


@pytest.mark.parametrize("cap", [True, False])
def test_compliant_or_uncapped_reply_does_not_trigger_length_repair(tmp_path, cap):
    settings, state, model, _ = length_runtime(tmp_path, [AIMessage(content="Concise reply")])
    with TestClient(create_app(settings, state, token="test")) as client:
        response = client.post(
            "/ask",
            json={"question": "At most 10 words" if cap else "Explain rollback"},
            headers={"Authorization": "Bearer test"},
        )
    assert response.status_code == 200
    assert len(model.observed) == 1


@pytest.mark.parametrize(
    "repair",
    [
        AIMessage(content="still far too many words"),
        AIMessage(
            content="",
            tool_calls=[{"name": "search_knowledge", "args": {"query": "retry"}, "id": "repair"}],
        ),
    ],
)
def test_length_repair_fails_once_without_extra_tools_or_loop(tmp_path, repair):
    settings, state, model, knowledge = length_runtime(
        tmp_path, [AIMessage(content="too many words"), repair]
    )
    with TestClient(create_app(settings, state, token="test")) as client:
        response = client.post(
            "/ask", json={"question": "At most 2 words"}, headers={"Authorization": "Bearer test"}
        )
    assert response.status_code == 503
    assert len(model.observed) == 2
    assert len(knowledge.calls) == 1


def test_length_repair_never_exceeds_four_model_calls(tmp_path):
    tools = [
        AIMessage(
            content="",
            tool_calls=[{"name": "search_knowledge", "args": {"query": "retry"}, "id": f"r-{i}"}],
        )
        for i in range(3)
    ]
    settings, state, model, knowledge = length_runtime(
        tmp_path, tools + [AIMessage(content="far too many words")]
    )
    with TestClient(create_app(settings, state, token="test")) as client:
        response = client.post(
            "/ask", json={"question": "At most 2 words"}, headers={"Authorization": "Bearer test"}
        )
    assert response.status_code == 503
    assert len(model.observed) == 4
    assert len(knowledge.calls) == 3


PREPARATION_QUESTION = (
    "When Nora prepares my documents, does it summarize or rewrite them? "
    "What information should survive preparation? Answer in at most 100 words, "
    "and name the saved source and heading you used."
)
PREPARATION_ANSWER = (
    "Preparation is deterministic, without summaries or rewriting meaning. "
    "It preserves originals, headings and substantive text, source identity and metadata, "
    "chunk identities, hashes and offsets, and model configuration with vectors. "
    "Source: Manual ingestion / Processing contract; Selected target workflow."
)


class PreparationKnowledge(CountingKnowledge):
    async def call(self, name, arguments):
        self.calls.append(name)
        return {"results": [{"title": "Manual ingestion", "text": PREPARATION_ANSWER}]}


@pytest.mark.parametrize("key", ["done_reason", "finish_reason"])
@pytest.mark.parametrize("capped", [True, False])
def test_known_length_stop_fails_and_releases_slot(tmp_path, key, capped):
    settings, state, model, knowledge = length_runtime(
        tmp_path,
        [
            AIMessage(content="A short partial answer.", response_metadata={key: "length"}),
            AIMessage(content="Next answer"),
        ],
    )
    thread = str(uuid.uuid4())
    with TestClient(create_app(settings, state, token="test")) as client:
        headers = {"Authorization": "Bearer test"}
        response = client.post(
            "/ask",
            headers=headers,
            json={
                "question": "At most 100 words" if capped else "Explain",
                "thread_id": thread,
            },
        )
        assert response.status_code == 503
        response = client.post(
            "/ask",
            headers=headers,
            json={
                "question": "Next",
                "thread_id": thread,
            },
        )
        assert response.status_code == 200
        assert response.json()["answer"] == "Next answer"
    assert len(model.observed) == 2
    assert len(knowledge.calls) == 2


@pytest.mark.parametrize("metadata", [{}, {"finish_reason": "stop"}, {"done_reason": "unknown"}])
def test_unknown_stop_metadata_alone_is_not_failure(tmp_path, metadata):
    settings, state, model, _ = length_runtime(
        tmp_path,
        [
            AIMessage(content="Valid answer", response_metadata=metadata),
        ],
    )
    with TestClient(create_app(settings, state, token="test")) as client:
        assert (
            client.post(
                "/ask", headers={"Authorization": "Bearer test"}, json={"question": "Explain"}
            ).status_code
            == 200
        )
    assert len(model.observed) == 1


def preparation_runtime(tmp_path, replies):
    settings, _, model, _ = length_runtime(tmp_path, replies)
    knowledge = PreparationKnowledge()
    graph = create_graph(model, knowledge, InMemorySaver(), settings)
    return (
        settings,
        Runtime(graph, knowledge, "synthetic", InMemoryOwnershipStore()),
        model,
        knowledge,
    )


def test_combined_preparation_and_length_repair_once_then_topic_reset(tmp_path):
    settings, state, model, knowledge = preparation_runtime(
        tmp_path,
        [
            AIMessage(content="Unrelated " * 105),
            AIMessage(content=PREPARATION_ANSWER),
            AIMessage(content="Different topic"),
        ],
    )
    with TestClient(create_app(settings, state, token="test")) as client:
        headers = {"Authorization": "Bearer test"}
        response = client.post("/ask", headers=headers, json={"question": PREPARATION_QUESTION})
        assert response.status_code == 200, response.text
        thread = response.json()["thread_id"]
        history = client.get("/history/" + thread, headers=headers).json()["messages"]
        assert history[-1]["content"] == PREPARATION_ANSWER
        assert len(history) == 2
        repair_prompt = str(model.observed[-1][-1].content)
        assert "source identity and metadata" in repair_prompt
        assert "word limit" in repair_prompt
        assert model.observed[-1][-1].name == "nora_answer_repair"
        assert len(model.bound) == 1
        response = client.post(
            "/ask",
            headers=headers,
            json={
                "question": "Explain Kafka partitions",
                "thread_id": thread,
            },
        )
        assert response.status_code == 200
    assert len(model.observed) == 3
    assert len(knowledge.calls) == 2


@pytest.mark.parametrize("rounds", [0, 3])
def test_preparation_failure_cannot_add_fifth_call(tmp_path, rounds):
    tools = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "search_knowledge",
                    "args": {"query": "NIS manual ingestion"},
                    "id": f"p-{i}",
                }
            ],
        )
        for i in range(rounds)
    ]
    settings, state, model, knowledge = preparation_runtime(
        tmp_path,
        tools
        + [
            AIMessage(content="Preserves originals."),
            AIMessage(content="Still originals."),
        ],
    )
    with TestClient(create_app(settings, state, token="test")) as client:
        response = client.post(
            "/ask",
            headers={"Authorization": "Bearer test"},
            json={"question": PREPARATION_QUESTION},
        )
    assert response.status_code == 503
    assert len(model.observed) == (2 if rounds == 0 else 4)
    assert len(knowledge.calls) <= 3


def test_preparation_scope_features_and_partial_evidence():
    from nora.agent import preparation_deficits, preparation_features, preparation_scope

    assert preparation_scope([HumanMessage(content=PREPARATION_QUESTION)], 4)
    assert preparation_scope(
        [HumanMessage(content=PREPARATION_QUESTION), HumanMessage(content="What else survives?")], 4
    )
    for question in [
        "Does Nora preparation summarize?",
        "Compare local storage and GCS",
        "What source metadata is available?",
        "Explain Kafka",
    ]:
        assert not preparation_scope([HumanMessage(content=question)], 4)
    assert "originals" not in preparation_features("It does not preserve originals.")
    assert "source identity and metadata" not in preparation_features(
        "Source identity and metadata are not preserved."
    )
    assert "source identity and metadata" not in preparation_features(
        "Source identity and chunk metadata are retained."
    )
    assert "chunk identities, hashes and offsets" not in preparation_features(
        "Chunk identities and hashes. Pagination offsets are available."
    )
    assert "source identity and metadata" not in preparation_features(
        "Chunk identities and metadata."
    )
    assert "chunk identities, hashes and offsets" in preparation_features(
        "Chunks retain identifiers, hashes and offsets."
    )
    messages = [
        HumanMessage(content=PREPARATION_QUESTION),
        ToolMessage(
            name="read_document",
            tool_call_id="x",
            content=json.dumps(
                {
                    "title": "Manual ingestion",
                    "text": "Preserves originals.",
                    "next_offset": 8000,
                }
            ),
        ),
    ]
    deficits = preparation_deficits(messages, "Preserves originals.", False)
    assert not any("Include supported fact" in d for d in deficits)
    assert any("evidence gap for: chunk" in d for d in deficits)


def test_preparation_guidance_prioritizes_owning_guide():
    from nora.assistant import ASSISTANT_ANSWER_GUIDANCE

    assert "prefer the requested owning Manual ingestion guide" in ASSISTANT_ANSWER_GUIDANCE
    assert "read the matching returned document ID at offset 0" in ASSISTANT_ANSWER_GUIDANCE
    assert "Do not hardcode an ID or request parallel reads" in ASSISTANT_ANSWER_GUIDANCE
    assert "When results concern another subject" not in ASSISTANT_ANSWER_GUIDANCE


def test_saved_manual_wording_and_evidence_gaps():
    from nora.agent import PREPARATION_GROUPS, preparation_deficits, preparation_features

    # Public Manual ingestion wording exercised in the dated pilot, rather than
    # a fixture that merely echoes the expected answer.
    passage = (
        "# Manual ingestion\n## Selected target workflow\n"
        "Selected original versions, read only. Extracted text/assets and source metadata.\n"
        "Deterministic preparation: normalized chunk records with stable identities, "
        "hashes and offsets.\n## Processing contract\n"
        "Select source versions and preserve originals. Preserve headings and substantive text. "
        "Do not generate source summaries or rewrite meaning. "
        "Retain text, stable identities, hashes and model configuration with vectors."
    )
    assert preparation_features(passage) == set(PREPARATION_GROUPS)
    messages = [
        HumanMessage(content=PREPARATION_QUESTION),
        ToolMessage(
            name="read_document",
            tool_call_id="manual",
            content=json.dumps({"text": passage}),
        ),
    ]
    assert preparation_deficits(messages, PREPARATION_ANSWER, True) == []
    followup = messages + [
        AIMessage(content=PREPARATION_ANSWER),
        HumanMessage(content="What else survives?"),
    ]
    assert preparation_deficits(followup, PREPARATION_ANSWER, False) == []
    partial = [
        HumanMessage(content=PREPARATION_QUESTION),
        ToolMessage(
            name="search_knowledge",
            tool_call_id="partial",
            content=json.dumps(
                {
                    "title": "Manual ingestion",
                    "results": [{"text": "Preserve originals."}],
                    "next_offset": 99,
                }
            ),
        ),
    ]
    gaps = "Preserves originals. " + ". ".join(
        f"Unavailable: {label}" for label in PREPARATION_GROUPS if label != "originals"
    )
    assert preparation_deficits(partial, gaps, False) == []
    assert any(
        "Remove unsupported claim" in d
        for d in preparation_deficits(
            partial,
            PREPARATION_ANSWER + " " + gaps,
            False,
        )
    )


def test_length_metadata_on_intermediate_tool_call_is_not_final_failure(tmp_path):
    settings, state, model, _ = length_runtime(
        tmp_path,
        [
            AIMessage(
                content="",
                response_metadata={"done_reason": "length"},
                tool_calls=[
                    {
                        "name": "search_knowledge",
                        "args": {"query": "Atlas"},
                        "id": "intermediate",
                    }
                ],
            ),
            AIMessage(content="Final answer"),
        ],
    )
    with TestClient(create_app(settings, state, token="test")) as client:
        response = client.post(
            "/ask", headers={"Authorization": "Bearer test"}, json={"question": "Explain"}
        )
    assert response.status_code == 200
    assert len(model.observed) == 2


UNTITLED_PROCESSING_CONTRACT = (
    "## Processing contract\n"
    "1. Select source versions and preserve originals.\n"
    "2. Extract readable text with Docling or a direct reader.\n"
    "3. Normalize deterministically; omit empty/unreadable content, exact duplicates, "
    "OS metadata and obvious repeated boilerplate from derived data.\n"
    "4. Preserve headings and substantive text. Do not generate source summaries or rewrite meaning.\n"
    "5. Chunk within the embedding model's complete input limit.\n"
    "6. Retain text, stable identities, hashes and model configuration with vectors."
)
MODEL_CONFIGURATION_VARIANT = (
    "Preparation is deterministic — no summaries or meaning rewrites. Preserved: "
    "original bytes unchanged; source identity and metadata; headings and substantive text; "
    "chunk records with stable identities, hashes and offsets; vectors tied to chunk IDs "
    "with pinned model revision, dimensions and normalization. "
    'Source: "Manual ingestion" — "Processing contract" and "Selected target workflow".'
)


def test_untitled_contract_supports_facts_without_inventing_source_title():
    from nora.agent import preparation_deficits, preparation_passages

    passage = {
        "doc_id": "a" * 64,
        "title": None,
        "heading": "## Processing contract",
        "text": UNTITLED_PROCESSING_CONTRACT,
    }
    evidence, titled = preparation_passages({"results": [passage]})
    assert evidence and not titled
    messages = [
        HumanMessage(content=PREPARATION_QUESTION),
        ToolMessage(
            name="search_knowledge",
            tool_call_id="contract",
            content=json.dumps({"results": [passage]}),
        ),
    ]
    deficits = preparation_deficits(messages, PREPARATION_ANSWER, True)
    assert not any("Remove unsupported claim: deterministic" in d for d in deficits)
    assert not any("Remove unsupported claim: headings" in d for d in deficits)
    assert any("source title is not verified" in d for d in deficits)


@pytest.mark.parametrize(
    "payload",
    [
        {"heading": "## 3. Manual ingestion outside conversations", "text": PREPARATION_ANSWER},
        {
            "title": "Architecture decisions",
            "heading": "## Processing contract",
            "text": UNTITLED_PROCESSING_CONTRACT,
        },
        {"heading": "## Processing contract", "text": "Chunk memory preserves original headings."},
        {"title": "Architecture decisions", "text": "# Manual ingestion\n" + PREPARATION_ANSWER},
    ],
)
def test_broad_or_unrelated_ingestion_mentions_are_not_owning_guide(payload):
    from nora.agent import preparation_passages

    assert preparation_passages({"results": [payload]}) == ([], False)
    assert preparation_passages(
        {"title": "Architecture decisions", "text": "# Manual ingestion\n" + PREPARATION_ANSWER}
    ) == ([], False)


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            "Vectors tied to chunk IDs with pinned model revision, dimensions and normalization.",
            True,
        ),
        ("Vectors use pinned model revision, dimensions and normalisation.", True),
        ("Pinned model revision with vectors.", False),
        ("Vectors have dimensions and normalization. Another model has a revision.", False),
        ("Model revision, dimensions and normalization are not retained with vectors.", False),
    ],
)
def test_model_configuration_synonyms_remain_specific(text, expected):
    from nora.agent import preparation_features

    assert ("model configuration with vectors" in preparation_features(text)) is expected


def test_configuration_variant_does_not_trigger_unnecessary_repair(tmp_path):
    settings, state, model, knowledge = preparation_runtime(
        tmp_path, [AIMessage(content=MODEL_CONFIGURATION_VARIANT)]
    )
    with TestClient(create_app(settings, state, token="test")) as client:
        response = client.post(
            "/ask",
            headers={"Authorization": "Bearer test"},
            json={"question": PREPARATION_QUESTION},
        )
    assert response.status_code == 200, response.text
    assert response.json()["answer"] == MODEL_CONFIGURATION_VARIANT
    assert len(model.observed) == 1
    assert len(knowledge.calls) == 1


class UntitledContractKnowledge(CountingKnowledge):
    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "read":
            return {
                "doc_id": "a" * 64,
                "text": "# Manual ingestion\n" + PREPARATION_ANSWER,
                "next_offset": 8000,
            }
        return {
            "results": [
                {
                    "doc_id": "a" * 64,
                    "heading": "## Processing contract",
                    "text": UNTITLED_PROCESSING_CONTRACT,
                }
            ]
        }


def test_returned_id_read_recovers_title_without_extra_search_or_repair(tmp_path):
    settings = replace(Settings(), state_dir=tmp_path)
    model = LengthModel(replies=[AIMessage(content=MODEL_CONFIGURATION_VARIANT)])
    knowledge = UntitledContractKnowledge()
    graph = create_graph(model, knowledge, InMemorySaver(), settings)
    state = Runtime(graph, knowledge, "synthetic", InMemoryOwnershipStore())
    with TestClient(create_app(settings, state, token="test")) as client:
        response = client.post(
            "/ask",
            headers={"Authorization": "Bearer test"},
            json={"question": PREPARATION_QUESTION},
        )
    assert response.status_code == 200, response.text
    assert [name for name, args in knowledge.calls] == ["search", "read"]
    assert knowledge.calls[1][1] == {"doc_id": "a" * 64, "offset": 0}
    assert len(model.observed) == 1
    assert [m.name for m in model.observed[0] if isinstance(m, ToolMessage)] == [
        "search_knowledge",
        "read_document",
    ]
    assert all(
        "Revise your preceding answer" not in str(msgs[0].content) for msgs in model.observed
    )
    assert "read that hit's returned document ID" in str(model.observed[0][0].content)


def test_context_trimming_ignores_repair_message_as_user_turn():
    from nora.agent import REPAIR_MESSAGE_NAME

    call = AIMessage(content="", tool_calls=[{"name": "read_document", "args": {}, "id": "r"}])
    tool = ToolMessage(content="x" * 10000, tool_call_id="r")
    repair_msg = HumanMessage(
        content="Revise your preceding answer. Preserve supported facts.",
        name=REPAIR_MESSAGE_NAME,
    )
    source = [
        HumanMessage(content="Old"),
        AIMessage(content="Old answer"),
        HumanMessage(content="New"),
        call,
        tool,
        AIMessage(content="Draft"),
        repair_msg,
    ]
    trimmed = bounded_messages(source, 1, 1000)
    assert len(trimmed) == 5
    assert [m.name for m in trimmed] == [None, None, None, None, REPAIR_MESSAGE_NAME]
    assert trimmed[1].tool_calls[0]["id"] == trimmed[2].tool_call_id
    assert len(tool.content) == 10000 and len(trimmed[2].content) < 1000


def test_repair_over_limit_synthetic_instruction_raises_and_preserves_originals():
    from nora.agent import REPAIR_MESSAGE_NAME

    call = AIMessage(content="", tool_calls=[{"name": "read_document", "args": {}, "id": "r"}])
    tool = ToolMessage(content="x" * 1000, tool_call_id="r")
    repair_msg = HumanMessage(content="y" * 1200, name=REPAIR_MESSAGE_NAME)
    source = [
        HumanMessage(content="Old"),
        AIMessage(content="Old answer"),
        HumanMessage(content="New current question"),
        call,
        tool,
        AIMessage(content="Draft"),
        repair_msg,
    ]
    original = [m.model_copy(deep=True) for m in source]
    with pytest.raises(ValueError, match="model context limit"):
        bounded_messages(source, 1, 1000)
    assert source == original


def test_repair_character_pressure_drops_old_turn_retains_current_user_and_tool():
    from nora.agent import REPAIR_MESSAGE_NAME

    call = AIMessage(content="", tool_calls=[{"name": "read_document", "args": {}, "id": "r"}])
    tool = ToolMessage(content="x" * 1000, tool_call_id="r")
    repair_msg = HumanMessage(content="y" * 300, name=REPAIR_MESSAGE_NAME)
    source = [
        HumanMessage(content="Old"),
        AIMessage(content="Old answer" * 100),
        HumanMessage(content="New current question"),
        call,
        tool,
        AIMessage(content="Draft"),
        repair_msg,
    ]
    original = [m.model_copy(deep=True) for m in source]
    trimmed = bounded_messages(source, 2, 1000)
    assert len(trimmed) == 5
    assert trimmed[0].content == "New current question"
    assert trimmed[1].tool_calls[0]["id"] == trimmed[2].tool_call_id
    assert trimmed[-1].name == REPAIR_MESSAGE_NAME
    assert sum(len(str(m.content)) for m in trimmed) <= 1000

    assert trimmed[-2].content == "Draft"
    assert source == original


def test_repair_request_persistence_and_checkpoint_isolation(tmp_path):
    import asyncio

    from nora.agent import REPAIR_MESSAGE_NAME

    settings, state, model, _ = length_runtime(
        tmp_path,
        [
            AIMessage(content="too long " * 5),
            AIMessage(content="Fixed."),
            AIMessage(content="Next"),
        ],
    )
    thread = str(uuid.uuid4())
    with TestClient(create_app(settings, state, token="test")) as client:
        auth = {"Authorization": "Bearer test"}
        response = client.post(
            "/ask", json={"question": "At most 2 words", "thread_id": thread}, headers=auth
        )
        assert response.status_code == 200, response.text
        assert response.json()["answer"] == "Fixed."
        history = client.get("/history/" + thread, headers=auth).json()["messages"]
        assert [m["content"] for m in history] == ["At most 2 words", "Fixed."]
        assert all("nora_answer_repair" not in str(m) for m in history)
        repair_request_msgs = model.observed[-1]
        assert repair_request_msgs[-1].name == REPAIR_MESSAGE_NAME
        assert isinstance(repair_request_msgs[-2], AIMessage)
        assert isinstance(repair_request_msgs[0], SystemMessage)
        assert any(isinstance(m, ToolMessage) for m in repair_request_msgs)

        checkpoint = asyncio.run(
            state.graph.aget_state({"configurable": {"thread_id": "assistant:" + thread}})
        )
        checkpoint_msgs = checkpoint.values.get("messages", [])
        assert sum(1 for m in checkpoint_msgs if isinstance(m, HumanMessage)) == 1
        assert all(m.name != REPAIR_MESSAGE_NAME for m in checkpoint_msgs)

        response = client.post(
            "/ask", json={"question": "Next question", "thread_id": thread}, headers=auth
        )
        assert response.status_code == 200, response.text
        assert response.json()["answer"] == "Next"
    assert all(m.name != REPAIR_MESSAGE_NAME for msgs in model.observed[-1:] for m in msgs)


def test_chatollama_serializes_repair_request_as_user_role_no_network(tmp_path):
    try:
        from langchain_ollama import ChatOllama
    except ImportError:
        pytest.skip("langchain_ollama not installed")

    settings, state, model, _ = length_runtime(
        tmp_path,
        [
            AIMessage(content="too long " * 5),
            AIMessage(content="Fixed."),
            AIMessage(content="Next"),
        ],
    )
    thread = str(uuid.uuid4())
    with TestClient(create_app(settings, state, token="test")) as client:
        auth = {"Authorization": "Bearer test"}
        response = client.post(
            "/ask", json={"question": "At most 2 words", "thread_id": thread}, headers=auth
        )
        assert response.status_code == 200, response.text
        repair_request_msgs = model.observed[-1]

    ollama = ChatOllama(model="gpt-oss:20b", base_url="http://127.0.0.1:1")
    serialized = ollama._convert_messages_to_ollama_messages(repair_request_msgs)
    assert serialized[-1]["role"] == "user"
    assert serialized[-2]["role"] == "assistant"
    assert serialized[0]["role"] == "system"
    assert serialized[0]["content"] == str(model.observed[0][0].content)
    assert "Revise your preceding answer" not in serialized[0]["content"]
    assert any(msg["role"] == "tool" for msg in serialized)


UNTITLED_WORKFLOW = (
    "## Selected target workflow\n"
    "Selected original versions are read only. Deterministic preparation produces "
    "full prepared documents and source metadata; chunk records have stable identities, "
    "hashes and offsets. Vectors are associated with chunk IDs and pinned model revision "
    "and encoding configuration."
)


class PreparationGuideKnowledge(CountingKnowledge):
    def __init__(self, rows, read_result=None, *, read_failure=False):
        super().__init__()
        self.rows = rows
        self.read_result = (
            {"doc_id": "a" * 64, "text": "# Manual ingestion\n" + PREPARATION_ANSWER}
            if read_result is None
            else read_result
        )
        self.read_failure = read_failure

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "search":
            return {"results": self.rows}
        if self.read_failure:
            raise RuntimeError("Synthetic read outage")
        return self.read_result


def guide_runtime(tmp_path, knowledge, replies, *, call_limit=3):
    settings = replace(Settings(), state_dir=tmp_path, knowledge_call_limit=call_limit)
    model = LengthModel(replies=replies)
    graph = create_graph(model, knowledge, InMemorySaver(), settings)
    return settings, Runtime(graph, knowledge, "synthetic", InMemoryOwnershipStore()), model


@pytest.mark.parametrize(
    "heading, text",
    [
        ("## Processing contract", UNTITLED_PROCESSING_CONTRACT),
        ("## Selected target workflow", UNTITLED_WORKFLOW),
    ],
)
def test_preparation_guide_is_read_before_first_model_call(tmp_path, heading, text):
    from nora.agent import PREPARATION_QUERY

    knowledge = PreparationGuideKnowledge([{"doc_id": "a" * 64, "heading": heading, "text": text}])
    settings, state, model = guide_runtime(
        tmp_path, knowledge, [AIMessage(content=PREPARATION_ANSWER)]
    )
    with TestClient(create_app(settings, state, token="test")) as client:
        response = client.post(
            "/ask",
            headers={"Authorization": "Bearer test"},
            json={"question": PREPARATION_QUESTION},
        )
    assert response.status_code == 200, response.text
    assert knowledge.calls == [
        ("search", {"query": PREPARATION_QUERY}),
        ("read", {"doc_id": "a" * 64, "offset": 0}),
    ]
    assert len(model.observed) == 1
    tool_messages = [m for m in model.observed[0] if isinstance(m, ToolMessage)]
    assert [m.name for m in tool_messages] == ["search_knowledge", "read_document"]
    assert "# Manual ingestion" in tool_messages[-1].content
    assert response.json()["knowledge_calls"] == 2


@pytest.mark.parametrize(
    "row",
    [
        {
            "title": "Architecture decisions",
            "heading": "## Processing contract",
            "text": UNTITLED_PROCESSING_CONTRACT,
        },
        {"heading": "## 3. Manual ingestion outside conversations", "text": PREPARATION_ANSWER},
        {"heading": "## Processing contract", "text": "Chunk memory preserves original headings."},
        {
            "heading": "## Selected target workflow",
            "text": "Deterministic preparation preserves original files.",
        },
        {"heading": "## Interview workflow", "text": UNTITLED_WORKFLOW},
        {"title": "Manual ingestion", "doc_id": "invalid"},
        {"title": "Manual ingestion", "doc_id": None},
        {"title": "Manual ingestion", "doc_id": 42},
    ],
)
def test_preparation_candidate_rejects_unrelated_and_malformed_results(row):
    from nora.agent import preparation_document

    assert preparation_document({"results": [{"doc_id": "a" * 64, **row}]}) is None


@pytest.mark.parametrize(
    "payload", [None, [], {"results": None}, {"results": [None]}, {"error": "unavailable"}]
)
def test_preparation_candidate_handles_missing_search_results(payload):
    from nora.agent import preparation_document

    assert preparation_document(payload) is None


def test_preparation_candidate_prioritizes_owner_then_contract_then_workflow():
    from nora.agent import preparation_document

    workflow = {
        "doc_id": "a" * 64,
        "heading": "## Selected target workflow",
        "text": UNTITLED_WORKFLOW,
    }
    contract = {
        "doc_id": "b" * 64,
        "heading": "## Processing contract",
        "text": UNTITLED_PROCESSING_CONTRACT,
    }
    owner = {"doc_id": "c" * 64, "title": "Manual ingestion"}
    assert preparation_document({"results": [workflow, contract, owner]}) == "c" * 64
    assert preparation_document({"results": [workflow, contract]}) == "b" * 64
    assert preparation_document({"results": [workflow]}) == "a" * 64
    assert preparation_document({"results": [owner, {**owner, "doc_id": "d" * 64}]}) == "c" * 64


def test_automatic_read_budget_blocks_parallel_excess_and_resets_on_followup(tmp_path):
    from nora.agent import PREPARATION_QUERY

    knowledge = PreparationGuideKnowledge([{"doc_id": "a" * 64, "title": "Manual ingestion"}])
    batch = AIMessage(
        content="",
        tool_calls=[
            {"name": "search_knowledge", "args": {"query": f"extra {i}"}, "id": f"extra-{i}"}
            for i in range(2)
        ],
    )
    settings, state, model = guide_runtime(
        tmp_path,
        knowledge,
        [
            batch,
            AIMessage(content=PREPARATION_ANSWER),
            batch.model_copy(deep=True),
            AIMessage(content=PREPARATION_ANSWER),
        ],
    )
    thread = str(uuid.uuid4())
    with TestClient(create_app(settings, state, token="test")) as client:
        for question in (
            PREPARATION_QUESTION,
            "For that preparation, what else survives? Restate all preserved information "
            "in at most 100 words, and name the saved source and headings.",
        ):
            start = len(knowledge.calls)
            response = client.post(
                "/ask",
                headers={"Authorization": "Bearer test"},
                json={"question": question, "thread_id": thread},
            )
            assert response.status_code == 200, response.text
            assert knowledge.calls[start:] == [
                ("search", {"query": PREPARATION_QUERY}),
                ("read", {"doc_id": "a" * 64, "offset": 0}),
                ("search", {"query": "extra 0"}),
            ]
    assert len(model.observed) == 4
    for messages in (model.observed[1], model.observed[3]):
        last_human = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
        blocked = [
            m for m in messages[last_human:] if isinstance(m, ToolMessage) and m.status == "error"
        ]
        assert [m.tool_call_id for m in blocked] == ["extra-1"]


def test_no_automatic_candidate_leaves_two_model_retrievals(tmp_path):
    knowledge = PreparationGuideKnowledge([])
    batch = AIMessage(
        content="",
        tool_calls=[
            {"name": "read_document", "args": {"doc_id": "a" * 64}, "id": f"read-{i}"}
            for i in range(3)
        ],
    )
    settings, state, model = guide_runtime(
        tmp_path, knowledge, [batch, AIMessage(content=PREPARATION_ANSWER)]
    )
    with TestClient(create_app(settings, state, token="test")) as client:
        response = client.post(
            "/ask",
            headers={"Authorization": "Bearer test"},
            json={"question": PREPARATION_QUESTION},
        )
    assert response.status_code == 200, response.text
    assert [name for name, _ in knowledge.calls] == ["search", "read", "read"]
    assert [
        m.tool_call_id
        for m in model.observed[-1]
        if isinstance(m, ToolMessage) and m.status == "error"
    ] == ["read-2"]


@pytest.mark.parametrize("call_limit", [1, 2])
def test_automatic_read_honors_smaller_configured_budget(tmp_path, call_limit):
    knowledge = PreparationGuideKnowledge(
        [{"doc_id": "a" * 64, "title": "Manual ingestion", "text": PREPARATION_ANSWER}]
    )
    request = AIMessage(
        content="",
        tool_calls=[{"name": "search_knowledge", "args": {"query": "extra"}, "id": "extra"}],
    )
    settings, state, model = guide_runtime(
        tmp_path, knowledge, [request, AIMessage(content=PREPARATION_ANSWER)], call_limit=call_limit
    )
    with TestClient(create_app(settings, state, token="test")) as client:
        response = client.post(
            "/ask",
            headers={"Authorization": "Bearer test"},
            json={"question": PREPARATION_QUESTION},
        )
    assert response.status_code == 200, response.text
    assert [name for name, _ in knowledge.calls] == (
        ["search"] if call_limit == 1 else ["search", "read"]
    )
    assert len(model.observed) == 2


@pytest.mark.parametrize(
    "read_result",
    [
        {"error": "document not found"},
        {"doc_id": "a" * 64, "text": "Original files are retained."},
        {"doc_id": "a" * 64, "text": "# Manual ingestion\nOriginal files are retained."},
    ],
)
def test_failed_or_partial_automatic_read_cannot_validate_invented_answer(tmp_path, read_result):
    knowledge = PreparationGuideKnowledge(
        [{"doc_id": "a" * 64, "heading": "## Selected target workflow", "text": UNTITLED_WORKFLOW}],
        read_result,
    )
    settings, state, model = guide_runtime(
        tmp_path, knowledge, [AIMessage(content=PREPARATION_ANSWER) for _ in range(2)]
    )
    with TestClient(create_app(settings, state, token="test")) as client:
        response = client.post(
            "/ask",
            headers={"Authorization": "Bearer test"},
            json={"question": PREPARATION_QUESTION},
        )
    assert response.status_code == 503
    assert [name for name, _ in knowledge.calls] == ["search", "read"]
    assert len(model.observed) == 2


def test_automatic_read_outage_preserves_existing_error_behavior(tmp_path):
    knowledge = PreparationGuideKnowledge(
        [{"doc_id": "a" * 64, "title": "Manual ingestion"}], read_failure=True
    )
    settings, state, model = guide_runtime(tmp_path, knowledge, [])
    with TestClient(create_app(settings, state, token="test")) as client:
        response = client.post(
            "/ask",
            headers={"Authorization": "Bearer test"},
            json={"question": PREPARATION_QUESTION},
        )
    assert response.status_code == 503
    assert [name for name, _ in knowledge.calls] == ["search", "read"]
    assert not model.observed


def test_preparation_followup_is_grounded_again_and_changed_topic_uses_original_query(tmp_path):
    from nora.agent import PREPARATION_QUERY

    knowledge = PreparationGuideKnowledge([{"doc_id": "a" * 64, "title": "Manual ingestion"}])
    settings, state, model = guide_runtime(
        tmp_path,
        knowledge,
        [
            AIMessage(content=PREPARATION_ANSWER),
            AIMessage(content=PREPARATION_ANSWER),
            AIMessage(content="Other topic"),
        ],
    )
    thread = str(uuid.uuid4())
    with TestClient(create_app(settings, state, token="test")) as client:
        for question in (
            PREPARATION_QUESTION,
            "For that preparation, what else survives?",
            "Explain Kafka partitions",
        ):
            response = client.post(
                "/ask",
                headers={"Authorization": "Bearer test"},
                json={"question": question, "thread_id": thread},
            )
            assert response.status_code == 200, response.text
    assert knowledge.calls == [
        ("search", {"query": PREPARATION_QUERY}),
        ("read", {"doc_id": "a" * 64, "offset": 0}),
        ("search", {"query": PREPARATION_QUERY}),
        ("read", {"doc_id": "a" * 64, "offset": 0}),
        ("search", {"query": "Explain Kafka partitions"}),
    ]
    assert len(model.observed) == 3


def test_automatic_grounding_sequential_exhaustion_and_repair_share_four_models(tmp_path):
    knowledge = PreparationGuideKnowledge([{"doc_id": "a" * 64, "title": "Manual ingestion"}])
    requests = [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "search_knowledge", "args": {"query": "extra"}, "id": f"extra-{i}"}
            ],
        )
        for i in range(2)
    ]
    settings, state, model = guide_runtime(
        tmp_path,
        knowledge,
        requests
        + [AIMessage(content="Preserves originals."), AIMessage(content=PREPARATION_ANSWER)],
    )
    with TestClient(create_app(settings, state, token="test")) as client:
        response = client.post(
            "/ask",
            headers={"Authorization": "Bearer test"},
            json={"question": PREPARATION_QUESTION},
        )
    assert response.status_code == 200, response.text
    assert response.json()["answer"] == PREPARATION_ANSWER
    assert [name for name, _ in knowledge.calls] == ["search", "read", "search"]
    assert len(model.observed) == 4
    assert [
        m.tool_call_id
        for m in model.observed[2]
        if isinstance(m, ToolMessage) and m.status == "error"
    ] == ["extra-1"]
    assert "Revise your preceding answer" in str(model.observed[-1][-1].content)
    assert model.observed[-1][-1].name == "nora_answer_repair"
    assert len(model.bound) == 3  # The fourth logical call is a tools-disabled repair.


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Preserves headings and substantive content.", True),
        ("Preserves headings and substantive text.", True),
        (
            "Extracted text with headings and substantive content "
            "(only empty, unreadable, duplicate, or boilerplate material is omitted).",
            True,
        ),
        ("Preserves headings and substantive content (only headings are omitted).", False),
        ("Preserves substantive content.", False),
        ("Preserves headings and boilerplate content.", False),
        ("Does not preserve headings and substantive content.", False),
        ("Headings remain. Substantive content is unavailable.", False),
    ],
)
def test_substantive_content_synonym_requires_preserved_headings(text, expected):
    from nora.agent import preparation_features

    assert ("headings and substantive text" in preparation_features(text)) is expected


def test_substantive_content_answer_passes_without_repair(tmp_path):
    answer = PREPARATION_ANSWER.replace(
        "headings and substantive text",
        "extracted text with headings and substantive content "
        "(only empty, unreadable, duplicate, or boilerplate material is omitted)",
    )
    settings, state, model, knowledge = preparation_runtime(tmp_path, [AIMessage(content=answer)])
    with TestClient(create_app(settings, state, token="test")) as client:
        response = client.post(
            "/ask",
            headers={"Authorization": "Bearer test"},
            json={"question": PREPARATION_QUESTION},
        )
    assert response.status_code == 200, response.text
    assert response.json()["answer"] == answer
    assert len(model.observed) == 1
    assert len(knowledge.calls) == 1


@pytest.mark.parametrize("complete_repair", [False, True])
def test_related_restatement_requires_current_turn_facts(tmp_path, complete_repair):
    from nora.agent import preparation_deficits

    # Saved-guide wording can include metadata and provenance without explicitly
    # preserving source identity or stating the deterministic/no-rewrite contract.
    incomplete = (
        "Original bytes unchanged; extracted text/assets and source metadata; "
        "headings and substantive text; normalized chunk records with stable identities, "
        "hashes and offsets; vectors tied to chunk IDs with pinned model revision and "
        "encoding configuration; provenance records. "
        "Source: Manual ingestion / Processing contract; Selected target workflow."
    )
    settings, state, model, knowledge = preparation_runtime(
        tmp_path,
        [
            AIMessage(content=PREPARATION_ANSWER),
            AIMessage(content=incomplete),
            AIMessage(content=PREPARATION_ANSWER if complete_repair else incomplete),
        ],
    )
    with TestClient(create_app(settings, state, token="test")) as client:
        headers = {"Authorization": "Bearer test"}
        first = client.post("/ask", headers=headers, json={"question": PREPARATION_QUESTION})
        assert first.status_code == 200
        thread = first.json()["thread_id"]
        followup = (
            "For that preparation, what else survives? Restate all preserved information "
            "in at most 100 words, and name the saved source and headings."
        )
        response = client.post(
            "/ask", headers=headers, json={"question": followup, "thread_id": thread}
        )
        assert response.status_code == (200 if complete_repair else 503), response.text
        if complete_repair:
            assert response.json()["answer"] == PREPARATION_ANSWER
            history = client.get("/history/" + thread, headers=headers).json()["messages"]
            assert history[-1]["content"] == PREPARATION_ANSWER
            assert all(m["content"] != incomplete for m in history)
    messages = [
        HumanMessage(content=PREPARATION_QUESTION),
        ToolMessage(
            name="read_document",
            tool_call_id="manual",
            content=json.dumps({"title": "Manual ingestion", "text": PREPARATION_ANSWER}),
        ),
        AIMessage(content=PREPARATION_ANSWER),
        HumanMessage(content=followup),
    ]
    deficits = preparation_deficits(messages, incomplete, True)
    assert deficits == [
        "Include supported fact: deterministic preparation without summaries or meaning rewrites",
        "Include supported fact: source identity and metadata",
    ]
    original_system = str(model.observed[-1][0].content)
    assert "repeat all six supported facts in the current answer" in original_system
    assert "Revise your preceding answer" not in original_system
    repair_msg = model.observed[-1][-1]
    assert repair_msg.name == "nora_answer_repair"
    repair_prompt = str(repair_msg.content)
    assert all(d in repair_prompt for d in deficits)
    assert len(model.observed) == 3  # One initial answer, one follow-up, one repair.
    assert len(knowledge.calls) == 2


CAPTURED_PREPARATION_INITIAL = (
    "Nora’s preparation is deterministic and non‑summarizing. It keeps the original file intact, "
    "extracts readable text, and preserves headings and substantive content. The output contains "
    "the full text, stable chunk identities, hashes, offsets, and the model configuration used for embedding. "
    "No summary or meaning‑rewrite is generated. Thus, the surviving information includes the original source, "
    "headings, substantive text, chunk records, hashes, offsets, and vector‑model metadata.  \n\n"
    "Source: *Manual ingestion* – “## Processing contract”."
)
CAPTURED_PREPARATION_REPAIR = (
    "Nora’s deterministic preparation keeps the original file unchanged, extracts readable text, "
    "and preserves headings and substantive content. The output bundle contains the full text, "
    "source identity and metadata, stable chunk identities, hashes, offsets, and the model configuration "
    "used for embedding. No summary or meaning rewrite is produced. Chunk offsets are defined by the "
    "Selected target workflow. The process omits duplicates, empty or unreadable parts, and boilerplate. "
    "All artifacts are stored for retrieval and rollback. Source: Manual ingestion – Processing contract; "
    "Selected target workflow."
)
CORRECTED_PREPARATION_REPAIR = CAPTURED_PREPARATION_REPAIR.replace(
    "model configuration used for embedding",
    "model configuration retained with vectors",
)


def test_preparation_field_retention_repair_replays_initial_and_failed_drafts(tmp_path):
    settings, state, model, knowledge = preparation_runtime(
        tmp_path,
        [
            AIMessage(content=CAPTURED_PREPARATION_INITIAL),
            AIMessage(content=CAPTURED_PREPARATION_REPAIR),
        ],
    )
    thread = str(uuid.uuid4())
    with TestClient(create_app(settings, state, token="test")) as client:
        headers = {"Authorization": "Bearer test"}
        response = client.post(
            "/ask", headers=headers, json={"question": PREPARATION_QUESTION, "thread_id": thread}
        )
    assert response.status_code == 503
    assert "answer" not in response.json()
    from nora.agent import preparation_deficits

    messages = [
        HumanMessage(content=PREPARATION_QUESTION),
        ToolMessage(
            name="read_document",
            tool_call_id="manual",
            content=json.dumps({"title": "Manual ingestion", "text": PREPARATION_ANSWER}),
        ),
    ]
    assert preparation_deficits(messages, CAPTURED_PREPARATION_REPAIR, True) == [
        "Include supported fact: model configuration with vectors"
    ]
    assert len(model.observed) == 2
    assert len(knowledge.calls) == 1
    repair_prompt = str(model.observed[-1][-1].content)
    assert model.observed[-1][-1].name == "nora_answer_repair"
    assert "Recheck and retain ALL supported requested preservation fields" in repair_prompt
    assert "model configuration retained with vectors" in repair_prompt


def test_preparation_field_retention_repair_succeeds_with_fixed_draft(tmp_path):
    settings, state, model, knowledge = preparation_runtime(
        tmp_path,
        [
            AIMessage(content=CAPTURED_PREPARATION_INITIAL),
            AIMessage(content=CORRECTED_PREPARATION_REPAIR),
        ],
    )
    thread = str(uuid.uuid4())
    with TestClient(create_app(settings, state, token="test")) as client:
        headers = {"Authorization": "Bearer test"}
        response = client.post(
            "/ask", headers=headers, json={"question": PREPARATION_QUESTION, "thread_id": thread}
        )
        assert response.status_code == 200, response.text
        assert response.json()["answer"] == CORRECTED_PREPARATION_REPAIR
        assert len(response.json()["answer"].split()) <= 100
        history = client.get("/history/" + thread, headers=headers).json()["messages"]
        assert [m["content"] for m in history] == [
            PREPARATION_QUESTION,
            CORRECTED_PREPARATION_REPAIR,
        ]
        assert all("nora_answer_repair" not in str(m) for m in history)
        repair_prompt = str(model.observed[-1][-1].content)
        assert "Recheck and retain ALL supported requested preservation fields" in repair_prompt
        assert "model configuration retained with vectors" in repair_prompt
    assert len(model.observed) == 2
    assert len(knowledge.calls) == 1


def test_unrelated_word_length_repair_does_not_get_preparation_checklist(tmp_path):
    settings, state, model, knowledge = length_runtime(
        tmp_path,
        [
            AIMessage(content="too many words here are repeated"),
            AIMessage(content="fixed now"),
        ],
    )
    thread = str(uuid.uuid4())
    with TestClient(create_app(settings, state, token="test")) as client:
        headers = {"Authorization": "Bearer test"}
        response = client.post(
            "/ask", headers=headers, json={"question": "At most 5 words", "thread_id": thread}
        )
        assert response.status_code == 200, response.text
        repair_prompt = str(model.observed[-1][-1].content)
        assert model.observed[-1][-1].name == "nora_answer_repair"
        assert "Recheck and retain ALL supported requested preservation fields" not in repair_prompt
        assert "Preserve supported facts" in repair_prompt
        assert "Answer exceeds the requested word limit" in repair_prompt
    assert len(model.observed) == 2
    assert len(knowledge.calls) == 1


CAPTURED_WHITESPACE_REPAIR = "Nora’s deterministic preparation keeps original files unchanged, preserves source identity and metadata, and retains headings and substantive text without summarizing or rewriting meaning. It extracts readable text, normalizes chunks deterministically, and records stable chunk identities, hashes, and offsets per the Selected\u202fTarget\u202fWorkflow. The process also stores model configuration and associated vectors for each chunk. Retrieval reads full text from the prepared‑full‑documents store, ensuring all original content and metadata survive the ingestion pipeline. Source: Manual ingestion – Processing contract."


def heading_guard_messages():
    return [
        HumanMessage(content=PREPARATION_QUESTION),
        ToolMessage(
            name="read_document",
            tool_call_id="manual",
            content=json.dumps({"title": "Manual ingestion", "text": PREPARATION_ANSWER}),
        ),
    ]


def test_captured_unicode_heading_repair_passes_guard():
    from nora.agent import preparation_deficits

    assert preparation_deficits(heading_guard_messages(), CAPTURED_WHITESPACE_REPAIR, True) == []
    assert len(CAPTURED_WHITESPACE_REPAIR.split()) == 79


@pytest.mark.parametrize("space", ["\u202f", "\u00a0", "  ", "\t"])
def test_attribution_headings_accept_equivalent_whitespace(space):
    from nora.agent import preparation_deficits

    answer = PREPARATION_ANSWER
    for heading in ["Manual ingestion", "Processing contract", "Selected target workflow"]:
        answer = answer.replace(heading, heading.replace(" ", space))
    assert preparation_deficits(heading_guard_messages(), answer, True) == []


@pytest.mark.parametrize("replacement", ["chosen pipeline", "Selected targets workflow"])
def test_missing_or_wrong_workflow_heading_still_rejected(replacement):
    from nora.agent import preparation_deficits

    answer = CAPTURED_WHITESPACE_REPAIR.replace("Selected\u202fTarget\u202fWorkflow", replacement)
    assert preparation_deficits(heading_guard_messages(), answer, True) == [
        "Name Selected target workflow for chunk offsets"
    ]
