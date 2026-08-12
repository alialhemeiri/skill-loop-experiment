"""Regression tests for the deterministic fixture generator."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


EVALUATOR_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = EVALUATOR_ROOT.parent
FIXTURE_ROOT = PROJECT_ROOT / "01-fixtures"
GENERATOR_PATH = FIXTURE_ROOT / "generator" / "generate.py"

SPEC = importlib.util.spec_from_file_location("frozen_generator", GENERATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


def fixture_bytes(root: Path) -> dict[str, bytes]:
    paths = list((root / "gold").glob("doc-*.json"))
    paths.extend((root / "docs" / "train").glob("doc-*.txt"))
    paths.extend((root / "docs" / "holdout").glob("doc-*.txt"))
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(paths, key=lambda item: item.as_posix())
    }


def load_committed_gold() -> list[dict[str, object]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((FIXTURE_ROOT / "gold").glob("doc-*.json"))
    ]


def test_same_seed_is_byte_identical(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    generator.generate_fixtures(generator.DEFAULT_SEED, first)
    generator.generate_fixtures(generator.DEFAULT_SEED, second)
    assert fixture_bytes(first) == fixture_bytes(second)


def test_cross_process_locale_generation_is_byte_identical(tmp_path: Path) -> None:
    first = tmp_path / "locale-c"
    second = tmp_path / "locale-c-utf8"
    for locale_name, output_root in (("C", first), ("C.utf8", second)):
        completed = subprocess.run(
            [
                sys.executable,
                str(GENERATOR_PATH),
                "--seed",
                str(generator.DEFAULT_SEED),
                "--out-root",
                str(output_root),
            ],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "LC_ALL": locale_name},
        )
        assert completed.returncode == 0, completed.stderr
    assert fixture_bytes(first) == fixture_bytes(second)


def test_long_date_rendering_does_not_call_locale_strftime() -> None:
    class DateWithoutStrftime:
        day = 7
        month = 9
        year = 2026

        def strftime(self, _format: str) -> str:
            raise AssertionError("locale-dependent strftime must not be called")

    assert generator.render_date(DateWithoutStrftime(), "long") == "7 September 2026"


def test_twelve_month_end_date_handles_a_crossed_leap_day() -> None:
    from datetime import date

    assert generator._iso_end_date(date(2027, 5, 1)) == date(2028, 4, 30)


def test_twelve_month_end_date_handles_a_leap_day_commencement() -> None:
    from datetime import date

    assert generator._iso_end_date(date(2028, 2, 29)) == date(2029, 2, 28)


def test_different_seed_changes_outputs(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    generator.generate_fixtures(generator.DEFAULT_SEED, first)
    generator.generate_fixtures(generator.DEFAULT_SEED + 1, second)
    assert fixture_bytes(first) != fixture_bytes(second)


def test_fixed_split_sizes_and_names() -> None:
    train_names = sorted(path.name for path in (FIXTURE_ROOT / "docs" / "train").glob("*.txt"))
    holdout_names = sorted(
        path.name for path in (FIXTURE_ROOT / "docs" / "holdout").glob("*.txt")
    )
    assert train_names == [f"doc-{index:02d}.txt" for index in range(1, 11)]
    assert holdout_names == [f"doc-{index:02d}.txt" for index in range(11, 17)]


def test_exact_gold_file_count_and_names() -> None:
    names = sorted(path.name for path in (FIXTURE_ROOT / "gold").glob("*.json"))
    assert names == [f"doc-{index:02d}.json" for index in range(1, 17)]


def test_gold_schema_keys_and_types_are_valid() -> None:
    for gold in load_committed_gold():
        assert tuple(gold) == generator.SCHEMA_FIELDS
        generator.validate_gold_record(gold)
        assert all(type(gold[field]) is str for field in generator.SCHEMA_FIELDS[:6])
        assert type(gold["annual_rent_aed"]) is int
        assert type(gold["number_of_payments"]) is int


def test_nullable_absence_bound_is_one_to_three_per_document() -> None:
    counts = [
        sum(gold[field] is None for field in generator.NULLABLE_FIELDS)
        for gold in load_committed_gold()
    ]
    assert all(1 <= count <= 3 for count in counts)


def test_nullable_field_rates_match_between_splits_within_ten_points() -> None:
    records = load_committed_gold()
    for field in generator.NULLABLE_FIELDS:
        train_rate = sum(record[field] is None for record in records[:10]) / 10
        holdout_rate = sum(record[field] is None for record in records[10:]) / 6
        assert abs(train_rate - holdout_rate) <= 0.10, (
            field,
            train_rate,
            holdout_rate,
        )


def test_difficulty_plan_has_prose_majority_gradient_and_derivation_per_doc() -> None:
    payloads = generator.build_fixture_payloads(generator.DEFAULT_SEED)
    easy_count = sum(payload["easy_labeled"] for payload in payloads)
    prose_count = 0
    labeled_count = 0
    derived_fields: set[str] = set()

    assert easy_count == 2
    for payload in payloads:
        present = {
            field: evidence
            for field, evidence in payload["evidence"].items()
            if payload["gold"][field] is not None
        }
        derived = [field for field, evidence in present.items() if evidence["mode"] == "derived"]
        assert derived, payload["index"]
        derived_fields.update(derived)
        doc_labeled = sum(evidence["location"] == "labeled" for evidence in present.values())
        doc_prose = sum(evidence["location"] == "prose" for evidence in present.values())
        if not payload["easy_labeled"]:
            assert doc_labeled <= 1, payload["index"]
            assert doc_prose > doc_labeled, payload["index"]
            expected_derived = 3 + int(payload["gold"]["security_deposit_aed"] is not None)
            assert len(derived) == expected_derived, payload["index"]
            if payload["gold"]["security_deposit_aed"] is not None:
                assert payload["evidence"]["security_deposit_aed"]["mode"] == "derived"
        else:
            assert len(derived) == 2, payload["index"]
        prose_count += doc_prose
        labeled_count += doc_labeled

    assert prose_count > labeled_count
    assert {
        "contract_end_date",
        "annual_rent_aed",
        "number_of_payments",
    } <= derived_fields


def test_evidence_plan_and_decoys_are_present_once_in_every_document() -> None:
    expected_decoys = {"representative", "money", "building", "date", "parking"}
    for payload in generator.build_fixture_payloads(generator.DEFAULT_SEED):
        text = payload["document"]
        assert set(payload["decoy_markers"]) == expected_decoys
        for marker in payload["decoy_markers"].values():
            assert text.count(marker) == 1, (payload["index"], marker)
        for field, evidence in payload["evidence"].items():
            if payload["gold"][field] is None:
                continue
            if evidence["mode"] == "copied":
                assert evidence["rendered"] in text, (payload["index"], field)
            else:
                assert text.count(evidence["statement"]) == 1, (payload["index"], field)
                assert all(value in text for value in evidence["inputs"]), (
                    payload["index"],
                    field,
                )


def test_annual_rent_derivation_uses_words_without_gold_digits() -> None:
    derived_rents = [
        payload
        for payload in generator.build_fixture_payloads(generator.DEFAULT_SEED)
        if payload["evidence"]["annual_rent_aed"]["mode"] == "derived"
    ]
    assert derived_rents
    for payload in derived_rents:
        rent = payload["gold"]["annual_rent_aed"]
        text = payload["document"]
        assert str(rent) not in text
        assert f"{rent:,}" not in text
        assert generator.number_to_words(rent) in text.casefold()


def test_post_dated_cheque_clause_agrees_in_singular_and_plural() -> None:
    corpus = "\n".join(
        payload["document"]
        for payload in generator.build_fixture_payloads(generator.DEFAULT_SEED)
    )

    assert (
        "One post-dated cheque, separately identified in the delivery record, "
        "constitutes the complete set of rent instruments."
    ) in corpus
    assert (
        "post-dated cheques, each separately identified in the delivery record, "
        "constitute the complete set of rent instruments."
    ) in corpus
    assert "One post-dated cheque, each separately identified" not in corpus


def test_sanity_guard_checks_derivation_inputs_and_unique_statement() -> None:
    payload = next(
        item
        for item in generator.build_fixture_payloads(generator.DEFAULT_SEED)
        if item["evidence"]["annual_rent_aed"]["mode"] == "derived"
    )
    evidence = payload["evidence"]["annual_rent_aed"]
    removed_input = payload["document"].replace(evidence["inputs"][0], "REMOVED WORD AMOUNT", 1)
    with pytest.raises(AssertionError, match="annual_rent_aed"):
        generator.sanity_check_document(removed_input, payload["gold"], payload["evidence"])

    duplicated = payload["document"].replace(
        evidence["statement"], evidence["statement"] + " " + evidence["statement"], 1
    )
    with pytest.raises(AssertionError, match="annual_rent_aed"):
        generator.sanity_check_document(duplicated, payload["gold"], payload["evidence"])


def test_every_document_passes_public_sanity_guard() -> None:
    for index, gold in enumerate(load_committed_gold(), start=1):
        split = "train" if index <= 10 else "holdout"
        text = (FIXTURE_ROOT / "docs" / split / f"doc-{index:02d}.txt").read_text(
            encoding="utf-8"
        )
        generator.sanity_check_document(text, gold)


def test_sanity_guard_catches_planted_present_value_violation() -> None:
    gold = load_committed_gold()[0]
    text = (FIXTURE_ROOT / "docs" / "train" / "doc-01.txt").read_text(encoding="utf-8")
    planted = text.replace(str(gold["community"]), "Removed Fictional Quarter", 1)
    with pytest.raises(AssertionError, match="community"):
        generator.sanity_check_document(planted, gold)


def test_sanity_guard_catches_planted_absent_field_mention() -> None:
    gold = load_committed_gold()[0]
    text = (FIXTURE_ROOT / "docs" / "train" / "doc-01.txt").read_text(encoding="utf-8")
    absent_field = next(field for field in generator.NULLABLE_FIELDS if gold[field] is None)
    planted_terms = {
        "security_deposit_aed": " A deposit is discussed.",
        "notice_period_days": " A notice is discussed.",
        "early_termination_penalty_months": " Early termination is discussed.",
        "furnished_status": " The home is furnished.",
    }
    with pytest.raises(AssertionError, match=absent_field):
        generator.sanity_check_document(text + planted_terms[absent_field], gold)


def test_all_document_word_counts_are_within_contract_bounds() -> None:
    documents = sorted((FIXTURE_ROOT / "docs").glob("*/*.txt"))
    counts = [len(path.read_text(encoding="utf-8").split()) for path in documents]
    assert len(counts) == 16
    assert min(counts) >= 400
    assert max(counts) <= 900


def test_corpus_contains_three_distinct_layouts() -> None:
    texts = [path.read_text(encoding="utf-8") for path in sorted((FIXTURE_ROOT / "docs").glob("*/*.txt"))]
    assert any("SCHEDULE A — KEY TERMS" in text for text in texts)
    assert any("1. PARTIES" in text for text in texts)
    assert any(text.startswith("This residential tenancy agreement") for text in texts)


def test_schedule_tables_are_padded_to_their_border_widths() -> None:
    schedule_texts = [
        path.read_text(encoding="utf-8")
        for path in sorted((FIXTURE_ROOT / "docs").glob("*/*.txt"))
        if "SCHEDULE A — KEY TERMS" in path.read_text(encoding="utf-8")
    ]
    assert schedule_texts
    for text in schedule_texts:
        lines = text.splitlines()
        border_indexes = [index for index, line in enumerate(lines) if line.startswith("+-")]
        assert len(border_indexes) >= 3
        table_lines = lines[border_indexes[0] : border_indexes[-1] + 1]
        assert len({len(line) for line in table_lines}) == 1


def test_corpus_visibly_covers_messiness_menu() -> None:
    corpus = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((FIXTURE_ROOT / "docs").glob("*/*.txt"))
    )
    assert re.search(r"\b\d{2}/\d{2}/\d{4}\b", corpus)
    assert re.search(r"\b\d{1,2} (?:August|September|October|November|December|January)", corpus)
    assert re.search(r"\b202[67]-\d{2}-\d{2}\b", corpus)
    assert "Dhs. " in corpus and " AED" in corpus and "dirhams (AED " in corpus
    assert "post-dated cheques" in corpus and "quarterly instalments" in corpus
    for phrase in ("agent commission", "DEWA", "Ejari", "Maintenance", "Arbitration"):
        assert phrase.casefold() in corpus.casefold()
    assert re.search(
        r"[\u0600-\u06ff]+\s*/\s*(?:Landlord|Tenant|Unit number|Community|Annual rent|Security deposit)",
        corpus,
    )
    assert "For this fixture" not in corpus
    assert "registartion" not in corpus
    assert "maintenence" not in corpus


def test_seeded_typos_are_sparse_and_not_hardcoded_by_document_index() -> None:
    first = generator.build_fixture_payloads(generator.DEFAULT_SEED)
    second = generator.build_fixture_payloads(generator.DEFAULT_SEED + 1)
    first_flags = [payload["typo_applied"] for payload in first]
    second_flags = [payload["typo_applied"] for payload in second]
    assert 2 <= sum(first_flags) <= 10
    assert first_flags != second_flags


def test_check_mode_comparison_is_clean_for_fresh_generation(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    generator.generate_fixtures(generator.DEFAULT_SEED, root)
    clean, report = generator.check_fixtures(generator.DEFAULT_SEED, root)
    assert clean is True
    assert report == []


def test_check_mode_reports_a_byte_difference(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    generator.generate_fixtures(generator.DEFAULT_SEED, root)
    changed = root / "docs" / "train" / "doc-01.txt"
    changed.write_text(changed.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")
    clean, report = generator.check_fixtures(generator.DEFAULT_SEED, root)
    assert clean is False
    assert report == ["different: docs/train/doc-01.txt"]
