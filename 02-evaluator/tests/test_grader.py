"""Tests for every frozen grading rule and both CLI-facing modes."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


EVALUATOR_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = EVALUATOR_ROOT.parent
GRADER_PATH = EVALUATOR_ROOT / "grader.py"
REAL_GOLD_DIR = PROJECT_ROOT / "01-fixtures" / "gold"

SPEC = importlib.util.spec_from_file_location("frozen_grader", GRADER_PATH)
assert SPEC is not None and SPEC.loader is not None
grader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(grader)


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


def perfect_prediction() -> dict[str, object]:
    return dict(sample_gold())


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_casefold_normalization_positive() -> None:
    assert grader.field_matches("community", "AL NAKHEEL GARDENS", "Al Nakheel Gardens")


def test_casefold_normalization_negative_for_different_text() -> None:
    assert not grader.field_matches("community", "Al Nakheel Garden", "Al Nakheel Gardens")


def test_whitespace_collapse_positive() -> None:
    assert grader.field_matches(
        "landlord_name", "Mariam\n  Qasim\tAl Nuaimi", "Mariam Qasim Al Nuaimi"
    )


def test_whitespace_collapse_does_not_remove_internal_characters() -> None:
    assert not grader.field_matches("tenant_name", "DanielOka for", "Daniel Okafor")


def test_surrounding_ascii_punctuation_is_stripped() -> None:
    assert grader.field_matches("unit_number", "[[B-1204]],", "B-1204")


def test_surrounding_unicode_punctuation_is_stripped() -> None:
    assert grader.field_matches("community", "—Al Nakheel Gardens—", "Al Nakheel Gardens")


def test_internal_punctuation_is_not_stripped() -> None:
    assert not grader.field_matches("unit_number", "B1204", "B-1204")


@pytest.mark.parametrize("honorific", ["Mr", "Mrs.", "MS", "Dr.", "Eng"])
def test_each_registered_leading_honorific_is_stripped(honorific: str) -> None:
    assert grader.field_matches("tenant_name", f"{honorific} Daniel Okafor", "Daniel Okafor")


def test_multiple_leading_honorifics_are_stripped() -> None:
    assert grader.field_matches("tenant_name", "Dr. Eng. Daniel Okafor", "Daniel Okafor")


def test_nonleading_honorific_is_not_stripped() -> None:
    assert not grader.field_matches("tenant_name", "Daniel Mr. Okafor", "Daniel Okafor")


def test_honorific_prefix_requires_a_token_boundary() -> None:
    assert not grader.field_matches("tenant_name", "MrDaniel Okafor", "Daniel Okafor")


def test_trailing_parenthetical_role_with_the_is_stripped() -> None:
    assert grader.field_matches(
        "landlord_name",
        "Mariam Qasim Al Nuaimi (the Landlord)",
        "Mariam Qasim Al Nuaimi",
    )


def test_trailing_parenthetical_role_without_the_is_stripped() -> None:
    assert grader.field_matches("tenant_name", "Daniel Okafor (Tenant)", "Daniel Okafor")


def test_role_suffix_survives_outer_punctuation_before_stripping() -> None:
    assert grader.field_matches(
        "landlord_name",
        '"Mr. Mariam Qasim Al Nuaimi (the landlord)."',
        "Mariam Qasim Al Nuaimi",
    )


def test_nontrailing_parenthetical_text_is_not_stripped() -> None:
    assert not grader.field_matches(
        "tenant_name", "Daniel (the Tenant) Okafor", "Daniel Okafor"
    )


@pytest.mark.parametrize("field", grader.STRING_FIELDS)
def test_each_free_string_field_rejects_non_string(field: str) -> None:
    assert not grader.field_matches(field, 123, sample_gold()[field])


def test_date_exact_iso_string_is_accepted() -> None:
    assert grader.field_matches("contract_start_date", "2026-09-01", "2026-09-01")


def test_date_display_format_is_rejected() -> None:
    assert not grader.field_matches("contract_start_date", "01/09/2026", "2026-09-01")


def test_date_with_extra_whitespace_is_rejected() -> None:
    assert not grader.field_matches("contract_start_date", " 2026-09-01 ", "2026-09-01")


def test_impossible_iso_shaped_date_is_rejected() -> None:
    assert not grader._is_iso_date_string("2026-02-30")


def test_date_wrong_type_is_rejected() -> None:
    assert not grader.field_matches("contract_end_date", 20270831, "2027-08-31")


def test_annual_rent_integer_is_accepted() -> None:
    assert grader.field_matches("annual_rent_aed", 85000, 85000)


def test_annual_rent_float_is_rejected() -> None:
    assert not grader.field_matches("annual_rent_aed", 85000.0, 85000)


def test_annual_rent_numeric_string_is_rejected() -> None:
    assert not grader.field_matches("annual_rent_aed", "85000", 85000)


def test_integer_field_rejects_boolean() -> None:
    assert not grader.field_matches("number_of_payments", True, 1)


def test_security_deposit_integer_type() -> None:
    assert grader.field_matches("security_deposit_aed", 4250, 4250)
    assert not grader.field_matches("security_deposit_aed", 4250.0, 4250)


def test_number_of_payments_integer_type() -> None:
    assert grader.field_matches("number_of_payments", 4, 4)
    assert not grader.field_matches("number_of_payments", "four", 4)


def test_notice_period_integer_type() -> None:
    assert grader.field_matches("notice_period_days", 60, 60)
    assert not grader.field_matches("notice_period_days", 60.0, 60)


def test_penalty_accepts_integer_number() -> None:
    assert grader.field_matches("early_termination_penalty_months", 2, 2)


def test_penalty_accepts_float_number() -> None:
    assert grader.field_matches("early_termination_penalty_months", 1.5, 1.5)


def test_penalty_accepts_equivalent_int_or_float() -> None:
    assert grader.field_matches("early_termination_penalty_months", 2.0, 2)


def test_penalty_rejects_numeric_string_and_boolean() -> None:
    assert not grader.field_matches("early_termination_penalty_months", "1.5", 1.5)
    assert not grader.field_matches("early_termination_penalty_months", True, 1)


def test_furnished_status_is_casefolded() -> None:
    assert grader.field_matches("furnished_status", "SEMI-FURNISHED", "semi-furnished")


def test_each_furnished_enum_is_accepted() -> None:
    for value in grader.FURNISHED_VALUES:
        assert grader.field_matches("furnished_status", value.upper(), value)


def test_furnished_status_rejects_non_enum() -> None:
    assert not grader.field_matches("furnished_status", "partly furnished", "furnished")


def test_furnished_status_uses_registered_string_normalization() -> None:
    assert grader.field_matches("furnished_status", "  semi-furnished \n ", "semi-furnished")
    assert grader.field_matches("furnished_status", "'furnished'", "furnished")


def test_furnished_status_normalization_does_not_expand_the_enum() -> None:
    assert not grader.field_matches("furnished_status", " partly  furnished ", "furnished")


def test_unicode_punctuation_outside_frozen_set_is_not_stripped() -> None:
    assert not grader.field_matches("community", "。Al Nakheel Gardens。", "Al Nakheel Gardens")


def test_gold_null_and_prediction_null_are_correct() -> None:
    report = grader.grade_prediction(perfect_prediction(), sample_gold())
    assert report["field_results"]["security_deposit_aed"] is True
    assert report["field_results"]["furnished_status"] is True


def test_gold_null_and_nonnull_prediction_is_hallucinated_absent() -> None:
    prediction = perfect_prediction()
    prediction["security_deposit_aed"] = 4250
    prediction["furnished_status"] = "furnished"
    report = grader.grade_prediction(prediction, sample_gold())
    assert report["hallucinated_absent"] == 2
    assert report["field_results"]["security_deposit_aed"] is False
    assert report["field_results"]["furnished_status"] is False


def test_gold_nonnull_and_prediction_null_is_wrong_not_hallucinated() -> None:
    prediction = perfect_prediction()
    prediction["notice_period_days"] = None
    report = grader.grade_prediction(prediction, sample_gold())
    assert report["field_results"]["notice_period_days"] is False
    assert report["hallucinated_absent"] == 0
    assert report["missed_present"] == 1


def test_wrong_nonnull_prediction_is_not_missed_present() -> None:
    prediction = perfect_prediction()
    prediction["notice_period_days"] = 30
    report = grader.grade_prediction(prediction, sample_gold())
    assert report["field_results"]["notice_period_days"] is False
    assert report["missed_present"] == 0


def test_missing_key_is_incorrect() -> None:
    prediction = perfect_prediction()
    del prediction["community"]
    report = grader.grade_prediction(prediction, sample_gold())
    assert report["correct_fields"] == 11
    assert report["field_results"]["community"] is False
    assert report["missed_present"] == 1


def test_missing_nullable_key_with_null_gold_is_not_missed_present() -> None:
    prediction = perfect_prediction()
    del prediction["security_deposit_aed"]
    report = grader.grade_prediction(prediction, sample_gold())
    assert report["field_results"]["security_deposit_aed"] is False
    assert report["missed_present"] == 0


def test_extra_prediction_key_is_ignored() -> None:
    prediction = perfect_prediction()
    prediction["agent_commission_aed"] = 4250
    report = grader.grade_prediction(prediction, sample_gold())
    assert report["score"] == 1.0


def test_one_wrong_field_score_is_eleven_twelfths() -> None:
    prediction = perfect_prediction()
    prediction["annual_rent_aed"] = 85001
    report = grader.grade_prediction(prediction, sample_gold())
    assert report["correct_fields"] == 11
    assert report["score"] == pytest.approx(11 / 12)


def test_unparseable_json_scores_zero(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold.json"
    pred_path = tmp_path / "pred.json"
    write_json(gold_path, sample_gold())
    pred_path.write_text('{"landlord_name": ', encoding="utf-8")
    report = grader.grade_files(pred_path, gold_path)
    assert report["score"] == 0.0
    assert report["correct_fields"] == 0
    assert report["unparseable"] is True
    assert report["wrong_shape"] is False
    assert report["missing"] is False


def test_nonstandard_nan_json_is_unparseable(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold.json"
    pred_path = tmp_path / "pred.json"
    write_json(gold_path, sample_gold())
    pred_path.write_text('{"annual_rent_aed": NaN}', encoding="utf-8")
    report = grader.grade_files(pred_path, gold_path)
    assert report["unparseable"] is True
    assert report["score"] == 0.0


def test_parseable_nonobject_scores_zero_and_is_wrong_shape(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold.json"
    pred_path = tmp_path / "pred.json"
    write_json(gold_path, sample_gold())
    write_json(pred_path, ["not", "an", "object"])
    report = grader.grade_files(pred_path, gold_path)
    assert report["score"] == 0.0
    assert report["unparseable"] is False
    assert report["wrong_shape"] is True
    assert report["missing"] is False
    assert report["missed_present"] == 0


def test_batch_aggregation_math_and_per_field_breakdown(tmp_path: Path) -> None:
    gold_dir = tmp_path / "gold"
    pred_dir = tmp_path / "pred"
    gold_dir.mkdir()
    pred_dir.mkdir()
    for name in ("doc-a.json", "doc-b.json"):
        write_json(gold_dir / name, sample_gold())

    write_json(pred_dir / "doc-a.json", perfect_prediction())
    half = perfect_prediction()
    for field in grader.FIELDS[:6]:
        half[field] = "wrong"
    write_json(pred_dir / "doc-b.json", half)

    report = grader.grade_directories(pred_dir, gold_dir)
    assert report["documents"] == 2
    assert report["mean_field_accuracy"] == pytest.approx(18 / 24)
    assert report["per_field"]["landlord_name"] == {
        "correct": 1,
        "total": 2,
        "accuracy": 0.5,
    }
    assert report["per_field"]["annual_rent_aed"]["accuracy"] == 1.0
    assert list(report["per_document"]) == ["doc-a.json", "doc-b.json"]


def test_batch_counts_hallucinations_and_unparseable_files(tmp_path: Path) -> None:
    gold_dir = tmp_path / "gold"
    pred_dir = tmp_path / "pred"
    gold_dir.mkdir()
    pred_dir.mkdir()
    for name in ("doc-a.json", "doc-b.json"):
        write_json(gold_dir / name, sample_gold())

    hallucinating = perfect_prediction()
    hallucinating["security_deposit_aed"] = 4250
    hallucinating["furnished_status"] = "unfurnished"
    write_json(pred_dir / "doc-a.json", hallucinating)
    (pred_dir / "doc-b.json").write_text("not json", encoding="utf-8")

    report = grader.grade_directories(pred_dir, gold_dir)
    assert report["hallucinated_absent"] == 2
    assert report["unparseable"] == 1
    assert report["wrong_shape"] == 0
    assert report["missing"] == 0
    assert report["missed_present"] == 0
    assert report["mean_field_accuracy"] == pytest.approx(10 / 24)


def test_batch_missing_prediction_file_is_zero_and_missing_not_unparseable(tmp_path: Path) -> None:
    gold_dir = tmp_path / "gold"
    pred_dir = tmp_path / "pred"
    gold_dir.mkdir()
    pred_dir.mkdir()
    write_json(gold_dir / "doc-a.json", sample_gold())
    report = grader.grade_directories(pred_dir, gold_dir)
    assert report["mean_field_accuracy"] == 0.0
    assert report["missing"] == 1
    assert report["unparseable"] == 0
    assert report["wrong_shape"] == 0
    assert report["missed_present"] == 0
    assert report["per_document"]["doc-a.json"]["score"] == 0.0
    assert report["per_document"]["doc-a.json"]["missing"] is True


def test_batch_counts_wrong_shape_and_missed_present(tmp_path: Path) -> None:
    gold_dir = tmp_path / "gold"
    pred_dir = tmp_path / "pred"
    gold_dir.mkdir()
    pred_dir.mkdir()
    for name in ("doc-a.json", "doc-b.json"):
        write_json(gold_dir / name, sample_gold())
    write_json(pred_dir / "doc-a.json", ["valid", "but", "wrong"])
    missing_present = perfect_prediction()
    missing_present["notice_period_days"] = None
    del missing_present["tenant_name"]
    write_json(pred_dir / "doc-b.json", missing_present)

    report = grader.grade_directories(pred_dir, gold_dir)

    assert report["wrong_shape"] == 1
    assert report["unparseable"] == 0
    assert report["missing"] == 0
    assert report["missed_present"] == 2
    assert report["per_document"]["doc-a.json"]["wrong_shape"] is True
    assert report["per_document"]["doc-a.json"]["missed_present"] == 0
    assert report["per_document"]["doc-b.json"]["missed_present"] == 2


def test_single_cli_emits_json_report(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold.json"
    pred_path = tmp_path / "pred.json"
    write_json(gold_path, sample_gold())
    write_json(pred_path, perfect_prediction())
    completed = subprocess.run(
        [sys.executable, str(GRADER_PATH), "--pred", str(pred_path), "--gold", str(gold_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["score"] == 1.0
    assert completed.stderr == ""


def test_batch_cli_emits_required_aggregate_keys(tmp_path: Path) -> None:
    gold_dir = tmp_path / "gold"
    pred_dir = tmp_path / "pred"
    gold_dir.mkdir()
    pred_dir.mkdir()
    write_json(gold_dir / "doc-a.json", sample_gold())
    write_json(pred_dir / "doc-a.json", perfect_prediction())
    completed = subprocess.run(
        [
            sys.executable,
            str(GRADER_PATH),
            "--pred-dir",
            str(pred_dir),
            "--gold-dir",
            str(gold_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    report = json.loads(completed.stdout)
    assert report["mean_field_accuracy"] == 1.0
    assert set(
        (
            "per_field",
            "per_document",
            "hallucinated_absent",
            "missed_present",
            "unparseable",
            "wrong_shape",
            "missing",
        )
    ) <= set(report)


def test_end_to_end_normalized_handcrafted_prediction_against_real_gold() -> None:
    gold_path = REAL_GOLD_DIR / "doc-01.json"
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    prediction = dict(gold)
    prediction["landlord_name"] = f'"Dr. {gold["landlord_name"].upper()} (the Landlord)."'
    prediction["tenant_name"] = f"Mr. {gold['tenant_name']} (Tenant)"
    prediction["unit_number"] = f"[{gold['unit_number']}]"
    prediction["community"] = f"—{gold['community'].upper()}—"
    if prediction["furnished_status"] is not None:
        prediction["furnished_status"] = str(prediction["furnished_status"]).upper()

    report = grader.grade_prediction(prediction, gold)
    assert report["score"] == 1.0
    assert report["hallucinated_absent"] == 0


def test_end_to_end_errors_and_hallucination_against_real_gold() -> None:
    gold_path = REAL_GOLD_DIR / "doc-02.json"
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    prediction = dict(gold)
    prediction["annual_rent_aed"] = str(gold["annual_rent_aed"])
    del prediction["tenant_name"]
    absent_field = next(
        field
        for field in (
            "security_deposit_aed",
            "notice_period_days",
            "early_termination_penalty_months",
            "furnished_status",
        )
        if gold[field] is None
    )
    prediction[absent_field] = "invented"

    report = grader.grade_prediction(prediction, gold)
    assert report["correct_fields"] == 9
    assert report["score"] == 0.75
    assert report["hallucinated_absent"] == 1
