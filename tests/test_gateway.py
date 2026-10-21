"""Gateway web contract; no external provider or database is used."""

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deploy"))
from gateway_web import create_web_app  # noqa: E402


async def request(app, body, *, token="gateway-test", path="/mcp"):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:4000"
    ) as client:
        return await client.post(
            path,
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2025-11-25",
            },
            json={"jsonrpc": "2.0", "id": 1, **body},
        )


@pytest.mark.asyncio
async def test_web_auth_bounded_results_and_search_contract():
    calls = []

    def upstream(req):
        calls.append(req)
        assert req.url == "https://ollama.com/api/web_search"
        assert req.headers["authorization"] == "Bearer provider-test"
        assert json.loads(req.content) == {"query": "public docs", "max_results": 2}
        return httpx.Response(
            200,
            json={
                "results": [
                    {"title": "Docs", "url": "https://example.org/docs", "content": "x" * 5000},
                    {"title": "Invalid", "url": "javascript:alert(1)", "content": "omit"},
                    {"title": "Beyond limit", "url": "https://example.org/extra"},
                ]
            },
        )

    inner, app = create_web_app(
        "gateway-test", "provider-test", transport=httpx.MockTransport(upstream)
    )
    async with inner.router.lifespan_context(inner):
        body = {"method": "tools/call", "params": {"name": "search", "arguments": {}}}
        assert (await request(app, body, token="wrong")).status_code == 401
        assert not calls
        listing = (await request(app, {"method": "tools/list"})).json()["result"]["tools"]
        assert [tool["name"] for tool in listing] == ["search"]
        assert listing[0]["annotations"]["readOnlyHint"] is True
        for arguments in ({"query": " "}, {"query": "x", "max_results": 11}):
            body["params"]["arguments"] = arguments
            assert (await request(app, body)).json()["result"]["isError"] is True
        assert not calls
        body["params"]["arguments"] = {"query": "  public docs  ", "max_results": 2}
        result = (await request(app, body)).json()["result"]
        assert not result.get("isError")
        rows = result["structuredContent"]["results"]
        assert len(rows) == 1
        assert rows[0]["title"] == "Docs"
        assert rows[0]["url"] == "https://example.org/docs"
        assert len(rows[0]["content"]) == 2500
        assert len(calls) == 1


@pytest.mark.asyncio
async def test_web_provider_failure_is_sanitized():
    def upstream(req):
        return httpx.Response(503, text="private provider-test response")

    inner, app = create_web_app(
        "gateway-test", "provider-test", transport=httpx.MockTransport(upstream)
    )
    async with inner.router.lifespan_context(inner):
        result = (
            await request(
                app,
                {
                    "method": "tools/call",
                    "params": {"name": "search", "arguments": {"query": "docs"}},
                },
            )
        ).json()["result"]
        assert result["isError"] is True
        assert "Public web search is unavailable" in json.dumps(result)
        assert "provider-test" not in json.dumps(result)


@pytest.mark.asyncio
async def test_web_mount_precedes_parent_catchall():
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Mount, Route

    inner, authenticated = create_web_app("gateway-test", "provider-test")
    parent = Starlette(
        routes=[
            Mount("/internal-web", app=authenticated),
            Route(
                "/{path:path}", lambda request: PlainTextResponse("UI fallback", status_code=404)
            ),
        ]
    )
    async with inner.router.lifespan_context(inner):
        result = (await request(parent, {"method": "tools/list"}, path="/internal-web/mcp")).json()
        assert result["result"]["tools"][0]["name"] == "search"


