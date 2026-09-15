#!/usr/bin/env python3
"""Helper utilities for offline Google Cloud plan rendering.

Usage:
    python3 helpers.py <config_path> <output_plan_path>

The script reads the environment‑style config file, validates required fields
and produces a plain‑text plan describing the resources that *would* be created.
No external network calls are performed.
"""

import re
import sys
from pathlib import Path

# Allowed configuration keys – any other key is considered unknown.
ALLOWED_KEYS = {
    "PROJECT_ID",
    "REGION",
    "ZONE",
    "VECTOR_DB",
    "MACHINE_TYPE",
    "DISK_SIZE_GB",
    "BACKUP_BUCKET_NAME",
}

# Qdrant is the accepted database for this setup.
ALLOWED_VECTOR_DBS = {"qdrant"}

# Regex patterns – flexible enough to accept all current GCP region/zone shapes.
PROJECT_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
REGION_RE = re.compile(r"^[a-z]+-[a-z]+[0-9]+$")          # e.g. us-central1, europe-west1
ZONE_RE = re.compile(r"^[a-z]+-[a-z]+[0-9]+-[a-z]$")     # e.g. us-central1-a
MACHINE_TYPE_RE = re.compile(r"^[a-z0-9\-]+$")
DISK_SIZE_RE = re.compile(r"^[1-9][0-9]*$")  # positive integer
BUCKET_RE = re.compile(r"^[a-z0-9\-]+$")

def load_config(path: Path) -> dict:
    """Parse a simple KEY=VALUE env file.
    - Ignores comments and blank lines.
    - Detects duplicate keys and unknown keys.
    Returns a dict of stripped key/value strings.
    """
    config = {}
    with path.open() as f:
        for lineno, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                raise ValueError(f"Malformed line {lineno} in config: '{raw_line.rstrip()}'")
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            if key in config:
                raise ValueError(f"Duplicate configuration key '{key}' on line {lineno}.")
            if key not in ALLOWED_KEYS:
                raise ValueError(f"Unknown configuration key '{key}' on line {lineno}.")
            config[key] = value
    return config

def validate_config(cfg: dict) -> None:
    """Validate required fields, basic shapes, and cross‑field consistency.
    Raises ValueError with a helpful message on failure.
    """
    # Required keys (project, region, zone) must be present and non‑empty
    for key in sorted(ALLOWED_KEYS):
        if not cfg.get(key):
            raise ValueError(f"Missing required configuration: {key}")

    # Basic shape checks
    if not PROJECT_RE.fullmatch(cfg["PROJECT_ID"]):
        raise ValueError("PROJECT_ID must be 6-30 lowercase letters/digits/hyphens, start with a letter and end with a letter or digit.")
    if not REGION_RE.fullmatch(cfg["REGION"]):
        raise ValueError("REGION has an invalid format (e.g., us-central1 or europe-west1).")
    if not ZONE_RE.fullmatch(cfg["ZONE"]):
        raise ValueError("ZONE has an invalid format (e.g., us-central1-a).")
    # Zone must start with region + '-'
    if not cfg["ZONE"].startswith(cfg["REGION"] + "-"):
        raise ValueError(f"ZONE must belong to REGION (zone should start with {cfg['REGION']}-).")

    # VECTOR_DB validation (selected Qdrant only)
    vector = cfg.get("VECTOR_DB", "")
    if vector not in ALLOWED_VECTOR_DBS:
        raise ValueError('VECTOR_DB must be "qdrant" (case‑sensitive).')

    # Optional machine type validation – if provided, must match pattern
    if cfg.get("MACHINE_TYPE"):
        if not MACHINE_TYPE_RE.fullmatch(cfg["MACHINE_TYPE"]):
            raise ValueError("MACHINE_TYPE may contain only lowercase letters, numbers, or hyphens.")

    # Optional disk size validation – if provided, must be a positive integer
    if cfg.get("DISK_SIZE_GB"):
        if not DISK_SIZE_RE.fullmatch(cfg["DISK_SIZE_GB"]):
            raise ValueError("DISK_SIZE_GB must be a positive integer.")

    # Optional bucket name validation – if provided, must match bucket naming rules
    if cfg.get("BACKUP_BUCKET_NAME"):
        if not BUCKET_RE.fullmatch(cfg["BACKUP_BUCKET_NAME"]):
            raise ValueError("BACKUP_BUCKET_NAME may contain only lowercase letters, numbers, or hyphens.")

