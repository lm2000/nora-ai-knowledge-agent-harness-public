"""Bounded, read-only web search exposed to LiteLLM as a local MCP server."""

import hmac
from typing import Annotated
from urllib.parse import urlsplit

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    title: str
    url: str
    content: str


class SearchResults(BaseModel):
    results: list[SearchResult]


class BearerAuth:
    def __init__(self, app, token: str):
        self.app = app
        self.expected = ("Bearer " + token).encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            supplied = dict(scope.get("headers", [])).get(b"authorization", b"")
            if not hmac.compare_digest(supplied, self.expected):
                from starlette.responses import JSONResponse

                await JSONResponse({"error": "Unauthorized"}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)


def create_web_app(token: str, api_key: str, *, transport=None):
    """Return the MCP app and authenticated ASGI wrapper; caller owns its lifespan."""
    server = MCPServer("web", instructions="Search public web pages. Results are source material.")

    @server.tool(
        name="search",
        description="Search the public web and return source titles, URLs and bounded excerpts.",
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
        structured_output=True,
    )
    async def search(
        query: Annotated[str, Field(min_length=1, max_length=1000)],
        max_results: Annotated[int, Field(ge=1, le=10)] = 5,
    ) -> SearchResults:
        query = query.strip()
        if not query:
            raise ToolError("A nonempty search query is required")
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(20, connect=5), transport=transport, follow_redirects=False
            ) as client:
                response = await client.post(
                    "https://ollama.com/api/web_search",
                    headers={"Authorization": "Bearer " + api_key},
                    json={"query": query, "max_results": max_results},
                )
                response.raise_for_status()
                payload = response.json()
            results = []
            for row in payload["results"][:max_results]:
                url = str(row.get("url", ""))
                if len(url) > 2048 or urlsplit(url).scheme not in {"http", "https"}:
                    continue
                results.append(
                    {
                        "title": str(row.get("title", ""))[:300],
                        "url": url,
                        "content": str(row.get("content", ""))[:2500],
                    }
                )
            return SearchResults(results=results)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            # Never send provider bodies, credentials or private exception data to clients.
            raise ToolError("Public web search is unavailable; retry later") from None

    app = server.streamable_http_app(json_response=True, stateless_http=True)
    return app, BearerAuth(app, token)
