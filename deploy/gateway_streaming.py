"""Compatibility fix for mixed Ollama chunks in pinned LiteLLM 1.103.2.

LiteLLM's Responses converter returns after the first populated channel. Split
mixed reasoning/text/tool deltas before conversion, rather than replaying a final
buffer. IDs, argument fragments, usage and terminal/error semantics stay upstream.
"""

from collections import deque
from copy import deepcopy
from functools import wraps
from importlib.metadata import version
from uuid import uuid4


class SeparateChannels:
    def __init__(self, source):
        self.source = source
        self.pending = deque()

    def __getattr__(self, name):
        return getattr(self.source, name)

    @staticmethod
    def split(chunk):
        if len(chunk.choices) != 1:
            return [chunk]
        choice = chunk.choices[0]
        delta = choice.delta
        channels = []
        if getattr(delta, "reasoning_content", None) or getattr(delta, "thinking_blocks", None):
            channels.append("reasoning")
        if delta.content:
            channels.append("text")
        if delta.tool_calls or getattr(delta, "function_call", None):
            channels.append("tools")
        if len(channels) < 2:
            return [chunk]
        parts = []
        for index, channel in enumerate(channels):
            fields = {}
            if channel != "reasoning":
                fields.update(reasoning_content=None, thinking_blocks=None)
            if channel != "text":
                fields["content"] = None
            if channel != "tools":
                fields.update(tool_calls=None, function_call=None)
            final = index == len(channels) - 1
            part_choice = choice.model_copy(
                update={
                    "delta": delta.model_copy(update=fields),
                    "finish_reason": choice.finish_reason if final else None,
                }
            )
            part = chunk.model_copy(update={"choices": [part_choice]})
            if not final:
                if hasattr(part, "usage"):
                    part.usage = None
                hidden = getattr(chunk, "_hidden_params", None)
                if isinstance(hidden, dict):
                    part._hidden_params = {k: v for k, v in hidden.items() if k != "usage"}
            parts.append(part)
        return parts

    def __iter__(self):
        return self

    def __next__(self):
        if not self.pending:
            self.pending.extend(self.split(next(self.source)))
        return self.pending.popleft()

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.pending:
            self.pending.extend(self.split(await self.source.__anext__()))
        return self.pending.popleft()


def install():
    if version("litellm") != "1.103.2":
        raise RuntimeError("Revalidate the streaming compatibility fix before upgrading LiteLLM")
    from litellm.llms.ollama.chat.transformation import OllamaChatCompletionResponseIterator
    from litellm.responses.litellm_completion_transformation.streaming_iterator import (
        LiteLLMCompletionStreamingIterator,
    )

    parser = OllamaChatCompletionResponseIterator.chunk_parser
    if not getattr(parser, "_nis_preserves_tool_indexes", False):

        @wraps(parser)
        def parse(self, chunk):
            # Ollama places the stream index inside function; LiteLLM drops it
            # and assigns every call index zero, concatenating independent JSON
            # arguments in the completed response. Keep provider IDs as well.
            chunk = deepcopy(chunk)
            tools = chunk.get("message", {}).get("tool_calls") or []
            indexes = getattr(self, "_nis_tool_indexes", {})
            ids = getattr(self, "_nis_tool_ids", {})
            normalized = []
            for tool in tools:
                raw_id = tool.get("id")
                index = tool.get("index", tool.get("function", {}).get("index"))
                if index is None:
                    index = indexes.get(raw_id, max(ids, default=-1) + 1)
                index = int(index)
                call_id = raw_id or ids.get(index) or str(uuid4())
                ids[index] = call_id
                indexes[call_id] = index
                tool["index"] = index
                normalized.append((index, call_id))
            self._nis_tool_indexes, self._nis_tool_ids = indexes, ids
            result = parser(self, chunk)
            parsed = result.choices[0].delta.tool_calls or []
            for tool, (index, call_id) in zip(parsed, normalized, strict=True):
                tool.index, tool.id = index, call_id
            return result

        parse._nis_preserves_tool_indexes = True
        OllamaChatCompletionResponseIterator.chunk_parser = parse

    original = LiteLLMCompletionStreamingIterator.__init__
    if getattr(original, "_nis_separates_channels", False):
        return

    @wraps(original)
    def initialize(self, model, litellm_custom_stream_wrapper, *args, **kwargs):
        if kwargs.get("custom_llm_provider") == "ollama_chat" or model.startswith("ollama_chat/"):
            litellm_custom_stream_wrapper = SeparateChannels(litellm_custom_stream_wrapper)
        original(self, model, litellm_custom_stream_wrapper, *args, **kwargs)

    initialize._nis_separates_channels = True
    LiteLLMCompletionStreamingIterator.__init__ = initialize
