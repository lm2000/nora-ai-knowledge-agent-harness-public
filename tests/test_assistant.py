"""Single assistant ownership, interfaces and checkpoint isolation."""

import uuid
from dataclasses import replace

from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage

from nora.assistant import assistant_thread_id, load_assistant_config
from nora.config import Settings
from nora.coordination import create_app
from tests.test_services import runtime


def test_namespace_and_inventory():
    thread = str(uuid.uuid4())
    assert assistant_thread_id(thread) == f"assistant:{thread}"
    config = load_assistant_config(Settings())
    assert config.call_limit == 3
    assert [m.provider for m in config.models] == ["ollama", "fireworks"]
    assert "Processing contract" in config.system_prompt


def test_removed_interfaces_and_role_fields(tmp_path):
    settings = replace(Settings(), state_dir=tmp_path)
    state, _ = runtime(settings)
    with TestClient(create_app(settings, state, token="test")) as client:
        auth = {"Authorization": "Bearer test"}
        thread = str(uuid.uuid4())
        assert (
            client.post(
                "/ask", json={"question": "Q", "role": "assistant"}, headers=auth
            ).status_code
            == 422
        )
        assert client.post("/transfer", json={}, headers=auth).status_code == 404
        assert client.get(f"/history/assistant/{thread}", headers=auth).status_code == 404
        payload = {
            "threadId": thread,
            "runId": str(uuid.uuid4()),
            "state": {},
            "messages": [{"id": "q", "role": "user", "content": "Q"}],
            "tools": [],
            "context": [],
            "forwardedProps": {},
        }
        assert (
            client.post(
                "/agent", json=payload, headers={**auth, "X-Nora-Role": "assistant"}
            ).status_code
            == 422
        )


def test_historical_owner_denied_without_exposing_owner(tmp_path):
    settings = replace(Settings(), state_dir=tmp_path)
    state, _ = runtime(settings)
    thread = str(uuid.uuid4())
    state.ownership._claims[thread] = "research"
    with TestClient(create_app(settings, state, token="test")) as client:
        auth = {"Authorization": "Bearer test"}
        for response in [
            client.post("/ask", json={"question": "Q", "thread_id": thread}, headers=auth),
            client.get(f"/history/{thread}", headers=auth),
        ]:
            assert response.status_code == 403
            assert "research" not in response.text


async def test_raw_legacy_checkpoints_are_not_resumed(tmp_path):
    settings = replace(Settings(), state_dir=tmp_path)
    state, _ = runtime(settings)
    thread = str(uuid.uuid4())
    await state.graph.aupdate_state(
        {"configurable": {"thread_id": thread}},
        {"messages": [HumanMessage(content="Legacy secret")]},
    )
    with TestClient(create_app(settings, state, token="test")) as client:
        auth = {"Authorization": "Bearer test"}
        assert client.get(f"/history/{thread}", headers=auth).json()["messages"] == []
        answer = client.post(
            "/ask", json={"question": "Fresh question", "thread_id": thread}, headers=auth
        )
        assert answer.status_code == 200
        assert answer.json()["answer"] == "Grounded turn 1"


def test_inventory_override_keeps_supported_provider_settings(monkeypatch):
    monkeypatch.setenv(
        "NORA_ASSISTANT_MODELS",
        '[{"provider":"ollama","model":"custom","base_url":"https://ollama.com","quality_tier":4,"relative_cost":0.7,"capability_tags":["knowledge"]}]',
    )
    config = load_assistant_config(Settings())
    assert len(config.models) == 1
    assert config.models[0].model == "custom"
    assert config.models[0].token_name == "OLLAMA_TOKEN"
    assert config.models[0].relative_cost == 0.7
