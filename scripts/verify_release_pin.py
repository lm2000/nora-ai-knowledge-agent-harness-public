#!/usr/bin/env python3
"""Verify coherent MCP search/read across a release activation and rollback.

Stage "capture" runs while the target release is active: it searches, records the
release identity, collection and the top document ID/text, and asserts the text
contains the expected release-specific phrase.

Stage "verify" runs after rollback to an earlier release: it reads the captured
document using the captured release pin, searches again with the same pin, checks
that the /release endpoint honors the pin, and finally checks that an unpinned
search returns the current (rolled-back) release text.

Uses deterministic doubles; no real BGE inference or external LLM call.
Run from the host against the loopback retrieval port exposed by acceptance Compose.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def _load(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


async def _mcp_call(
    url: str,
    token: str,
    release: str | None,
    name: str,
    arguments: dict,
    timeout: int = 45,
) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    if release:
        headers["X-Nora-Release"] = release
    async with asyncio.timeout(timeout):
        async with httpx2.AsyncClient(headers=headers, timeout=timeout) as http:
            async with streamable_http_client(url, http_client=http) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments)
                    if result.is_error:
                        raise RuntimeError(f"MCP tool {name} failed")
                    if result.structured_content is not None:
                        return result.structured_content
                    text = next(block.text for block in result.content if block.type == "text")
                    payload = json.loads(text)
                    if not isinstance(payload, dict):
                        raise RuntimeError("Invalid knowledge response")
                    return payload


async def _release_info(base_url: str, token: str, release: str | None) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    if release:
        headers["X-Nora-Release"] = release
    async with httpx2.AsyncClient(timeout=10) as http:
        response = await http.get(f"{base_url}/release", headers=headers)
        response.raise_for_status()
        return response.json()


async def _capture(args) -> int:
    base_url = args.retrieval_url.rsplit("/", 1)[0]
    release_info = await _release_info(base_url, args.token, None)
    release = release_info.get("release")
    if not release:
        print(
            json.dumps({"pass": False, "error": "no active release", "release_info": release_info})
        )
        return 1

    search = await _mcp_call(
        args.retrieval_url,
        args.token,
        None,
        "search",
        {"query": args.query, "limit": 5},
        timeout=args.timeout,
    )
    results = search.get("results", [])
    if not results:
        print(
            json.dumps(
                {
                    "pass": False,
                    "error": "no search results",
                    "release_info": release_info,
                    "search": search,
                }
            )
        )
        return 1

    top = results[0]
    doc_id = top.get("doc_id")
    text = top.get("text", "")
    if args.expected not in text:
        print(
            json.dumps(
                {
                    "pass": False,
                    "error": f"expected '{args.expected}' in captured search text",
                    "release_info": release_info,
                    "search": search,
                }
            )
        )
        return 1

    record = {
        "pass": True,
        "stage": "capture",
        "release": release,
        "collection": release_info.get("collection"),
        "doc_id": doc_id,
        "search_text": text[:240],
    }
    if args.output:
        args.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0


async def _verify(args) -> int:
    prior = _load(args.output)
    pin_release = args.release or prior.get("release")
    doc_id = args.doc_id or prior.get("doc_id")
    expected_pinned = args.expected
    expected_current = args.expected_current

    if not pin_release or not doc_id:
        print(
            json.dumps(
                {
                    "pass": False,
                    "error": "missing release pin or doc_id for verify stage",
                    "prior": prior,
                }
            )
        )
        return 1

    base_url = args.retrieval_url.rsplit("/", 1)[0]

    # Pinned read of the captured document must still return the full text.
    read_result = await _mcp_call(
        args.retrieval_url,
        args.token,
        pin_release,
        "read",
        {"doc_id": doc_id, "offset": 0, "limit": 8000},
        timeout=args.timeout,
    )
    read_text = read_result.get("text", "")
    if expected_pinned not in read_text:
        print(
            json.dumps(
                {
                    "pass": False,
                    "error": f"pinned read did not contain '{expected_pinned}'",
                    "pin_release": pin_release,
                    "doc_id": doc_id,
                    "read": read_result,
                }
            )
        )
        return 1

    # Pinned search of the old release must still find the same document.
    search_result = await _mcp_call(
        args.retrieval_url,
        args.token,
        pin_release,
        "search",
        {"query": args.query, "limit": 5},
        timeout=args.timeout,
    )
    pinned_results = search_result.get("results", [])
    if not pinned_results or expected_pinned not in pinned_results[0].get("text", ""):
        print(
            json.dumps(
                {
                    "pass": False,
                    "error": f"pinned search did not return '{expected_pinned}'",
                    "pin_release": pin_release,
                    "search": search_result,
                }
            )
        )
        return 1
    if pinned_results[0].get("doc_id") != doc_id:
        print(
            json.dumps(
                {
                    "pass": False,
                    "error": "pinned search returned a different doc_id",
                    "pin_release": pin_release,
                    "expected_doc_id": doc_id,
                    "search": search_result,
                }
            )
        )
        return 1

    # /release endpoint must honor the same pin.
    release_pinned = await _release_info(base_url, args.token, pin_release)
    if release_pinned.get("release") != pin_release:
        print(
            json.dumps(
                {
                    "pass": False,
                    "error": "/release did not honor the release pin",
                    "pin_release": pin_release,
                    "release_pinned": release_pinned,
                }
            )
        )
        return 1

    # Unpinned /release and search must see the current (rolled-back) release.
    release_current = await _release_info(base_url, args.token, None)
    current_release_id = release_current.get("release")
    if current_release_id == pin_release:
        print(
            json.dumps(
                {
                    "pass": False,
                    "error": "unpinned /release still returned the pinned release",
                    "release_current": release_current,
                }
            )
        )
        return 1

    current_search = await _mcp_call(
        args.retrieval_url,
        args.token,
        None,
        "search",
        {"query": args.query, "limit": 5},
        timeout=args.timeout,
    )
    current_results = current_search.get("results", [])
    if not current_results or expected_current not in current_results[0].get("text", ""):
        print(
            json.dumps(
                {
                    "pass": False,
                    "error": f"unpinned search did not contain '{expected_current}'",
                    "release_current": release_current,
                    "search": current_search,
                }
            )
        )
        return 1

    report = {
        "pass": True,
        "stage": "verify",
        "pin_release": pin_release,
        "pin_collection": release_pinned.get("collection"),
        "pin_read_doc_id": doc_id,
        "pin_read_contains": expected_pinned in read_text,
        "pin_search_doc_id": pinned_results[0].get("doc_id"),
        "pin_search_contains": expected_pinned in pinned_results[0].get("text", ""),
        "current_release": current_release_id,
        "current_collection": release_current.get("collection"),
        "current_search_contains": expected_current in current_results[0].get("text", ""),
    }
    print(json.dumps(report, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--retrieval-url", default=os.environ.get("NORA_RETRIEVAL_URL", "http://127.0.0.1:8001/mcp")
    )
    parser.add_argument("--token", default=os.environ.get("NORA_MCP_TOKEN", ""))
    parser.add_argument("--stage", choices=["capture", "verify"], required=True)
    parser.add_argument("--release", help="explicit release pin for verify stage")
    parser.add_argument("--doc-id", help="explicit document ID for verify stage")
    parser.add_argument("--query", default="When does Atlas ship?")
    parser.add_argument(
        "--expected", default="October 19, 2026", help="phrase expected in pinned result"
    )
    parser.add_argument(
        "--expected-current",
        default="October 12, 2026",
        help="phrase expected in unpinned current result",
    )
    parser.add_argument(
        "--output", type=Path, help="JSON file to write capture results or read prior capture"
    )
    parser.add_argument("--timeout", type=int, default=45)
    args = parser.parse_args()

    if not args.token:
        print(json.dumps({"pass": False, "error": "missing MCP token"}))
        return 1

    try:
        if args.stage == "capture":
            return asyncio.run(_capture(args))
        return asyncio.run(_verify(args))
    except Exception as error:
        print(json.dumps({"pass": False, "error": str(error)}))
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"pass": False, "error": str(error)}))
        raise SystemExit(1)