@pytest.mark.skipif(importlib.util.find_spec("litellm") is None, reason="gateway image dependency")
def test_responses_mixed_channels():
    # This test runs against the locked LiteLLM dependency in the gateway image.
    import asyncio

    from gateway_streaming import install
    from litellm.responses.litellm_completion_transformation.streaming_iterator import (
        LiteLLMCompletionStreamingIterator,
    )
    from litellm.types.utils import Delta, ModelResponseStream, StreamingChoices

    install()

    def chunks():
        return [
            ModelResponseStream(
                model="glm-5.3-flash",
                choices=[
                    StreamingChoices(
                        delta=Delta(reasoning_content="synthetic reasoning", content="ANSWER ")
                    )
                ],
            ),
            ModelResponseStream(
                model="glm-5.3-flash",
                choices=[
                    StreamingChoices(
                        delta=Delta(
                            content="OK",
                            tool_calls=[
                                {
                                    "index": 0,
                                    "id": "call_test",
                                    "type": "function",
                                    "function": {"name": "lookup", "arguments": '{"query":'},
                                }
                            ],
                        )
                    )
                ],
            ),
            ModelResponseStream(
                model="glm-5.3-flash",
                choices=[
                    StreamingChoices(
                        delta=Delta(
                            tool_calls=[{"index": 0, "function": {"arguments": '"public"}'}}]
                        ),
                        finish_reason="tool_calls",
                    )
                ],
            ),
        ]

    class Source:
        logging_obj = None

        def __init__(self, fail=False):
            self.items = iter(chunks())
            self.fail = fail

        def __next__(self):
            return next(self.items)

        async def __anext__(self):
            try:
                return next(self.items)
            except StopIteration:
                if self.fail:
                    raise RuntimeError("synthetic upstream interruption")
                raise StopAsyncIteration from None

    def iterator(fail=False):
        return LiteLLMCompletionStreamingIterator(
            model="ollama_chat/glm-5.3-flash",
            litellm_custom_stream_wrapper=Source(fail),
            request_input="synthetic test",
            responses_api_request={},
            custom_llm_provider="ollama_chat",
        )

    def check(events):
        assert (
            "".join(e.delta for e in events if e.type == "response.output_text.delta")
            == "ANSWER OK"
        )
        assert [e.text for e in events if e.type == "response.output_text.done"] == ["ANSWER OK"]
        args = [e for e in events if e.type == "response.function_call_arguments.delta"]
        assert "".join(e.delta for e in args) == '{"query":"public"}'
        completed = [e for e in events if e.type == "response.completed"]
        assert len(completed) == 1
        tool = next(item for item in completed[0].response.output if item.type == "function_call")
        assert tool.call_id == "call_test"
        assert json.loads(tool.arguments) == {"query": "public"}
        messages = [
            e for e in events if e.type == "response.output_item.added" and e.item.type == "message"
        ]
        assert len(messages) == 1
        assert all(
            e.item_id == messages[0].item.id
            for e in events
            if e.type == "response.output_text.delta"
        )

    check(list(iterator()))

    async def collect():
        check([event async for event in iterator()])
        failed = []
        with pytest.raises(RuntimeError, match="upstream interruption"):
            async for event in iterator(fail=True):
                failed.append(event)
        assert not any(event.type == "response.completed" for event in failed)

    asyncio.run(collect())


@pytest.mark.skipif(importlib.util.find_spec("litellm") is None, reason="gateway image dependency")
def test_ollama_multiple_calls_keep_provider_indexes_and_ids():
    from gateway_streaming import install
    from litellm import stream_chunk_builder
    from litellm.llms.ollama.chat.transformation import OllamaChatCompletionResponseIterator

    install()
    parser = object.__new__(OllamaChatCompletionResponseIterator)
    chunks = []
    for index, name, value in [(0, "route_a", "A"), (1, "route_b", "B")]:
        chunk = {
            "model": "glm-5.3-flash",
            "done": False,
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": f"call_{index}",
                        "function": {"index": index, "name": name, "arguments": {"value": value}},
                    }
                ],
            },
        }
        parsed = parser.chunk_parser(chunk)
        call = parsed.choices[0].delta.tool_calls[0]
        assert call.index == index and call.id == f"call_{index}"
        assert chunk["message"]["tool_calls"][0]["id"] == f"call_{index}"
        chunks.append(parsed)
    chunks.append(
        parser.chunk_parser(
            {
                "model": "glm-5.3-flash",
                "done": True,
                "done_reason": "stop",
                "message": {"role": "assistant", "content": ""},
            }
        )
    )
    complete = stream_chunk_builder(chunks)
    calls = complete.choices[0].message.tool_calls
    assert [
        (call.id, call.function.name, json.loads(call.function.arguments)) for call in calls
    ] == [("call_0", "route_a", {"value": "A"}), ("call_1", "route_b", {"value": "B"})]
