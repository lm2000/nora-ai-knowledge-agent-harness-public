"""MCP client with protocol initialization, bounded time and explicit errors."""

import asyncio
import contextvars
import json
from contextlib import asynccontextmanager

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


class KnowledgeUnavailable(RuntimeError):
    pass


_RELEASE_PIN = contextvars.ContextVar("nora_release_pin", default=None)


class KnowledgeClient:
    def __init__(self, url: str, token: str, timeout: int = 45):
        self.url, self.token, self.timeout = url, token, timeout

    def _headers(self):
        headers = {"Authorization": "Bearer " + self.token}
        pinned = _RELEASE_PIN.get()
        if pinned:
            headers["X-Nora-Release"] = pinned
        return headers

    async def _active_release(self) -> dict:
        url = self.url.rsplit("/", 1)[0] + "/release"
        async with httpx2.AsyncClient(timeout=min(self.timeout, 5)) as http:
            response = await http.get(url, headers={"Authorization": "Bearer " + self.token})
            response.raise_for_status()
            return response.json()

    async def call(self, name: str, arguments: dict) -> dict:
        if name not in {"search", "read"}:
            raise ValueError("Unknown knowledge operation")
        # Resolve and pin the active release on the first call in this context.
        if _RELEASE_PIN.get() is None:
            release = await self._active_release()
            if release.get("release"):
                _RELEASE_PIN.set(release["release"])
        try:
            async with asyncio.timeout(self.timeout):
                async with httpx2.AsyncClient(
                    headers=self._headers(), timeout=self.timeout
                ) as http:
                    async with streamable_http_client(self.url, http_client=http) as (
                        reader,
                        writer,
                    ):
                        async with ClientSession(reader, writer) as session:
                            await session.initialize()
                            result = await session.call_tool(name, arguments)
                            if result.is_error:
                                raise KnowledgeUnavailable("Knowledge tool failed")
                            if result.structured_content is not None:
                                return result.structured_content
                            payload = json.loads(
                                next(block.text for block in result.content if block.type == "text")
                            )
                            if not isinstance(payload, dict):
                                raise KnowledgeUnavailable("Invalid knowledge response")
                            return payload
        except (TimeoutError, OSError, ValueError) as error:
            raise KnowledgeUnavailable("Knowledge request failed") from error

    async def health(self) -> dict:
        url = self.url.rsplit("/", 1)[0] + "/health"
        async with httpx2.AsyncClient(timeout=min(self.timeout, 5)) as http:
            response = await http.get(url, headers={"Authorization": "Bearer " + self.token})
            response.raise_for_status()
            return response.json()

    @asynccontextmanager
    async def pinned(self):
        """Clear any existing per-context release pin on entry and exit."""
        token = _RELEASE_PIN.set(None)
        try:
            yield self
        finally:
            _RELEASE_PIN.reset(token)
