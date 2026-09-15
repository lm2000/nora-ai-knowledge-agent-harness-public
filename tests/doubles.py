"""Canonical deterministic doubles for tests and verification scripts.

These are intentionally kept outside the production `src/nora/` tree so they are
never silently loaded by application code. Test doubles verify interface contracts,
not model answer quality or real BGE inference.
"""

import hashlib
import re

import numpy as np
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from nora.common import DIMENSION, QUERY_PREFIX


class TokenizerDouble:
    """Split on non-whitespace tokens; returns offsets and synthetic input IDs."""

    def __call__(
        self,
        text,
        add_special_tokens=False,
        return_offsets_mapping=False,
        **kwargs,
    ):
        spans = [m.span() for m in re.finditer(r"\S+", text)]
        input_ids = list(range(len(spans) + (2 if add_special_tokens else 0)))
        result = {"input_ids": input_ids}
        if return_offsets_mapping:
            result["offset_mapping"] = spans
        return result


class DeterministicEncoderDouble:
    """Test double: stable 768-D vectors from token hashes.

    The `query` flag is honored by prepending the BGE query prefix before hashing,
    so the same raw text produces different vectors for query and document mode.
    This proves the HTTP `query` flag reaches the encoder without pretending to be
    a real BGE inference run.
    """

    tokenizer = TokenizerDouble()

    def encode(self, texts: list[str], *, query: bool = False):
        result = np.zeros((len(texts), DIMENSION), dtype=np.float32)
        for i, text in enumerate(texts):
            effective = (QUERY_PREFIX + text) if query else text
            for term in re.findall(r"\w+", effective.lower()):
                index = (
                    int.from_bytes(hashlib.sha256(term.encode()).digest()[:2], "big") % DIMENSION
                )
                result[i, index] += 1.0
            norm = np.linalg.norm(result[i])
            if norm == 0:
                result[i, 0] = 1.0
            else:
                result[i] /= norm
        return result


class DeterministicModelDouble(BaseChatModel):
    """Test double: answers from the last tool result, no citations or IDs shown."""

    observed: list = Field(default_factory=list, exclude=True)

    @property
    def _llm_type(self):
        return "nora-deterministic-model"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.observed.append(messages)
        tool_texts = [str(m.content) for m in messages if isinstance(m, ToolMessage)]
        combined = " ".join(tool_texts)
        match = re.search(r"October\s+\d{1,2},?\s+2026", combined)
        answer = match.group(0) if match else "No date found"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=answer))])


class SlowEncoderDouble(DeterministicEncoderDouble):
    """Deterministic encoder that sleeps during encode to test HTTP admission control.

    The delay is applied once per batch, so concurrent requests compete for a small
    number of worker slots. The vectors are still deterministic and honor the query flag.
    """

    def __init__(self, delay_seconds: float = 0.5):
        self.delay_seconds = delay_seconds

    def encode(self, texts: list[str], *, query: bool = False):
        import time

        time.sleep(self.delay_seconds)
        return super().encode(texts, query=query)