def generate_plan(cfg: dict) -> str:
    """Create a human‑readable plan description based on the config.
    The plan is deliberately high‑level and does not contain any secret values.
    """
    lines = []
    lines.append(
        f"Project: {cfg['PROJECT_ID']} (region: {cfg['REGION']}, zone: {cfg['ZONE']})"
    )

    # GCS bucket – explicit name or derived default
    bucket_name = cfg["BACKUP_BUCKET_NAME"]
    lines.append(f"- Create GCS bucket: gs://{bucket_name}")

    # Service Account placeholder
    sa_email = f"nora-agent-sa@{cfg['PROJECT_ID']}.iam.gserviceaccount.com"
    lines.append(f"- Prepare Service Account: {sa_email}")

    # Secret Manager placeholder
    lines.append("- Reserve Secret Manager secret: nora-api-key (placeholder, no value stored)")

    # IAM binding description
    lines.append("- IAM: Grant the Service Account 'roles/storage.objectAdmin' on the bucket")

    # Vector DB description – only Qdrant is supported
    vector = cfg.get('VECTOR_DB', '')
    if vector:
        lines.append(
            f"- Vector DB: Deploy {vector} instance (pin version 1.19.1, data stored at /qdrant/storage, accessible only via localhost)"
        )
    else:
        lines.append("- Vector DB: None selected (skip)")

    # Compute Engine details – optional
    if cfg.get('MACHINE_TYPE') and cfg.get('DISK_SIZE_GB'):
        lines.append(
            f"- Compute Engine VM: type={cfg['MACHINE_TYPE']}, dedicated-data-disk={cfg['DISK_SIZE_GB']}GiB"
        )
    else:
        lines.append("- Compute Engine VM: Configuration omitted (optional)")

    lines.extend([
        "- Extraction: Docling (selected; application component not installed by this bundle).",
        "- Embeddings: self-hosted BAAI/bge-base-en-v1.5, English first version; cloud worker not deployed.",
        "- Integration framework: LangChain (selected; application wiring still to implement).",
        "- BGE evidence: Mac speed advantage only; retrieval quality and Google Cloud performance unverified.",
        "- Mount dedicated data disk at /mnt/disks/nora-qdrant; bind storage/snapshots into Qdrant. Boot disk is separate.",
        "- Back up Qdrant application snapshots as GCS objects; GCS is not the live database filesystem.",
        "- Use VM identity with access limited to this backup bucket and the specific Qdrant Secret Manager secret.",
        "- Access through IAP SSH tunnel; no external VM IP or public Qdrant port. Provisioning/egress design remains deferred.",
        "- Compose template: qdrant-compose.yml; pinned 1.19.1, loopback 6333/6334, generated secret configuration required.",
    ])
    lines.append("")
    lines.append("# NOTE: This plan is offline only. No resources are created.")
    return "\n".join(lines)

def write_plan(cfg: dict, output_path: Path) -> None:
    """Validate the config and write the plan to *output_path* using exclusive
    creation. If the file already exists, a FileExistsError is raised.
    """
    validate_config(cfg)
    plan_text = generate_plan(cfg)
    # Exclusive creation – fails if file exists
    with output_path.open('x') as fp:
        fp.write(plan_text)

def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: helpers.py <config_path> <output_plan_path>", file=sys.stderr)
        sys.exit(1)
    config_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    try:
        cfg = load_config(config_path)
        write_plan(cfg, output_path)
    except Exception as e:
        print(f"❌ Error while generating plan: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
