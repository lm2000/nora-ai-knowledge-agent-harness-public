#!/usr/bin/env python3
"""Real-process smoke for the shared HTTP BGE service.

Starts the production BGE HTTP stack with a deterministic encoder double,
waits for /health, then verifies query/document encoding and bounded admission
control over actual TCP sockets. This is not an ASGI TestClient or real model
inference test. If this sandbox cannot bind a loopback socket, the script exits
with code 2 and prints the exact command for a parent escalation run.
"""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def find_port() -> int:
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    except PermissionError as error:
        raise PermissionError(
            "Sandbox blocked loopback socket bind; run this script outside the sandbox"
        ) from error
    finally:
        sock.close()


def wait_for_health(port: int, token: str, timeout: float = 15.0) -> bool:
    url = f"http://127.0.0.1:{port}/health"
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        try:
            request = Request(url, headers={"Authorization": f"Bearer {token}"})
            with urlopen(request, timeout=1) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


def request(port: int, token: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        f"http://127.0.0.1:{port}/encode",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    os.environ["NORA_BGE_TOKEN"] = "smoke-test"
    token = os.environ["NORA_BGE_TOKEN"]
    try:
        port = find_port()
    except PermissionError as error:
        print(json.dumps({"error": str(error), "escalate_command": sys.argv[0]}))
        return 2

    env = os.environ.copy()
    repo = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = f"{repo / 'src'}:{repo / 'tests'}"
    proc = None
    try:
        proc = subprocess.Popen(
            [sys.executable, str(repo / "scripts" / "serve_bge_double.py"), str(port)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if not wait_for_health(port, token):
            stdout, stderr = proc.communicate(timeout=5)
            print(
                json.dumps(
                    {
                        "error": "BGE server did not become healthy",
                        "stdout": stdout.decode("utf-8", errors="replace"),
                        "stderr": stderr.decode("utf-8", errors="replace"),
                    }
                )
            )
            return 1

        times = {}
        text = "hello world example"
        t0 = time.perf_counter()
        doc = request(port, token, {"texts": [text], "query": False})
        times["document_encode_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        t0 = time.perf_counter()
        query = request(port, token, {"texts": [text], "query": True})
        times["query_encode_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        assert len(doc["vectors"][0]) == 768
        assert len(query["vectors"][0]) == 768
        # The double honors the HTTP query flag, so the vectors must differ.
        assert doc["vectors"][0] != query["vectors"][0]

        # Auth and oversized-batch rejection should still work over real sockets.
        try:
            req = Request(f"http://127.0.0.1:{port}/encode")
            urlopen(req, timeout=2)
            auth_rejected = False
        except HTTPError as error:
            auth_rejected = error.code == 401
        assert auth_rejected

        try:
            req = Request(
                f"http://127.0.0.1:{port}/encode",
                data=json.dumps({"texts": ["x"] * 200}).encode(),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            urlopen(req, timeout=2)
            oversized_rejected = False
        except HTTPError as error:
            oversized_rejected = error.code == 413
        assert oversized_rejected

        report = {
            "pass": True,
            "encoder_double": "DeterministicEncoderDouble (query flag sensitive, not BGE)",
            "socket": f"127.0.0.1:{port}",
            "latencies_ms": times,
            "checks": {
                "health": True,
                "document_encode": True,
                "query_encode": True,
                "query_flag_reaches_encoder": doc["vectors"][0] != query["vectors"][0],
                "auth_rejected": auth_rejected,
                "oversized_batch_rejected": oversized_rejected,
            },
            "notes": [
                "Started a real child process and bound a TCP loopback socket.",
                "No real BGE model weights were loaded or executed.",
            ],
        }
        print(json.dumps(report, indent=2))
        return 0
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    sys.exit(main())
