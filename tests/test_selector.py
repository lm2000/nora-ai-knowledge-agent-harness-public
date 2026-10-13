"""Quality-first model selector contract tests."""

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from nora.providers import ProviderSpec, ProviderUnavailable
from nora.selector import build_selector


class FakeModel(BaseChatModel):
    name: str = ""
    failure: str | None = None
    calls: int = 0

    @property
    def _llm_type(self):
        return f"fake-{self.name}"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        if self.failure == "before":
            raise RuntimeError("Synthetic failure")
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=f"from-{self.name}"))]
        )

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        if self.failure == "before":
            raise RuntimeError("Synthetic failure")
        yield ChatGenerationChunk(message=AIMessageChunk(content=f"from-{self.name}-1"))
        if self.failure == "partial":
            raise RuntimeError("Synthetic partial failure")
        yield ChatGenerationChunk(message=AIMessageChunk(content=f"from-{self.name}-2"))

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        for chunk in self._stream(messages, stop=stop, run_manager=run_manager, **kwargs):
            yield chunk


def _make_selector(monkeypatch, *, cheap_failure=None, strong_failure=None, log=None):
    # Unknown/synthetic providers require a configured credential to be routable.
    monkeypatch.setenv("NORA_FAKE_TOKEN", "fake-token-for-tests")
    cheap = FakeModel(name="cheap")
    cheap.failure = cheap_failure
    strong = FakeModel(name="strong")
    strong.failure = strong_failure
    specs = [
        ProviderSpec(
            provider="fake",
            model="cheap",
            base_url="http://fake",
            token_name="FAKE_TOKEN",
            quality_tier=2,
            relative_cost=0.5,
            relative_latency=0.5,
            capability_tags=("knowledge",),
        ),
        ProviderSpec(
            provider="fake",
            model="strong",
            base_url="http://fake",
            token_name="FAKE_TOKEN",
            quality_tier=5,
            relative_cost=2.0,
            relative_latency=2.0,
            capability_tags=("knowledge", "reasoning"),
        ),
    ]
    selector = build_selector(specs, timeout=60, cost_weight=1.0, latency_weight=1.0, log_path=log)
    # Patch build_model so we don't need real provider adapters.
    import nora.selector

    original = nora.selector.build_model
    nora.selector.build_model = lambda spec, timeout: cheap if spec.model == "cheap" else strong
    return selector, cheap, strong, original


def _restore(original):
    import nora.selector

    nora.selector.build_model = original


def test_simple_prompt_prefers_cheap_model(monkeypatch, tmp_path):
    selector, cheap, strong, orig = _make_selector(monkeypatch)
    try:
        result = selector.invoke([HumanMessage(content="Hello")])
        assert result.content == "from-cheap"
        assert cheap.calls == 1
        assert strong.calls == 0
    finally:
        _restore(orig)


def test_reasoning_prompt_prefers_strong_model(monkeypatch, tmp_path):
    selector, cheap, strong, orig = _make_selector(monkeypatch)
    try:
        result = selector.invoke([HumanMessage(content="Explain the architecture tradeoffs")])
        assert result.content == "from-strong"
        assert cheap.calls == 0
        assert strong.calls == 1
    finally:
        _restore(orig)


def test_fallback_before_output_uses_strong_model(monkeypatch, tmp_path):
    selector, cheap, strong, orig = _make_selector(monkeypatch, cheap_failure="before")
    try:
        result = selector.invoke([HumanMessage(content="Hello")])
        assert result.content == "from-strong"
        assert cheap.calls == 1
        assert strong.calls == 1
    finally:
        _restore(orig)


def test_partial_stream_failure_does_not_fallback(monkeypatch, tmp_path):
    selector, cheap, strong, orig = _make_selector(monkeypatch, cheap_failure="partial")
    try:
        chunks = []
        with pytest.raises(RuntimeError):
            for chunk in selector.stream([HumanMessage(content="Hello")]):
                chunks.append(chunk.content)
        assert chunks == ["from-cheap-1"]
        assert strong.calls == 0
    finally:
        _restore(orig)


def test_log_contains_no_prompt_and_no_secrets(monkeypatch, tmp_path):
    log = tmp_path / "selector.jsonl"
    selector, cheap, strong, orig = _make_selector(monkeypatch, log=str(log))
    try:
        selector.invoke([HumanMessage(content="Private question")])
        text = log.read_text()
        assert "Private question" not in text
        assert "from-cheap" not in text
        assert "query_sha256" in text
    finally:
        _restore(orig)


def test_selector_requires_at_least_one_spec():
    with pytest.raises(Exception):
        build_selector([], timeout=60)


def test_tool_binding_propagates_to_selected_model(monkeypatch, tmp_path):
    """When the selector is bound to tools, the selected model receives them."""
    from langchain_core.tools import tool

    from nora.selector import build_selector

    monkeypatch.setenv("NORA_FAKE_TOKEN", "fake-token-for-tests")
    recorded = []

    class RecordingModel(BaseChatModel):
        name: str = "recording"

        @property
        def _llm_type(self):
            return "recording"

        def bind_tools(self, tools, *, tool_choice=None, **kwargs):
            recorded.append([t.name for t in tools])
            return self

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok"))])

        async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
            return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    spec = ProviderSpec(
        provider="fake",
        model="recording",
        base_url="http://fake",
        token_name="FAKE_TOKEN",
        quality_tier=3,
        capability_tags=("knowledge",),
    )
    selector = build_selector([spec], timeout=60)

    import nora.selector

    original = nora.selector.build_model
    nora.selector.build_model = lambda spec, timeout: RecordingModel()
    try:

        @tool
        def example_tool(x: str) -> str:
            """Example."""
            return x

        bound = selector.bind_tools([example_tool])
        bound.invoke([HumanMessage(content="Hello")])
        assert recorded == [["example_tool"]], recorded
    finally:
        nora.selector.build_model = original


