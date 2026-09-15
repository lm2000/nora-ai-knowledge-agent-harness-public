#!/usr/bin/env bash
# Bounded Docker acceptance for the first knowledge-update-to-answer slice.
#
# - Unique Compose project name, unique image tags and a checked free loopback port.
# - Builds production backend and conversion images plus an acceptance harness image.
# - Starts only qdrant, a deterministic-double BGE service, and retrieval.
# - Runs the actual four-job launcher (scripts/knowledge-update) for Oct 12, a
#   deliberately failed update, Oct 19, and a rollback to Oct 12.
# - Verifies the live retrieval/MCP boundary through the real agent graph with doubles.
# - Exercises real-process HTTP BGE admission control with a slow encoder double.
# - Cleans up only its own project resources and acceptance task directories.
#
# Run outside the sandbox with a Docker host and an active Colima/Docker Desktop.
# No external LLM inference or cloud resources are required.

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
TAG_SUFFIX="$(date -u +%Y%m%d_%H%M%S)_$(openssl rand -hex 4)"
PROJECT="nora-accept-${TAG_SUFFIX}"
PYTHON="${NORA_PYTHON:-python3}"

export NORA_BACKEND_IMAGE="nora-backend:accept-${TAG_SUFFIX}"
export NORA_CONVERSION_IMAGE="nora-conversion:accept-${TAG_SUFFIX}"
export NORA_ACCEPTANCE_IMAGE="nora-acceptance:accept-${TAG_SUFFIX}"
export NORA_ACCEPTANCE_TOKENIZER_DOUBLE=1
export NORA_COMPOSE_PROJECT="$PROJECT"

# Choose a free loopback port unless the operator provided one. Avoids collisions
# with unrelated services such as an existing SSH forward on 127.0.0.1:8001.
if [[ -n "${NORA_ACCEPTANCE_PORT:-}" ]]; then
  PORT="$NORA_ACCEPTANCE_PORT"
else
  PORT="$("$PYTHON" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"
fi
export NORA_ACCEPTANCE_PORT="$PORT"

TASK_DIR="$REPO/.runtime/acceptance/tmp"
mkdir -p "$TASK_DIR"
SOURCE="$(mktemp -d "$TASK_DIR/nora-accept-source.XXXXXX")"
RELEASES="$(mktemp -d "$TASK_DIR/nora-accept-releases.XXXXXX")"
SOURCE_BAD="$(mktemp -d "$TASK_DIR/nora-accept-bad.XXXXXX")"
SOURCE_V2="$(mktemp -d "$TASK_DIR/nora-accept-v2.XXXXXX")"
export NORA_ACCEPTANCE_RELEASES="$RELEASES"

# Ensure local dummy secrets exist for the isolated acceptance stack.
SECRETS_DIR="$REPO/.runtime/secrets"
mkdir -p "$SECRETS_DIR"
for name in postgres qdrant mcp internal ollama bge; do
  if [[ ! -f "$SECRETS_DIR/$name" ]]; then
    openssl rand -hex 32 > "$SECRETS_DIR/$name"
    chmod 600 "$SECRETS_DIR/$name"
  fi
done

cleanup() {
  echo "Cleaning up project $PROJECT ..."
  docker compose -f "$REPO/compose.yaml" -f "$REPO/scripts/acceptance.compose.yaml" -p "$PROJECT" down -v --remove-orphans 2>/dev/null || true
  rm -rf "$SOURCE" "$SOURCE_BAD" "$SOURCE_V2" "$RELEASES"
  # Remove the acceptance symlink if it points inside this run.
  if [[ -L "$REPO/.runtime/releases/current" ]]; then
    target=$(readlink "$REPO/.runtime/releases/current" 2>/dev/null || true)
    if [[ "$target" == *"$(basename "$RELEASES")"* ]]; then
      rm -f "$REPO/.runtime/releases/current"
    fi
  fi
}
trap cleanup EXIT

