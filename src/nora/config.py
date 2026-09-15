"""Explicit environment configuration. Values are read only when requested."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    """An installation setting is missing or invalid."""


def credential(name: str, *, required: bool = True, env: Mapping[str, str] | None = None) -> str:
    """Read NORA_<NAME> or NORA_<NAME>_FILE without exposing its value in errors."""
    values = os.environ if env is None else env
    key = f"NORA_{name.upper()}"
    value, filename = values.get(key, "").strip(), values.get(key + "_FILE", "").strip()
    if value and filename:
        raise ConfigurationError(f"Set either {key} or {key}_FILE, not both")
    if filename:
        try:
            value = Path(filename).read_text(encoding="utf-8").strip()
        except OSError as error:
            raise ConfigurationError(f"Cannot read {key}_FILE") from error
    if not value and required:
        raise ConfigurationError(f"Configure {key} or {key}_FILE")
    if any(c in value for c in "\r\n\0"):
        raise ConfigurationError(f"Invalid multiline value for {key}")
    return value


def gs_pointer(value: str, name: str) -> str:
    """Validate a gs://bucket/object activation pointer."""
    if not value.startswith("gs://"):
        raise ConfigurationError(f"{name} must be a gs:// URL")
    rest = value[5:]
    if "/" not in rest:
        raise ConfigurationError(f"{name} must include an object path")
    bucket, _, object_name = rest.partition("/")
    if not bucket or not object_name:
        raise ConfigurationError(f"{name} must include a bucket and an object path")
    return value


def endpoint(value: str, name: str) -> str:
    try:
        parsed = urlsplit(value)
        valid = parsed.scheme in {"http", "https"} and parsed.hostname and parsed.port != 0
    except ValueError:
        valid = False
    if not valid or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigurationError(f"{name} must be an HTTP(S) URL without embedded credentials")
    return value.rstrip("/")


def _float(values: Mapping[str, str], name: str, default: float) -> float:
    try:
        return float(values.get(name, str(default)))
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a number") from error


