# Setup

[Home](../../README.md) · [Services](containers/README.md) · [Configuration](configuration.md)

Install the same [Python package](../../src/nora/__init__.py), [Browser UI](../../ui/package.json)
and [Compose file](../../compose.yaml) on a development machine or Linux host.
For example, start with the fictional Atlas documents before selecting a private
corpus. The cloud and Beelink pages cover host-specific considerations.

![The services assembled by the setup instructions.](../architecture/diagrams/container-service-inventory.gif)

[Local browser version](../architecture/diagrams/container-service-inventory.html)

These commands configure the existing application. [Architecture](../architecture/architecture-concept.md)
owns the accepted workflow design; [Coordination](containers/coordination.md#client-contract)
owns the question/optional-UUID interfaces, and [deployment status](private-deployment/STATUS.md)
owns dated running-service and conversational evidence.

## Install for development

Use Python 3.12, Node.js 22.22 or newer, pnpm 12.8.1, Conda and Make. Run commands from the repository root:

```bash
conda create -n nora-ai python=3.12 pip
conda run -n nora-ai python -m pip install -c requirements.lock -e '.[server,gcs,dev]'
conda activate nora-ai
pnpm --dir ui install --frozen-lockfile
make validate
```

Activate `nora-ai` explicitly with Conda before running Python commands; Node and UI packages use pnpm. Run `conda deactivate` when finished. Verify with `python -c 'import sys; print(sys.executable)'`; the path should be under the `nora-ai` Conda environment.

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

Use this Docker route on a fresh target after development setup. An earlier
five-service package passed the [isolated ARM Linux trial](../evaluation/VALIDATION.md#isolated-container-trial);
that dated result does not validate every current source change. Existing
deployments use their own complete Compose file set and operating record.
On Docker Desktop or Colima, keep the checkout and `.runtime` in a directory
shared with the Linux VM so credentials and data can be mounted.

1. **Initialize on the host.** From the repository root, create missing credentials and state directories. Existing credentials are retained.

   ```bash
   nora init
   mkdir -p .runtime/state .runtime/models
   cp -n .env.example .env
   id -u
   id -g
   ```

   Put the reported IDs into `NORA_UID` and `NORA_GID` in `.env`. Set the
   Ollama endpoint/model to one available to your account, and put its token in
   `.runtime/secrets/ollama`. `nora init` creates the service credentials,
   including BGE and Gateway, without replacing existing files.

   Compose also requires a Fireworks credential file, which `nora init` does
   not create. If Fireworks is disabled, create an empty private file only when
   it is absent; retain any existing credential:

   ```bash
   if [ ! -e .runtime/secrets/fireworks ]; then
     (umask 077; set -C; : > .runtime/secrets/fireworks)
   fi
   ```

   Files remain local and ignored by Git. An empty Fireworks token keeps that
   provider out of model selection while satisfying the required file mount.

2. **Cache the embedding model on the host.** In the activated Conda environment:

   ```bash
   python -m pip install -c requirements.lock -e '.[embeddings]'
   nora cache-model
   ```

   Expected result: `.runtime/models/bge` contains the pinned model and its
   checksum receipt. If that verified cache already exists from the smoke test,
   reuse it and skip `nora cache-model`, which requires a new destination.
   This step downloads the model; it does not ingest documents.

3. **Build and ingest into the same Docker project.** Docker Engine/Desktop and
   Compose are required. Run from the repository root:

   ```bash
   export NORA_COMPOSE_PROJECT=nora
   docker compose -p nora config --quiet
   docker compose -p nora --profile ingestion build bge coordination ui job-convert
   docker compose -p nora up -d --wait bge postgres qdrant
   scripts/knowledge-update examples/documents .runtime/releases
   ```

   Expected result: four temporary jobs convert, prepare, embed and import/verify
   the three fictional documents. A release appears under `.runtime/releases`,
   and `current` advances after import verification. The launcher and application
   both use project `nora`, so they share the same Qdrant volume and network.
   The launcher otherwise defaults to a different project; keep the explicit
   setting for subsequent updates.

   For your own complete source set, the conversion entrypoint accepts PDF,
   DOCX, HTML, PPTX, XLSX, Markdown and TXT. JSON support belongs to the separate
   preparation interface, not this four-job launcher; see the
   [processing contract](../workflows/ingestion/README.md#processing-contract).
   The [operator checklist](../workflows/ingestion/knowledge-base-update-checklist.md)
   covers additions while retaining an existing corpus.

4. **Start the conversational services.**

   ```bash
   docker compose -p nora up -d --wait retrieval coordination ui
   docker compose -p nora ps
   ```

   Open `http://localhost:8080`. Ask the Atlas example, follow up, and reload
   the page to check conversation recovery. Inspect service logs if readiness
   fails. Retrieval remains internal to Docker; this browser path does not
   require Gateway.

   For MCP clients through LiteLLM, first satisfy the
   [Gateway database prerequisite](private-deployment/README.md#litellm-admin-ui-persistence).
   The current gateway connects an already initialized LiteLLM database and
   requires a nonempty Ollama credential. Do not initialize its schema with an
   unrestricted sync against the NIS conversation database. Once those
   prerequisites are met:

   ```bash
   docker compose -p nora build gateway
   docker compose -p nora up -d --wait gateway
   ```

   The gateway publishes loopback port 4000; its Coordination MCP route is
   `http://127.0.0.1:4000/mcp/nis`. Configure the client's bearer authentication
   from `.runtime/secrets/gateway`. [Model routing](model-routing.md) explains
   the separate gateway inference and MCP routes.

5. **Stop processes while keeping data.**

   ```bash
   docker compose -p nora down
   ```

   Named database volumes, host data, model files and credentials remain. Back
   them up separately before migrations. [Operations reference](private-deployment/ROLLOUT.md#operate-and-recover).

For an isolated development acceptance run that owns and cleans up a separate
project, use `scripts/docker_acceptance.sh`. It uses synthetic services as
described in [validation](../workflows/ingestion/README.md#verification-commands).
Use the Docker launcher above for this installation route. The host
`nora knowledge-update` alternative has separate
[tokenizer-cache and service-access prerequisites](../workflows/ingestion/README.md#operator-commands).

## Private access with Tailscale

Use the host's existing Tailscale connection for private client access. [Tailscale Serve](https://tailscale.com/docs/reference/tailscale-cli/serve) can proxy the NIS loopback UI within the tailnet. The application continues to use its configured origin checks and service credentials.

On the application host, inspect existing routes and choose an unused HTTPS listener. For example, if 8443 is available:

```bash
tailscale serve status
tailscale serve --bg --https=8443 http://127.0.0.1:8080
```

Use the actual HTTPS URL reported by Serve, including its port, in `NORA_UI_ALLOWED_ORIGINS` in `.env`. Keep the local origins if you also use the UI locally, then apply the setting from the repository root:

```bash
docker compose -p nora up -d --no-deps ui
```

From the intended second Tailscale device, open that URL, check the document
count, send a question and reload its history. Retrieval has no host port in
root Compose. Direct remote Retrieval access needs an explicit private proxy
or overlay, its exact forwarded Host value in `NORA_MCP_ALLOWED_HOSTS`, a
Retrieval restart and the intended client's MCP credential. Gateway MCP access
is a separate route. The earlier local trial checked origin/host forwarding and
accepted/rejected requests; it did not validate those remote connections.

## Optional local inference

The `local-model` profile provides Ollama. Set `NORA_OLLAMA_URL=http://ollama:11434` and your chosen installed model in `.env`; an empty provider-token file is valid for local Ollama.

```bash
docker compose -p nora --profile local-model up -d ollama
docker compose -p nora exec ollama ollama pull YOUR_MODEL
```

Choose a tool-capable model that fits the host. This profile was not started during the refactor. It does not change the hosted default or any existing installation.

## Target guides

- [Linux / Beelink](beelink/README.md): host storage, ownership and capacity.
- [Google Cloud foundation](google-cloud/README.md): optional VM/network provisioning CLI; it does not install the application.
- [Private deployment history](private-deployment/README.md): prior evidence and migration considerations.
- [Manual ingestion](../workflows/ingestion/README.md): preparation, repeat imports and dataset replacement.
