"""Optional two-tier heuristic routing through public LangChain model interfaces."""

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from langchain_core.callbacks.manager import (
    AsyncCallbackManager,
    AsyncCallbackManagerForLLMRun,
    CallbackManager,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_ollama import ChatOllama
from pydantic import Field

from nora.config import ConfigurationError, Settings, credential, endpoint

logger = logging.getLogger(__name__)
HINTS = (
    "compare",
    "why",
    "explain",
    "multi",
    "synthesize",
    "tradeoff",
    "architecture",
    "evaluate",
    "analyze",
    "design",
)


def complexity_score(prompt: str) -> int:
    return min(len(prompt), 30) + 10 * sum(hint in prompt.lower() for hint in HINTS)


class RoutingChatModel(BaseChatModel):
    """Routes each call; fallback occurs once, only before output has been emitted."""

    cheap_model: Any = Field(exclude=True, repr=False)
    strong_model: Any = Field(exclude=True, repr=False)
    threshold: int = 40
    log_path: Path | None = None

    @property
    def _llm_type(self) -> str:
        return "nora-router"

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        binding = dict(kwargs)
        if tool_choice is not None:
            binding["tool_choice"] = tool_choice
        return self.model_copy(
            update={
                "cheap_model": self.cheap_model.bind_tools(tools, **binding),
                "strong_model": self.strong_model.bind_tools(tools, **binding),
            }
        )

    def _selection(self, messages):
        last = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
        prompt = (
            last.content
            if last and isinstance(last.content, str)
            else str(last.content if last else "")
        )
        first = "cheap" if complexity_score(prompt) < self.threshold else "strong"
        tiers = [
            (first, self.cheap_model if first == "cheap" else self.strong_model),
            (
                "strong" if first == "cheap" else "cheap",
                self.strong_model if first == "cheap" else self.cheap_model,
            ),
        ]
        return prompt, tiers

    def _record(self, prompt, tier, fallback, started, outcome):
        if self.log_path is None:
            return
        record = {
            "ts": time.time(),
            "query_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "tier": tier,
            "score": complexity_score(prompt),
            "threshold": self.threshold,
            "fallback": fallback,
            "outcome": outcome,
            "latency_ms": round((time.monotonic() - started) * 1000, 2),
        }
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as output:
                output.write(json.dumps(record) + "\n")
        except OSError:
            # A telemetry failure must never trigger another paid model request.
            logger.warning("Routing decision log could not be written")

    @staticmethod
    def _callbacks(run_manager):
        if run_manager is None:
            return None
        manager = (
            AsyncCallbackManager
            if isinstance(run_manager, AsyncCallbackManagerForLLMRun)
            else CallbackManager
        )
        return {
            "callbacks": manager(
                handlers=run_manager.handlers,
                inheritable_handlers=run_manager.inheritable_handlers,
                parent_run_id=run_manager.run_id,
                tags=run_manager.tags,
                inheritable_tags=run_manager.inheritable_tags,
                metadata=run_manager.metadata,
                inheritable_metadata=run_manager.inheritable_metadata,
            )
        }

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        prompt, tiers = self._selection(messages)
        started = time.monotonic()
        for attempt, (tier, model) in enumerate(tiers):
            try:
                message = model.invoke(
                    messages, config=self._callbacks(run_manager), stop=stop, **kwargs
                )
            except Exception:
                self._record(prompt, tier, bool(attempt), started, "failed")
                if attempt:
                    raise
            else:
                self._record(prompt, tier, bool(attempt), started, "success")
                return ChatResult(generations=[ChatGeneration(message=message)])
        raise AssertionError("Unreachable routing state")

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        prompt, tiers = self._selection(messages)
        started = time.monotonic()
        for attempt, (tier, model) in enumerate(tiers):
            try:
                message = await model.ainvoke(
                    messages, config=self._callbacks(run_manager), stop=stop, **kwargs
                )
            except Exception:
                self._record(prompt, tier, bool(attempt), started, "failed")
                if attempt:
                    raise
            else:
                self._record(prompt, tier, bool(attempt), started, "success")
                return ChatResult(generations=[ChatGeneration(message=message)])
        raise AssertionError("Unreachable routing state")

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        prompt, tiers = self._selection(messages)
        started = time.monotonic()
        for attempt, (tier, model) in enumerate(tiers):
            emitted = False
            try:
                for chunk in model.stream(
                    messages, config=self._callbacks(run_manager), stop=stop, **kwargs
                ):
                    emitted = True
                    yield ChatGenerationChunk(message=chunk)
            except Exception:
                self._record(
                    prompt, tier, bool(attempt), started, "partial_failure" if emitted else "failed"
                )
                if emitted or attempt:
                    raise
            else:
                self._record(prompt, tier, bool(attempt), started, "success")
                return

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        prompt, tiers = self._selection(messages)
        started = time.monotonic()
        for attempt, (tier, model) in enumerate(tiers):
            emitted = False
            try:
                async for chunk in model.astream(
                    messages, config=self._callbacks(run_manager), stop=stop, **kwargs
                ):
                    emitted = True
                    yield ChatGenerationChunk(message=chunk)
            except Exception:
                self._record(
                    prompt, tier, bool(attempt), started, "partial_failure" if emitted else "failed"
                )
                if emitted or attempt:
                    raise
            else:
                self._record(prompt, tier, bool(attempt), started, "success")
                return


def _ollama(model: str, url: str, token: str, timeout: int):
    options: dict = {"timeout": timeout}
    if token:
        options["headers"] = {"Authorization": "Bearer " + token}
    return ChatOllama(
        model=model,
        base_url=url,
        client_kwargs=options,
        temperature=0,
        num_predict=1800,
        num_ctx=16000,
    )


def build_model(settings: Settings):
    enabled = os.environ.get("NORA_ROUTER_ENABLED", "false").lower()
    if enabled not in {"true", "false", "1", "0", "yes", "no"}:
        raise ConfigurationError("NORA_ROUTER_ENABLED must be true or false")
    token = credential("OLLAMA_TOKEN", required=False)
    default = _ollama(settings.ollama_model, settings.ollama_url, token, settings.request_timeout)
    if enabled in {"false", "0", "no"}:
        return default
    cheap_name = os.environ.get("NORA_ROUTER_CHEAP_MODEL", "").strip()
    if not cheap_name:
        raise ConfigurationError("Set NORA_ROUTER_CHEAP_MODEL when routing is enabled")
    cheap_url = endpoint(
        os.environ.get("NORA_ROUTER_CHEAP_URL", settings.ollama_url), "NORA_ROUTER_CHEAP_URL"
    )
    # A token for one provider is not silently forwarded to a different endpoint.
    cheap_token = credential("ROUTER_CHEAP_TOKEN", required=False)
    if not cheap_token and cheap_url == settings.ollama_url:
        cheap_token = token
    try:
        threshold = int(os.environ.get("NORA_ROUTER_THRESHOLD", "40"))
    except ValueError as error:
        raise ConfigurationError("NORA_ROUTER_THRESHOLD must be an integer") from error
    if threshold < 0:
        raise ConfigurationError("NORA_ROUTER_THRESHOLD must be nonnegative")
    log = os.environ.get("NORA_ROUTER_LOG", "")
    return RoutingChatModel(
        cheap_model=_ollama(cheap_name, cheap_url, cheap_token, settings.request_timeout),
        strong_model=default,
        threshold=threshold,
        log_path=Path(log) if log else None,
    )
