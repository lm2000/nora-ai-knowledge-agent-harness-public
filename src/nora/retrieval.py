"""Shared retrieval service. Use the application factory to start dependencies."""

import contextvars
import json
from pathlib import Path
from typing import Protocol

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from qdrant_client import models
from starlette.responses import JSONResponse
from starlette.routing import Route

from nora.auth import BearerAuth
from nora.bge_client import BGEClient
from nora.common import sparse
from nora.config import Settings, credential
from nora.documents import (
    DocumentStore as _DocumentStore,
)
from nora.documents import (
    GCSDocumentStore,
    LocalDocumentStore,
    load_manifest_from_pointer_entry,
    parse_gs_url,
    passage,
    read_cloud_pointer,
)
from nora.indexing import connect

RELEASE_PIN = contextvars.ContextVar("nora_release", default=None)


class Release(Protocol):
    @property
    def collection(self) -> str: ...

    def coverage(self) -> dict: ...

    def document_store(self) -> _DocumentStore: ...


class LocalRelease:
    def __init__(self, path: Path):
        self.path = path.resolve()
        self._coverage: dict | None = None

    def coverage(self) -> dict:
        if self._coverage is None:
            coverage_path = self.path / "coverage.json"
            self._coverage = json.loads(coverage_path.read_text()) if coverage_path.exists() else {}
        return self._coverage

    @property
    def collection(self) -> str:
        return self.coverage().get("qdrant_collection", "")

    def document_store(self) -> _DocumentStore:
        return LocalDocumentStore(self.path / "docs")


class GCSRelease:
    def __init__(self, manifest: dict, client):
        self.manifest = manifest
        self.client = client

    def coverage(self) -> dict:
        return {
            **self.manifest.get("coverage", {}),
            "phase": "embedded",
            "representation": self.manifest.get("representation", {}),
        }

    @property
    def collection(self) -> str:
        return self.manifest.get("collection", "")

    def document_store(self) -> _DocumentStore:
        return GCSDocumentStore(self.manifest, self.client)


def _gcs_client(settings: Settings, provided=None):
    if provided is not None:
        return provided
    from google.cloud import storage

    return storage.Client(project=settings.gcs_project)


def _release_id(release: Release) -> str:
    if isinstance(release, LocalRelease):
        return str(release.path)
    if isinstance(release, GCSRelease):
        return f"{release.manifest['manifest_object']}#{release.manifest['manifest_generation']}"
    return ""


def current_release(settings: Settings, client=None) -> Release | None:
    """Resolve the authoritative active release, whether local or cloud."""
    if settings.gcs_pointer:
        bucket, object_name = parse_gs_url(settings.gcs_pointer)
        client = _gcs_client(settings, client)
        pointer = read_cloud_pointer(bucket, object_name, client)
        manifest = load_manifest_from_pointer_entry(pointer["active_manifest"], client)
        return GCSRelease(manifest, client)

    current = settings.data_dir
    if current.is_symlink():
        resolved = current.resolve()
        if resolved.is_dir() and (resolved / "job-import.json").exists():
            return LocalRelease(resolved)
    if current.is_dir() and (current / "job-import.json").exists():
        return LocalRelease(current)
    return None


def _local_pin_is_valid(pin: str, settings: Settings) -> Path | None:
    try:
        path = Path(pin).resolve()
        root = settings.releases_root.resolve()
        path.relative_to(root)
    except (ValueError, RuntimeError):
        return None
    if not (path / "job-import.json").exists():
        return None
    return path


def _gcs_pin_is_valid(pin: str, settings: Settings, client) -> GCSRelease | None:
    bucket, pointer_object = parse_gs_url(settings.gcs_pointer)
    try:
        pointer = read_cloud_pointer(bucket, pointer_object, client)
    except Exception:
        return None
    prefix = pointer.get("prefix", "")
    # Accept the active manifest or any earlier generation-pinned manifest under the same prefix.
    if "#" in pin:
        object_name, _, generation = pin.rpartition("#")
        if not object_name.startswith(prefix):
            return None
        try:
            manifest = load_manifest_from_pointer_entry(
                {"bucket": bucket, "object": object_name, "generation": int(generation)}, client
            )
            return GCSRelease(manifest, client)
        except Exception:
            return None
    return None


def pinned_release(settings: Settings, pin: str, client=None) -> Release | None:
    """Return a validated pinned release, or None if the pin is untrusted or invalid."""
    if not pin:
        return None
    if settings.gcs_pointer:
        client = _gcs_client(settings, client)
        return _gcs_pin_is_valid(pin, settings, client)
    path = _local_pin_is_valid(pin, settings)
    return LocalRelease(path) if path else None


def resolved_release(settings: Settings, client=None) -> Release | None:
    """Pinned release wins; otherwise resolve the authoritative active release."""
    pin = RELEASE_PIN.get()
    if pin:
        release = pinned_release(settings, pin, client)
        if release is not None:
            return release
    return current_release(settings, client)


