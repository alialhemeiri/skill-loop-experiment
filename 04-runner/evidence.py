#!/usr/bin/env python3
"""Build a deterministic, training-only evidence pack for one runner batch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Sequence


EVALUATOR_DIR = Path(__file__).resolve().parent.parent / "02-evaluator"
if str(EVALUATOR_DIR) not in sys.path:
    sys.path.insert(0, str(EVALUATOR_DIR))

import grader  # noqa: E402  (the frozen sibling module is added above)
import score  # noqa: E402  (the frozen sibling module is added above)


FOOTER = (
    "This pack contains training-set data only. Holdout documents and holdout gold exist "
    "but are never shown to you."
)
PACK_COUNTERS = (
    "unparseable",
    "wrong_shape",
    "missing",
    "hallucinated_absent",
    "missed_present",
    "fence_stripped",
    "turn_check_retries",
)


class EvidenceError(ValueError):
    """Raised when an evidence pack cannot be built safely."""


def _contains_holdout(value: Any) -> bool:
    return isinstance(value, str) and "holdout" in value.casefold()


def _document_records(manifest: dict[str, Any]) -> list[tuple[str, Any]]:
    records: list[tuple[str, Any]] = []
    documents = manifest.get("documents")
    if isinstance(documents, dict):
        records.extend((f"documents.{doc_id}", record) for doc_id, record in documents.items())

    snapshots = manifest.get("fixture_snapshots")
    snapshot_documents = snapshots.get("documents") if isinstance(snapshots, dict) else None
    if isinstance(snapshot_documents, dict):
        records.extend(
            (f"fixture_snapshots.documents.{doc_id}", record)
            for doc_id, record in snapshot_documents.items()
        )
    return records


def assert_training_only(manifest: dict[str, Any]) -> None:
    """Fail closed when the manifest identifies any held-out document source."""

    docs_dir = manifest.get("docs_dir")
    if not isinstance(docs_dir, str) or not docs_dir:
        raise EvidenceError(
            "refusing evidence pack: manifest docs_dir must be a non-empty string"
        )
    if _contains_holdout(docs_dir):
        raise EvidenceError(
            "refusing evidence pack: batch docs directory contains 'holdout'"
        )

    for label, record in _document_records(manifest):
        document_path = record.get("path") if isinstance(record, dict) else None
        if _contains_holdout(document_path):
            raise EvidenceError(
                f"refusing evidence pack: manifest document path {label} contains 'holdout'"
            )


def _manifest_identity(manifest: dict[str, Any]) -> tuple[str, str, str]:
    batch_id = manifest.get("batch_id")
    skill = manifest.get("skill")
    skill_path = skill.get("path") if isinstance(skill, dict) else None
    skill_sha256 = skill.get("sha256") if isinstance(skill, dict) else None
    if not isinstance(batch_id, str) or not batch_id:
        raise EvidenceError("manifest batch_id must be a non-empty string")
    if not isinstance(skill_path, str) or not skill_path:
        raise EvidenceError("manifest skill.path must be a non-empty string")
    if not isinstance(skill_sha256, str) or not skill_sha256:
        raise EvidenceError("manifest skill.sha256 must be a non-empty string")
    return batch_id, skill_path, skill_sha256


def _json_literal(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def _skip_json_whitespace(text: str, position: int) -> int:
    while position < len(text) and text[position] in " \t\r\n":
        position += 1
    return position


def _top_level_value_literals(prediction_text: str) -> dict[str, str]:
    """Return each top-level object's exact value token from valid JSON text."""

    decoder = json.JSONDecoder()
    position = _skip_json_whitespace(prediction_text, 0)
    if position >= len(prediction_text) or prediction_text[position] != "{":
        raise EvidenceError("loaded object prediction has no opening brace")
    position = _skip_json_whitespace(prediction_text, position + 1)
    literals: dict[str, str] = {}
    if position < len(prediction_text) and prediction_text[position] == "}":
        position = _skip_json_whitespace(prediction_text, position + 1)
        if position != len(prediction_text):
            raise EvidenceError("loaded object prediction has trailing content")
        return literals

    try:
        while position < len(prediction_text):
            key, position = decoder.raw_decode(prediction_text, position)
            if not isinstance(key, str):
                raise EvidenceError("loaded object prediction has a non-string key")
            position = _skip_json_whitespace(prediction_text, position)
            if position >= len(prediction_text) or prediction_text[position] != ":":
                raise EvidenceError("loaded object prediction has no colon after a key")
            value_start = _skip_json_whitespace(prediction_text, position + 1)
            _value, value_end = decoder.raw_decode(prediction_text, value_start)
            literals[key] = prediction_text[value_start:value_end]
            position = _skip_json_whitespace(prediction_text, value_end)
            if position < len(prediction_text) and prediction_text[position] == ",":
                position = _skip_json_whitespace(prediction_text, position + 1)
                continue
            if position < len(prediction_text) and prediction_text[position] == "}":
                position = _skip_json_whitespace(prediction_text, position + 1)
                if position != len(prediction_text):
                    raise EvidenceError("loaded object prediction has trailing content")
                return literals
            raise EvidenceError("loaded object prediction has no comma or closing brace")
    except json.JSONDecodeError as exc:
        raise EvidenceError(
            f"cannot locate verbatim values in loaded object prediction: {exc}"
        ) from exc
    raise EvidenceError("loaded object prediction has no closing brace")


