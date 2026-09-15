#!/bin/sh
set -eu
# Read the owner-only host file before the upstream entrypoint changes user.
POSTGRES_PASSWORD=$(cat /run/secrets/postgres)
export POSTGRES_PASSWORD
exec /usr/local/bin/docker-entrypoint.sh "$@"
