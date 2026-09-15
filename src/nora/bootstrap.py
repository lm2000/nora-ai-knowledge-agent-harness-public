"""Initialize local runtime credentials without replacing existing values."""

import os
import secrets
from pathlib import Path


def initialize(directory: Path) -> dict:
    if directory.is_symlink():
        raise ValueError("Runtime credential directory must not be a symlink")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    created, retained = [], []
    for name in ("postgres", "qdrant", "mcp", "internal", "ollama", "bge"):
        path = directory / name
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            if path.is_symlink() or not path.is_file():
                raise ValueError("Runtime credential must be a regular file")
            if name != "ollama" and not path.read_text().strip():
                raise ValueError(f"Existing {name} credential is empty")
            path.chmod(0o600)
            retained.append(name)
        else:
            with os.fdopen(descriptor, "w") as output:
                output.write(secrets.token_hex(32) + "\n" if name != "ollama" else "")
            created.append(name)
    return {"created": created, "retained": retained, "provider_token": "configure separately"}
