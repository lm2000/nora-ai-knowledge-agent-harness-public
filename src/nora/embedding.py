"""Pinned BGE encoding; weights and heavy libraries load only on explicit use."""

import hashlib
import json
import os
import tempfile
import threading
from pathlib import Path

from nora.common import DIMENSION, MAX_TOKENS, MODEL, QUERY_PREFIX, REVISION


class BGEEncoder:
    dimension = DIMENSION

    def __init__(self, model_path: str, threads: int = 2):
        self.model_path = model_path
        self.threads = threads
        self._tokenizer = None
        self._model = None
        self._lock = threading.RLock()
        self._verified = False

    def _verify_cache(self):
        if self._verified:
            return
        root = Path(self.model_path)
        receipt = json.loads((root / "nora-model.json").read_text())
        if (
            receipt.get("model") != MODEL
            or receipt.get("revision") != REVISION
            or not receipt.get("files")
        ):
            raise ValueError("Model cache does not match the pinned BGE revision")
        for name, expected in receipt["files"].items():
            path = root / name
            if Path(name).name != name or path.is_symlink() or file_digest(path) != expected:
                raise ValueError("Model cache checksum mismatch")
        actual = {p.name for p in root.iterdir() if p.name != "nora-model.json"}
        if actual != set(receipt["files"]):
            raise ValueError("Model cache file inventory differs from its receipt")
        self._verified = True

    @property
    def tokenizer(self):
        with self._lock:
            if self._tokenizer is None:
                self._verify_cache()
                from transformers import AutoTokenizer

                self._tokenizer = AutoTokenizer.from_pretrained(
                    self.model_path, local_files_only=True
                )
            return self._tokenizer

    def initialize(self):
        with self._lock:
            if self._model is None:
                self._verify_cache()
                import torch
                from transformers import AutoModel

                torch.set_num_threads(self.threads)
                self._model = AutoModel.from_pretrained(
                    self.model_path,
                    local_files_only=True,
                    use_safetensors=True,
                    torch_dtype=torch.float32,
                ).eval()
                if self._model.config.hidden_size != DIMENSION:
                    raise ValueError("Model dimension does not match the BGE representation")
                _ = self.tokenizer
        return self

    def encode(self, texts: list[str], *, query: bool = False):
        import torch

        self.initialize()
        if not texts:
            raise ValueError("Cannot encode an empty batch")
        with self._lock, torch.inference_mode():
            inputs = [QUERY_PREFIX + t[:1500] for t in texts] if query else texts
            tokens = self.tokenizer(
                inputs, padding=True, truncation=query, max_length=MAX_TOKENS, return_tensors="pt"
            )
            if tokens["input_ids"].shape[1] > MAX_TOKENS:
                raise ValueError("Document exceeds the complete embedding token limit")
            vectors = self._model(**tokens).last_hidden_state[:, 0]
            return torch.nn.functional.normalize(vectors, dim=1).numpy()


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def cache_model(destination: Path) -> None:
    """Explicitly download the pinned public weights; never called by imports or queries."""
    from transformers import AutoModel, AutoTokenizer

    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError("Choose a new model destination")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".nora-model-", dir=destination.parent) as tmp:
        stage = Path(tmp) / "model"
        options = {"revision": REVISION}
        AutoTokenizer.from_pretrained(MODEL, **options).save_pretrained(stage)
        AutoModel.from_pretrained(MODEL, use_safetensors=True, **options).save_pretrained(stage)
        files = {p.name: file_digest(p) for p in stage.iterdir() if p.is_file()}
        (stage / "nora-model.json").write_text(
            json.dumps({"model": MODEL, "revision": REVISION, "files": files}, indent=2) + "\n"
        )
        if destination.exists():
            raise FileExistsError("Model destination appeared during download")
        os.rename(stage, destination)
