"""Versionable retrieval diagnostics with explicit setup failures."""

import json
from pathlib import Path

from nora.common import digest, valid_document_id


def load_queries(path: Path) -> list[dict]:
    content = json.loads(path.read_text(encoding="utf-8"))
    queries = content["queries"] if isinstance(content, dict) else content
    if not isinstance(queries, list) or not queries:
        raise ValueError("Query fixture must contain a nonempty list")
    prepared, seen = [], set()
    for row in queries:
        if not isinstance(row, dict):
            raise ValueError("Each query must be an object")
        if (
            not isinstance(row.get("query"), str)
            or not row["query"].strip()
            or row.get("id") in seen
        ):
            raise ValueError("Questions need unique IDs and nonempty text")
        if not isinstance(row.get("id"), str) or not row["id"]:
            raise ValueError("Each query needs an ID")
        seen.add(row["id"])
        expected = set(row.get("expected_doc_ids", []))
        for name in row.get("expected_files", []):
            original = path.parent / name
            source = original.resolve()
            if not source.is_relative_to(path.parent.resolve()) or original.is_symlink():
                raise ValueError("Expected files must stay inside the fixture directory")
            expected.add(digest(source.read_bytes()))
        if not expected or any(not valid_document_id(value) for value in expected):
            raise ValueError("Every scored question needs valid expected documents")
        prepared.append(
            {"id": row["id"], "query": row["query"], "expected_doc_ids": sorted(expected)}
        )
    return prepared


async def evaluate(queries: list[dict], knowledge, thresholds: dict[str, float]) -> dict:
    if not queries or set(thresholds) != {"hit1", "hit5", "mrr5"}:
        raise ValueError("Provide queries and all three thresholds")
    if any(not 0 <= value <= 1 for value in thresholds.values()):
        raise ValueError("Thresholds must be between zero and one")
    results = []
    for query in queries:
        payload = await knowledge.call("search", {"query": query["query"], "limit": 5})
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("results"), list)
            or "error" in payload
        ):
            raise ValueError(
                "Search failed or returned an invalid result; this is not a scored miss"
            )
        if any(
            not isinstance(row, dict) or not valid_document_id(row.get("doc_id"))
            for row in payload["results"]
        ):
            raise ValueError("Search returned invalid document IDs")
        hits = list(dict.fromkeys(row["doc_id"] for row in payload["results"]))[:5]
        expected = set(query["expected_doc_ids"])
        rank = next((i for i, doc_id in enumerate(hits, 1) if doc_id in expected), None)
        results.append(
            {
                "id": query["id"],
                "rank": rank,
                "hit1": rank == 1,
                "hit5": rank is not None,
                "mrr5": 1 / rank if rank else 0.0,
            }
        )
    metrics = {name: sum(row[name] for row in results) / len(results) for name in thresholds}
    return {
        "count": len(results),
        **metrics,
        "thresholds": thresholds,
        "queries": results,
        "pass": all(metrics[name] >= value for name, value in thresholds.items()),
    }
