#!/usr/bin/env python3
"""Mechanical grader for the frozen tenancy-extraction schema."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence


FIELDS = (
    "landlord_name",
    "tenant_name",
    "unit_number",
    "community",
    "contract_start_date",
    "contract_end_date",
    "annual_rent_aed",
    "security_deposit_aed",
    "number_of_payments",
    "notice_period_days",
    "early_termination_penalty_months",
    "furnished_status",
)

STRING_FIELDS = (
    "landlord_name",
    "tenant_name",
    "unit_number",
    "community",
)

DATE_FIELDS = ("contract_start_date", "contract_end_date")

INTEGER_FIELDS = (
    "annual_rent_aed",
    "security_deposit_aed",
    "number_of_payments",
    "notice_period_days",
)

FURNISHED_VALUES = ("furnished", "semi-furnished", "unfurnished")
TOTAL_FIELDS = len(FIELDS)

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_HONORIFIC_RE = re.compile(r"^(?:(?:mr|mrs|ms|dr|eng)\.?\s+)+", re.IGNORECASE)
_ROLE_SUFFIX_RE = re.compile(
    r"\s*\(\s*(?:the\s+)?(?:landlord|tenant|lessor|lessee|owner|occupant)\s*\)\s*$",
    re.IGNORECASE,
)

_MISSING = object()
FROZEN_PUNCTUATION = frozenset("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~—")


class GoldRecordError(ValueError):
    """Raised when a gold file does not conform to the frozen schema."""


def _is_punctuation(character: str) -> bool:
    return character in FROZEN_PUNCTUATION


def _strip_outer_punctuation(value: str, preserve_parentheses: bool = False) -> str:
    start = 0
    end = len(value)

    def removable(character: str) -> bool:
        if character.isspace():
            return True
        if preserve_parentheses and character in "()":
            return False
        return _is_punctuation(character)

    while start < end and removable(value[start]):
        start += 1
    while end > start and removable(value[end - 1]):
        end -= 1
    return value[start:end]


def normalize_string(value: str) -> str:
    """Apply exactly the registered free-string normalization rules."""

    normalized = " ".join(value.casefold().split())
    # Preserve parentheses long enough to recognize a role suffix, while still
    # removing surrounding quotes/dashes/full stops around the whole value.
    normalized = _strip_outer_punctuation(normalized, preserve_parentheses=True)
    normalized = _ROLE_SUFFIX_RE.sub("", normalized)
    normalized = _strip_outer_punctuation(normalized)
    normalized = _HONORIFIC_RE.sub("", normalized)
    normalized = _strip_outer_punctuation(normalized)
    return " ".join(normalized.split())


def _is_iso_date_string(value: Any) -> bool:
    if type(value) is not str or _DATE_RE.fullmatch(value) is None:
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _is_json_integer(value: Any) -> bool:
    # bool is intentionally rejected even though it subclasses int in Python.
    return type(value) is int


def _is_json_number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def field_matches(field: str, prediction: Any, gold: Any) -> bool:
    """Return whether one present prediction value matches its gold value."""

    if field not in FIELDS:
        raise KeyError(field)

    if gold is None:
        return prediction is None
    if prediction is None:
        return False

    if field in STRING_FIELDS:
        return type(prediction) is str and normalize_string(prediction) == normalize_string(gold)
    if field in DATE_FIELDS:
        return _is_iso_date_string(prediction) and prediction == gold
    if field in INTEGER_FIELDS:
        return _is_json_integer(prediction) and prediction == gold
    if field == "early_termination_penalty_months":
        return _is_json_number(prediction) and prediction == gold
    if field == "furnished_status":
        if type(prediction) is not str:
            return False
        normalized = normalize_string(prediction)
        return normalized in FURNISHED_VALUES and normalized == normalize_string(gold)
    raise KeyError(field)


def validate_gold_record(gold: Any) -> None:
    if not isinstance(gold, dict):
        raise GoldRecordError("gold JSON root must be an object")
    missing = [field for field in FIELDS if field not in gold]
    if missing:
        raise GoldRecordError(f"gold record is missing keys: {', '.join(missing)}")

    for field in STRING_FIELDS:
        if type(gold[field]) is not str:
            raise GoldRecordError(f"gold {field} must be a string")
    for field in DATE_FIELDS:
        if not _is_iso_date_string(gold[field]):
            raise GoldRecordError(f"gold {field} must be an exact ISO date string")
    if not _is_json_integer(gold["annual_rent_aed"]):
        raise GoldRecordError("gold annual_rent_aed must be an integer")
    if not _is_json_integer(gold["number_of_payments"]):
        raise GoldRecordError("gold number_of_payments must be an integer")
    for field in ("security_deposit_aed", "notice_period_days"):
        if gold[field] is not None and not _is_json_integer(gold[field]):
            raise GoldRecordError(f"gold {field} must be an integer or null")
    penalty = gold["early_termination_penalty_months"]
    if penalty is not None and not _is_json_number(penalty):
        raise GoldRecordError("gold early_termination_penalty_months must be a number or null")
    furnished = gold["furnished_status"]
    if furnished is not None and furnished not in FURNISHED_VALUES:
        raise GoldRecordError("gold furnished_status has an invalid enum value")


def grade_prediction(
    prediction: Any,
    gold: Mapping[str, Any],
    *,
    unparseable: bool = False,
    missing: bool = False,
) -> dict[str, Any]:
    """Grade one already-loaded prediction against one gold record."""

    validate_gold_record(gold)
    is_object = isinstance(prediction, dict) and not unparseable and not missing
    wrong_shape = not is_object and not unparseable and not missing
    field_results: dict[str, bool] = {}
    hallucinated_absent = 0
    missed_present = 0

    for field in FIELDS:
        predicted_value = prediction.get(field, _MISSING) if is_object else _MISSING
        if gold[field] is None and predicted_value is not _MISSING and predicted_value is not None:
            hallucinated_absent += 1
        if (
            is_object
            and gold[field] is not None
            and (predicted_value is _MISSING or predicted_value is None)
        ):
            missed_present += 1
        field_results[field] = (
            predicted_value is not _MISSING
            and field_matches(field, predicted_value, gold[field])
        )

    correct_fields = sum(field_results.values())
    return {
        "score": correct_fields / TOTAL_FIELDS,
        "correct_fields": correct_fields,
        "total_fields": TOTAL_FIELDS,
        "field_results": field_results,
        "hallucinated_absent": hallucinated_absent,
        "missed_present": missed_present,
        "unparseable": bool(unparseable),
        "wrong_shape": wrong_shape,
        "missing": bool(missing),
    }


def _reject_nonstandard_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _load_strict_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_nonstandard_constant,
    )


def _load_prediction(path: Path) -> tuple[Any, str]:
    try:
        return _load_strict_json(path), "loaded"
    except FileNotFoundError:
        return None, "missing"
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return None, "unparseable"


def _load_gold(path: Path) -> dict[str, Any]:
    try:
        gold = _load_strict_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise GoldRecordError(f"cannot parse gold file {path}: {error}") from error
    validate_gold_record(gold)
    return gold


def grade_files(prediction_path: Path | str, gold_path: Path | str) -> dict[str, Any]:
    pred_path = Path(prediction_path)
    reference_path = Path(gold_path)
    gold = _load_gold(reference_path)
    prediction, load_status = _load_prediction(pred_path)
    result = grade_prediction(
        prediction,
        gold,
        unparseable=load_status == "unparseable",
        missing=load_status == "missing",
    )
    return {
        "mode": "single",
        "document": reference_path.name,
        **result,
    }


def grade_directories(prediction_dir: Path | str, gold_dir: Path | str) -> dict[str, Any]:
    pred_root = Path(prediction_dir)
    reference_root = Path(gold_dir)
    gold_paths = sorted(reference_root.glob("*.json"), key=lambda path: path.name)
    if not gold_paths:
        raise GoldRecordError(f"no .json gold files found in {reference_root}")

    per_document: dict[str, dict[str, Any]] = {}
    field_correct = {field: 0 for field in FIELDS}
    total_correct = 0
    total_hallucinated = 0
    total_missed_present = 0
    total_unparseable = 0
    total_wrong_shape = 0
    total_missing = 0

    for gold_path in gold_paths:
        gold = _load_gold(gold_path)
        prediction, load_status = _load_prediction(pred_root / gold_path.name)
        result = grade_prediction(
            prediction,
            gold,
            unparseable=load_status == "unparseable",
            missing=load_status == "missing",
        )
        per_document[gold_path.name] = result
        total_correct += result["correct_fields"]
        total_hallucinated += result["hallucinated_absent"]
        total_missed_present += result["missed_present"]
        total_unparseable += int(result["unparseable"])
        total_wrong_shape += int(result["wrong_shape"])
        total_missing += int(result["missing"])
        for field, correct in result["field_results"].items():
            field_correct[field] += int(correct)

    document_count = len(gold_paths)
    per_field = {
        field: {
            "correct": field_correct[field],
            "total": document_count,
            "accuracy": field_correct[field] / document_count,
        }
        for field in FIELDS
    }
    return {
        "mode": "batch",
        "documents": document_count,
        "mean_field_accuracy": total_correct / (document_count * TOTAL_FIELDS),
        "per_field": per_field,
        "per_document": per_document,
        "hallucinated_absent": total_hallucinated,
        "missed_present": total_missed_present,
        "unparseable": total_unparseable,
        "wrong_shape": total_wrong_shape,
        "missing": total_missing,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pred", type=Path, help="one prediction JSON file")
    parser.add_argument("--gold", type=Path, help="one gold JSON file")
    parser.add_argument("--pred-dir", type=Path, help="directory of prediction JSON files")
    parser.add_argument("--gold-dir", type=Path, help="directory of gold JSON files")
    return parser


def _select_mode(parser: argparse.ArgumentParser, args: argparse.Namespace) -> str:
    single_values = (args.pred, args.gold)
    batch_values = (args.pred_dir, args.gold_dir)
    has_single = any(value is not None for value in single_values)
    has_batch = any(value is not None for value in batch_values)
    if has_single and has_batch:
        parser.error("single-file and batch arguments cannot be combined")
    if has_single:
        if not all(value is not None for value in single_values):
            parser.error("single mode requires both --pred and --gold")
        return "single"
    if has_batch:
        if not all(value is not None for value in batch_values):
            parser.error("batch mode requires both --pred-dir and --gold-dir")
        return "batch"
    parser.error("provide --pred/--gold or --pred-dir/--gold-dir")
    raise AssertionError("argparse.error always exits")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    mode = _select_mode(parser, args)
    try:
        if mode == "single":
            report = grade_files(args.pred, args.gold)
        else:
            report = grade_directories(args.pred_dir, args.gold_dir)
    except GoldRecordError as error:
        print(f"grader error: {error}", file=sys.stderr)
        return 2
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2, allow_nan=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
