#!/bin/bash
set -euo pipefail
IFS= read -r token < /run/secrets/qdrant
exec 3<>/dev/tcp/127.0.0.1/6333
printf 'GET /readyz HTTP/1.1\r\nHost: localhost\r\napi-key: %s\r\nConnection: close\r\n\r\n' "$token" >&3
read -r protocol status rest <&3
[[ "$status" == 200 ]]
