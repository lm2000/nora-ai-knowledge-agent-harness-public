#!/usr/bin/env python3
"""Exercise real pinned BGE, local Qdrant and the MCP client/server on synthetic data."""

import argparse
import asyncio
import json
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from qdrant_client import QdrantClient

from nora.config import Settings
from nora.documents import LocalDocumentStore
from nora.embedding import BGEEncoder
from nora.evaluation import evaluate, load_queries
from nora.indexing import import_bundle, verify_bundle
from nora.mcp_client import KnowledgeClient
from nora.preparation import prepare
from nora.retrieval import RetrievalService, create_app


def run(model_path: str) -> dict:
    root = Path(__file__).resolve().parents[1]
    encoder = BGEEncoder(model_path).initialize()
    with tempfile.TemporaryDirectory(prefix="nora-smoke-") as temporary:
        bundle = Path(temporary) / "data"
        coverage = prepare(root / "examples/documents", bundle, encoder)
        client = QdrantClient(path=str(Path(temporary) / "index"))
        server = thread = sock = None
        try:
            import_bundle(client, "synthetic", bundle)
            verified = verify_bundle(client, "synthetic", bundle)
            service = RetrievalService(
                client,
                encoder,
                LocalDocumentStore(bundle / "docs"),
                collection="synthetic",
                data_dir=bundle,
            )
            app = create_app(Settings(), service, token="synthetic-local-test")
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
            thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
            thread.start()
            for _ in range(100):
                if server.started:
                    break
                if not thread.is_alive():
                    raise RuntimeError("Synthetic MCP server stopped during startup")
                time.sleep(0.05)
            if not server.started:
                raise RuntimeError("Synthetic MCP server did not start")
            knowledge = KnowledgeClient(f"http://127.0.0.1:{port}/mcp", "synthetic-local-test")

            async def checks():
                health = await knowledge.health()
                assert health["ready"] and health["documents"] == 3
                queries = load_queries(root / "examples/queries.json")
                result = await evaluate(queries, knowledge, {"hit1": 1, "hit5": 1, "mrr5": 1})
                for query in queries:
                    document = await knowledge.call(
                        "read", {"doc_id": query["expected_doc_ids"][0], "limit": 20}
                    )
                    assert len(document["text"]) == 20 and document["next_offset"] == 20
                return result

            result = asyncio.run(checks())
            return {
                "scope": "Real BGE and embedded Qdrant over MCP; three synthetic questions; no answer model or cloud calls",
                "documents": coverage["documents"],
                "chunks": coverage["chunks"],
                "index": verified,
                "retrieval": result,
                "pass": result["pass"],
            }
        finally:
            if server:
                server.should_exit = True
            if thread:
                thread.join(timeout=10)
            if sock:
                sock.close()
            client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.model_path)
    if args.output:
        with args.output.open("x") as stream:
            json.dump(result, stream, indent=2)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["pass"] else 1)
