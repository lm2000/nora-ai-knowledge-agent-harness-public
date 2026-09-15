"""Shared HTTP BGE service: one pinned model, bounded concurrency, query capacity preserved."""

import asyncio
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from nora.auth import BearerAuth, BodyLimit
from nora.config import Settings, credential
from nora.embedding import BGEEncoder


class Capacity:
    """Bounded admission: reject if too many queued, otherwise wait for a slot."""

    def __init__(self, max_inflight: int, max_queued: int, label: str, timeout: float):
        self.max_inflight = max_inflight
        self.max_queued = max_queued
        self.label = label
        self.timeout = timeout
        self._inflight = 0
        self._queued = 0
        self._lock = asyncio.Lock()
        self._cond = asyncio.Condition(self._lock)

    async def acquire(self):
        async with self._lock:
            if self._queued >= self.max_queued:
                raise HTTPException(503, f"BGE {self.label} queue full; throttle batch work")
            self._queued += 1
        try:
            async with self._lock:
                if self._inflight >= self.max_inflight:
                    try:
                        await asyncio.wait_for(self._cond.wait(), timeout=self.timeout)
                    except asyncio.TimeoutError as error:
                        raise HTTPException(503, f"BGE {self.label} capacity timeout") from error
                if self._inflight >= self.max_inflight:
                    raise HTTPException(503, f"BGE {self.label} capacity unavailable")
                self._inflight += 1
                self._queued -= 1
        except BaseException:
            async with self._lock:
                self._queued = max(0, self._queued - 1)
            raise

    def release(self):
        async def _release():
            async with self._lock:
                self._inflight = max(0, self._inflight - 1)
                self._cond.notify()

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_release())
        except RuntimeError:
            pass

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.release()
        return False


class EncodeRequest(BaseModel):
    texts: list[str] = Field(min_length=1)
    query: bool = False


class EncodeResponse(BaseModel):
    vectors: list[list[float]]


def create_app(
    settings: Settings | None = None,
    encoder: Any | None = None,
    *,
    token: str | None = None,
):
    settings = settings or Settings.from_env()
    token = credential("BGE_TOKEN") if token is None else token
    if encoder is None:
        encoder = BGEEncoder(settings.model_path).initialize()

    max_batch_size = max(
        1, int(os.environ.get("NORA_BGE_MAX_BATCH_SIZE", settings.bge_max_batch_size))
    )
    query_concurrency = max(1, int(os.environ.get("NORA_BGE_QUERY_CONCURRENCY", "3")))
    batch_concurrency = max(1, int(os.environ.get("NORA_BGE_BATCH_CONCURRENCY", "3")))
    total_concurrency = max(1, int(os.environ.get("NORA_BGE_TOTAL_CONCURRENCY", "5")))
    max_queue = max(0, int(os.environ.get("NORA_BGE_MAX_QUEUE", "8")))
    query_timeout = max(1.0, float(os.environ.get("NORA_BGE_QUERY_TIMEOUT", "10")))
    batch_timeout = max(
        1.0, float(os.environ.get("NORA_BGE_BATCH_TIMEOUT", str(settings.bge_timeout)))
    )

    query_cap = Capacity(query_concurrency, max_queue, "query", query_timeout)
    batch_cap = Capacity(batch_concurrency, max_queue, "batch", batch_timeout)
    total_cap = Capacity(
        total_concurrency, max_queue * 2, "total", max(query_timeout, batch_timeout)
    )

    app = FastAPI()
    app.add_middleware(BearerAuth, token=token)
    app.add_middleware(BodyLimit, limit=70000)

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "ready": True,
            "model": getattr(encoder, "_model", None) is not None,
        }

    @app.post("/encode", response_model=EncodeResponse)
    async def encode(request: EncodeRequest):
        if not request.texts:
            raise HTTPException(400, "texts must not be empty")
        if len(request.texts) > max_batch_size:
            raise HTTPException(
                413,
                f"Batch size {len(request.texts)} exceeds limit {max_batch_size}",
            )
        cap = query_cap if request.query else batch_cap
        try:
            async with cap, total_cap:
                loop = asyncio.get_running_loop()
                vectors = await loop.run_in_executor(
                    None, lambda: encoder.encode(request.texts, query=request.query)
                )
                return {"vectors": vectors.tolist()}
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(500, f"Encoding failed: {error}") from error

    return app