on_error() {
  echo "=== Container logs on failure (project $PROJECT) ===" >&2
  docker compose -f "$REPO/compose.yaml" -f "$REPO/scripts/acceptance.compose.yaml" -p "$PROJECT" logs --tail=80 retrieval bge qdrant 2>/dev/null || true
}
trap on_error ERR

cat > "$SOURCE/atlas.md" <<'EOFMD'
# Atlas
Atlas ships on October 12, 2026.
EOFMD

cat > "$SOURCE_BAD/bad.jpg" <<'EOFMD'
not a document
EOFMD

cat > "$SOURCE_V2/atlas.md" <<'EOFMD'
# Atlas
Atlas ships on October 19, 2026.
EOFMD

COMPOSE="docker compose -f $REPO/compose.yaml -f $REPO/scripts/acceptance.compose.yaml -p $PROJECT"

wait_retrieval_ready() {
  local token="$1" url="http://127.0.0.1:$PORT/health"
  local end=$(( $(date +%s) + 120 ))
  while true; do
    local state
    state=$(curl -sf -H "Authorization: Bearer $token" "$url" 2>/dev/null || echo '{"ready":false}')
    if [[ "$(echo "$state" | "$PYTHON" -c "import sys,json; d=json.load(sys.stdin); print(d.get('ready',False) and d.get('documents',0)>0)")" == "True" ]]; then
      return 0
    fi
    if [[ $(date +%s) -gt $end ]]; then
      echo "Retrieval did not become ready in time: $state" >&2
      return 1
    fi
    sleep 1
  done
}

echo "=== Building images for project $PROJECT ==="
docker build --target backend --tag "$NORA_BACKEND_IMAGE" --file "$REPO/deploy/Dockerfile" "$REPO"
docker build --target conversion --tag "$NORA_CONVERSION_IMAGE" --file "$REPO/deploy/Dockerfile" "$REPO"
docker build --build-arg "NORA_BACKEND_IMAGE=$NORA_BACKEND_IMAGE" --tag "$NORA_ACCEPTANCE_IMAGE" --file "$REPO/deploy/Dockerfile.acceptance" "$REPO"

echo "=== Starting qdrant, BGE double and retrieval on 127.0.0.1:$PORT ==="
$COMPOSE up -d qdrant bge retrieval

echo "=== Waiting for retrieval endpoint to respond ==="
MCP_TOKEN="$(cat "$SECRETS_DIR/mcp" | tr -d '\n')"
deadline=$(($(date +%s) + 120))
while true; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $MCP_TOKEN" "http://127.0.0.1:$PORT/health" || true)
  if [[ "$code" == "200" || "$code" == "503" ]]; then
    break
  fi
  if [[ $(date +%s) -gt $deadline ]]; then
    echo "Retrieval endpoint did not respond in time (last HTTP $code)" >&2
    exit 1
  fi
  sleep 1
done

echo "=== Stage 0: Verify conversion image with a real DOCX ==="
PYTHONPATH="$REPO/src:$REPO/tests" "$PYTHON" "$REPO/scripts/verify_conversion_image.py"

echo "=== Stages 1-4: Initial four-job launcher (Atlas October 12) ==="
NORA_COMPOSE_FILES="-f $REPO/compose.yaml -f $REPO/scripts/acceptance.compose.yaml" \
  "$REPO/scripts/knowledge-update" "$SOURCE" "$RELEASES"

echo "=== Waiting for retrieval to report ready after activation ==="
wait_retrieval_ready "$MCP_TOKEN"

echo "=== Verify initial answer through live retrieval/agent boundary ==="
export NORA_RETRIEVAL_URL="http://127.0.0.1:$PORT/mcp"
export NORA_MCP_TOKEN="$MCP_TOKEN"
export NORA_BGE_TOKEN="$(cat "$SECRETS_DIR/bge" | tr -d '\n')"
export NORA_QDRANT_KEY="$(cat "$SECRETS_DIR/qdrant" | tr -d '\n')"
PYTHONPATH="$REPO/src:$REPO/tests" "$PYTHON" "$REPO/scripts/verify_docker_acceptance.py"