def _fenced_block(content: str, language: str) -> str:
    longest_run = max((len(match) for match in re.findall(r"`+", content)), default=0)
    fence = "`" * max(3, longest_run + 1)
    ending = "" if content.endswith("\n") else "\n"
    return f"{fence}{language}\n{content}{ending}{fence}"


def _answer_for_field(
    prediction_text: str,
    prediction: Any,
    load_status: str,
    field: str,
    value_literals: dict[str, str],
) -> tuple[str, str]:
    if load_status != "loaded" or not isinstance(prediction, dict):
        return prediction_text, "text"
    if field not in prediction:
        return "MISSING KEY", "text"
    return value_literals[field], "json"


def _run_index(manifest: dict[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    runs = manifest.get("runs")
    if not isinstance(runs, list):
        raise EvidenceError("manifest runs must be a list")
    return {
        (run["doc_id"], run["rep"]): run
        for run in runs
        if isinstance(run, dict)
        and isinstance(run.get("doc_id"), str)
        and type(run.get("rep")) is int
    }


def _wrong_instances(
    batch_dir: Path,
    gold_root: Path,
    manifest: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    run_index = _run_index(manifest)
    wrong_by_field: dict[str, list[dict[str, Any]]] = {
        field: [] for field in grader.FIELDS
    }
    doc_ids = sorted(report["per_document"])
    reps = int(report["reps"])

    for doc_id in doc_ids:
        gold = grader._load_gold(gold_root / f"{doc_id}.json")
        for rep in range(1, reps + 1):
            run = run_index[(doc_id, rep)]
            prediction_path = score._safe_batch_path(
                batch_dir, run["files"]["prediction"]
            )
            if prediction_path is None:
                raise EvidenceError(f"invalid prediction path for {doc_id} rep{rep}")
            try:
                prediction_text = prediction_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise EvidenceError(
                    f"cannot read stripped prediction for {doc_id} rep{rep}: {exc}"
                ) from exc
            prediction, load_status = grader._load_prediction(prediction_path)
            value_literals = (
                _top_level_value_literals(prediction_text)
                if load_status == "loaded" and isinstance(prediction, dict)
                else {}
            )
            field_results = report["per_document"][doc_id]["per_rep"][str(rep)][
                "field_results"
            ]

            for field in grader.FIELDS:
                if field_results[field]:
                    continue
                answer, language = _answer_for_field(
                    prediction_text,
                    prediction,
                    load_status,
                    field,
                    value_literals,
                )
                wrong_by_field[field].append(
                    {
                        "doc_id": doc_id,
                        "rep": rep,
                        "answer": answer,
                        "answer_language": language,
                        "gold": _json_literal(gold[field]),
                    }
                )
    return wrong_by_field


def _select_exemplars(
    wrong_by_field: dict[str, list[dict[str, Any]]],
    report: dict[str, Any],
) -> dict[str, list[str]]:
    selected_fields_by_doc: dict[str, list[str]] = {}

    def document_rank(doc_id: str) -> tuple[int, str]:
        return int(report["per_document"][doc_id]["correct_fields"]), doc_id

    for field in grader.FIELDS:
        wrong_docs = {instance["doc_id"] for instance in wrong_by_field[field]}
        for doc_id in sorted(wrong_docs, key=document_rank)[:2]:
            selected_fields_by_doc.setdefault(doc_id, []).append(field)
    return selected_fields_by_doc


def _read_document(batch_dir: Path, manifest: dict[str, Any], doc_id: str) -> str:
    documents = manifest.get("documents")
    record = documents.get(doc_id) if isinstance(documents, dict) else None
    recorded_path = record.get("path") if isinstance(record, dict) else None
    document_path = score._recorded_document_path(batch_dir, recorded_path)
    if document_path is None:
        raise EvidenceError(f"invalid manifest document path for {doc_id}")
    try:
        return document_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise EvidenceError(f"cannot read training document {doc_id}: {exc}") from exc


def render_pack(
    batch_dir: Path,
    manifest: dict[str, Any],
    report: dict[str, Any],
    wrong_by_field: dict[str, list[dict[str, Any]]],
) -> str:
    batch_id, skill_path, skill_sha256 = _manifest_identity(manifest)
    pooled_correct = int(report["correct_fields"])
    pooled_total = int(report["total_fields"])
    pooled_accuracy = float(report["pooled_mean_field_accuracy"])
    per_rep_parts = []
    for rep in range(1, int(report["reps"]) + 1):
        rep_report = report["per_rep"][str(rep)]
        per_rep_parts.append(
            f"rep{rep} {int(rep_report['correct_fields'])}/{int(rep_report['total_fields'])} "
            f"({float(rep_report['mean_field_accuracy']):.6f})"
        )
    counters = "; ".join(
        f"{counter}={int(report[counter])}" for counter in PACK_COUNTERS
    )

    lines = [
        f"# Evidence Pack — {batch_id}",
        "",
        f"- **Batch ID:** `{batch_id}`",
        f"- **Skill:** `{skill_path}` (`sha256: {skill_sha256}`)",
        f"- **Pooled score:** {pooled_correct}/{pooled_total} ({pooled_accuracy:.6f})",
        f"- **Per-rep scores:** {', '.join(per_rep_parts)}",
        f"- **Counters:** {counters}",
        "",
        "## Per-field accuracy",
        "",
        "| Field | Correct/total | Accuracy |",
        "|---|---:|---:|",
    ]
    for field in grader.FIELDS:
        field_report = report["per_field"][field]
        lines.append(
            f"| `{field}` | {int(field_report['correct'])}/{int(field_report['total'])} "
            f"| {float(field_report['accuracy']):.6f} |"
        )

    lines.extend(["", "## Wrong instances", ""])
    has_wrong = False
    for field in grader.FIELDS:
        instances = wrong_by_field[field]
        if not instances:
            continue
        has_wrong = True
        lines.extend([f"### `{field}`", ""])
        for instance in instances:
            lines.extend(
                [
                    f"#### `{instance['doc_id']}`, rep {instance['rep']}",
                    "",
                    "Worker answer:",
                    "",
                    _fenced_block(instance["answer"], instance["answer_language"]),
                    "",
                    "Training gold:",
                    "",
                    _fenced_block(instance["gold"], "json"),
                    "",
                ]
            )
    if not has_wrong:
        lines.extend(["No wrong instances.", ""])

    lines.extend(["## Exemplar documents", ""])
    selected_fields_by_doc = _select_exemplars(wrong_by_field, report)

    def exemplar_rank(doc_id: str) -> tuple[int, str]:
        return int(report["per_document"][doc_id]["correct_fields"]), doc_id

    if not selected_fields_by_doc:
        lines.extend(["No exemplar documents were needed.", ""])
    else:
        for doc_id in sorted(selected_fields_by_doc, key=exemplar_rank):
            fields = selected_fields_by_doc[doc_id]
            field_list = ", ".join(f"`{field}`" for field in fields)
            document_text = _read_document(batch_dir, manifest, doc_id)
            lines.extend(
                [
                    f"### `{doc_id}`",
                    "",
                    f"Wrong fields exemplified: {field_list}",
                    "",
                    _fenced_block(document_text, "text"),
                    "",
                ]
            )

    lines.extend(["---", "", FOOTER])
    return "\n".join(lines) + "\n"


def build_evidence_pack(
    batch_dir: Path | str,
    gold_root: Path | str,
) -> str:
    batch_path = Path(batch_dir).resolve()
    gold_path = Path(gold_root).resolve()
    manifest = score._read_manifest(batch_path)
    assert_training_only(manifest)
    report = score.score_batch(batch_path, gold_path)
    wrong_by_field = _wrong_instances(
        batch_path, gold_path, manifest, report
    )
    return render_pack(batch_path, manifest, report, wrong_by_field)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", required=True, type=Path)
    parser.add_argument("--gold-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        pack = build_evidence_pack(args.batch_dir, args.gold_root)
        args.out.write_text(pack, encoding="utf-8")
    except (EvidenceError, score.ScoreError, grader.GoldRecordError, OSError) as exc:
        print(f"evidence error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
