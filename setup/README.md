# Setup

[Home](../README.md) · [Services](containers/README.md) · [Configuration](configuration.md)

Use the same [Python package](../src/nora/__init__.py), [UI](../ui/package.json) and [Compose file](../compose.yaml) on a development machine or a Linux host. The cloud and Beelink pages describe target considerations; they do not maintain separate application copies.

![The services assembled by the setup instructions.](../architecture/diagrams/container-service-inventory.gif)

[Local browser version](../architecture/diagrams/container-service-inventory.html)


## Accepted target and current interfaces

The settings and commands below configure the single-assistant implementation. The [one-assistant target](../Decisions.md#selected-target-one-assistant-with-a-gateway-backed-mcp-entrance) retains the selector, Deep Agents/LangGraph and PostgreSQL, and adds FastMCP in the existing FastAPI process with a separate LiteLLM gateway and direct MCP access. Its ask tool uses a question and optional thread UUID, with no role argument. The one-assistant interface and gateway are running in the dated private candidate. Bounded Codex/OpenClaw conversational checks passed on October 3; see [the acceptance record](private-deployment/STATUS.md#ordinary-unrestricted-openclaw-acceptance--2026-10-03) for the exact-prompt correction and remaining quality limits. Use [the roadmap](../Plan.md) for current priorities. Existing history is retained without migration or continuation through the new interface.

## Install for development

Use Python 3.12, Node.js 22.22 or newer, pnpm 12.8.1, Conda, mise and Make. Run commands from the repository root:

```bash
conda create -n nora-ai python=3.12 pip
conda run -n nora-ai python -m pip install -c requirements.lock -e '.[server,gcs,dev]'
mise trust
pnpm --dir ui install --frozen-lockfile
make validate
```

The checked-in mise configuration activates `nora-ai` when an interactive shell enters this repository and restores the previous environment after leaving it. Verify with `python -c 'import sys; print(sys.executable)'`; the path should be under the `nora-ai` Conda environment.

Expected result: Python and UI tests, lint, TypeScript, production UI build, shell syntax and documentation checks pass without an inference credential or private corpus. [Validation](../evaluation/VALIDATION.md) records what was exercised during this refactor.

## Test real retrieval

Install the embedding extra and explicitly download the pinned public BGE model. The model directory must be new; `cache-model` writes a revision and file-checksum receipt.

```bash
python -m pip install -c requirements.lock -e '.[embeddings]'
nora cache-model
python scripts/synthetic_smoke.py --model-path .runtime/models/bge
```

The smoke test creates temporary prepared documents, an embedded Qdrant index and a loopback MCP server. It verifies import, document reads and three labeled synthetic searches, then removes temporary state. It does not call an answer model, use PostgreSQL or start Docker. Model download needs internet access; the subsequent smoke test uses the local cache.

Optional document conversion is separate:

```bash
python -m pip install -e '.[conversion]'
nora convert path/to/document.pdf .runtime/converted-document
```

Docling extracts Markdown and structured JSON into a new directory. Supply its Markdown output to preparation. The conversion job container (`job-convert`) uses a dedicated image that installs the Docling extra. To verify that image against a synthetic non-Markdown document, run `scripts/verify_conversion_image.py` outside the sandbox.

## Browser acceptance with synthetic services

This optional check starts its own local UI and in-memory assistant with model
and retrieval doubles. It exercises conversation continuity, new chats, history,
mobile layout and an unavailable-service state without provider credentials or
private data. From the repository root after installing development dependencies:

```bash
python -m pip install playwright==1.64.0
python -m playwright install chromium
python scripts/ui_acceptance.py
```

Expected result: ten browser checks pass and screenshots/results appear under
ignored `.verification/`. The runner cleans up its own temporary services. Set
`NIS_BROWSER_EXECUTABLE` when using an existing Chrome/Chromium executable.

## Run the application

This procedure passed an isolated ARM Linux trial with the three fictional documents and Ollama Cloud. Use a fresh target; existing deployments retain their original versions and volumes. On Docker Desktop or Colima, keep the checkout and `.runtime` under a directory shared with the Linux VM. A host-only temporary directory may build successfully but fail when Compose mounts credentials or data.

1. **Initialize on the host.** From the repository root, create missing credentials and state directories. Existing credentials are retained.

   ```bash
   nora init
   mkdir -p .runtime/state .runtime/models
   cp -n .env.example .env
   id -u
   id -g
   ```

   Put the reported IDs into `NORA_UID` and `NORA_GID` in `.env`. Put your Ollama Cloud API token in `.runtime/secrets/ollama`; the other credentials (including the new `bge` secret) are generated by `nora init`. Files remain local and ignored by Git.

2. **Prepare synthetic data on the host.** Install the embedding extra and run `nora cache-model` first if the model is not cached.

   ```bash
   nora cache-model
   nora knowledge-update examples/documents .runtime/releases
   ```

   Expected result: a new release directory under `.runtime/releases`, a `current` symlink pointing to it, and `coverage.json` in the active release. The four job stages (convert, prepare, embed, import/verify) run in order; activation advances both the prepared documents and the matching Qdrant collection. A failed run leaves `current` unchanged. For your own corpus, use a directory of UTF-8 Markdown, text or supported JSON mail exports; convert other formats first.

3. **Build and start the application on the Docker host.** Docker Engine/Desktop and Compose are required. Use the host-side launcher to run the four distinct job containers:

   ```bash
   docker compose config --quiet
   docker compose build
   docker compose up -d bge postgres qdrant
   scripts/knowledge-update examples/documents .runtime/releases
   ```

   Expected result: the `bge`, database services and the four distinct temporary job containers start. The launcher verifies each stage manifest and stops before activation on any failure; `current` is updated only after import/verify succeeds. It uses a unique Compose project name (`nora-ingestion-e2e`) so it does not collide with an existing `nora` stack. For a bounded, unique-project acceptance run that starts only the required services and cleans up its own resources, use `scripts/docker_acceptance.sh` (requires Docker outside the sandbox).

4. **Start the conversational services.**

   ```bash
   docker compose up -d retrieval coordination ui
   docker compose ps
   ```

   Open `http://localhost:8080`. Ask the Atlas example, follow up, and reload the page to check conversation recovery. Inspect service logs if readiness fails. The default model name is an editable example; the operator must select a model available to their provider account.

5. **Stop processes while keeping data.**

   ```bash
   docker compose down
   ```

   Named database volumes, host data, model files and credentials remain. Backup and restore them separately before migrations. [Operations reference](private-deployment/ROLLOUT.md#operate-and-recover).

## Private access with Tailscale

Use the host's existing Tailscale connection for private client access. [Tailscale Serve](https://tailscale.com/docs/reference/tailscale-cli/serve) can proxy Nora's loopback UI within the tailnet. The application continues to use its configured origin checks and service credentials.

On the application host, inspect existing routes and choose an unused HTTPS listener. For example, if 8443 is available:

```bash
tailscale serve status
tailscale serve --bg --https=8443 http://127.0.0.1:8080
```

Use the actual HTTPS URL reported by Serve, including its port, in `NORA_UI_ALLOWED_ORIGINS` in `.env`. Keep the local origins if you also use the UI locally, then apply the setting from the repository root:

```bash
docker compose up -d --no-deps ui
```

From the intended second Tailscale device, open that URL, check the document count, send a question and reload its history. A separate MCP proxy also needs its exact hostname and port in `NORA_MCP_ALLOWED_HOSTS`, followed by a Retrieval restart, and the intended client's MCP credential. Those client connections remain to validate; the local trial checked configuration forwarding and accepted/rejected HTTP requests only.

## Optional local inference

The `local-model` profile provides Ollama. Set `NORA_OLLAMA_URL=http://ollama:11434` and your chosen installed model in `.env`; an empty provider-token file is valid for local Ollama.

```bash
docker compose --profile local-model up -d ollama
docker compose exec ollama ollama pull YOUR_MODEL
```

Choose a tool-capable model that fits the host. This profile was not started during the refactor. It does not change the hosted default or any existing installation.

## Target guides

- [Linux / Beelink](beelink/README.md): host storage, ownership and capacity.
- [Google Cloud foundation](google-cloud/README.md): optional VM/network provisioning CLI; it does not install the application.
- [Private deployment history](private-deployment/README.md): prior evidence and migration considerations.
- [Manual ingestion](../workflows/ingestion/README.md): preparation, repeat imports and dataset replacement.
