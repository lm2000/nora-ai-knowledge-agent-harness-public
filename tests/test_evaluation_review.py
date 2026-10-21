"""Synthetic review receipts and owner decisions, never model-quality claims."""

import json
from pathlib import Path

import pytest

from nora.cli import main
from nora.common import digest
from nora.evaluation import (
    MAX_REVIEW_BYTES,
    ReviewFailure,
    record_review_revision,
    replay_review,
    run_review_example,
)

FIXTURES = Path(__file__).resolve().parents[1] / "examples/artifact-review"


def saved_response(tmp_path, mutate):
    envelope = json.loads((FIXTURES / "response.json").read_text())
    report = json.loads(envelope["choices"][0]["message"]["content"])
    mutate(envelope, report)
    envelope["choices"][0]["message"]["content"] = json.dumps(report)
    path = tmp_path / "response.json"
    path.write_text(json.dumps(envelope))
    return path


def test_example_records_decisions_versions_and_unchanged_scores(tmp_path):
    output = tmp_path / "cycle"
    result = run_review_example(FIXTURES, output)
    assert result["status"] == "synthetic_cycle_complete"
    assert result["accepted_findings"] == ["F1"]
    assert result["model_calls"] == 0 and not result["quality_improvement_measured"]
    assert not (output / "pending.json").exists()
    before = json.loads((output / "review-v1/packet.json").read_text())
    after = json.loads((output / "revision/artifact.json").read_text())
    assert "completed rollback rehearsal" not in before["artifact"]["text"]
    assert "completed rollback rehearsal" in after["text"]
    assert "five minutes" not in after["text"]
    assert after["text"].count("Open questions:") == 1
    revision = json.loads((output / "revision/state.json").read_text())
    assert revision["from_response_sha256"] == digest((FIXTURES / "response.json").read_bytes())
    for version in ("v1", "v2"):
        state = json.loads((output / f"review-{version}/state.json").read_text())
        assert state["score"] == 3  # Same fixture opinion, no numerical improvement.
        assert state["current_artifact_score"] is None
    with pytest.raises(FileExistsError):
        run_review_example(FIXTURES, output)


@pytest.mark.parametrize(
    "mutation,code",
    [
        (lambda e, r: r.update(artifact_version="atlas-other"), "review_identity_mismatch"),
        (lambda e, r: r.update(packet_sha256="f" * 64), "review_identity_mismatch"),
        (lambda e, r: r.update(persona="Another reviewer"), "review_identity_mismatch"),
        (lambda e, r: r.update(rubric_version="changed"), "review_identity_mismatch"),
        (lambda e, r: e.update(model="other-model"), "observed_model_mismatch"),
        (lambda e, r: r.update(score=0), "invalid_score"),
        (lambda e, r: r.update(score=True), "invalid_score"),
        (lambda e, r: r.pop("findings"), "invalid_findings"),
        (lambda e, r: r["findings"][0].update(quote="invented"), "unsupported_artifact_quote"),
        (lambda e, r: r["findings"][0].update(source_quote="invented"), "unsupported_source_quote"),
        (
            lambda e, r: r["findings"][0].update(kind="missing_evidence"),
            "unknown_fact_requires_input",
        ),
        (lambda e, r: r["findings"][0].update(kind=[]), "invalid_finding_kind"),
        (lambda e, r: r["findings"].append(dict(r["findings"][0])), "duplicate_finding"),
        (
            lambda e, r: r["findings"][1].update(
                recommendation="  ADD the COMPLETED rollback rehearsal as a release prerequisite. "
            ),
            "duplicate_recommendation",
        ),
        (lambda e, r: e["choices"][0].update(finish_reason="length"), "incomplete_generation"),
    ],
)
def test_invalid_reviews_preserve_raw_response_and_expose_no_score(tmp_path, mutation, code):
    response = saved_response(tmp_path, mutation)
    output = tmp_path / "review"
    result = replay_review(FIXTURES / "packet.json", response, output, http_status=200)
    assert result["status"] == "failed" and result["error_code"] == code
    assert result["score"] is None and not result["pass"]
    assert (output / "provider-response.body").read_bytes() == response.read_bytes()
    assert not (output / "feedback.md").exists()


@pytest.mark.parametrize("body", [b"{", b"{}", b'{"model":"a","model":"b"}', b'{"model":NaN}'])
def test_malformed_envelopes_fail_without_losing_input(tmp_path, body):
    response = tmp_path / "body"
    response.write_bytes(body)
    output = tmp_path / "review"
    result = replay_review(FIXTURES / "packet.json", response, output, http_status=200)
    assert not result["pass"] and result["score"] is None
    assert (output / "provider-response.body").read_bytes() == body


