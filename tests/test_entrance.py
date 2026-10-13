"""Embedded MCP and HTTP share one graph and conversation namespace."""

import asyncio
import json
import uuid
from dataclasses import replace

from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from nora.agent import create_graph
from nora.assistant import load_assistant_config
from nora.config import Settings
from nora.coordination import Runtime, create_app
from nora.ownership import InMemoryOwnershipStore
from tests.test_services import Knowledge, Model


def build_runtime(settings, saver):
    model, knowledge = Model(), Knowledge()
    graph = create_graph(
        model,
        knowledge,
        saver,
        settings,
        assistant_config=load_assistant_config(settings),
    )
    return Runtime(graph, knowledge, "synthetic", InMemoryOwnershipStore())


def test_embedded_mcp_http_continuity_errors_and_lifecycle(tmp_path):
    settings = replace(Settings(), state_dir=tmp_path)
    saver = InMemorySaver()
    runtime = build_runtime(settings, saver)
    headers = {"Authorization": "Bearer test", "Accept": "application/json, text/event-stream"}
    with TestClient(
        create_app(settings, runtime, token="test"), base_url="http://localhost"
    ) as client:

        def rpc(method, params):
            response = client.post(
                "/mcp/",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": method,
                    "params": params,
                },
            )
            assert response.status_code == 200, response.text
            return response.json()["result"]

        assert client.post("/mcp/", json={}).status_code == 401
        initialized = rpc(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        )
        headers["MCP-Protocol-Version"] = initialized["protocolVersion"]
        tools = rpc("tools/list", {})["tools"]
        assert [t["name"] for t in tools] == ["ask_nis"]
        assert set(tools[0]["inputSchema"]["properties"]) == {"question", "thread_id"}
        first = rpc("tools/call", {"name": "ask_nis", "arguments": {"question": "Question"}})
        assert not first.get("isError"), first
        answer = first["structuredContent"]
        assert answer["answer"] == "Grounded turn 1"
        thread = str(uuid.UUID(answer["thread_id"]))
        followup = client.post(
            "/ask", headers=headers, json={"question": "Follow-up", "thread_id": thread}
        )
        assert followup.json()["answer"] == "Grounded turn 2"
        separate = rpc("tools/call", {"name": "ask_nis", "arguments": {"question": "Separate"}})
        assert separate["structuredContent"]["thread_id"] != thread
        assert separate["structuredContent"]["answer"] == "Grounded turn 1"
        empty = rpc("tools/call", {"name": "ask_nis", "arguments": {"question": " "}})
        assert empty["isError"] and "422" in json.dumps(empty)
        invalid = rpc(
            "tools/call", {"name": "ask_nis", "arguments": {"question": "Q", "thread_id": "bad"}}
        )
        assert invalid["isError"]
        # The shared semaphore is released after a failed graph invocation.
        runtime.knowledge.failure = True
        failed = rpc("tools/call", {"name": "ask_nis", "arguments": {"question": "Q"}})
        assert failed["isError"] and "503" in json.dumps(failed)
        assert "Synthetic retrieval outage" not in json.dumps(failed)
        runtime.knowledge.failure = False
        assert not rpc("tools/call", {"name": "ask_nis", "arguments": {"question": "Retry"}}).get(
            "isError"
        )
    # Re-entering a new application lifecycle reuses persisted checkpoint state.
    with TestClient(create_app(settings, build_runtime(settings, saver), token="test")) as client:
        result = client.post(
            "/ask", headers=headers, json={"question": "After restart", "thread_id": thread}
        )
        assert result.json()["answer"] == "Grounded turn 3"


def test_assistant_does_not_resume_legacy_checkpoint(tmp_path):
    settings = replace(Settings(), state_dir=tmp_path)
    saver = InMemorySaver()
    runtime = build_runtime(settings, saver)
    thread = str(uuid.uuid4())
    asyncio.run(
        runtime.graph.ainvoke(
            {"messages": [HumanMessage(content="Old topic")]},
            {"configurable": {"thread_id": thread}},
        )
    )
    with TestClient(create_app(settings, runtime, token="test")) as client:
        response = client.post(
            "/ask",
            headers={"Authorization": "Bearer test"},
            json={"question": "New", "thread_id": thread},
        )
        assert response.json()["answer"] == "Grounded turn 1"
        history = client.get("/history/" + thread, headers={"Authorization": "Bearer test"}).json()
        assert all(m["content"] != "Old topic" for m in history["messages"])


def test_browser_stream_and_http_share_assistant_checkpoint(tmp_path):
    settings = replace(Settings(), state_dir=tmp_path)
    runtime = build_runtime(settings, InMemorySaver())
    thread = str(uuid.uuid4())
    headers = {"Authorization": "Bearer test"}
    with TestClient(create_app(settings, runtime, token="test")) as client:
        response = client.post(
            "/agent",
            headers=headers,
            json={
                "threadId": thread,
                "runId": str(uuid.uuid4()),
                "state": {},
                "messages": [{"id": "q", "role": "user", "content": "Question"}],
                "tools": [],
                "context": [],
                "forwardedProps": {},
            },
        )
        assert response.status_code == 200
        events = [
            json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
        ]
        assert events[-1]["type"] == "RUN_FINISHED"
        assert events[-1]["threadId"] == thread
        answer = client.post(
            "/ask", headers=headers, json={"question": "Follow-up", "thread_id": thread}
        )
        assert answer.json()["answer"] == "Grounded turn 2"
