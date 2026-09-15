"""Quality-first automatic model selection inside each role runtime.

The selector filters models by required task capabilities, then sorts by quality
first and weighted cost/latency second. It logs decisions without prompts or
secret values. Fallback to the next eligible model happens once, before any
output chunk is emitted.
"""

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

from langchain_core.callbacks.manager import (
    AsyncCallbackManager,
    AsyncCallbackManagerForLLMRun,
    CallbackManager,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field

from nora.config import ConfigurationError
from nora.providers import ProviderSpec, ProviderUnavailable, build_model

logger = logging.getLogger(__name__)

# Task signals that raise the minimum quality tier.
REASONING_HINTS = (
    "compare",
    "why",
    "explain",
    "analyze",
    "evaluate",
    "design",
    "architecture",
    "tradeoff",
    "synthesize",
    "multi",
)
CODE_HINTS = ("code", "python", "function", "debug", "script", "implementation")
TRANSCRIPT_HINTS = ("transcript", "feedback", "interview", "practice")


def _task_requirements(prompt: str) -> tuple[int, set[str]]:
    """Return (minimum_quality_tier, required_capability_tags) for a prompt."""
    lowered = prompt.lower()
    tags: set[str] = {"knowledge"}
    min_tier = 2
    if any(h in lowered for h in REASONING_HINTS):
        min_tier = max(min_tier, 3)
        tags.add("reasoning")
    if any(h in lowered for h in CODE_HINTS):
        min_tier = max(min_tier, 3)
        tags.add("coding")
    if any(h in lowered for h in TRANSCRIPT_HINTS):
        min_tier = max(min_tier, 3)
        tags.add("interview")
    if len(prompt) > 800:
        min_tier = max(min_tier, 3)
    return min_tier, tags


def _eligible(specs: list[ProviderSpec], min_tier: int, tags: set[str]) -> list[ProviderSpec]:
    """Filter specs that meet quality and capability requirements."""
    eligible = []
    for spec in specs:
        if spec.quality_tier < min_tier:
            continue
        if not tags.issubset(spec.capability_tags):
            continue
        eligible.append(spec)
    return eligible


def _score(
    spec: ProviderSpec, min_tier: int, tags: set[str], cost_weight: float, latency_weight: float
) -> float:
    """Lower is better: excess quality is lightly penalized, then cost/latency."""
    # A model that just meets the required tier is preferred over one that far
    # exceeds it, once both pass the minimum-quality filter.
    quality_penalty = max(0, spec.quality_tier - min_tier) * 0.5
    # Cost/latency are normalized assumptions, not measurements.
    cost_penalty = spec.relative_cost * cost_weight
    latency_penalty = spec.relative_latency * latency_weight
    # Slight preference for a capability match beyond the minimum.
    tag_bonus = len(tags & set(spec.capability_tags)) * -0.2
    return quality_penalty + cost_penalty + latency_penalty + tag_bonus


@dataclass(frozen=True)
class Selection:
    spec: ProviderSpec
    model: BaseChatModel
    tier_index: int


class RoleSelectorModel(BaseChatModel):
    """Per-request selection across a role's provider inventory.

    Fallback occurs once and only before any stream chunk is emitted, matching
    the contract verified for the older RoutingChatModel.
    """

    specs: list[ProviderSpec] = Field(default_factory=list, exclude=True, repr=False)
    timeout: int = 180
    cost_weight: float = 1.0
    latency_weight: float = 1.0
    log_path: Path | None = None
    bound_tools: list = Field(default_factory=list, exclude=True, repr=False)
    bound_kwargs: dict = Field(default_factory=dict, exclude=True, repr=False)

    @property
    def _llm_type(self) -> str:
        return "nora-role-selector"

    def _selection(self, messages) -> tuple[str, list[Selection]]:
        last = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
        prompt = (
            last.content
            if last and isinstance(last.content, str)
            else str(last.content if last else "")
        )
        min_tier, tags = _task_requirements(prompt)
        eligible = _eligible(self.specs, min_tier, tags)
        if not eligible:
            eligible = self.specs[:]  # Degrade to the full inventory rather than fail.
        eligible.sort(
            key=lambda spec: _score(spec, min_tier, tags, self.cost_weight, self.latency_weight)
        )
        selections: list[Selection] = []
        for index, spec in enumerate(eligible):
            try:
                model = build_model(spec, self.timeout)
            except Exception:
                logger.warning("Could not build %s/%s at selection time", spec.provider, spec.model)
                continue
            selections.append(Selection(spec=spec, model=model, tier_index=index))
        if not selections:
            raise ProviderUnavailable("No eligible model could be built for this request")
        return prompt, selections

    def _record(
        self,
        prompt: str,
        spec: ProviderSpec,
        tier_index: int,
        fallback: bool,
        started: float,
        outcome: str,
    ):
        if self.log_path is None:
            return
        record = {
            "ts": time.time(),
            "query_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "provider": spec.provider,
            "model": spec.model,
            "tier_index": tier_index,
            "fallback": fallback,
            "outcome": outcome,
            "latency_ms": round((time.monotonic() - started) * 1000, 2),
        }
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as output:
                output.write(json.dumps(record) + "\n")
        except OSError:
            # Telemetry failure must not trigger another paid model request.
            logger.warning("Selector decision log could not be written")

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
        for attempt, selection in enumerate(tiers):
            try:
                result = self._model_with_tools(selection.model).invoke(
                    messages, config=self._callbacks(run_manager), stop=stop, **kwargs
                )
            except Exception:
                self._record(
                    prompt, selection.spec, selection.tier_index, bool(attempt), started, "failed"
                )
                if attempt:
                    raise
            else:
                self._record(
                    prompt, selection.spec, selection.tier_index, bool(attempt), started, "success"
                )
                return ChatResult(generations=[ChatGeneration(message=result)])
        raise AssertionError("Unreachable selector state")

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        prompt, tiers = self._selection(messages)
        started = time.monotonic()
        for attempt, selection in enumerate(tiers):
            try:
                result = await self._model_with_tools(selection.model).ainvoke(
                    messages, config=self._callbacks(run_manager), stop=stop, **kwargs
                )
            except Exception:
                self._record(
                    prompt, selection.spec, selection.tier_index, bool(attempt), started, "failed"
                )
                if attempt:
                    raise
            else:
                self._record(
                    prompt, selection.spec, selection.tier_index, bool(attempt), started, "success"
                )
                return ChatResult(generations=[ChatGeneration(message=result)])
        raise AssertionError("Unreachable selector state")

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        prompt, tiers = self._selection(messages)
        started = time.monotonic()
        for attempt, selection in enumerate(tiers):
            emitted = False
            try:
                for chunk in self._model_with_tools(selection.model).stream(
                    messages, config=self._callbacks(run_manager), stop=stop, **kwargs
                ):
                    emitted = True
                    yield ChatGenerationChunk(message=chunk)
            except Exception:
                self._record(
                    prompt,
                    selection.spec,
                    selection.tier_index,
                    bool(attempt),
                    started,
                    "partial_failure" if emitted else "failed",
                )
                if emitted or attempt:
                    raise
            else:
                self._record(
                    prompt, selection.spec, selection.tier_index, bool(attempt), started, "success"
                )
                return

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        prompt, tiers = self._selection(messages)
        started = time.monotonic()
        for attempt, selection in enumerate(tiers):
            emitted = False
            try:
                async for chunk in self._model_with_tools(selection.model).astream(
                    messages, config=self._callbacks(run_manager), stop=stop, **kwargs
                ):
                    emitted = True
                    yield ChatGenerationChunk(message=chunk)
            except Exception:
                self._record(
                    prompt,
                    selection.spec,
                    selection.tier_index,
                    bool(attempt),
                    started,
                    "partial_failure" if emitted else "failed",
                )
                if emitted or attempt:
                    raise
            else:
                self._record(
                    prompt, selection.spec, selection.tier_index, bool(attempt), started, "success"
                )
                return

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        # Capture the tool binding so each dynamically selected provider model
        # receives the same tool set at invocation time.
        bound_kwargs = dict(kwargs)
        if tool_choice is not None:
            bound_kwargs["tool_choice"] = tool_choice
        return self.model_copy(
            deep=True,
            update={
                "specs": self.specs,
                "bound_tools": list(tools),
                "bound_kwargs": bound_kwargs,
            },
        )

    def _model_with_tools(self, model: BaseChatModel) -> BaseChatModel:
        """Apply the stored tool binding to a freshly built provider model."""
        if not self.bound_tools:
            return model
        kwargs = dict(self.bound_kwargs)
        tool_choice = kwargs.pop("tool_choice", None)
        if tool_choice is not None:
            return model.bind_tools(self.bound_tools, tool_choice=tool_choice, **kwargs)
        return model.bind_tools(self.bound_tools, **kwargs)


def build_selector(
    specs: list[ProviderSpec],
    *,
    timeout: int = 180,
    cost_weight: float | None = None,
    latency_weight: float | None = None,
    log_path: str | Path | None = None,
) -> RoleSelectorModel:
    """Build a quality-first selector from a role model inventory."""
    if not specs:
        raise ConfigurationError("A role must have at least one model spec")
    return RoleSelectorModel(
        specs=specs,
        timeout=timeout,
        cost_weight=float(
            cost_weight
            if cost_weight is not None
            else os.environ.get("NORA_SELECTOR_COST_WEIGHT", "1")
        ),
        latency_weight=float(
            latency_weight
            if latency_weight is not None
            else os.environ.get("NORA_SELECTOR_LATENCY_WEIGHT", "1")
        ),
        log_path=Path(log_path) if log_path else None,
    )
