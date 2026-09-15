import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from nora.config import Settings
from nora.routing import RoutingChatModel, build_model


class Model:
    def __init__(self, *, failure=None):
        self.calls = 0
        self.failure = failure
        self.tools = []

    def bind_tools(self, tools, **kwargs):
        self.tools = tools
        return self

    def invoke(self, messages, **kwargs):
        self.calls += 1
        if self.failure:
            raise RuntimeError("Synthetic provider failure")
        return AIMessage(
            content="done",
            tool_calls=[{"name": "search_knowledge", "args": {"query": "test"}, "id": "test"}],
        )

    async def ainvoke(self, messages, **kwargs):
        return self.invoke(messages, **kwargs)

    def stream(self, messages, **kwargs):
        self.calls += 1
        if self.failure == "before":
            raise RuntimeError("Synthetic provider failure")
        yield AIMessageChunk(content="first")
        if self.failure == "partial":
            raise RuntimeError("Synthetic provider failure")
        yield AIMessageChunk(content="second")

    async def astream(self, messages, **kwargs):
        for chunk in self.stream(messages, **kwargs):
            yield chunk


def test_tool_binding_and_tool_calls_survive_router():
    cheap, strong = Model(), Model()
    model = RoutingChatModel(cheap_model=cheap, strong_model=strong).bind_tools(
        ["search_knowledge"]
    )
    result = model.invoke([HumanMessage(content="Hello")])
    assert result.tool_calls[0]["name"] == "search_knowledge"
    assert cheap.tools == strong.tools == ["search_knowledge"]
    assert (cheap.calls, strong.calls) == (1, 0)


def test_telemetry_failure_never_calls_another_model(tmp_path):
    cheap, strong = Model(), Model()
    path = tmp_path / "not-a-directory"
    path.write_text("file")
    model = RoutingChatModel(cheap_model=cheap, strong_model=strong, log_path=path / "log.jsonl")
    assert model.invoke("Hello").content == "done"
    assert (cheap.calls, strong.calls) == (1, 0)


async def test_async_fallback_is_once_and_log_contains_no_question(tmp_path):
    cheap, strong = Model(failure="before"), Model()
    path = tmp_path / "routing.jsonl"
    model = RoutingChatModel(cheap_model=cheap, strong_model=strong, log_path=path)
    assert (await model.ainvoke("Private question")).content == "done"
    assert (cheap.calls, strong.calls) == (1, 1)
    assert "Private question" not in path.read_text()


@pytest.mark.parametrize("asynchronous", [False, True])
async def test_partial_stream_failure_does_not_fallback(asynchronous):
    cheap, strong = Model(failure="partial"), Model()
    model = RoutingChatModel(cheap_model=cheap, strong_model=strong)
    chunks = []
    with pytest.raises(RuntimeError):
        if asynchronous:
            async for chunk in model.astream("Hello"):
                chunks.append(chunk.content)
        else:
            for chunk in model.stream("Hello"):
                chunks.append(chunk.content)
    assert chunks == ["first"] and strong.calls == 0


async def test_stream_failure_before_output_can_fallback():
    cheap, strong = Model(failure="before"), Model()
    model = RoutingChatModel(cheap_model=cheap, strong_model=strong)
    chunks = [chunk.content async for chunk in model.astream("Hello")]
    assert "".join(chunks) == "firstsecond"
    assert (cheap.calls, strong.calls) == (1, 1)


def test_provider_credential_is_not_forwarded_to_another_host(monkeypatch):
    monkeypatch.setenv("NORA_OLLAMA_TOKEN", "synthetic-primary-token")
    monkeypatch.setenv("NORA_ROUTER_ENABLED", "true")
    monkeypatch.setenv("NORA_ROUTER_CHEAP_MODEL", "test-model")
    monkeypatch.setenv("NORA_ROUTER_CHEAP_URL", "http://localhost:11434")
    model = build_model(Settings())
    assert (
        model.strong_model.client_kwargs["headers"]["Authorization"]
        == "Bearer synthetic-primary-token"
    )
    assert "headers" not in model.cheap_model.client_kwargs