def test_cost_and_latency_weights_affect_selection(tmp_path):
    """With two adequate models, shifting weights changes the selected model."""
    from nora.selector import _score

    fast_costly = ProviderSpec(
        provider="fake",
        model="fast-costly",
        base_url="http://fake",
        token_name="FAKE_TOKEN",
        quality_tier=3,
        relative_cost=2.0,
        relative_latency=0.5,
        capability_tags=("knowledge",),
    )
    slow_cheap = ProviderSpec(
        provider="fake",
        model="slow-cheap",
        base_url="http://fake",
        token_name="FAKE_TOKEN",
        quality_tier=3,
        relative_cost=0.5,
        relative_latency=2.0,
        capability_tags=("knowledge",),
    )
    # Cost weight high = prefer slow_cheap.
    assert _score(fast_costly, 2, {"knowledge"}, 10.0, 1.0) > _score(
        slow_cheap, 2, {"knowledge"}, 10.0, 1.0
    )
    # Latency weight high = prefer fast_costly.
    assert _score(fast_costly, 2, {"knowledge"}, 1.0, 10.0) < _score(
        slow_cheap, 2, {"knowledge"}, 1.0, 10.0
    )


def test_missing_provider_credential_falls_back_to_viable_model(tmp_path, monkeypatch, caplog):
    """Empty Fireworks credential file: the strong-tier Fireworks candidate is
    filtered out of routing and the viable Ollama candidate answers, with a
    logged fallback note. Regression test for the 2026-09-15 clean-install
    acceptance defect (503 on /ask with an empty .runtime/secrets/fireworks)."""
    import nora.selector

    empty_token = tmp_path / "fireworks"
    empty_token.write_text("")
    monkeypatch.setenv("NORA_FIREWORKS_TOKEN_FILE", str(empty_token))
    monkeypatch.delenv("NORA_FIREWORKS_TOKEN", raising=False)
    monkeypatch.delenv("NORA_OLLAMA_TOKEN", raising=False)
    monkeypatch.delenv("NORA_OLLAMA_TOKEN_FILE", raising=False)

    ollama_spec = ProviderSpec(
        provider="ollama",
        model="gpt-oss:20b",
        base_url="http://localhost:11434",
        token_name="OLLAMA_TOKEN",
        quality_tier=4,
        capability_tags=("knowledge",),
    )
    fireworks_spec = ProviderSpec(
        provider="fireworks",
        model="accounts/fireworks/models/kimi-k3",
        base_url="https://api.fireworks.ai/inference/v1",
        token_name="FIREWORKS_TOKEN",
        quality_tier=5,
        capability_tags=("knowledge", "reasoning"),
    )
    ollama = FakeModel(name="ollama")
    fireworks = FakeModel(name="fireworks")
    original = nora.selector.build_model
    nora.selector.build_model = lambda spec, timeout: (
        ollama if spec.provider == "ollama" else fireworks
    )
    selector = build_selector([ollama_spec, fireworks_spec], timeout=60)
    try:
        # Reasoning hint requires tier 3 and the 'reasoning' tag, which only the
        # Fireworks candidate has -- but its credential is empty, so routing
        # must skip it instead of failing the request.
        with caplog.at_level("INFO", logger="nora.selector"):
            result = selector.invoke([HumanMessage(content="Explain the architecture here")])
        assert result.content == "from-ollama"
        assert ollama.calls == 1
        assert fireworks.calls == 0
        skip_lines = [r.message for r in caplog.records if "Skipping fireworks/" in str(r.message)]
        assert skip_lines, caplog.text
        assert "FIREWORKS_TOKEN" in skip_lines[0]
    finally:
        nora.selector.build_model = original


def test_selector_ignores_repair_message_for_routing(monkeypatch, tmp_path):
    selector, cheap, strong, orig = _make_selector(monkeypatch)
    try:
        # Case 1: Hello + repair architecture/reasoning text (cheap route)
        repair_msg1 = HumanMessage(
            content="Revise architecture tradeoffs", name="nora_answer_repair"
        )
        result1 = selector.invoke(
            [HumanMessage(content="Hello"), AIMessage(content="Draft"), repair_msg1]
        )
        assert result1.content == "from-cheap"
        assert cheap.calls == 1 and strong.calls == 0

        # Case 2: architecture tradeoffs + repair Hello (strong route)
        cheap.calls = 0
        repair_msg2 = HumanMessage(content="Hello", name="nora_answer_repair")
        result2 = selector.invoke(
            [
                HumanMessage(content="Explain the architecture tradeoffs"),
                AIMessage(content="Draft"),
                repair_msg2,
            ]
        )
        assert result2.content == "from-strong"
        assert cheap.calls == 0 and strong.calls == 1
    finally:
        _restore(orig)


def test_all_candidates_missing_credentials_fails_clearly(tmp_path, monkeypatch):
    """When every candidate's provider credential is missing, the request fails
    before routing with a clear ProviderUnavailable instead of a build error."""

    monkeypatch.setenv("NORA_FIREWORKS_TOKEN", "")
    monkeypatch.delenv("NORA_FIREWORKS_TOKEN_FILE", raising=False)

    spec = ProviderSpec(
        provider="fireworks",
        model="accounts/fireworks/models/kimi-k3",
        base_url="https://api.fireworks.ai/inference/v1",
        token_name="FIREWORKS_TOKEN",
        quality_tier=5,
        capability_tags=("knowledge", "reasoning"),
    )
    selector = build_selector([spec], timeout=60)
    with pytest.raises(ProviderUnavailable):
        selector.invoke([HumanMessage(content="Hello")])
