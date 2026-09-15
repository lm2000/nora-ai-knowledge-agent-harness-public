#!/usr/bin/env python3
"""Verify an end-to-end containerized update through the real retrieval/agent boundary.

Uses deterministic model and encoder doubles; no real BGE inference or external LLM call.
Run from the host against a loopback retrieval port exposed by the acceptance Compose stack.
"""

import argparse
import asyncio
import json
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

from doubles import DeterministicModelDouble
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from nora.agent import create_graph
from nora.config import Settings, credential
from nora.mcp_client import KnowledgeClient


class _RetrievalKnowledge:
    """Wrap the async MCP KnowledgeClient as the synchronous-ish graph knowledge contract."""

    def __init__(self, client: KnowledgeClient):
        self.client = client

    async def call(self, name: str, arguments: dict):
        return await self.client.call(name, arguments)

    async def health(self):
        return await self.client.health()

    @asynccontextmanager
    async def pinned(self):
        async with self.client.pinned() as pinned:
            yield pinned


def wait_for_health(url: str, token: str, timeout: float = 60.0) -> dict:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        try:
            request = Request(url, headers={"Authorization": f"Bearer {token}"})
            with urlopen(request, timeout=2) as response:
                if response.status == 200:
                    return json.loads(response.read().decode("utf-8"))
        except (HTTPError, Exception):
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Retrieval did not become healthy at {url}")


def ask_agent(graph, question: str, thread_id: str) -> str:
    result = asyncio.run(
        graph.ainvoke(
            {"messages": [HumanMessage(content=question)]},
            {"configurable": {"thread_id": thread_id}, "recursion_limit": 10},
        )
    )
    for message in reversed(result["messages"]):
        if isinstance(message, AIMessage) and message.content and not message.tool_calls:
            return str(message.content)
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", default="October 12, 2026")
    args = parser.parse_args()

    settings = Settings.from_env()
    retrieval_base = settings.retrieval_url.rsplit("/", 1)[0]
    health_url = retrieval_base + "/health"
    release_url = retrieval_base + "/release"
    token = credential("MCP_TOKEN")

    health = wait_for_health(health_url, token)
    if not health.get("ready") or health.get("documents", 0) <= 0:
        print(json.dumps({"pass": False, "error": "retrieval not ready", "health": health}))
        return 1

    release = json.loads(
        urlopen(Request(release_url, headers={"Authorization": f"Bearer {token}"}))
        .read()
        .decode("utf-8")
    )
    if not release.get("release"):
        print(json.dumps({"pass": False, "error": "no active release", "release": release}))
        return 1

    knowledge = KnowledgeClient(settings.retrieval_url, token, settings.tool_timeout)
    model = DeterministicModelDouble()
    graph = create_graph(model, _RetrievalKnowledge(knowledge), InMemorySaver(), settings)
    answer = ask_agent(
        graph, "When does Atlas ship?", f"acceptance-thread-{args.expected.replace(' ', '_')}"
    )
    if args.expected not in answer:
        # Debug: show what the search tool actually returned for this release.
        import asyncio

        debug = asyncio.run(knowledge.call("search", {"query": "When does Atlas ship?"}))
        print(
            json.dumps(
                {
                    "pass": False,
                    "error": f"expected '{args.expected}' in answer",
                    "answer": answer,
                    "release": release,
                    "search_debug": debug,
                }
            )
        )
        return 1

    print(
        json.dumps(
            {
                "pass": True,
                "expected": args.expected,
                "encoder_double": "DeterministicEncoderDouble (query flag sensitive, not BGE)",
                "model_double": "DeterministicModelDouble (extracts date from tool text)",
                "health": health,
                "release": release,
                "answer": answer,
                "notes": [
                    "Verified through the live retrieval MCP boundary and the real agent graph.",
                    "No real BGE inference or external LLM provider was called.",
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"pass": False, "error": str(error)}))
        raise SystemExit(1)