@pytest.mark.parametrize("content", [None, "", "   "])
def test_reasoning_is_not_a_substitute_for_final_content(tmp_path, content):
    response = tmp_path / "body"
    response.write_text(
        json.dumps(
            {
                "model": "scripted-reviewer",
                "done": True,
                "done_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": content,
                    "thinking": "This reasoning is not a review.",
                },
            }
        )
    )
    result = replay_review(FIXTURES / "packet.json", response, tmp_path / "review", http_status=200)
    assert result["error_code"] == "final_content_missing" and result["score"] is None


def test_native_ollama_and_clean_no_change_review(tmp_path):
    envelope = json.loads((FIXTURES / "response.json").read_text())
    report = json.loads(envelope["choices"][0]["message"]["content"])
    report["findings"] = []
    report["score"] = None
    response = tmp_path / "body"
    response.write_text(
        json.dumps(
            {
                "model": "scripted-reviewer",
                "done": True,
                "done_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "```json\n" + json.dumps(report) + "\n```",
                },
            }
        )
    )
    review = tmp_path / "review"
    result = replay_review(FIXTURES / "packet.json", response, review, http_status=200)
    assert result["pass"] and result["score"] is None
    assert result["observed_provider"] is None
    decisions = tmp_path / "decisions.json"
    decisions.write_text(
        json.dumps(
            {
                "packet_sha256": digest((FIXTURES / "packet.json").read_bytes()),
                "response_sha256": digest(response.read_bytes()),
                "decisions": [],
            }
        )
    )
    retained = record_review_revision(
        review, decisions, FIXTURES / "packet.json", tmp_path / "retained"
    )
    assert retained["status"] == "artifact_retained"


def test_http_failure_and_corrupted_frozen_source_are_not_scores(tmp_path):
    assert (
        replay_review(
            FIXTURES / "packet.json", FIXTURES / "response.json", tmp_path / "http", http_status=402
        )["error_code"]
        == "provider_http_error"
    )
    packet = json.loads((FIXTURES / "packet.json").read_text())
    packet["sources"][0]["text"] += " Changed source."
    path = tmp_path / "packet.json"
    path.write_text(json.dumps(packet))
    assert (
        replay_review(path, FIXTURES / "response.json", tmp_path / "corrupt", http_status=200)[
            "error_code"
        ]
        == "source_hash_mismatch"
    )


def test_oversized_response_is_rejected_before_run_creation(tmp_path):
    response = tmp_path / "oversized"
    response.write_bytes(b"x" * (MAX_REVIEW_BYTES + 1))
    with pytest.raises(ReviewFailure, match="review_input_too_large"):
        replay_review(FIXTURES / "packet.json", response, tmp_path / "review", http_status=200)
    assert not (tmp_path / "review").exists()


def test_interrupted_run_retains_pending_state_and_refuses_overwrite(tmp_path, monkeypatch):
    def crash(body):
        raise KeyboardInterrupt

    monkeypatch.setattr("nora.evaluation._review_json", crash)
    output = tmp_path / "review"
    with pytest.raises(KeyboardInterrupt):
        replay_review(FIXTURES / "packet.json", FIXTURES / "response.json", output, http_status=200)
    assert json.loads((output / "state.json").read_text())["status"] == "pending"
    assert (output / "provider-response.body").is_file()
    with pytest.raises(FileExistsError):
        replay_review(FIXTURES / "packet.json", FIXTURES / "response.json", output, http_status=200)


@pytest.mark.parametrize(
    "change,code",
    [
        (lambda d: d.update(packet_sha256="a" * 64), "decision_version_mismatch"),
        (lambda d: d.pop("response_sha256"), "decision_review_mismatch"),
        (lambda d: d["decisions"].pop(), "incomplete_decisions"),
        (lambda d: d["decisions"].append(d["decisions"][0]), "invalid_decision_finding"),
    ],
)
def test_stale_or_incomplete_owner_decisions_are_rejected(tmp_path, change, code):
    replay_review(
        FIXTURES / "packet.json", FIXTURES / "response.json", tmp_path / "review", http_status=200
    )
    decisions = json.loads((FIXTURES / "decisions.json").read_text())
    change(decisions)
    path = tmp_path / "decisions.json"
    path.write_text(json.dumps(decisions))
    with pytest.raises(ReviewFailure, match=code):
        record_review_revision(
            tmp_path / "review", path, FIXTURES / "packet-v2.json", tmp_path / "revision"
        )
    assert not (tmp_path / "revision").exists()


