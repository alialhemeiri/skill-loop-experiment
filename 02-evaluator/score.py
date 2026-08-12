#!/usr/bin/env python3
"""Validate and score one complete autoresearch runner batch."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from grader import FIELDS, TOTAL_FIELDS, GoldRecordError, grade_files


TERMINAL_STATUSES = frozenset(("completed", "model_failure", "transport_failure"))
COUNTERS = (
    "unparseable",
    "wrong_shape",
    "missing",
    "hallucinated_absent",
    "missed_present",
)


class ScoreError(ValueError):
    """Raised when a batch cannot produce a trustworthy score."""


def _read_manifest(batch_dir: Path) -> dict[str, Any]:
    manifest_path = batch_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ScoreError(f"cannot read valid batch manifest {manifest_path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ScoreError(f"batch manifest root must be an object: {manifest_path}")
    return manifest


def _safe_batch_path(batch_dir: Path, relative: str) -> Path | None:
    if not isinstance(relative, str) or not relative:
        return None
    candidate = (batch_dir / relative).resolve()
    try:
        candidate.relative_to(batch_dir.resolve())
    except ValueError:
        return None
    return candidate


def _recorded_document_path(batch_dir: Path, recorded: Any) -> Path | None:
    if not isinstance(recorded, str) or not recorded:
        return None
    path = Path(recorded)
    if path.is_absolute():
        return path.resolve()
    return (batch_dir.parent.parent / path).resolve()


def _is_turn_check_reason(reason: Any) -> bool:
    return bool(
        reason == "CLI result contained permission denials"
        or (
            isinstance(reason, str)
            and reason.startswith("CLI result used ")
            and reason.endswith(" turns")
        )
    )


def assert_complete_batch(
    batch_dir: Path, manifest: dict[str, Any]
) -> tuple[list[str], int, dict[tuple[str, int], dict[str, Any]]]:
    """Return the expected run index or raise with every completeness defect."""

    problems: list[str] = []
    doc_ids = manifest.get("doc_ids")
    reps = manifest.get("reps")
    runs = manifest.get("runs")
    if (
        not isinstance(doc_ids, list)
        or not doc_ids
        or not all(isinstance(doc_id, str) and doc_id for doc_id in doc_ids)
        or len(set(doc_ids)) != len(doc_ids)
    ):
        problems.append("manifest doc_ids must be a non-empty unique string list")
        doc_ids = []
    if type(reps) is not int or reps < 1:
        problems.append("manifest reps must be an integer of at least 1")
        reps = 0
    if not isinstance(runs, list):
        problems.append("manifest runs must be a list")
        runs = []

    documents = manifest.get("documents")
    fixture_mismatches: list[str] = []
    if not isinstance(documents, dict):
        problems.append("manifest documents must be an object")
    else:
        if set(documents) != set(doc_ids):
            problems.append("manifest documents must match doc_ids exactly")
        for doc_id in doc_ids:
            record = documents.get(doc_id)
            if not isinstance(record, dict):
                fixture_mismatches.append(doc_id)
                continue
            expected_hash = record.get("sha256")
            document_path = _recorded_document_path(batch_dir, record.get("path"))
            if not isinstance(expected_hash, str) or document_path is None:
                fixture_mismatches.append(doc_id)
                continue
            try:
                actual_hash = hashlib.sha256(document_path.read_bytes()).hexdigest()
            except OSError:
                fixture_mismatches.append(doc_id)
                continue
            if actual_hash != expected_hash:
                fixture_mismatches.append(doc_id)
    if fixture_mismatches:
        problems.append(
            "fixture identity mismatch for document(s): "
            + ", ".join(sorted(set(fixture_mismatches)))
        )

    index: dict[tuple[str, int], dict[str, Any]] = {}
    observed_reps: dict[str, set[int]] = {doc_id: set() for doc_id in doc_ids}
    for position, run in enumerate(runs, start=1):
        if not isinstance(run, dict):
            problems.append(f"run record {position} is not an object")
            continue
        doc_id = run.get("doc_id")
        rep = run.get("rep")
        if not isinstance(doc_id, str) or type(rep) is not int:
            problems.append(f"run record {position} has invalid doc_id or rep")
            continue
        key = (doc_id, rep)
        if key in index:
            problems.append(f"duplicate run {doc_id} rep{rep}")
            continue
        index[key] = run
        if doc_id in observed_reps:
            observed_reps[doc_id].add(rep)
        if doc_id not in doc_ids or rep < 1 or rep > reps:
            problems.append(f"unexpected run {doc_id} rep{rep}")

    expected_reps = list(range(1, reps + 1))
    for doc_id in doc_ids:
        observed = sorted(observed_reps[doc_id])
        if observed != expected_reps:
            problems.append(
                f"rep gap for {doc_id}: expected {expected_reps}, observed {observed}"
            )
        for rep in expected_reps:
            key = (doc_id, rep)
            run = index.get(key)
            if run is None:
                problems.append(f"missing run {doc_id} rep{rep}")
                continue
            status = run.get("status")
            if status not in TERMINAL_STATUSES:
                problems.append(f"non-terminal run {doc_id} rep{rep}: {status!r}")
            if status == "transport_failure":
                problems.append(f"transport failure {doc_id} rep{rep}")
            files = run.get("files")
            prediction_rel = files.get("prediction") if isinstance(files, dict) else None
            prediction_path = _safe_batch_path(batch_dir, prediction_rel)
            if prediction_path is None:
                problems.append(f"invalid prediction path for {doc_id} rep{rep}")
            elif not prediction_path.is_file():
                problems.append(f"missing prediction file for {doc_id} rep{rep}")

    if problems:
        details = "\n".join(f"- {problem}" for problem in problems)
        raise ScoreError(f"completeness check failed:\n{details}")
    return doc_ids, reps, index


def _empty_counter_map() -> dict[str, int]:
    return {counter: 0 for counter in COUNTERS}


def score_batch(batch_dir: Path | str, gold_root: Path | str) -> dict[str, Any]:
    batch_path = Path(batch_dir).resolve()
    gold_path = Path(gold_root).resolve()
    manifest = _read_manifest(batch_path)
    doc_ids, reps, run_index = assert_complete_batch(batch_path, manifest)

    pooled_correct = 0
    pooled_field_correct = {field: 0 for field in FIELDS}
    pooled_counters = _empty_counter_map()
    per_rep: dict[str, dict[str, Any]] = {}
    per_document_work: dict[str, dict[str, Any]] = {
        doc_id: {
            "correct_fields": 0,
            "total_fields": reps * TOTAL_FIELDS,
            "field_correct": {field: 0 for field in FIELDS},
            "counters": _empty_counter_map(),
            "per_rep": {},
        }
        for doc_id in doc_ids
    }

    for rep in range(1, reps + 1):
        rep_correct = 0
        rep_counters = _empty_counter_map()
        for doc_id in doc_ids:
            run = run_index[(doc_id, rep)]
            prediction_rel = run["files"]["prediction"]
            prediction_path = _safe_batch_path(batch_path, prediction_rel)
            assert prediction_path is not None
            reference_path = gold_path / f"{doc_id}.json"
            try:
                grade = grade_files(prediction_path, reference_path)
            except GoldRecordError as exc:
                raise ScoreError(f"cannot score {doc_id} rep{rep}: {exc}") from exc
            if grade["missing"]:
                raise ScoreError(
                    "completeness check failed:\n"
                    f"- missing prediction file for {doc_id} rep{rep} during scoring"
                )

            pooled_correct += grade["correct_fields"]
            rep_correct += grade["correct_fields"]
            document = per_document_work[doc_id]
            document["correct_fields"] += grade["correct_fields"]
            for field, correct in grade["field_results"].items():
                value = int(correct)
                pooled_field_correct[field] += value
                document["field_correct"][field] += value
            for counter in COUNTERS:
                amount = int(grade[counter])
                pooled_counters[counter] += amount
                rep_counters[counter] += amount
                document["counters"][counter] += amount
            document["per_rep"][str(rep)] = {
                "score": grade["score"],
                "correct_fields": grade["correct_fields"],
                "total_fields": grade["total_fields"],
                "field_results": grade["field_results"],
                **{counter: grade[counter] for counter in COUNTERS},
            }

        rep_total = len(doc_ids) * TOTAL_FIELDS
        per_rep[str(rep)] = {
            "mean_field_accuracy": rep_correct / rep_total,
            "correct_fields": rep_correct,
            "total_fields": rep_total,
            **rep_counters,
        }

    total_runs = len(doc_ids) * reps
    pooled_total = total_runs * TOTAL_FIELDS
    per_field = {
        field: {
            "correct": pooled_field_correct[field],
            "total": total_runs,
            "accuracy": pooled_field_correct[field] / total_runs,
        }
        for field in FIELDS
    }
    per_document: dict[str, dict[str, Any]] = {}
    for doc_id, work in per_document_work.items():
        per_document[doc_id] = {
            "mean_field_accuracy": work["correct_fields"] / work["total_fields"],
            "correct_fields": work["correct_fields"],
            "total_fields": work["total_fields"],
            "per_field": {
                field: {
                    "correct": work["field_correct"][field],
                    "total": reps,
                    "accuracy": work["field_correct"][field] / reps,
                }
                for field in FIELDS
            },
            "per_rep": work["per_rep"],
            **work["counters"],
        }

    return {
        "batch_id": manifest.get("batch_id"),
        "documents": len(doc_ids),
        "reps": reps,
        "runs": total_runs,
        "pooled_mean_field_accuracy": pooled_correct / pooled_total,
        "correct_fields": pooled_correct,
        "total_fields": pooled_total,
        "per_rep": per_rep,
        "per_field": per_field,
        "per_document": per_document,
        **pooled_counters,
        "fence_stripped": sum(
            int(run.get("fence_stripped") is True) for run in run_index.values()
        ),
        "turn_check_retries": sum(
            1
            for run in run_index.values()
            for retry in (
                run.get("retry_log") if isinstance(run.get("retry_log"), list) else []
            )
            if isinstance(retry, dict) and _is_turn_check_reason(retry.get("reason"))
        ),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", required=True, type=Path)
    parser.add_argument("--gold-root", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        report = score_batch(args.batch_dir, args.gold_root)
    except ScoreError as exc:
        print(f"score error: {exc}", file=sys.stderr)
        return 2
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2, allow_nan=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
