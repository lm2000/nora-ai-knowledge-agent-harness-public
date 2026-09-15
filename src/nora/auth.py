"""Shared ASGI bearer authentication, with no credential values in responses."""

import hmac

from starlette.responses import JSONResponse


class BearerAuth:
    def __init__(self, app, token: str):
        if not token:
            raise ValueError("A bearer credential is required")
        self.app = app
        self.expected = ("Bearer " + token).encode("utf-8")

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            values = [value for key, value in scope["headers"] if key.lower() == b"authorization"]
            if len(values) != 1 or not hmac.compare_digest(values[0], self.expected):
                await JSONResponse({"error": "unauthorized"}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)


class BodyLimit:
    """Bound bytes before JSON parsing, including requests without Content-Length."""

    def __init__(self, app, limit: int = 70000):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        parts, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > self.limit:
                return await JSONResponse({"error": "request too large"}, status_code=413)(
                    scope, receive, send
                )
            parts.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        pending = True

        async def replay():
            nonlocal pending
            if pending:
                pending = False
                return {"type": "http.request", "body": b"".join(parts), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
