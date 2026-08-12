"""Integration tests for the frozen batch scorer."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


EVALUATOR_ROOT = Path(__file__).resolve().parents[1]
SCORE_PATH = EVALUATOR_ROOT / "score.py"


def sample_gold() -> dict[str, object]:
    return {
        "landlord_name": "Mariam Qasim Al Nuaimi",
        "tenant_name": "Daniel Okafor",
        "unit_number": "B-1204",
        "community": "Al Nakheel Gardens",
        "contract_start_date": "2026-09-01",
        "contract_end_date": "2027-08-31",
        "annual_rent_aed": 85000,
        "security_deposit_aed": None,
        "number_of_payments": 4,
        "notice_period_days": 60,
        "early_termination_penalty_months": 1.5,
        "furnished_status": None,
    }


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_run(
    doc_id: str,
    rep: int,
    *,
    status: str = "completed",
    fence_stripped: bool = False,
    retry_log: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "doc_id": doc_id,
        "rep": rep,
        "status": status,
        "fence_stripped": fence_stripped,
        "retry_log": retry_log or [],
        "files": {"prediction": f"preds/rep{rep}/{doc_id}.json"},
    }


def write_batch(
    root: Path,
    *,
    doc_ids: list[str],
    reps: int,
    runs: list[dict[str, object]],
) -> Path:
    documents: dict[str, dict[str, str]] = {}
    for doc_id in doc_ids:
        document_bytes = f"Fixture document {doc_id}.\n".encode("utf-8")
        document_path = root / "01-fixtures" / "docs" / "train" / f"{doc_id}.txt"
        document_path.parent.mkdir(parents=True, exist_ok=True)
        document_path.write_bytes(document_bytes)
        documents[doc_id] = {
            "path": f"01-fixtures/docs/train/{doc_id}.txt",
            "sha256": hashlib.sha256(document_bytes).hexdigest(),
        }
    batch_dir = root / "05-runs" / "batch"
    write_json(
        batch_dir / "manifest.json",
        {
            "batch_id": "handcrafted",
            "doc_ids": doc_ids,
            "documents": documents,
            "reps": reps,
            "runs": runs,
        },
    )
    return batch_dir


def invoke_score(batch_dir: Path, gold_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCORE_PATH),
            "--batch-dir",
            str(batch_dir),
            "--gold-root",
            str(gold_root),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_completeness_refuses_missing_run(tmp_path: Path) -> None:
    gold_root = tmp_path / "gold"
    for doc_id in ("doc-a", "doc-b"):
        write_json(gold_root / f"{doc_id}.json", sample_gold())
    runs = [
        make_run("doc-a", 1),
        make_run("doc-b", 1),
        make_run("doc-a", 2),
    ]
    batch_dir = write_batch(tmp_path, doc_ids=["doc-a", "doc-b"], reps=2, runs=runs)
    for run in runs:
        write_json(batch_dir / str(run["files"]["prediction"]), sample_gold())

    completed = invoke_score(batch_dir, gold_root)

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "completeness check failed" in completed.stderr
    assert "missing run doc-b rep2" in completed.stderr


def test_completeness_refuses_transport_failure(tmp_path: Path) -> None:
    gold_root = tmp_path / "gold"
    write_json(gold_root / "doc-a.json", sample_gold())
    run = make_run("doc-a", 1, status="transport_failure")
    batch_dir = write_batch(tmp_path, doc_ids=["doc-a"], reps=1, runs=[run])

    completed = invoke_score(batch_dir, gold_root)

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "transport failure doc-a rep1" in completed.stderr


def test_completeness_refuses_rep_gap(tmp_path: Path) -> None:
    gold_root = tmp_path / "gold"
    write_json(gold_root / "doc-a.json", sample_gold())
    runs = [make_run("doc-a", 1), make_run("doc-a", 3)]
    batch_dir = write_batch(tmp_path, doc_ids=["doc-a"], reps=3, runs=runs)
    for run in runs:
        write_json(batch_dir / str(run["files"]["prediction"]), sample_gold())

    completed = invoke_score(batch_dir, gold_root)

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "rep gap for doc-a: expected [1, 2, 3], observed [1, 3]" in completed.stderr


def test_completeness_refuses_missing_prediction_file(tmp_path: Path) -> None:
    gold_root = tmp_path / "gold"
    write_json(gold_root / "doc-a.json", sample_gold())
    batch_dir = write_batch(
        tmp_path, doc_ids=["doc-a"], reps=1, runs=[make_run("doc-a", 1)]
    )

    completed = invoke_score(batch_dir, gold_root)

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "missing prediction file for doc-a rep1" in completed.stderr


def test_fixture_identity_accepts_untouched_batch_and_refuses_wrong_hash(
    tmp_path: Path,
) -> None:
    gold_root = tmp_path / "gold"
    write_json(gold_root / "doc-a.json", sample_gold())
    run = make_run("doc-a", 1)
    batch_dir = write_batch(tmp_path, doc_ids=["doc-a"], reps=1, runs=[run])
    write_json(batch_dir / "preds/rep1/doc-a.json", sample_gold())

    untouched = invoke_score(batch_dir, gold_root)

    assert untouched.returncode == 0, untouched.stderr
    assert json.loads(untouched.stdout)["pooled_mean_field_accuracy"] == 1.0

    manifest_path = batch_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["documents"]["doc-a"]["sha256"] = "0" * 64
    write_json(manifest_path, manifest)

    doctored = invoke_score(batch_dir, gold_root)

    assert doctored.returncode == 2
    assert doctored.stdout == ""
    assert "fixture identity mismatch" in doctored.stderr
    assert "doc-a" in doctored.stderr


def test_two_rep_aggregation_math_and_manifest_doc_filter(tmp_path: Path) -> None:
    gold_root = tmp_path / "gold"
    for doc_id in ("doc-a", "doc-b", "doc-extra"):
        write_json(gold_root / f"{doc_id}.json", sample_gold())
    runs = [
        make_run("doc-a", 1, fence_stripped=True),
        make_run("doc-b", 1),
        make_run("doc-a", 2),
        make_run("doc-b", 2, fence_stripped=True),
    ]
    batch_dir = write_batch(tmp_path, doc_ids=["doc-a", "doc-b"], reps=2, runs=runs)

    perfect = sample_gold()
    half = dict(perfect)
    for field in tuple(perfect)[:6]:
        half[field] = "wrong"
    empty: dict[str, object] = {}
    write_json(batch_dir / "preds/rep1/doc-a.json", perfect)
    write_json(batch_dir / "preds/rep1/doc-b.json", half)
    write_json(batch_dir / "preds/rep2/doc-a.json", empty)
    write_json(batch_dir / "preds/rep2/doc-b.json", perfect)

    completed = invoke_score(batch_dir, gold_root)

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["pooled_mean_field_accuracy"] == pytest.approx(30 / 48)
    assert report["per_rep"]["1"]["mean_field_accuracy"] == pytest.approx(18 / 24)
    assert report["per_rep"]["2"]["mean_field_accuracy"] == pytest.approx(12 / 24)
    assert report["per_field"]["landlord_name"] == {
        "correct": 2,
        "total": 4,
        "accuracy": 0.5,
    }
    assert report["per_field"]["annual_rent_aed"] == {
        "correct": 3,
        "total": 4,
        "accuracy": 0.75,
    }
    assert report["per_document"]["doc-a"]["mean_field_accuracy"] == pytest.approx(12 / 24)
    assert report["per_document"]["doc-b"]["mean_field_accuracy"] == pytest.approx(18 / 24)
    assert set(report["per_document"]) == {"doc-a", "doc-b"}
    assert report["fence_stripped"] == 2
    assert report["missed_present"] == 10
    assert report["unparseable"] == 0
    assert report["wrong_shape"] == 0
    assert report["missing"] == 0


def test_turn_check_retries_counts_only_turn_guard_retry_log_entries(
    tmp_path: Path,
) -> None:
    gold_root = tmp_path / "gold"
    for doc_id in ("doc-a", "doc-b"):
        write_json(gold_root / f"{doc_id}.json", sample_gold())
    runs = [
        make_run(
            "doc-a",
            1,
            retry_log=[
                {"reason": "CLI result used 2 turns"},
                {"reason": "nonzero CLI exit (7)"},
                {"reason": None},
            ],
        ),
        make_run(
            "doc-b",
            1,
            retry_log=[
                {"reason": "CLI result contained permission denials"},
                {"reason": None},
            ],
        ),
    ]
    batch_dir = write_batch(tmp_path, doc_ids=["doc-a", "doc-b"], reps=1, runs=runs)
    for doc_id in ("doc-a", "doc-b"):
        write_json(batch_dir / f"preds/rep1/{doc_id}.json", sample_gold())

    completed = invoke_score(batch_dir, gold_root)

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["turn_check_retries"] == 2


def test_grader_counters_pass_through_pooled_score(tmp_path: Path) -> None:
    gold_root = tmp_path / "gold"
    for doc_id in ("doc-a", "doc-b", "doc-c"):
        write_json(gold_root / f"{doc_id}.json", sample_gold())
    runs = [
        make_run("doc-a", 1, status="model_failure"),
        make_run("doc-b", 1),
        make_run("doc-c", 1),
    ]
    batch_dir = write_batch(
        tmp_path, doc_ids=["doc-a", "doc-b", "doc-c"], reps=1, runs=runs
    )
    invalid_path = batch_dir / "preds/rep1/doc-a.json"
    invalid_path.parent.mkdir(parents=True, exist_ok=True)
    invalid_path.write_text("not json", encoding="utf-8")
    write_json(batch_dir / "preds/rep1/doc-b.json", ["wrong shape"])
    two_counter_prediction = sample_gold()
    two_counter_prediction["security_deposit_aed"] = 4250
    two_counter_prediction["notice_period_days"] = None
    write_json(batch_dir / "preds/rep1/doc-c.json", two_counter_prediction)

    completed = invoke_score(batch_dir, gold_root)

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["unparseable"] == 1
    assert report["wrong_shape"] == 1
    assert report["missing"] == 0
    assert report["hallucinated_absent"] == 1
    assert report["missed_present"] == 1
    assert report["per_document"]["doc-a"]["unparseable"] == 1
    assert report["per_document"]["doc-b"]["wrong_shape"] == 1
    assert report["per_document"]["doc-c"]["hallucinated_absent"] == 1
    assert report["per_document"]["doc-c"]["missed_present"] == 1