def positive_int(values: Mapping[str, str], name: str, default: int) -> int:
    try:
        result = int(values.get(name, str(default)))
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a positive integer") from error
    if result <= 0:
        raise ConfigurationError(f"{name} must be a positive integer")
    return result


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(".runtime/data")
    releases_root: Path = Path(".runtime/releases")
    state_dir: Path = Path(".runtime/state")
    model_path: str = ".runtime/models/bge"
    collection: str = "nora_prepared_bge_v1"
    qdrant_url: str = "http://localhost:6333"
    retrieval_url: str = "http://localhost:8001/mcp"
    ollama_url: str = "https://ollama.com"
    ollama_model: str = "gpt-oss:20b"
    gcs_manifest: Path | None = None
    gcs_pointer: str | None = None
    gcs_project: str | None = None
    gcs_bucket: str | None = None
    gcs_prefix: str | None = None
    gcs_publisher_credentials: Path | None = None
    gcs_publisher_service_account: str | None = None
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "nora"
    postgres_user: str = "nora"
    daily_limit: int = 60
    concurrency: int = 1
    request_timeout: int = 180
    tool_timeout: int = 45
    bge_url: str = "http://localhost:8002"
    bge_timeout: int = 60
    bge_max_batch_size: int = 64
    question_limit: int = 4000
    history_turns: int = 4
    knowledge_call_limit: int = 3
    mcp_allowed_hosts: tuple[str, ...] = ("localhost:*", "127.0.0.1:*", "retrieval:*")
    role: str = "knowledge"
    # Provider adapter settings
    fireworks_url: str = "https://api.fireworks.ai/inference/v1"
    fireworks_model: str = "accounts/fireworks/models/kimi-k3"
    # Selector weights (assumptions, not measurements)
    selector_cost_weight: float = 1.0
    selector_latency_weight: float = 1.0
    selector_log_path: Path | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        e = os.environ if env is None else env
        gcs = e.get("NORA_GCS_MANIFEST", "").strip()
        pointer = e.get("NORA_GCS_POINTER", "").strip()
        project = e.get("NORA_GCS_PROJECT", "").strip() or None
        bucket = e.get("NORA_GCS_BUCKET", "").strip() or None
        prefix = e.get("NORA_GCS_PREFIX", "").strip() or None
        publisher_creds = e.get("NORA_GCS_PUBLISHER_CREDENTIALS_FILE", "").strip()
        publisher_service_account = e.get("NORA_GCS_PUBLISHER_SERVICE_ACCOUNT", "").strip() or None
        hosts = tuple(
            h.strip()
            for h in e.get("NORA_MCP_ALLOWED_HOSTS", "localhost:*,127.0.0.1:*,retrieval:*").split(
                ","
            )
            if h.strip()
        )
        collection = e.get("NORA_COLLECTION", cls.collection)
        if not collection or any(c in collection for c in "/\\\0"):
            raise ConfigurationError("NORA_COLLECTION must be a nonempty collection name")
        releases_root = Path(e.get("NORA_RELEASES_ROOT", str(cls.releases_root))).expanduser()
        data_dir = Path(e.get("NORA_DATA_DIR", str(cls.data_dir))).expanduser()
        return cls(
            data_dir=data_dir,
            releases_root=releases_root,
            state_dir=Path(e.get("NORA_STATE_DIR", str(cls.state_dir))).expanduser(),
            model_path=e.get("NORA_MODEL_PATH", cls.model_path),
            collection=collection,
            qdrant_url=endpoint(e.get("NORA_QDRANT_URL", cls.qdrant_url), "NORA_QDRANT_URL"),
            retrieval_url=endpoint(
                e.get("NORA_RETRIEVAL_URL", cls.retrieval_url), "NORA_RETRIEVAL_URL"
            ),
            ollama_url=endpoint(e.get("NORA_OLLAMA_URL", cls.ollama_url), "NORA_OLLAMA_URL"),
            ollama_model=e.get("NORA_OLLAMA_MODEL", cls.ollama_model),
            gcs_manifest=Path(gcs).expanduser() if gcs else None,
            gcs_pointer=gs_pointer(pointer, "NORA_GCS_POINTER") if pointer else None,
            gcs_project=project,
            gcs_bucket=bucket,
            gcs_prefix=prefix,
            gcs_publisher_credentials=Path(publisher_creds).expanduser()
            if publisher_creds
            else None,
            gcs_publisher_service_account=publisher_service_account,
            postgres_host=e.get("NORA_POSTGRES_HOST", cls.postgres_host),
            postgres_port=positive_int(e, "NORA_POSTGRES_PORT", cls.postgres_port),
            postgres_db=e.get("NORA_POSTGRES_DB", cls.postgres_db),
            postgres_user=e.get("NORA_POSTGRES_USER", cls.postgres_user),
            daily_limit=positive_int(e, "NORA_DAILY_LIMIT", cls.daily_limit),
            concurrency=positive_int(e, "NORA_CONCURRENCY", cls.concurrency),
            request_timeout=positive_int(e, "NORA_REQUEST_TIMEOUT", cls.request_timeout),
            tool_timeout=positive_int(e, "NORA_TOOL_TIMEOUT", cls.tool_timeout),
            question_limit=positive_int(e, "NORA_QUESTION_LIMIT", cls.question_limit),
            history_turns=positive_int(e, "NORA_HISTORY_TURNS", cls.history_turns),
            knowledge_call_limit=positive_int(
                e, "NORA_KNOWLEDGE_CALL_LIMIT", cls.knowledge_call_limit
            ),
            bge_url=endpoint(e.get("NORA_BGE_URL", cls.bge_url), "NORA_BGE_URL"),
            bge_timeout=positive_int(e, "NORA_BGE_TIMEOUT", cls.bge_timeout),
            bge_max_batch_size=positive_int(e, "NORA_BGE_MAX_BATCH_SIZE", cls.bge_max_batch_size),
            mcp_allowed_hosts=hosts,
            role=e.get("NORA_ROLE", cls.role),
            fireworks_url=endpoint(
                e.get("NORA_FIREWORKS_URL", cls.fireworks_url), "NORA_FIREWORKS_URL"
            ),
            fireworks_model=e.get("NORA_FIREWORKS_MODEL", cls.fireworks_model),
            selector_cost_weight=_float(e, "NORA_SELECTOR_COST_WEIGHT", cls.selector_cost_weight),
            selector_latency_weight=_float(
                e, "NORA_SELECTOR_LATENCY_WEIGHT", cls.selector_latency_weight
            ),
            selector_log_path=Path(lp) if (lp := e.get("NORA_SELECTOR_LOG", "").strip()) else None,
        )
