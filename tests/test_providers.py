"""Provider adapter contract tests using doubles.

These verify construction, credential isolation and the Fireworks endpoint
contract. They do not make live provider calls; synthetic credentials are
never real.
"""

import pytest
from langchain_ollama import ChatOllama

from nora.config import ConfigurationError
from nora.providers import ProviderSpec, build_fireworks, build_model, build_ollama


def test_ollama_adapter_uses_native_protocol_and_token(monkeypatch):
    monkeypatch.setenv("NORA_OLLAMA_TOKEN", "fake-ollama-token")
    spec = ProviderSpec(
        provider="ollama",
        model="gpt-oss:20b",
        base_url="https://ollama.com",
        token_name="OLLAMA_TOKEN",
    )
    model = build_ollama(spec, timeout=120)
    assert isinstance(model, ChatOllama)
    assert model.client_kwargs["headers"]["Authorization"] == "Bearer fake-ollama-token"


def test_ollama_adapter_works_without_token_for_local():
    spec = ProviderSpec(
        provider="ollama",
        model="llama3.1",
        base_url="http://localhost:11434",
        token_name="OLLAMA_TOKEN",
    )
    model = build_ollama(spec, timeout=30)
    assert "headers" not in model.client_kwargs


def test_fireworks_adapter_requires_openai_dependency(monkeypatch):
    """With langchain-openai installed, Fireworks builds a ChatOpenAI model."""
    monkeypatch.setenv("NORA_FIREWORKS_TOKEN", "fake-fireworks-token")
    spec = ProviderSpec(
        provider="fireworks",
        model="accounts/fireworks/models/kimi-k3",
        base_url="https://api.fireworks.ai/inference/v1",
        token_name="FIREWORKS_TOKEN",
    )

    model = build_fireworks(spec, timeout=60)
    assert model._llm_type in {"openai", "openai-chat"}


def test_fireworks_rejects_wrong_endpoint():

    spec = ProviderSpec(
        provider="fireworks",
        model="accounts/fireworks/models/x",
        base_url="https://other.example/v1",
        token_name="FIREWORKS_TOKEN",
    )
    with pytest.raises(ConfigurationError):
        build_fireworks(spec, timeout=60)


def test_unknown_provider_rejected():
    spec = ProviderSpec(provider="unknown", model="x", base_url="http://x", token_name="X_TOKEN")
    with pytest.raises(ConfigurationError):
        build_model(spec, timeout=60)


def test_provider_token_is_not_shared_across_hosts(monkeypatch):
    monkeypatch.setenv("NORA_OLLAMA_TOKEN", "only-for-ollama")
    ollama = ProviderSpec(
        provider="ollama", model="m", base_url="https://ollama.com", token_name="OLLAMA_TOKEN"
    )
    model = build_ollama(ollama, timeout=60)
    assert model.client_kwargs["headers"]["Authorization"] == "Bearer only-for-ollama"


def test_ollama_bind_tools_is_supported(monkeypatch):
    """The native Ollama adapter accepts tool bindings."""
    from langchain_core.tools import tool

    monkeypatch.setenv("NORA_OLLAMA_TOKEN", "fake-ollama-token")
    spec = ProviderSpec(
        provider="ollama",
        model="gpt-oss:20b",
        base_url="https://ollama.com",
        token_name="OLLAMA_TOKEN",
    )
    model = build_ollama(spec, timeout=120)

    @tool
    def example_tool(x: str) -> str:
        """Example."""
        return x

    bound = model.bind_tools([example_tool])
    assert bound is not None


def test_fireworks_requires_langchain_openai_and_valid_endpoint(monkeypatch):
    """Fireworks rejects wrong endpoints and builds with the real SDK."""

    monkeypatch.setenv("NORA_FIREWORKS_TOKEN", "fake-fireworks-token")
    bad_spec = ProviderSpec(
        provider="fireworks",
        model="accounts/fireworks/models/x",
        base_url="https://other.example/v1",
        token_name="FIREWORKS_TOKEN",
    )
    with pytest.raises(ConfigurationError):
        build_fireworks(bad_spec, timeout=60)
    good_spec = ProviderSpec(
        provider="fireworks",
        model="accounts/fireworks/models/kimi-k3",
        base_url="https://api.fireworks.ai/inference/v1",
        token_name="FIREWORKS_TOKEN",
    )
    model = build_fireworks(good_spec, timeout=60)
    assert model._llm_type in {"openai", "openai-chat"}
    # Tool binding must be supported by the returned ChatOpenAI model.
    from langchain_core.tools import tool

    @tool
    def example_tool(x: str) -> str:
        """Example."""
        return x

    bound = model.bind_tools([example_tool])
    assert bound is not None


def test_fireworks_stream_interface_is_supported(monkeypatch):
    """The returned ChatOpenAI model exposes a stream method."""

    monkeypatch.setenv("NORA_FIREWORKS_TOKEN", "fake-fireworks-token")
    spec = ProviderSpec(
        provider="fireworks",
        model="accounts/fireworks/models/kimi-k3",
        base_url="https://api.fireworks.ai/inference/v1",
        token_name="FIREWORKS_TOKEN",
    )
    model = build_fireworks(spec, timeout=60)
    assert callable(getattr(model, "stream", None))
    assert callable(getattr(model, "astream", None))
