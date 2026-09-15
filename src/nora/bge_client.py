"""HTTP client for the shared BGE service; splits batches and retries under load."""

import json
import time
from typing import Any

import numpy as np


class BGEClient:
    """Double-labeled HTTP BGE client: query mode for retrieval, document mode for batch jobs."""

    def __init__(
        self,
        url: str,
        token: str,
        *,
        timeout: float = 60.0,
        max_batch_size: int = 64,
        retries: int = 3,
    ):
        self.url = url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.max_batch_size = max_batch_size
        self.retries = retries

    def _request(self, texts: list[str], query: bool) -> np.ndarray:
        import urllib.request

        body = json.dumps({"texts": texts, "query": query}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.url}/encode",
            data=body,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        last_error = None
        for attempt in range(self.retries):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    vectors = np.asarray(payload["vectors"], dtype=np.float32)
                    if vectors.shape != (len(texts), 768):
                        raise ValueError(f"BGE response shape mismatch: {vectors.shape}")
                    return vectors
            except urllib.error.HTTPError as error:
                if error.code in (503, 429) and attempt + 1 < self.retries:
                    last_error = error
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise
        raise RuntimeError(f"BGE request failed after retries: {last_error}")

    def encode(self, texts: list[str], *, query: bool = False) -> np.ndarray:
        if not texts:
            raise ValueError("Cannot encode an empty batch")
        results = []
        for start in range(0, len(texts), self.max_batch_size):
            batch = texts[start : start + self.max_batch_size]
            results.append(self._request(batch, query))
        return np.concatenate(results, axis=0)

    def health(self) -> dict:
        import urllib.request

        request = urllib.request.Request(
            f"{self.url}/health",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    @classmethod
    def from_settings(cls, settings: Any) -> "BGEClient":
        from nora.config import credential

        return cls(
            settings.bge_url,
            credential("BGE_TOKEN"),
            timeout=settings.bge_timeout,
            max_batch_size=settings.bge_max_batch_size,
        )
