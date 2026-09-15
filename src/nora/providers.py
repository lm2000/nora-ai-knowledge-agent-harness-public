"""Provider adapters for answer inference.

Each adapter returns a LangChain chat model with normalized tool/stream binding.
Credentials are read from NORA_<PROVIDER>_TOKEN or NORA_<PROVIDER>_TOKEN_FILE.
A token for one provider is never forwarded to a different host.
"""

from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from nora.config import ConfigurationError, credential


class ProviderUnavailable(RuntimeError):
    """A provider cannot answer because of a missing capability or credential."""


@dataclass(frozen=True)
class ProviderSpec:
    """Declarative contract for one inference route."""

    provider: str  # 'ollama', 'fireworks'
    model: str  # provider-specific model slug
    base_url: str
    token_name: str  # env name suffix, e.g. 'OLLAMA_TOKEN'
    supports_tools: bool = True
    supports_streaming: bool = True
    context_length: int = 16000
    quality_tier: int = 3  # 1 = lowest acceptable, 5 = strongest
    relative_cost: float = 1.0  # assumption, not a measured price
    relative_latency: float = 1.0  # assumption, not a measured latency
    capability_tags: tuple[str, ...] = ()


def _token_for(spec: ProviderSpec, *, required: bool = False) -> str | None:
    """Read a provider token by its spec name, isolated from other providers."""
    return credential(spec.token_name, required=required)


def build_ollama(spec: ProviderSpec, timeout: int) -> BaseChatModel:
    """Native Ollama protocol adapter."""
    token = _token_for(spec, required=False)
    options: dict[str, Any] = {"timeout": timeout}
    if token:
        options["headers"] = {"Authorization": "Bearer " + token}
    return ChatOllama(
        model=spec.model,
        base_url=spec.base_url,
        client_kwargs=options,
        temperature=0,
        num_predict=1800,
        num_ctx=spec.context_length,
    )


def _openai_compatible(spec: ProviderSpec, timeout: int) -> BaseChatModel:
    """Build a ChatOpenAI-backed model for OpenAI-compatible endpoints."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as error:
        raise ProviderUnavailable(
            f"OpenAI-compatible provider '{spec.provider}' needs langchain-openai; "
            "install the 'openai' extra or use the Ollama provider"
        ) from error
    token = _token_for(spec, required=True)
    if not token:
        raise ProviderUnavailable(f"Configure {spec.token_name} or {spec.token_name}_FILE")
    return ChatOpenAI(
        model=spec.model,
        api_key=token,
        base_url=spec.base_url,
        temperature=0,
        max_tokens=1800,
        timeout=timeout,
    )


def build_fireworks(spec: ProviderSpec, timeout: int) -> BaseChatModel:
    """Fireworks.ai OpenAI-compatible adapter.

    Model slugs follow `accounts/fireworks/models/<name>` as returned by the
    Fireworks model catalog. The endpoint is fixed by the provider contract.
    """
    if not spec.base_url.startswith("https://api.fireworks.ai/inference"):
        raise ConfigurationError("NORA_FIREWORKS_URL must use the Fireworks inference endpoint")
    return _openai_compatible(spec, timeout)


BUILDERS = {
    "ollama": build_ollama,
    "fireworks": build_fireworks,
}


def build_model(spec: ProviderSpec, timeout: int) -> BaseChatModel:
    """Build a verified LangChain chat model from a provider spec."""
    builder = BUILDERS.get(spec.provider)
    if builder is None:
        raise ConfigurationError(f"Unknown provider type: {spec.provider}")
    return builder(spec, timeout)
