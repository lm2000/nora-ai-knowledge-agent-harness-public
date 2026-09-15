FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false
WORKDIR /app
COPY pyproject.toml requirements.lock README.md LICENSE NOTICE.md ./
COPY architecture/diagrams/Excalifont-LICENSE.txt ./architecture/diagrams/Excalifont-LICENSE.txt
COPY src ./src
# CPU wheels avoid installing the CUDA runtime on the retrieval host.
RUN pip install --no-cache-dir torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -c requirements.lock '.[server,embeddings,gcs]'

# Default production target: Coordination, Retrieval and BGE services.
FROM base AS backend
COPY deploy/health.py /app/health.py
ENTRYPOINT ["nora"]

# Conversion target: adds Docling for the temporary manual ingestion job.
# The extra CPU index keeps torchvision CPU-only (Docling pulls it transitively).
FROM base AS conversion
RUN pip install --no-cache-dir -c requirements.lock '.[conversion]' \
    --extra-index-url https://download.pytorch.org/whl/cpu
ENTRYPOINT ["nora"]