echo "=== Stage 5: Failed update must leave active release unchanged ==="
set +e
NORA_COMPOSE_FILES="-f $REPO/compose.yaml -f $REPO/scripts/acceptance.compose.yaml" \
  "$REPO/scripts/knowledge-update" "$SOURCE_BAD" "$RELEASES"
BAD_EXIT=$?
set -e
if [[ $BAD_EXIT -eq 0 ]]; then
  echo "Expected the bad update to fail, but it succeeded" >&2
  exit 1
fi
# Answer should still be the October 12 release.
PYTHONPATH="$REPO/src:$REPO/tests" "$PYTHON" "$REPO/scripts/verify_docker_acceptance.py"

echo "=== Stage 6: Valid October 19 update ==="
NORA_COMPOSE_FILES="-f $REPO/compose.yaml -f $REPO/scripts/acceptance.compose.yaml" \
  "$REPO/scripts/knowledge-update" "$SOURCE_V2" "$RELEASES"

echo "=== Waiting for retrieval to report ready after October 19 activation ==="
wait_retrieval_ready "$MCP_TOKEN"

echo "=== Verify October 19 answer ==="
PYTHONPATH="$REPO/src:$REPO/tests" "$PYTHON" "$REPO/scripts/verify_docker_acceptance.py" --expected "October 19, 2026"

PIN_FILE="$TASK_DIR/pin-record.json"
echo "=== Capture October 19 release pin and document ID for Stage 8 ==="
PYTHONPATH="$REPO/src:$REPO/tests" "$PYTHON" "$REPO/scripts/verify_release_pin.py"   --retrieval-url "http://127.0.0.1:$PORT/mcp"   --token "$MCP_TOKEN"   --stage capture   --expected "October 19, 2026"   --output "$PIN_FILE"

echo "=== Stage 7: Rollback to October 12 ==="
$COMPOSE run --rm retrieval rollback /data

echo "=== Verify October 12 answer after rollback ==="
PYTHONPATH="$REPO/src:$REPO/tests" "$PYTHON" "$REPO/scripts/verify_docker_acceptance.py"

echo "=== Stage 8: Release pin keeps MCP search/read on October 19 while active is October 12 ==="
PIN_FILE="$TASK_DIR/pin-record.json"
PYTHONPATH="$REPO/src:$REPO/tests" "$PYTHON" "$REPO/scripts/verify_release_pin.py"   --retrieval-url "http://127.0.0.1:$PORT/mcp"   --token "$MCP_TOKEN"   --stage verify   --expected "October 19, 2026"   --expected-current "October 12, 2026"   --output "$PIN_FILE"

echo "=== Stage 9: Source checksums unchanged ==="
SHA1=$(shasum -a 256 "$SOURCE/atlas.md" | awk '{print $1}')
SHA2=$(shasum -a 256 "$SOURCE_V2/atlas.md" | awk '{print $1}')
if [[ "$SHA1" != "$(printf '%s' '# Atlas
Atlas ships on October 12, 2026.
' | shasum -a 256 | awk '{print $1}')" ]]; then
  echo "Original October 12 source checksum changed" >&2
  exit 1
fi
if [[ "$SHA2" != "$(printf '%s' '# Atlas
Atlas ships on October 19, 2026.
' | shasum -a 256 | awk '{print $1}')" ]]; then
  echo "Original October 19 source checksum changed" >&2
  exit 1
fi

echo "=== Stage 10: HTTP admission control with a slow BGE double ==="
PYTHONPATH="$REPO/src:$REPO/tests" "$PYTHON" "$REPO/scripts/bge_admission_smoke.py"

echo "=== Docker acceptance passed for project $PROJECT ==="
