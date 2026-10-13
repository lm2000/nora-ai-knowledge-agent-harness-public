"""LiteLLM gateway launcher with explicit mounted-ASGI lifespan ownership.

Uses public ASGI app/router interfaces, without patching LiteLLM session-manager
internals. The MCP sub-application is loaded before serving client requests.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path


def read_credential(variable: str, default: str) -> str:
    value = Path(os.environ.get(variable, default)).read_text().strip()
    if not value or any(char in value for char in "\r\n\0"):
        raise ValueError(f"Invalid credential file for {variable}")
    return value


def create_app():
    import httpx
    from starlette.routing import Mount

    os.environ["LITELLM_MASTER_KEY"] = read_credential(
        "NIS_GATEWAY_TOKEN_FILE", "/run/secrets/gateway"
    )
    os.environ["NIS_UPSTREAM_TOKEN"] = read_credential(
        "NIS_UPSTREAM_TOKEN_FILE", "/run/secrets/internal"
    )
    os.environ.setdefault("CONFIG_FILE_PATH", "/app/gateway.yaml")

    from litellm.proxy.proxy_server import app

    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with original_lifespan(application):
            # This metadata route loads LiteLLM's lazy MCP app without opening
            # a client session or executing a tool/model request.
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://localhost",
                headers={"x-litellm-api-key": "Bearer " + os.environ["LITELLM_MASTER_KEY"]},
            ) as client:
                response = await client.get("/mcp/enabled")
                response.raise_for_status()
            mounted = next(
                (
                    route.app
                    for route in application.routes
                    if isinstance(route, Mount) and route.path == "/mcp"
                ),
                None,
            )
            if mounted is None or not hasattr(mounted, "router"):
                raise RuntimeError("LiteLLM MCP application mount is unavailable")
            # Enter and exit the mounted application's public lifespan in this
            # same task, before the parent gateway shuts down.
            async with mounted.router.lifespan_context(mounted):
                yield

    app.router.lifespan_context = lifespan
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "4000")))
