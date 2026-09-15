"""Four manual ingestion job entrypoints and the operator update command."""

import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nora.config import Settings
from nora.conversion import convert as convert_one
from nora.documents import (
    publish_release,
    write_cloud_pointer,
    write_pointer,
)
from nora.indexing import connect, import_bundle, verify_bundle
from nora.preparation import embed_bundle, prepare_texts


def _release_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f") + "_" + secrets.token_hex(4)


def _publisher_gcs_client(settings: Settings):
    """Build a GCS client using the explicit publisher credential context.

    Retrieval uses normal ADC; ingestion must not silently reuse the reader
    identity. Reject a missing credential file before any upload side effects.
    """
    from nora.config import ConfigurationError

    cred_path = settings.gcs_publisher_credentials
    publisher_service_account = settings.gcs_publisher_service_account
    from google.cloud import storage

    if cred_path:
        if not cred_path.exists():
            raise ConfigurationError(f"GCS publisher credentials file not found: {cred_path}")
        credential_config = json.loads(cred_path.read_text())
        if credential_config.get("type") == "service_account" or "private_key" in credential_config:
            raise ConfigurationError(
                "Use a keyless publisher ADC configuration, not a service-account key"
            )
        from google.auth import load_credentials_from_file

        credentials, project_id = load_credentials_from_file(str(cred_path))
    elif publisher_service_account:
        import google.auth
        from google.auth import impersonated_credentials

        source_credentials, project_id = google.auth.default()
        credentials = impersonated_credentials.Credentials(
            source_credentials=source_credentials,
            target_principal=publisher_service_account,
            target_scopes=["https://www.googleapis.com/auth/devstorage.read_write"],
            lifetime=900,
        )
    else:
        raise ConfigurationError(
            "GCS activation requires NORA_GCS_PUBLISHER_CREDENTIALS_FILE or "
            "NORA_GCS_PUBLISHER_SERVICE_ACCOUNT"
        )
    return storage.Client(project=settings.gcs_project or project_id, credentials=credentials)


