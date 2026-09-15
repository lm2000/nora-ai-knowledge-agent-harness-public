"""Container readiness using only the Python standard library."""

import os
import sys
from urllib.request import Request, urlopen

from nora.config import credential

service = sys.argv[1]
role_ports = {"knowledge": 8000, "research": 8003, "interview": 8004}
role = os.environ.get("NORA_ROLE", "knowledge")
ports = {"retrieval": 8001, "coordination": 8000, "bge": 8002, "role": role_ports.get(role, 8000)}
keys = {
    "retrieval": "MCP_TOKEN",
    "coordination": "INTERNAL_TOKEN",
    "bge": "BGE_TOKEN",
    "role": "INTERNAL_TOKEN",
}
port = ports[service]
key = keys[service]
request = Request(
    f"http://127.0.0.1:{port}/health", headers={"Authorization": "Bearer " + credential(key)}
)
try:
    with urlopen(request, timeout=5) as response:
        raise SystemExit(0 if response.status == 200 else 1)
except Exception:
    raise SystemExit(1)
