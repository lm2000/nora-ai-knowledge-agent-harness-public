from pathlib import Path

"""In-memory GCS double for local publish/activate/rollback verification."""


class FakeGCSClient:
    """In-memory GCS double for local publish/activate/rollback verification."""

    def __init__(self):
        self._buckets: dict[str, dict[str, dict[int, bytes]]] = {}
        self._generations: dict[tuple[str, str], int] = {}

    def bucket(self, name: str):
        return _FakeBucket(self, name)

    def _upload(
        self,
        bucket: str,
        object_name: str,
        data: bytes,
        *,
        if_generation_match: int | None = None,
    ) -> int:
        current = self._generations.get((bucket, object_name), 0)
        if if_generation_match is not None and current != if_generation_match:
            raise ValueError(
                f"Generation precondition failed for {object_name}: "
                f"expected {if_generation_match}, found {current}"
            )
        generation = current + 1
        self._generations[(bucket, object_name)] = generation
        self._buckets.setdefault(bucket, {}).setdefault(object_name, {})[generation] = data
        return generation

    def _download(self, bucket: str, object_name: str, generation: int) -> bytes | None:
        return self._buckets.get(bucket, {}).get(object_name, {}).get(generation)

    def _current_generation(self, bucket: str, object_name: str) -> int:
        return self._generations.get((bucket, object_name), 0)


class _FakeBucket:
    def __init__(self, client: FakeGCSClient, name: str):
        self.client = client
        self.name = name

    def blob(self, object_name: str, generation: int | None = None):
        return _FakeBlob(self.client, self.name, object_name, generation)


class _FakeBlob:
    def __init__(
        self, client: FakeGCSClient, bucket: str, object_name: str, generation: int | None
    ):
        self.client = client
        self.bucket = bucket
        self.object_name = object_name
        self.generation = generation

    def upload_from_string(self, data: str | bytes, *, timeout: float = 30, **kwargs):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.generation = self.client._upload(
            self.bucket,
            self.object_name,
            data,
            if_generation_match=kwargs.get("if_generation_match"),
        )

    def upload_from_filename(self, filename: str | Path, *, timeout: float = 30, **kwargs):
        data = Path(filename).read_bytes()
        self.generation = self.client._upload(
            self.bucket,
            self.object_name,
            data,
            if_generation_match=kwargs.get("if_generation_match"),
        )

    def download_as_bytes(self, *, timeout: float = 30) -> bytes:
        generation = self.generation
        if generation is None:
            generation = self.client._current_generation(self.bucket, self.object_name)
        if generation == 0:
            raise FileNotFoundError(f"No such object: {self.object_name}")
        data = self.client._download(self.bucket, self.object_name, generation)
        if data is None:
            raise FileNotFoundError(f"No such object generation: {self.object_name}#{generation}")
        return data