def run_convert(source_dir: Path, output_dir: Path) -> dict:
    """Convert selected originals to a `files/` tree of Markdown and a manifest."""
    source_dir, output_dir = source_dir.resolve(), output_dir.resolve()
    if not source_dir.is_dir():
        raise ValueError("Source must be a document directory")
    if output_dir.exists():
        if any(output_dir.iterdir()):
            raise FileExistsError("Conversion output already exists and is not empty")
    else:
        output_dir.mkdir(parents=True)
    files_dir = output_dir / "files"
    files_dir.mkdir(parents=True)
    reports = []
    for source in sorted(source_dir.rglob("*")):
        if not source.is_file() or source.is_symlink():
            continue
        relative = source.relative_to(source_dir)
        if any(p.startswith(".") for p in relative.parts):
            continue
        if source.suffix.lower() not in {".pdf", ".docx", ".html", ".pptx", ".xlsx", ".md", ".txt"}:
            reports.append(
                {"source": str(relative), "skipped": True, "reason": "unsupported_format"}
            )
            continue
        name = relative.with_suffix(".md").as_posix().replace("/", "__")
        target = files_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            if source.suffix.lower() in {".md", ".txt"}:
                text = source.read_text(encoding="utf-8")
                target.write_text(text, encoding="utf-8")
                provenance = {"source_sha256": _sha256_file(source)}
            else:
                import tempfile as _tf

                with _tf.TemporaryDirectory(prefix=".nora-docling-", dir=files_dir) as tmp:
                    stage = Path(tmp) / "stage"
                    provenance = convert_one(source, stage)
                    (stage / "document.md").rename(target)
            reports.append(
                {
                    "source": str(relative),
                    "converted": str(target.relative_to(output_dir)),
                    "source_sha256": provenance["source_sha256"],
                }
            )
        except Exception as error:
            reports.append({"source": str(relative), "failed": True, "error": str(error)})
    if not any(r.get("converted") for r in reports):
        raise ValueError("No documents were converted")
    manifest = {"stage": "convert", "files_dir": "files", "reports": reports}
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def run_prepare(extracted_dir: Path, release_dir: Path, tokenizer) -> dict:
    """Deterministic normalization and chunking from converted files."""
    extracted_dir, release_dir = extracted_dir.resolve(), release_dir.resolve()
    manifest_path = extracted_dir / "manifest.json"
    if not manifest_path.exists():
        raise ValueError("Conversion stage manifest missing")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("stage") != "convert":
        raise ValueError("Input is not a completed conversion stage")
    files_dir = extracted_dir / manifest.get("files_dir", "files")
    if not files_dir.is_dir():
        raise ValueError("Converted files directory missing")
    coverage = prepare_texts(files_dir, release_dir, tokenizer)
    (release_dir / "job-prepare.json").write_text(
        json.dumps(
            {"stage": "prepare", "input_manifest_sha256": _sha256_file(manifest_path)}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    return coverage


def run_embed(release_dir: Path, encoder, *, qdrant_collection: str | None = None) -> dict:
    """Encode chunks through the shared BGE service."""
    release_dir = release_dir.resolve()
    prepare_report = release_dir / "job-prepare.json"
    if not prepare_report.exists():
        raise ValueError("Prepare stage did not complete")
    coverage_path = release_dir / "coverage.json"
    if not coverage_path.exists():
        raise ValueError("Release coverage missing")
    coverage = json.loads(coverage_path.read_text())
    if coverage.get("phase") != "prepared":
        raise ValueError("Release is not in the prepared-text state")
    coverage = embed_bundle(release_dir, encoder, qdrant_collection=qdrant_collection)
    (release_dir / "job-embed.json").write_text(
        json.dumps({"stage": "embed", "qdrant_collection": qdrant_collection}, indent=2) + "\n",
        encoding="utf-8",
    )
    return coverage


def run_import_verify(release_dir: Path, settings: Settings) -> dict:
    """Import an embedded bundle into Qdrant and independently verify it."""
    release_dir = release_dir.resolve()
    embed_report = release_dir / "job-embed.json"
    if not embed_report.exists():
        raise ValueError("Embed stage did not complete")
    coverage = json.loads((release_dir / "coverage.json").read_text())
    collection = coverage.get("qdrant_collection")
    if not collection:
        collection = settings.collection
        coverage["qdrant_collection"] = collection
        (release_dir / "coverage.json").write_text(
            json.dumps(coverage, indent=2) + "\n", encoding="utf-8"
        )
    from contextlib import closing

    with closing(connect(settings)) as client:
        imported = import_bundle(client, collection, release_dir)
        verified = verify_bundle(client, collection, release_dir)
    report = {
        "stage": "import-verify",
        "collection": collection,
        "imported": imported,
        "verified": verified,
    }
    (release_dir / "job-import.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def active_release(releases_root: Path) -> Path | None:
    current = releases_root / "current"
    if current.is_symlink():
        resolved = current.resolve()
        if resolved.is_dir():
            return resolved
    return None


def knowledge_update(
    source_dir: Path,
    releases_root: Path,
    settings: Settings,
    encoder: Any,
    *,
    collection: str | None = None,
    gcs_client=None,
) -> dict:
    """Run the four jobs in order, validate, and activate the new release."""
    releases_root = releases_root.resolve()
    releases_root.mkdir(parents=True, exist_ok=True)

    if settings.gcs_pointer:
        from nora.config import ConfigurationError
        from nora.documents import parse_gs_url

        pointer_bucket, pointer_object = parse_gs_url(settings.gcs_pointer)
        bucket = settings.gcs_bucket
        if not bucket:
            raise ConfigurationError("GCS activation requires NORA_GCS_BUCKET")
        if bucket != pointer_bucket:
            raise ConfigurationError("NORA_GCS_BUCKET must match the bucket in NORA_GCS_POINTER")
        prefix = settings.gcs_prefix
        if prefix is None:
            raise ConfigurationError("GCS activation requires NORA_GCS_PREFIX")
        client = gcs_client if gcs_client is not None else _publisher_gcs_client(settings)

    release_dir = releases_root / _release_id()
    if release_dir.exists():
        raise FileExistsError("Release identifier collision")
    release_dir.mkdir(parents=True)
    extracted = release_dir / "extracted"
    prepared = release_dir / "prepared"
    collection = collection or f"{settings.collection}_{release_dir.name}"

    run_convert(source_dir, extracted)
    run_prepare(extracted, prepared, encoder.tokenizer)
    run_embed(prepared, encoder, qdrant_collection=collection)
    run_import_verify(prepared, settings)
    if settings.gcs_pointer:
        pointer = activate_cloud(
            releases_root, prepared, bucket, prefix, pointer_object, client, collection=collection
        )
        return {
            "release": str(prepared),
            "collection": collection,
            "activated": True,
            "pointer": pointer,
        }
    activate(releases_root, prepared)
    return {
        "release": str(prepared),
        "collection": collection,
        "activated": True,
    }


def _sha256_file(path: Path) -> str:
    from nora.common import digest

    return digest(path.read_bytes())


def _releases_history(releases_root: Path) -> list[Path]:
    """Return activated release directories in order (oldest first)."""
    releases_root = releases_root.resolve()
    history = releases_root / ".history"
    if not history.exists():
        return []
    lines = [
        line.strip() for line in history.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    result = []
    for line in lines:
        path = releases_root / line
        if path.is_dir() and (path / "job-import.json").exists():
            result.append(path)
    return result


def _record_activation(releases_root: Path, release_dir: Path):
    """Append a validated release to the local activation history log."""
    releases_root, release_dir = releases_root.resolve(), release_dir.resolve()
    if not release_dir.is_relative_to(releases_root):
        raise ValueError("Release is outside the releases root")
    history = releases_root / ".history"
    history.parent.mkdir(parents=True, exist_ok=True)
    with history.open("a", encoding="utf-8") as log:
        log.write(release_dir.relative_to(releases_root).as_posix() + "\n")


def _pointer_generation(bucket: str, object_name: str, client) -> int:
    """Return the current generation of a cloud pointer, or 0 if it does not exist."""
    # Injected test doubles expose a fast path for generation-aware verification.
    if hasattr(client, "_current_generation"):
        return client._current_generation(bucket, object_name)
    blob = client.bucket(bucket).blob(object_name)
    try:
        blob.reload(timeout=10)
    except Exception as error:
        from google.api_core.exceptions import NotFound

        if isinstance(error, NotFound):
            return 0
        raise
    return blob.generation


def _cloud_history_path(releases_root: Path) -> Path:
    return releases_root.resolve() / ".history-gcs"


def _cloud_history(releases_root: Path) -> list[dict]:
    path = _cloud_history_path(releases_root)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_cloud_history(releases_root: Path, history: list[dict]):
    path = _cloud_history_path(releases_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / (path.name + ".tmp." + uuid.uuid4().hex)
    tmp.write_text(
        "".join(json.dumps(entry, indent=None) + "\n" for entry in history), encoding="utf-8"
    )
    os.replace(tmp, path)


def _record_cloud_activation(releases_root: Path, release_dir: Path, manifest: dict):
    """Record a cloud activation so rollback can return to the previous manifest."""
    history = _cloud_history(releases_root)
    history.append(
        {
            "release_dir": release_dir.relative_to(releases_root.resolve()).as_posix(),
            "manifest_object": manifest["manifest_object"],
            "manifest_generation": manifest["manifest_generation"],
            "bucket": manifest["bucket"],
            "prefix": manifest["prefix"],
        }
    )
    _write_cloud_history(releases_root, history)


def activate_cloud(
    releases_root: Path,
    release_dir: Path,
    bucket: str,
    prefix: str,
    pointer_object: str,
    client,
    *,
    collection: str | None = None,
) -> dict:
    """Publish a release and atomically update the authoritative cloud pointer."""
    releases_root, release_dir = releases_root.resolve(), release_dir.resolve()
    if not release_dir.is_dir():
        raise ValueError("Release is not a directory")
    if not (release_dir / "job-import.json").exists():
        raise ValueError("Release has not passed import/verify")
    coverage = json.loads((release_dir / "coverage.json").read_text())
    collection = collection or coverage.get("qdrant_collection")
    if not collection:
        raise ValueError("Release coverage has no Qdrant collection")

    manifest = publish_release(release_dir, bucket, prefix, client, collection=collection)
    expected = _pointer_generation(bucket, pointer_object, client)
    pointer = write_cloud_pointer(
        bucket, pointer_object, manifest, client, expected_generation=expected
    )
    _record_cloud_activation(releases_root, release_dir, manifest)

    current = releases_root / "current"
    tmp = releases_root / ("current.tmp." + uuid.uuid4().hex)
    # Use a relative target so the symlink stays valid when the releases root is
    # bind-mounted at a different host path inside a container.
    tmp.symlink_to(release_dir.relative_to(releases_root).as_posix())
    os.replace(tmp, current)
    _record_activation(releases_root, release_dir)
    return pointer


def rollback_cloud(
    releases_root: Path,
    bucket: str,
    pointer_object: str,
    client,
) -> dict:
    """Activate the previous release by rewinding the cloud pointer."""
    releases_root = releases_root.resolve()
    history = _cloud_history(releases_root)
    if len(history) < 2:
        raise ValueError("No previous cloud release available for rollback")
    previous_entry = history[-2]
    expected = _pointer_generation(bucket, pointer_object, client)

    previous_manifest = {
        "bucket": previous_entry["bucket"],
        "prefix": previous_entry.get("prefix", ""),
        "manifest_object": previous_entry["manifest_object"],
        "manifest_generation": previous_entry["manifest_generation"],
    }
    pointer = write_cloud_pointer(
        bucket, pointer_object, previous_manifest, client, expected_generation=expected
    )

    previous_dir = releases_root / previous_entry["release_dir"]
    current = releases_root / "current"
    tmp = releases_root / ("current.tmp." + uuid.uuid4().hex)
    # Use a relative target so the symlink stays valid when the releases root is
    # bind-mounted at a different host path inside a container.
    tmp.symlink_to(previous_dir.relative_to(releases_root).as_posix())
    os.replace(tmp, current)

    _write_cloud_history(releases_root, history[:-1])
    return pointer


def activate(
    releases_root: Path,
    release_dir: Path,
    *,
    gcs_manifest_path: Path | None = None,
    gcs_pointer: tuple[str, str] | None = None,
    gcs_client=None,
    bucket: str | None = None,
    prefix: str | None = None,
) -> Path | dict:
    """Atomically switch the `current` symlink and optional GCS pointer."""
    releases_root, release_dir = releases_root.resolve(), release_dir.resolve()
    if not release_dir.is_dir():
        raise ValueError("Release is not a directory")
    if not (release_dir / "job-import.json").exists():
        raise ValueError("Release has not passed import/verify")
    coverage = json.loads((release_dir / "coverage.json").read_text())
    collection = coverage.get("qdrant_collection")
    if not collection:
        raise ValueError("Release coverage has no Qdrant collection")

    if gcs_pointer is not None and gcs_client is None:
        raise ValueError("GCS client is required when a GCS pointer is provided")

    if gcs_pointer is not None:
        pointer_bucket, pointer_object = gcs_pointer
        return activate_cloud(
            releases_root,
            release_dir,
            pointer_bucket,
            prefix or "",
            pointer_object,
            gcs_client,
            collection=collection,
        )

    if gcs_manifest_path is not None:
        if gcs_client is None:
            raise ValueError("GCS client is required when a GCS manifest path is provided")
        manifest = publish_release(
            release_dir,
            bucket or "",
            prefix or "",
            gcs_client,
            collection=collection,
        )
        write_pointer(gcs_manifest_path, manifest)

    current = releases_root / "current"
    tmp = releases_root / ("current.tmp." + uuid.uuid4().hex)
    # Use a relative target so the symlink stays valid when the releases root is
    # bind-mounted at a different host path inside a container.
    tmp.symlink_to(release_dir.relative_to(releases_root).as_posix())
    os.replace(tmp, current)
    _record_activation(releases_root, release_dir)
    return current


def rollback(
    releases_root: Path,
    *,
    gcs_pointer: tuple[str, str] | None = None,
    gcs_client=None,
) -> Path | dict:
    """Atomically activate the previous release in the local history log or cloud pointer."""
    releases_root = releases_root.resolve()
    if gcs_pointer is not None:
        if gcs_client is None:
            raise ValueError("GCS client is required for cloud rollback")
        bucket, pointer_object = gcs_pointer
        return rollback_cloud(releases_root, bucket, pointer_object, gcs_client)

    history = _releases_history(releases_root)
    current = active_release(releases_root)
    if current is None:
        raise ValueError("No active release to roll back from")
    try:
        index = history.index(current.resolve())
    except ValueError:
        index = len(history) - 1
    if index <= 0:
        raise ValueError("No previous release available for rollback")
    previous = history[index - 1]
    return activate(releases_root, previous)
