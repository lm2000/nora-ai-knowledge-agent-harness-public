#!/bin/sh
set -eu
QDRANT__SERVICE__API_KEY=$(cat /run/secrets/qdrant)
export QDRANT__SERVICE__API_KEY
exec ./entrypoint.sh "$@"