def test_cli_example_does_not_load_service_settings(tmp_path, monkeypatch, capsys):
    def forbidden():
        raise AssertionError("Offline review must not load live configuration")

    monkeypatch.setattr("nora.cli.Settings.from_env", forbidden)
    assert (
        main(["review-example", "--fixtures", str(FIXTURES), "--output", str(tmp_path / "cycle")])
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["synthetic"] and result["model_calls"] == 0


def test_revision_cannot_claim_an_edit_without_changed_content(tmp_path):
    review = tmp_path / "review"
    replay_review(FIXTURES / "packet.json", FIXTURES / "response.json", review, http_status=200)
    with pytest.raises(ReviewFailure, match="revision_without_accepted_change"):
        record_review_revision(
            review, FIXTURES / "decisions.json", FIXTURES / "packet.json", tmp_path / "revision"
        )


def test_revision_does_not_silently_change_task_or_rubric(tmp_path):
    review = tmp_path / "review"
    replay_review(FIXTURES / "packet.json", FIXTURES / "response.json", review, http_status=200)
    packet = json.loads((FIXTURES / "packet-v2.json").read_text())
    packet["criteria"] = ["A new criterion"]
    path = tmp_path / "next.json"
    path.write_text(json.dumps(packet))
    with pytest.raises(ReviewFailure, match="revision_context_changed"):
        record_review_revision(review, FIXTURES / "decisions.json", path, tmp_path / "revision")


def test_decisions_cannot_transfer_to_another_review_of_the_same_packet(tmp_path):
    def swap_ids(envelope, report):
        report["findings"][0]["id"], report["findings"][1]["id"] = (
            report["findings"][1]["id"],
            report["findings"][0]["id"],
        )

    response = saved_response(tmp_path, swap_ids)
    review = tmp_path / "review"
    assert replay_review(FIXTURES / "packet.json", response, review, http_status=200)["pass"]
    with pytest.raises(ReviewFailure, match="decision_review_mismatch"):
        record_review_revision(
            review, FIXTURES / "decisions.json", FIXTURES / "packet-v2.json", tmp_path / "revision"
        )
    assert not (tmp_path / "revision").exists()


def test_revision_rejects_feedback_changed_after_replay(tmp_path):
    review = tmp_path / "review"
    replay_review(FIXTURES / "packet.json", FIXTURES / "response.json", review, http_status=200)
    path = review / "feedback.json"
    report = json.loads(path.read_text())
    report["findings"][0]["recommendation"] = "Keep the rollback prerequisite omitted."
    path.write_text(json.dumps(report))
    with pytest.raises(ReviewFailure, match="review_feedback_mismatch"):
        record_review_revision(
            review, FIXTURES / "decisions.json", FIXTURES / "packet-v2.json", tmp_path / "revision"
        )
    assert not (tmp_path / "revision").exists()


def test_revision_rejects_saved_response_changed_after_replay(tmp_path):
    review = tmp_path / "review"
    replay_review(FIXTURES / "packet.json", FIXTURES / "response.json", review, http_status=200)
    path = review / "provider-response.body"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ReviewFailure, match="review_receipt_mismatch"):
        record_review_revision(
            review, FIXTURES / "decisions.json", FIXTURES / "packet-v2.json", tmp_path / "revision"
        )
    assert not (tmp_path / "revision").exists()


def test_large_valid_review_can_advance_to_revision(tmp_path):
    response = saved_response(tmp_path, lambda e, r: r.update(limitations=["x"] * 140000))
    assert response.stat().st_size <= MAX_REVIEW_BYTES
    review = tmp_path / "review"
    assert replay_review(FIXTURES / "packet.json", response, review, http_status=200)["pass"]
    decisions = json.loads((FIXTURES / "decisions.json").read_text())
    decisions["response_sha256"] = digest(response.read_bytes())
    path = tmp_path / "decisions.json"
    path.write_text(json.dumps(decisions))
    result = record_review_revision(
        review, path, FIXTURES / "packet-v2.json", tmp_path / "revision"
    )
    assert result["status"] == "revision_recorded"


def test_expanded_feedback_fails_before_claiming_owner_review(tmp_path):
    envelope = json.loads((FIXTURES / "response.json").read_text())
    content = envelope["choices"][0]["message"]["content"].rstrip()
    envelope["choices"][0]["message"]["content"] = (
        content[:-1] + ',"extra":[' + ",".join(["1e15"] * 70000) + "]}"
    )
    response = tmp_path / "response.json"
    response.write_text(json.dumps(envelope))
    assert response.stat().st_size <= MAX_REVIEW_BYTES
    output = tmp_path / "review"
    result = replay_review(FIXTURES / "packet.json", response, output, http_status=200)
    assert result["status"] == "failed"
    assert result["error_code"] == "review_feedback_too_large"
    assert result["score"] is None
    assert not (output / "feedback.json").exists()
    assert (output / "provider-response.body").read_bytes() == response.read_bytes()
