"""Separate retrieval diagnostics and offline artifact-review workflows."""

import json
import re
from pathlib import Path

from nora.common import digest, valid_document_id

MAX_REVIEW_BYTES = 1_048_576
MAX_FINDINGS = 20


class ReviewFailure(ValueError):
    """A stable failure code; never includes provider or source text."""


def _require_review(condition, code):
    if not condition:
        raise ReviewFailure(code)


def _review_json(body):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require_review(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ReviewFailure("invalid_json_constant")

    try:
        result = json.loads(body, object_pairs_hook=unique, parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, ReviewFailure):
            raise
        raise ReviewFailure("invalid_json") from None
    _require_review(isinstance(result, dict), "expected_json_object")
    return result


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _review_packet(packet):
    """Validate frozen answer/source excerpts, not a model's view of their identity."""
    _require_review(
        type(packet.get("schema_version")) is int and packet["schema_version"] == 1,
        "packet_schema_mismatch",
    )
    for key in ("artifact_version", "rubric_version", "persona", "provider", "model", "task"):
        _require_review(_text(packet.get(key)), "packet_identity_missing")
    criteria = packet.get("criteria")
    _require_review(
        isinstance(criteria, list) and bool(criteria) and all(map(_text, criteria)),
        "criteria_missing",
    )
    artifact = packet.get("artifact")
    _require_review(isinstance(artifact, dict), "artifact_missing")
    _require_review(_text(artifact.get("text")), "artifact_text_missing")
    _require_review(
        digest(artifact["text"].encode()) == artifact.get("sha256"), "artifact_hash_mismatch"
    )
    anchors = artifact.get("anchors")
    _require_review(isinstance(anchors, dict) and bool(anchors), "anchors_missing")
    _require_review(
        all(
            _text(key) and _text(value) and value in artifact["text"]
            for key, value in anchors.items()
        ),
        "invalid_artifact_anchor",
    )
    sources = packet.get("sources")
    _require_review(isinstance(sources, list) and bool(sources), "sources_missing")
    indexed = {}
    for source in sources:
        _require_review(isinstance(source, dict), "invalid_source")
        doc_id = source.get("doc_id")
        _require_review(
            valid_document_id(doc_id) and doc_id not in indexed, "invalid_source_identity"
        )
        _require_review(
            _text(source.get("text")) and _text(source.get("heading")), "source_text_missing"
        )
        _require_review(
            digest(source["text"].encode()) == source.get("sha256"), "source_hash_mismatch"
        )
        indexed[doc_id] = source
    return indexed


def _review_content(envelope, packet):
    """Only terminal assistant content; never promote reasoning or tool arguments."""
    observed = envelope.get("model")
    _require_review(_text(observed), "observed_model_missing")
    _require_review(observed == packet["model"], "observed_model_mismatch")
    if "message" in envelope:  # Native Ollama non-streaming response.
        _require_review(
            envelope.get("done") is True and envelope.get("done_reason") == "stop",
            "incomplete_generation",
        )
        message = envelope["message"]
    else:  # OpenAI-compatible non-streaming response.
        choices = envelope.get("choices")
        _require_review(isinstance(choices, list) and len(choices) == 1, "invalid_choices")
        choice = choices[0]
        _require_review(isinstance(choice, dict), "invalid_choice")
        _require_review(choice.get("finish_reason") == "stop", "incomplete_generation")
        message = choice.get("message")
    _require_review(isinstance(message, dict), "message_missing")
    _require_review(message.get("role") == "assistant", "invalid_message_role")
    _require_review(
        not message.get("tool_calls") and not message.get("refusal"), "nonfinal_message"
    )
    content = message.get("content")
    _require_review(_text(content), "final_content_missing")
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", content.strip(), flags=re.S | re.I)
    return _review_json(fence[1] if fence else content)


def _validate_review(report, packet, packet_hash, sources):
    expected = {
        "schema_version": 1,
        "packet_sha256": packet_hash,
        "artifact_version": packet["artifact_version"],
        "artifact_sha256": packet["artifact"]["sha256"],
        "rubric_version": packet["rubric_version"],
        "persona": packet["persona"],
    }
    _require_review(type(report.get("schema_version")) is int, "review_identity_mismatch")
    _require_review(
        all(report.get(key) == value for key, value in expected.items()), "review_identity_mismatch"
    )
    score = report.get("score")
    _require_review(
        "score" in report and (score is None or type(score) is int and 1 <= score <= 4),
        "invalid_score",
    )
    _require_review(_text(report.get("rationale")), "rationale_missing")
    limits = report.get("limitations")
    _require_review(
        isinstance(limits, list) and bool(limits) and all(map(_text, limits)), "limitations_missing"
    )
    findings = report.get("findings")
    _require_review(
        isinstance(findings, list) and len(findings) <= MAX_FINDINGS, "invalid_findings"
    )
    seen_ids, seen_changes = set(), set()
    for row in findings:
        _require_review(isinstance(row, dict), "invalid_finding")
        for field in (
            "id",
            "anchor",
            "quote",
            "source_doc_id",
            "source_quote",
            "issue",
            "recommendation",
        ):
            _require_review(_text(row.get(field)), "incomplete_finding")
        _require_review(row["id"] not in seen_ids, "duplicate_finding")
        seen_ids.add(row["id"])
        anchor = packet["artifact"]["anchors"].get(row["anchor"])
        _require_review(anchor is not None and row["quote"] in anchor, "unsupported_artifact_quote")
        source = sources.get(row["source_doc_id"])
        _require_review(
            source is not None and row["source_quote"] in source["text"], "unsupported_source_quote"
        )
        _require_review(
            row.get("kind") in ("defect", "missing_evidence", "optional"), "invalid_finding_kind"
        )
        _require_review(
            row.get("resolution_owner") in ("author", "user", "external"),
            "invalid_resolution_owner",
        )
        _require_review(
            row["kind"] != "missing_evidence" or row["resolution_owner"] in {"user", "external"},
            "unknown_fact_requires_input",
        )
        change = " ".join(row["recommendation"].casefold().split())
        _require_review(change not in seen_changes, "duplicate_recommendation")
        seen_changes.add(change)


def _review_markdown(report):
    """Render only validated fields; do not ask another model to summarize."""
    lines = [
        "# Saved artifact review",
        "",
        f"Artifact: {report['artifact_version']} / {report['artifact_sha256']}",
        f"Persona: {report['persona']}; rubric: {report['rubric_version']}",
        f"Model opinion (1–4): {report['score'] if report['score'] is not None else 'N/A'}",
        "",
        report["rationale"],
        "",
        "Identity and quotes checked. Semantic usefulness and current-version applicability require owner review.",
    ]
    for row in report["findings"]:
        lines.extend(
            [
                "",
                f"## {row['id']} — {row['kind']} ({row['resolution_owner']})",
                f"Artifact anchor: {row['anchor']}; quote: {row['quote']}",
                f"Source: {row['source_doc_id']}; quote: {row['source_quote']}",
                row["issue"],
                row["recommendation"],
            ]
        )
    lines.extend(["", "## Limitations", "", *[f"- {value}" for value in report["limitations"]]])
    return "\n".join(lines) + "\n"


def replay_review(
    packet_path: Path, response_path: Path, output: Path, *, http_status: int
) -> dict:
    """Replay one already-captured response offline into a new private directory.

    Callers supply credential-free inputs. No credentials, provider SDK, network,
    retries, current-artifact edits or interrupted-run recovery are involved.
    """
    # Refuse unbounded inputs before allocating a run or reading their content.
    for path in (packet_path, response_path):
        if path.stat().st_size > MAX_REVIEW_BYTES:
            raise ReviewFailure("review_input_too_large")
    packet_body, response_body = packet_path.read_bytes(), response_path.read_bytes()
    _require_review(
        max(len(packet_body), len(response_body)) <= MAX_REVIEW_BYTES, "review_input_too_large"
    )
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.mkdir(mode=0o700)  # Exclusive, including pending or partially written runs.

    def save(name, value):
        with (output / name).open("x", encoding="utf-8") as stream:
            (output / name).chmod(0o600)
            stream.write(value)

    def state(value):
        # Replace only this run's state, never an existing run or its raw inputs.
        temporary = output / "state.next.json"
        save(temporary.name, json.dumps(value, indent=2) + "\n")
        temporary.replace(output / "state.json")

    result = {
        "status": "pending",
        "pass": False,
        "score": None,
        "http_status": http_status,
        "packet_sha256": digest(packet_body),
        "response_sha256": digest(response_body),
        "configured_provider": None,
        "configured_model": None,
        "observed_provider": None,
        "observed_model": None,
        "semantic_acceptance": "not_assessed",
        "current_artifact_score": None,
        "model_calls": 0,
        "automatic_retries": 0,
    }
    state(result)
    # Byte copies precede decoding/parsing, including on malformed/HTTP-error inputs.
    for name, body in (("packet.json", packet_body), ("provider-response.body", response_body)):
        with (output / name).open("xb") as stream:
            (output / name).chmod(0o600)
            stream.write(body)
    try:
        packet = _review_json(packet_body)
        sources = _review_packet(packet)
        result.update(configured_provider=packet["provider"], configured_model=packet["model"])
        _require_review(
            type(http_status) is int and 200 <= http_status < 300, "provider_http_error"
        )
        envelope = _review_json(response_body)
        if _text(envelope.get("model")):
            result["observed_model"] = envelope["model"]
        report = _review_content(envelope, packet)
        _validate_review(report, packet, result["packet_sha256"], sources)
        # Keep the machine report readable by the revision recorder; Markdown is the reader view.
        feedback = json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n"
        _require_review(
            len(feedback.encode("utf-8")) <= MAX_REVIEW_BYTES, "review_feedback_too_large"
        )
        save("feedback.json", feedback)
        save("feedback.md", _review_markdown(report))
        result.update(status="requires_owner_review", score=report["score"], **{"pass": True})
    except ReviewFailure as error:
        result.update(status="failed", error_code=str(error))
    state(result)
    return result


def _read_review_file(path):
    with path.open("rb") as stream:
        body = stream.read(MAX_REVIEW_BYTES + 1)
    _require_review(len(body) <= MAX_REVIEW_BYTES, "review_input_too_large")
    return body, _review_json(body)


def _save_review_file(output, name, value):
    with (output / name).open("x", encoding="utf-8") as stream:
        (output / name).chmod(0o600)
        stream.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def record_review_revision(
    review: Path, decisions_path: Path, next_packet_path: Path, output: Path
) -> dict:
    """Record owner decisions and an explicitly supplied artifact; never edit it.

    Checks connect versions and findings. Whether an edit is useful or truthful
    remains the owner's judgment, not a semantic claim by this recorder.
    """
    _, state = _read_review_file(review / "state.json")
    _require_review(state.get("status") == "requires_owner_review", "review_not_complete")
    packet_body, packet = _read_review_file(review / "packet.json")
    _, report = _read_review_file(review / "feedback.json")
    response_body, envelope = _read_review_file(review / "provider-response.body")
    response_hash = digest(response_body)
    _require_review(
        state.get("packet_sha256") == digest(packet_body)
        and state.get("response_sha256") == response_hash,
        "review_receipt_mismatch",
    )
    sources = _review_packet(packet)
    _require_review(report == _review_content(envelope, packet), "review_feedback_mismatch")
    _validate_review(report, packet, digest(packet_body), sources)
    _, decisions = _read_review_file(decisions_path)
    next_body, next_packet = _read_review_file(next_packet_path)
    _review_packet(next_packet)
    _require_review(
        decisions.get("packet_sha256") == digest(packet_body), "decision_version_mismatch"
    )
    _require_review(decisions.get("response_sha256") == response_hash, "decision_review_mismatch")
    # A revision compares like with like. A changed task or rubric starts a new review.
    for key in ("task", "criteria", "rubric_version", "sources", "persona", "provider", "model"):
        _require_review(next_packet[key] == packet[key], "revision_context_changed")
    rows = decisions.get("decisions")
    _require_review(isinstance(rows, list), "decisions_missing")
    findings = {finding["id"] for finding in report["findings"]}
    seen, accepted = set(), []
    for row in rows:
        _require_review(isinstance(row, dict), "invalid_decision")
        key = row.get("finding_id")
        _require_review(
            _text(key) and key in findings and key not in seen, "invalid_decision_finding"
        )
        seen.add(key)
        _require_review(
            row.get("decision") in ("accept", "reject", "already_resolved", "needs_input"),
            "invalid_decision",
        )
        _require_review(_text(row.get("reason")), "decision_reason_missing")
        if row["decision"] == "accept":
            accepted.append(key)
    _require_review(seen == findings, "incomplete_decisions")
    changed = next_packet["artifact"]["sha256"] != packet["artifact"]["sha256"]
    _require_review(bool(accepted) == changed, "revision_without_accepted_change")
    _require_review(
        (next_packet["artifact_version"] != packet["artifact_version"]) == changed,
        "revision_version_mismatch",
    )
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.mkdir(mode=0o700)
    result = {
        "status": "revision_recorded" if changed else "artifact_retained",
        "pass": True,
        "from_packet_sha256": digest(packet_body),
        "from_response_sha256": response_hash,
        "to_packet_sha256": digest(next_body),
        "from_version": packet["artifact_version"],
        "to_version": next_packet["artifact_version"],
        "accepted_findings": accepted,
        "owner_decisions_recorded": True,
        "semantic_acceptance": "owner_decision",
        "current_artifact_score": None,
        "model_calls": 0,
    }
    _save_review_file(output, "decisions.json", decisions)
    _save_review_file(output, "artifact.json", next_packet["artifact"])
    _save_review_file(output, "state.json", result)
    return result


def run_review_example(fixtures: Path, output: Path) -> dict:
    """Replay a two-version synthetic cycle. No inference or automatic editing."""
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.mkdir(mode=0o700)
    _save_review_file(output, "pending.json", {"status": "pending", "synthetic": True})
    first = replay_review(
        fixtures / "packet.json", fixtures / "response.json", output / "review-v1", http_status=200
    )
    _require_review(first["pass"], "example_first_review_failed")
    revision = record_review_revision(
        output / "review-v1",
        fixtures / "decisions.json",
        fixtures / "packet-v2.json",
        output / "revision",
    )
    second = replay_review(
        fixtures / "packet-v2.json",
        fixtures / "response-v2.json",
        output / "review-v2",
        http_status=200,
    )
    _require_review(second["pass"], "example_second_review_failed")
    result = {
        "status": "synthetic_cycle_complete",
        "pass": True,
        "synthetic": True,
        "from_version": revision["from_version"],
        "to_version": revision["to_version"],
        "accepted_findings": revision["accepted_findings"],
        "model_calls": 0,
        "automatic_retries": 0,
        "quality_improvement_measured": False,
        "delivery_decision": "requires_owner_review",
    }
    _save_review_file(output, "summary.json", result)
    (output / "pending.json").unlink()
    return result


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