class RetrievalService:
    def __init__(
        self,
        client,
        encoder,
        store=None,
        *,
        collection: str,
        data_dir: Path,
        settings: Settings | None = None,
        gcs_client=None,
    ):
        self.client, self.encoder, self.store = client, encoder, store
        self.collection, self.data_dir = collection, data_dir
        self.settings = settings
        self._gcs_client = gcs_client

    def _release(self) -> Release | None:
        if self.settings is not None:
            release = resolved_release(self.settings, self._gcs_client)
            if release is not None:
                return release
        if self.store is not None:
            # Test fallback: an explicit prepared bundle passed directly into the service.
            if self.data_dir.is_dir() and (self.data_dir / "coverage.json").exists():
                return LocalRelease(self.data_dir)
            return None
        return None

    def search(self, query: str, limit: int = 5) -> dict:
        release = self._release()
        if release is None:
            raise RuntimeError("No active release for search")
        query = query.strip()[:1500]
        if not query:
            raise ValueError("Search query must not be empty")
        limit = max(1, min(limit, 6))
        vector = self.encoder.encode([query], query=True)[0].tolist()
        prefetch = [models.Prefetch(query=vector, using="dense", limit=40)]
        lexical = sparse(query)
        if lexical.indices:
            prefetch.append(models.Prefetch(query=lexical, using="lexical", limit=40))
        collection = release.collection or self.collection
        hits = self.client.query_points(
            collection,
            prefetch=prefetch,
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=40,
            with_payload=True,
        ).points
        seen, rows = set(), []
        for hit in hits:
            payload = hit.payload or {}
            doc_id = payload.get("doc_id")
            if not doc_id or doc_id in seen:
                continue
            seen.add(doc_id)
            rows.append(
                {
                    "doc_id": doc_id,
                    "heading": payload.get("heading", ""),
                    "text": payload["text"][:2600],
                    "score": hit.score,
                    "categories": payload.get("categories", []),
                }
            )
            if len(rows) >= limit:
                break
        coverage = release.coverage()
        return {
            "results": rows,
            "coverage": coverage.get("phase", "unknown"),
            "documents": coverage.get("documents", 0),
        }

    def read(self, doc_id: str, offset: int = 0, limit: int = 8000) -> dict:
        release = self._release()
        if release is None:
            raise RuntimeError("No active release for reading")
        return passage(release.document_store(), doc_id, offset, limit)

    def health(self) -> dict:
        release = self._release()
        if release is None:
            return {"ready": False, "points": 0, "documents": 0}
        collection = release.collection or self.collection
        try:
            info = self.client.get_collection(collection)
        except Exception:
            return {"ready": False, "points": 0, "documents": 0}
        coverage = release.coverage()
        return {
            "ready": info.status == models.CollectionStatus.GREEN
            and info.points_count == coverage.get("chunks", -1)
            and coverage.get("documents", 0) > 0,
            "points": info.points_count,
            "documents": coverage.get("documents", 0),
        }


class ReleasePinMiddleware:
    """Read X-Nora-Release and pin retrieval to that release for this request."""

    def __init__(self, app, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        release = None
        for name, value in scope.get("headers", []):
            if name.lower() == b"x-nora-release":
                try:
                    release = value.decode("utf-8")
                except UnicodeDecodeError:
                    pass
                break
        token = None
        if release:
            token = RELEASE_PIN.set(release)
        try:
            await self.app(scope, receive, send)
        finally:
            if token is not None:
                RELEASE_PIN.reset(token)


def create_app(
    settings: Settings | None = None,
    service: RetrievalService | None = None,
    *,
    token: str | None = None,
):
    settings = settings or Settings.from_env()
    token = credential("MCP_TOKEN") if token is None else token
    if service is None:
        service = RetrievalService(
            connect(settings),
            BGEClient.from_settings(settings),
            None,
            collection=settings.collection,
            data_dir=settings.data_dir,
            settings=settings,
        )
    mcp = MCPServer("Nora Knowledge")

    @mcp.tool()
    def search(query: str, limit: int = 5) -> dict:
        """Search prepared documents for passages; document IDs are internal metadata."""
        return service.search(query, limit)

    @mcp.tool()
    def read(doc_id: str, offset: int = 0, limit: int = 8000) -> dict:
        """Read a bounded passage using an internal document ID returned by search."""
        return service.read(doc_id, offset, limit)

    app = mcp.streamable_http_app(
        host="0.0.0.0",
        stateless_http=True,
        json_response=True,
        max_request_body_size=70000,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True, allowed_hosts=list(settings.mcp_allowed_hosts)
        ),
    )
    app.add_middleware(BearerAuth, token=token)
    app.add_middleware(ReleasePinMiddleware, settings=settings)

    def release_endpoint(request):
        release = resolved_release(settings, getattr(service, "_gcs_client", None))
        return JSONResponse(
            {
                "release": _release_id(release) if release else None,
                "collection": release.collection if release else settings.collection,
            }
        )

    def readiness(request):
        try:
            state = service.health()
            return JSONResponse(state, status_code=200 if state["ready"] else 503)
        except Exception:
            return JSONResponse({"ready": False}, status_code=503)

    app.routes.append(Route("/health", readiness, methods=["GET"]))
    app.routes.append(Route("/release", release_endpoint, methods=["GET"]))
    return app
