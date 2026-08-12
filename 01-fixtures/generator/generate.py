#!/usr/bin/env python3
"""Generate deterministic synthetic UAE residential-tenancy fixtures."""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_SEED = 20260811
DOCUMENT_COUNT = 16
TRAIN_COUNT = 10

SCHEMA_FIELDS = (
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

NULLABLE_FIELDS = (
    "security_deposit_aed",
    "notice_period_days",
    "early_termination_penalty_months",
    "furnished_status",
)

FURNISHED_STATUSES = ("furnished", "semi-furnished", "unfurnished")
ENGLISH_MONTH_NAMES = (
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

FEMALE_FIRST_NAMES = (
    "Mariam",
    "Latifa",
    "Noura",
    "Hessa",
    "Elena",
    "Priya",
    "Amina",
    "Mei",
    "Sofia",
    "Anika",
    "Ifeoma",
    "Leonie",
    "Camila",
    "Salma",
    "Farah",
    "Nina",
    "Aya",
    "Petra",
)

# Every party, representative, building, and community is invented.
PERSON_NAMES = (
    "Mariam Qasim Al Nuaimi",
    "Saeed Nasser Al Mazrouei",
    "Latifa Hamdan Al Rashedi",
    "Rashid Salem Al Falahi",
    "Noura Khalfan Al Mehairi",
    "Tariq Juma Al Mansoori",
    "Hessa Adel Al Darmaki",
    "Yousef Majid Al Ketbi",
    "Elena Vukovic",
    "Daniel Okafor",
    "Priya Nandakumar",
    "Mateo Villanueva",
    "Amina Bensaid",
    "Tomasz Kowalski",
    "Mei Lin Tan",
    "Sofia Petrescu",
    "Lucas Ferreira",
    "Anika Bergstrom",
    "Nabil Khourani",
    "Ifeoma Eze",
    "Leonie Hartmann",
    "Arjun Menon",
    "Camila Duarte",
    "Marek Nowicki",
    "Salma Benyahia",
    "Jonas Lindholm",
    "Farah Siddiqui",
    "Dario Kovac",
    "Nina Velasquez",
    "Kofi Mensima",
    "Aya Morimoto",
    "Petra Horvat",
)

REPRESENTATIVE_NAMES = (
    "Rania Mourad",
    "Omar Vellani",
    "Lina Sarraf",
    "Harun Bekele",
    "Dina Kosic",
    "Zayd Rahmani",
    "Maya Torvik",
    "Bilal Azzam",
    "Noor Calder",
    "Samir Petrov",
    "Tala Mensah",
    "Elias Verma",
    "Ruba Kassem",
    "Adel Marin",
    "Yara Solberg",
    "Karim Novac",
)

COMMUNITIES = (
    "Al Nakheel Gardens",
    "Safa Crescent Quarter",
    "Marsa Lantern District",
    "Wadi Pearl Enclave",
    "Al Rimal Orchard",
    "Jumeira Cedar Walk",
    "Qasr Willow Gardens",
    "Al Dana Courtyard",
    "Barsha Amber Grove",
    "Mina Juniper Bay",
    "Al Raha Dune Park",
    "Khalidiya Palm Court",
    "Zayed Saffron Square",
    "Reem Copper Gardens",
    "Mushrif Iris Quarter",
    "Saadiyat Acacia Reach",
)

BUILDINGS = (
    "Copper Dune Tower",
    "Juniper Court",
    "Pearl Lantern House",
    "Cedar Arch Residences",
    "Amber Courtyard Building",
    "Saffron Gate House",
    "Willow Crest Tower",
    "Iris Quay Residences",
    "Acacia Shade Building",
    "Silver Ghaf Court",
    "Coral Compass House",
    "Dune Lattice Tower",
    "Palm Loom Residences",
    "Indigo Wind Court",
    "Marble Reed House",
    "Ghaf Lantern Building",
)

RENT_VALUES = (
    72000,
    78000,
    84000,
    90000,
    96000,
    102000,
    108000,
    114000,
    120000,
    126000,
    132000,
    138000,
    144000,
    150000,
    156000,
    162000,
    168000,
    174000,
    180000,
    186000,
)

PAYMENT_COUNTS = (1, 2, 4, 6, 12)
NOTICE_PERIODS = (30, 45, 60, 90)
PENALTY_MONTHS = (1, 1.5, 2, 3)
DERIVABLE_FIELDS = (
    "contract_end_date",
    "annual_rent_aed",
    "number_of_payments",
)

ABSENCE_PATTERNS = {
    "security_deposit_aed": (re.compile(r"\bdeposit\b", re.IGNORECASE),),
    "notice_period_days": (re.compile(r"\bnotices?\b", re.IGNORECASE),),
    "early_termination_penalty_months": (
        re.compile(r"\bearly[\s-]+termination\b", re.IGNORECASE),
        re.compile(r"\btermination[\s-]+penalt(?:y|ies)\b", re.IGNORECASE),
        re.compile(r"\bbreak[\s-]+fee\b", re.IGNORECASE),
    ),
    "furnished_status": (
        re.compile(r"\b(?:semi[\s-]*)?furnished\b", re.IGNORECASE),
        re.compile(r"\bunfurnished\b", re.IGNORECASE),
        re.compile(r"\bfurnish(?:ing|ings|ed|ure)?\b", re.IGNORECASE),
        re.compile(r"\bfurniture\b", re.IGNORECASE),
    ),
}


BASE_CLAUSES = (
    (
        "Purpose and occupation",
        "The home is let only for private residential occupation by the Occupant and members "
        "of the Occupant's household. It may not be used as a shop, office, holiday rental, "
        "shared lodging business, or address for an unrelated commercial licence. Guests "
        "remain the Occupant's responsibility while inside the premises or common areas.",
    ),
    (
        "Handover and condition",
        "At handover, both sides may complete a written condition record and attach dated "
        "photographs. Acceptance of keys confirms access but does not waive a hidden defect "
        "reported promptly after discovery. The Occupant shall keep the interior reasonably "
        "clean and return it in comparable condition, allowing for ordinary wear.",
    ),
    (
        "Payment administration",
        "Rent instruments shall be delivered to the Owner or a representative authorised in "
        "writing. Bank handling charges caused by a rejected instrument remain the Occupant's "
        "responsibility. Both sides should retain a receipt or bank record. Cash collection "
        "does not change a financial term unless both sides sign a written variation.",
    ),
    (
        "Utilities and services",
        "The Occupant is responsible for consumption-based household services connected to "
        "the premises. The Owner remains responsible for charges attaching solely to ownership "
        "of the building. Each side shall cooperate with account-opening papers, meter access, "
        "and final clearance without treating a service bill as part of the rent.",
    ),
    (
        "Care of the premises",
        "Routine cleaning, replacement of consumable items, and repair of damage caused by "
        "misuse fall to the Occupant. Structural defects and failures caused by age fall to the "
        "Owner, subject to building access rules. A problem should be reported promptly with "
        "enough detail for a suitable technician to be arranged.",
    ),
    (
        "Alterations",
        "Painting, drilling into stone, changing locks, installing exterior equipment, or "
        "altering service connections requires the Owner's written consent in advance. Any "
        "approved work must comply with building management rules and be carried out by a "
        "competent person. Consent to one alteration does not imply consent to another.",
    ),
    (
        "Access and privacy",
        "The Owner may request access at a reasonable hour for inspection, repair, or a "
        "building-management requirement. Except in a genuine emergency, the parties shall "
        "coordinate a suitable time in writing. The Owner shall not interfere unnecessarily "
        "with peaceful occupation, and the Occupant shall not unreasonably withhold access.",
    ),
    (
        "Conduct and common areas",
        "The Occupant shall observe access, parking, waste, noise, pool, lift, and visitor rules "
        "issued for the building. Corridors and fire routes must remain clear. Any access card "
        "or key supplied for common facilities remains linked to the premises and may not be "
        "copied for an unrelated person.",
    ),
    (
        "Records and changes",
        "This agreement and its operative particulars record the entire residential "
        "arrangement. A change is effective only when written clearly and accepted by both "
        "sides. Informal messages may coordinate practical matters, but they do not replace a "
        "signed change to a financial or occupancy obligation.",
    ),
    (
        "Counterparts",
        "The agreement may be signed in matching counterparts or by an accepted electronic "
        "signature method. Each counterpart is treated as part of the same instrument. The "
        "parties confirm that they had an opportunity to read the complete text and seek "
        "independent advice before acceptance.",
    ),
)

DISTRACTOR_CLAUSES = (
    (
        "DEWA and chiller services",
        "Where DEWA and district cooling serve the premises, the Occupant handles activation, "
        "consumption, and final clearance directly with the service companies. Those accounts "
        "do not alter any residential sum recorded in the operative particulars.",
    ),
    (
        "Ejari administration",
        "The parties shall provide ordinary identity and property papers needed for Ejari "
        "registration. A typing-centre receipt proves filing activity only and does not amend "
        "the dates, parties, premises, or financial bargain recorded here.",
    ),
    (
        "Maintenance allocation",
        "Minor maintenance arising from day-to-day use is handled by the Occupant, while major "
        "building-system work remains with the Owner unless misuse caused the damage. A help "
        "desk may classify a call, but that classification does not decide a dispute.",
    ),
    (
        "Arbitration",
        "A dispute not resolved through good-faith discussion may be referred to one arbitrator "
        "seated in the same Emirate. The arbitrator may allocate filing costs in the award. "
        "This process clause creates no additional rent, instalment, or utility charge.",
    ),
)


def number_to_words(value: int) -> str:
    """Return a deterministic English rendering for a non-negative integer."""

    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("number_to_words expects a non-negative integer")
    ones = (
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
    )
    tens = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")

    def below_thousand(number: int) -> str:
        parts: list[str] = []
        if number >= 100:
            parts.extend((ones[number // 100], "hundred"))
            number %= 100
        if number >= 20:
            tail = tens[number // 10]
            if number % 10:
                tail += "-" + ones[number % 10]
            parts.append(tail)
        elif number:
            parts.append(ones[number])
        return " ".join(parts)

    if value == 0:
        return "zero"
    if value >= 1_000_000:
        raise ValueError("number_to_words supports values below one million")
    thousands, remainder = divmod(value, 1000)
    parts: list[str] = []
    if thousands:
        parts.extend((below_thousand(thousands), "thousand"))
    if remainder:
        parts.append(below_thousand(remainder))
    return " ".join(parts)


def render_date(value: Any, style: str) -> str:
    if style == "slash":
        return f"{value.day:02d}/{value.month:02d}/{value.year:04d}"
    if style == "long":
        return f"{value.day} {ENGLISH_MONTH_NAMES[value.month]} {value.year}"
    if style == "iso":
        return f"{value.year:04d}-{value.month:02d}-{value.day:02d}"
    raise ValueError(f"unknown date style: {style}")


def render_money(value: int, style: str) -> str:
    if style == "aed_prefix":
        return f"AED {value:,}"
    if style == "aed_suffix":
        return f"{value} AED"
    if style == "dhs":
        return f"Dhs. {value:,}/-"
    if style == "words_digits":
        return f"{number_to_words(value).capitalize()} dirhams (AED {value:,})"
    raise ValueError(f"unknown money style: {style}")


def render_payment(count: int, variant: int) -> str:
    options = {
        1: ("one annual payment", "a single rent payment"),
        2: ("two equal instalments", "two (2) post-dated cheques"),
        4: ("quarterly instalments", "four (4) post-dated cheques"),
        6: ("six equal instalments", "six (6) post-dated cheques"),
        12: ("monthly payments", "twelve (12) post-dated cheques"),
    }
    return options[count][variant % 2]


def render_penalty(value: int | float, digit_style: bool) -> str:
    if digit_style:
        label = str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)
        return f"{label} {'month' if value == 1 else 'months'} of the agreed rent"
    return {
        1: "one month of the agreed rent",
        1.5: "one and one-half months of the agreed rent",
        2: "two months of the agreed rent",
        3: "three months of the agreed rent",
    }[value]


def render_name(name: str, role: str, style: str) -> str:
    if style == "caps":
        return name.upper()
    if style == "honorific":
        honorific = "Mrs." if name.split()[0] in FEMALE_FIRST_NAMES else "Mr."
        return f"{honorific} {name}"
    if style == "role":
        return f"{name} (the {role})"
    if style == "plain":
        return name
    raise ValueError(f"unknown name style: {style}")


def _iso_end_date(start: date) -> date:
    try:
        anniversary = start.replace(year=start.year + 1)
    except ValueError:
        # A 29 February commencement runs through 28 February the following year.
        return start.replace(year=start.year + 1, day=28)
    return anniversary - timedelta(days=1)


def _format_candidates(field: str, value: Any) -> tuple[str, ...]:
    if field in {"landlord_name", "tenant_name", "unit_number", "community"}:
        return (str(value),)
    if field in {"contract_start_date", "contract_end_date"}:
        parsed = date.fromisoformat(value)
        return tuple(render_date(parsed, style) for style in ("slash", "long", "iso"))
    if field in {"annual_rent_aed", "security_deposit_aed"}:
        return tuple(
            render_money(value, style)
            for style in ("aed_prefix", "aed_suffix", "dhs", "words_digits")
        )
    if field == "number_of_payments":
        return (render_payment(value, 0), render_payment(value, 1))
    if field == "notice_period_days":
        return (f"{value} calendar days",)
    if field == "early_termination_penalty_months":
        return (render_penalty(value, False), render_penalty(value, True))
    if field == "furnished_status":
        return (value,)
    raise KeyError(field)


def validate_gold_record(gold: Mapping[str, Any]) -> None:
    assert tuple(gold.keys()) == SCHEMA_FIELDS, "gold keys do not match the frozen schema/order"
    for field in ("landlord_name", "tenant_name", "unit_number", "community"):
        assert isinstance(gold[field], str) and gold[field], f"{field} must be a non-empty string"
    for field in ("contract_start_date", "contract_end_date"):
        assert isinstance(gold[field], str), f"{field} must be a string"
        assert date.fromisoformat(gold[field]).isoformat() == gold[field], f"{field} must be ISO"
    for field in ("annual_rent_aed", "number_of_payments"):
        assert type(gold[field]) is int, f"{field} must be an integer"
    for field in ("security_deposit_aed", "notice_period_days"):
        assert gold[field] is None or type(gold[field]) is int, f"{field} has the wrong type"
    penalty = gold["early_termination_penalty_months"]
    assert penalty is None or type(penalty) in (int, float), "penalty has the wrong type"
    furnished = gold["furnished_status"]
    assert furnished is None or furnished in FURNISHED_STATUSES, "invalid furnished_status"
    absent_count = sum(gold[field] is None for field in NULLABLE_FIELDS)
    assert 1 <= absent_count <= 3, "each document must omit 1–3 nullable fields"


def _fallback_present(text: str, field: str, value: Any, gold: Mapping[str, Any]) -> bool:
    folded = text.casefold()
    if any(candidate.casefold() in folded for candidate in _format_candidates(field, value)):
        return True
    if field == "contract_end_date":
        starts = _format_candidates("contract_start_date", gold["contract_start_date"])
        return "a term of twelve months" in folded and any(
            candidate.casefold() in folded for candidate in starts
        )
    if field == "annual_rent_aed":
        return f"{number_to_words(value)} dirhams" in folded
    if field == "security_deposit_aed":
        return (
            value == gold["annual_rent_aed"] // 20
            and "security deposit is fixed at five per cent" in folded
        )
    if field == "number_of_payments":
        word_count = number_to_words(value)
        if f"{word_count} post-dated cheque" in folded:
            return True
        if value > 1 and gold["annual_rent_aed"] % value == 0:
            per_payment = gold["annual_rent_aed"] // value
            return "taken together, the instruments exactly discharge" in folded and any(
                render_money(per_payment, style).casefold() in folded
                for style in ("aed_prefix", "aed_suffix", "dhs")
            )
    return False


def sanity_check_document(
    text: str,
    gold: Mapping[str, Any],
    evidence: Mapping[str, Mapping[str, Any]] | None = None,
) -> None:
    """Assert word bounds, copied/derived evidence, and total nullable absence."""

    validate_gold_record(gold)
    word_count = len(text.split())
    assert 400 <= word_count <= 900, f"document has {word_count} words; expected 400–900"
    folded = text.casefold()
    for field in SCHEMA_FIELDS:
        value = gold[field]
        if value is None:
            for pattern in ABSENCE_PATTERNS[field]:
                assert pattern.search(text) is None, (
                    f"absent field {field} is mentioned by {pattern.pattern!r}"
                )
            if evidence is not None:
                assert evidence[field]["mode"] == "absent", f"{field} evidence must be absent"
            continue

        if evidence is None:
            assert _fallback_present(text, field, value, gold), (
                f"no supported copy or derivation for non-null field {field}"
            )
            continue

        item = evidence[field]
        if item["mode"] == "copied":
            rendered = item["rendered"]
            assert isinstance(rendered, str) and rendered, f"{field} has no copied rendering"
            occurrences = folded.count(rendered.casefold())
            if field == "furnished_status" and rendered.casefold() == "furnished":
                occurrences -= folded.count("furnished status")
            assert occurrences == 1, f"copied field {field} occurs {occurrences} times"
        elif item["mode"] == "derived":
            statement = item["statement"]
            assert text.count(statement) == 1, (
                f"derived field {field} statement occurs {text.count(statement)} times"
            )
            for derivation_input in item["inputs"]:
                assert derivation_input in text, (
                    f"derived field {field} input is absent: {derivation_input!r}"
                )
            for forbidden in item.get("forbidden", ()):
                assert forbidden not in text, (
                    f"derived field {field} leaks copied value {forbidden!r}"
                )
        else:
            raise AssertionError(f"present field {field} has invalid evidence mode")


def _balanced_absence_patterns(rng: random.Random) -> list[tuple[str, str]]:
    pairs = [
        (NULLABLE_FIELDS[0], NULLABLE_FIELDS[1]),
        (NULLABLE_FIELDS[2], NULLABLE_FIELDS[3]),
        (NULLABLE_FIELDS[0], NULLABLE_FIELDS[2]),
        (NULLABLE_FIELDS[1], NULLABLE_FIELDS[3]),
        (NULLABLE_FIELDS[0], NULLABLE_FIELDS[3]),
        (NULLABLE_FIELDS[1], NULLABLE_FIELDS[2]),
    ]
    train = pairs + pairs[:4]
    holdout = list(pairs)
    rng.shuffle(train)
    rng.shuffle(holdout)
    return train + holdout


def _render_table(rows: Sequence[tuple[str, str]]) -> str:
    all_rows = [("Field", "Agreed detail"), *rows]
    label_width = max(len(label) for label, _ in all_rows)
    value_width = max(len(value) for _, value in all_rows)
    border = f"+-{'-' * label_width}-+-{'-' * value_width}-+"

    def row(label: str, value: str) -> str:
        return f"| {label:<{label_width}} | {value:<{value_width}} |"

    lines = [border, row("Field", "Agreed detail"), border]
    lines.extend(row(label, value) for label, value in rows)
    lines.append(border)
    return "\n".join(lines)


def _layout_header(
    layout: str,
    rows: Sequence[tuple[str, str]],
    *,
    easy_labeled: bool,
) -> str:
    completeness = "COMPLETE KEY TERMS" if easy_labeled else "SELECTED ADMINISTRATIVE DETAILS"
    if layout == "numbered":
        lines = ["RESIDENTIAL TENANCY AGREEMENT", "", f"1. PARTIES AND {completeness}"]
        lines.extend(f"{label}: {value}" for label, value in rows)
        return "\n".join(lines)
    if layout == "prose":
        lines = ["This residential tenancy agreement is recorded in narrative form."]
        if rows:
            lines.extend(("", completeness))
            lines.extend(f"{label}: {value}" for label, value in rows)
        return "\n".join(lines)
    if layout == "schedule":
        return "\n".join(
            (
                "RESIDENTIAL TENANCY AGREEMENT",
                "",
                "SCHEDULE A — KEY TERMS",
                completeness,
                _render_table(rows),
                "",
                "Schedule A forms part of this agreement; operative prose controls every "
                "matter not recorded in the table.",
            )
        )
    raise ValueError(f"unknown layout: {layout}")


def _render_facts(layout: str, facts: Sequence[str]) -> str:
    paragraphs = [" ".join(facts[index : index + 3]) for index in range(0, len(facts), 3)]
    if layout == "numbered":
        headings = ("2. OPERATIVE PARTICULARS", "3. TERM AND MONEY", "4. OTHER AGREED TERMS")
        blocks: list[str] = []
        for index, paragraph in enumerate(paragraphs):
            heading = headings[min(index, len(headings) - 1)]
            blocks.append(f"{heading}\n{paragraph}")
        return "\n\n".join(blocks)
    if layout == "prose":
        return "\n\n".join(paragraphs)
    return "OPERATIVE TERMS\n" + "\n\n".join(paragraphs)


def _choose_distractors(index: int, rng: random.Random) -> list[tuple[str, str]]:
    chosen = {index % len(DISTRACTOR_CLAUSES)}
    candidates = [
        position
        for position in range(len(DISTRACTOR_CLAUSES))
        if position not in chosen
    ]
    rng.shuffle(candidates)
    chosen.update(candidates[: rng.randint(1, 2)])
    return [DISTRACTOR_CLAUSES[position] for position in sorted(chosen)]


def _apply_sparse_typo(text: str, rng: random.Random) -> tuple[str, bool]:
    """Use the per-document RNG once; only static boilerplate is eligible."""

    if rng.random() >= 0.42:
        return text, False
    replacements = (
        ("responsibility", "responsiblity"),
        ("separate", "seperate"),
        ("opportunity", "oportunity"),
        ("reasonable", "reasonble"),
        ("electronic", "eletronic"),
        ("ordinary", "ordnary"),
    )
    available = [(old, new) for old, new in replacements if old in text]
    if not available:
        return text, False
    old, new = available[rng.randrange(len(available))]
    return text.replace(old, new, 1), True


def _render_clauses(layout: str, index: int, rng: random.Random) -> tuple[str, bool]:
    clauses = list(BASE_CLAUSES)
    distractors = _choose_distractors(index, rng)
    insertion_points = list(range(1, len(clauses)))
    rng.shuffle(insertion_points)
    for offset, clause in enumerate(distractors):
        clauses.insert(min(insertion_points[offset] + offset, len(clauses)), clause)
    rendered: list[str] = []
    for clause_number, (heading, body) in enumerate(clauses, start=5):
        if layout == "numbered":
            rendered.append(f"{clause_number}. {heading.upper()}\n{body}")
        elif layout == "prose":
            rendered.append(f"{heading}. {body}")
        else:
            rendered.append(f"{heading.upper()}\n{body}")
    return _apply_sparse_typo("\n\n".join(rendered), rng)


def _absent_evidence() -> dict[str, Any]:
    return {
        "mode": "absent",
        "location": "absent",
        "rendered": None,
        "statement": None,
        "inputs": (),
        "forbidden": (),
    }


def _copied_evidence(rendered: str, statement: str) -> dict[str, Any]:
    return {
        "mode": "copied",
        "location": "prose",
        "rendered": rendered,
        "statement": statement,
        "inputs": (rendered,),
        "forbidden": (),
    }


def _derived_evidence(
    statement: str,
    inputs: Sequence[str],
    forbidden: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "mode": "derived",
        "location": "prose",
        "rendered": None,
        "statement": statement,
        "inputs": tuple(inputs),
        "forbidden": tuple(forbidden),
    }


def _build_payload(
    *,
    index: int,
    rng: random.Random,
    names: Sequence[str],
    representatives: Sequence[str],
    communities: Sequence[str],
    buildings: Sequence[str],
    rents: Sequence[int],
    absence: Sequence[str],
    layout: str,
    date_style: str,
    money_style: str,
    name_styles: Sequence[str],
    payment_count: int,
    easy_labeled: bool,
    primary_derivation: str,
) -> dict[str, Any]:
    landlord_name = names[index]
    tenant_name = names[index + DOCUMENT_COUNT]
    representative_name = representatives[index]
    representative_role = rng.choice(("leasing agent", "property manager"))
    unit_prefix = rng.choice(("A", "B", "C", "D", "E", "F"))
    unit_number = f"{unit_prefix}-{rng.randint(2, 38):02d}{rng.randint(1, 12):02d}"
    parking_bay = f"P-{rng.randint(101, 989)}"
    start = date(2026, 8, 15) + timedelta(days=index * 19 + rng.randint(0, 11))
    end = _iso_end_date(start)
    rent = rents[index]
    absent = set(absence)
    security_deposit = None if "security_deposit_aed" in absent else rent // 20
    notice_period = None if "notice_period_days" in absent else rng.choice(NOTICE_PERIODS)
    penalty = None if "early_termination_penalty_months" in absent else rng.choice(PENALTY_MONTHS)
    furnished = None if "furnished_status" in absent else rng.choice(FURNISHED_STATUSES)

    gold: dict[str, Any] = {
        "landlord_name": landlord_name,
        "tenant_name": tenant_name,
        "unit_number": unit_number,
        "community": communities[index],
        "contract_start_date": start.isoformat(),
        "contract_end_date": end.isoformat(),
        "annual_rent_aed": rent,
        "security_deposit_aed": security_deposit,
        "number_of_payments": payment_count,
        "notice_period_days": notice_period,
        "early_termination_penalty_months": penalty,
        "furnished_status": furnished,
    }
    validate_gold_record(gold)

    if easy_labeled:
        derivations = {primary_derivation}
        derivations.add(
            rng.choice([field for field in DERIVABLE_FIELDS if field not in derivations])
        )
    else:
        derivations = set(DERIVABLE_FIELDS)

    landlord_rendered = render_name(landlord_name, "Landlord", name_styles[0])
    tenant_rendered = render_name(tenant_name, "Tenant", name_styles[1])
    start_rendered = render_date(start, date_style)
    end_rendered = render_date(end, date_style)
    decoy_date = start - timedelta(days=rng.randint(1, 7)) if rng.randrange(2) == 0 else start + timedelta(days=rng.randint(1, 4))
    decoy_date_rendered = render_date(decoy_date, rng.choice(("slash", "long", "iso")))
    date_subject = rng.choice(("handover inspection", "Ejari registration appointment"))
    commission = 2275 + index * 175
    chiller_guarantee = 675 + (index % 5) * 125
    decoy_money_styles = ("aed_prefix", "aed_suffix", "dhs", "words_digits")
    commission_rendered = render_money(
        commission, decoy_money_styles[index % len(decoy_money_styles)]
    )
    chiller_rendered = render_money(
        chiller_guarantee,
        decoy_money_styles[(index + 2) % len(decoy_money_styles)],
    )
    money_marker = (
        f"agent commission of {commission_rendered} and chiller account guarantee of "
        f"{chiller_rendered}"
    )

    representative_statement = (
        f"{landlord_rendered} is the Landlord, with {representative_role} "
        f"{representative_name} authorised only to coordinate access and paperwork; the "
        "representative acquires no ownership interest."
    )
    tenant_statement = (
        f"{tenant_rendered} takes the premises as Tenant and bears the obligations assigned "
        "to the Occupant."
    )
    unit_statement = (
        f"The demised premises are Unit {unit_number}; parking bay {parking_bay} is a separate "
        "access reference and is not part of the unit identifier."
    )
    community_statement = (
        f"The unit lies in {buildings[index]}, within the wider community of "
        f"{communities[index]}; the building name does not replace the community."
    )

    if "contract_end_date" in derivations:
        term_statement = (
            f"The contractual term is a term of twelve months commencing {start_rendered}; "
            f"the {date_subject} dated {decoy_date_rendered} is an administrative event, not "
            "the tenancy commencement."
        )
    else:
        term_statement = (
            f"The contractual term begins {start_rendered} and ends {end_rendered}; the "
            f"{date_subject} dated {decoy_date_rendered} is an administrative event, not a "
            "second term date."
        )

    if "annual_rent_aed" in derivations:
        annual_rendered = f"{number_to_words(rent).capitalize()} dirhams"
        rent_statement = (
            f"The yearly residential consideration is {annual_rendered} in total; the "
            f"{money_marker} are separate sums owed only to their named service providers."
        )
    else:
        annual_rendered = render_money(rent, money_style)
        rent_statement = (
            f"The annual residential rent is {annual_rendered}; the {money_marker} are "
            "separate sums owed only to their named service providers."
        )

    deposit_is_derived = security_deposit is not None and not easy_labeled
    if security_deposit is not None:
        if deposit_is_derived:
            deposit_rendered = None
            deposit_statement = (
                "The tenancy security deposit is fixed at five per cent of the yearly "
                "residential consideration; that percentage does not describe either "
                "external service-provider amount."
            )
        else:
            deposit_rendered = render_money(
                security_deposit,
                rng.choice(("aed_prefix", "aed_suffix", "dhs", "words_digits")),
            )
            deposit_statement = (
                f"The Owner holds {deposit_rendered} as the tenancy security deposit, "
                "distinct from every external service-provider amount."
            )
    else:
        deposit_rendered = None
        deposit_statement = None

    if "number_of_payments" in derivations:
        if payment_count == 1 or rng.randrange(2) == 0:
            count_phrase = (
                f"{number_to_words(payment_count).capitalize()} post-dated "
                f"{'cheque' if payment_count == 1 else 'cheques'}"
            )
            if payment_count == 1:
                payment_statement = (
                    f"{count_phrase}, separately identified in the delivery record, "
                    "constitutes the complete set of rent instruments."
                )
            else:
                payment_statement = (
                    f"{count_phrase}, each separately identified in the delivery record, "
                    "constitute the complete set of rent instruments."
                )
            payment_inputs = (count_phrase,)
        else:
            per_payment = rent // payment_count
            per_rendered = render_money(per_payment, rng.choice(("aed_prefix", "aed_suffix", "dhs")))
            relation = "taken together, the instruments exactly discharge"
            payment_statement = (
                f"Each equal rent instrument is {per_rendered}; {relation} the full yearly "
                "residential consideration stated in this agreement."
            )
            payment_inputs = (annual_rendered, per_rendered, relation)
        payment_rendered = None
    else:
        payment_rendered = render_payment(payment_count, rng.randrange(2))
        payment_statement = f"Rent is payable through {payment_rendered}."

    notice_rendered = f"{notice_period} calendar days" if notice_period is not None else None
    notice_statement = (
        f"A party declining renewal must give the other party {notice_rendered} before expiry."
        if notice_rendered is not None
        else None
    )
    penalty_rendered = render_penalty(penalty, bool(rng.randrange(2))) if penalty is not None else None
    penalty_statement = (
        f"If the Occupant ends the tenancy early, the agreed termination penalty equals "
        f"{penalty_rendered}."
        if penalty_rendered is not None
        else None
    )
    furnished_rendered = furnished
    furnished_statement = (
        f"At commencement the premises are delivered {furnished_rendered}."
        if furnished_rendered is not None
        else None
    )

    evidence: dict[str, dict[str, Any]] = {
        "landlord_name": _copied_evidence(landlord_rendered, representative_statement),
        "tenant_name": _copied_evidence(tenant_rendered, tenant_statement),
        "unit_number": _copied_evidence(unit_number, unit_statement),
        "community": _copied_evidence(communities[index], community_statement),
        "contract_start_date": _copied_evidence(start_rendered, term_statement),
        "contract_end_date": (
            _derived_evidence(
                term_statement,
                ("a term of twelve months", start_rendered),
                _format_candidates("contract_end_date", end.isoformat()),
            )
            if "contract_end_date" in derivations
            else _copied_evidence(end_rendered, term_statement)
        ),
        "annual_rent_aed": (
            _derived_evidence(
                rent_statement,
                (annual_rendered,),
                (str(rent), f"{rent:,}"),
            )
            if "annual_rent_aed" in derivations
            else _copied_evidence(annual_rendered, rent_statement)
        ),
        "security_deposit_aed": (
            _absent_evidence()
            if security_deposit is None
            else (
                _derived_evidence(
                    deposit_statement,
                    (annual_rendered, "five per cent"),
                    _format_candidates("security_deposit_aed", security_deposit),
                )
                if deposit_is_derived
                else _copied_evidence(deposit_rendered, deposit_statement)
            )
        ),
        "number_of_payments": (
            _derived_evidence(payment_statement, payment_inputs)
            if "number_of_payments" in derivations
            else _copied_evidence(payment_rendered, payment_statement)
        ),
        "notice_period_days": (
            _absent_evidence()
            if notice_period is None
            else _copied_evidence(notice_rendered, notice_statement)
        ),
        "early_termination_penalty_months": (
            _absent_evidence()
            if penalty is None
            else _copied_evidence(penalty_rendered, penalty_statement)
        ),
        "furnished_status": (
            _absent_evidence()
            if furnished is None
            else _copied_evidence(furnished_rendered, furnished_statement)
        ),
    }

    bilingual = index % 3 == 0 or rng.random() < 0.18
    labels = {
        "landlord_name": "المالك / Landlord" if bilingual else "Landlord",
        "tenant_name": "المستأجر / Tenant" if bilingual else "Tenant",
        "unit_number": "رقم الوحدة / Unit number" if bilingual else "Unit number",
        "community": "المجتمع / Community" if bilingual else "Community",
        "contract_start_date": "Contract start date",
        "contract_end_date": "Contract end date",
        "annual_rent_aed": "الإيجار السنوي / Annual rent" if bilingual else "Annual rent",
        "security_deposit_aed": "مبلغ التأمين / Security deposit" if bilingual else "Security deposit",
        "number_of_payments": "Payment plan",
        "notice_period_days": "Renewal notice period",
        "early_termination_penalty_months": "Early-termination penalty",
        "furnished_status": "Furnished status",
    }
    label_values: dict[str, str] = {
        "landlord_name": (
            f"{landlord_rendered}; {representative_role} {representative_name} coordinates "
            "access and paperwork only"
        ),
        "tenant_name": tenant_rendered,
        "unit_number": f"{unit_number}; separate parking-bay reference {parking_bay}",
        "community": f"{communities[index]}; building {buildings[index]}",
        "contract_start_date": (
            f"{start_rendered}; {date_subject} {decoy_date_rendered} is administrative only"
        ),
        "contract_end_date": end_rendered,
        "annual_rent_aed": (
            f"{annual_rendered}; {money_marker} are external service-provider sums"
        ),
        "security_deposit_aed": deposit_rendered,
        "number_of_payments": payment_rendered,
        "notice_period_days": notice_rendered,
        "early_termination_penalty_months": penalty_rendered,
        "furnished_status": furnished_rendered,
    }

    labelable = [
        field
        for field in SCHEMA_FIELDS
        if evidence[field]["mode"] == "copied" and label_values.get(field) is not None
    ]
    if "contract_end_date" in derivations:
        labelable = [field for field in labelable if field != "contract_start_date"]
    if easy_labeled:
        selected_labels = set(labelable)
    elif layout == "prose":
        selected_labels = set()
    else:
        hard_candidates = [
            field
            for field in labelable
            if field not in {"contract_start_date", "contract_end_date"}
        ]
        selected_labels = set(rng.sample(hard_candidates, min(1, len(hard_candidates))))
    if not easy_labeled:
        selected_labels.discard("contract_start_date")
        selected_labels.discard("contract_end_date")

    for field in selected_labels:
        evidence[field]["location"] = "labeled"

    rows = [
        (labels[field], label_values[field])
        for field in SCHEMA_FIELDS
        if field in selected_labels
    ]
    facts: list[str] = []
    seen_facts: set[str] = set()
    for field in SCHEMA_FIELDS:
        item = evidence[field]
        if item["mode"] == "absent" or item["location"] == "labeled":
            continue
        statement = item["statement"]
        if statement not in seen_facts:
            facts.append(statement)
            seen_facts.add(statement)

    header = _layout_header(layout, rows, easy_labeled=easy_labeled)
    operative_facts = _render_facts(layout, facts)
    clauses, typo_applied = _render_clauses(layout, index, rng)
    signature = (
        "SIGNATURE CONFIRMATION\nThe parties accept this agreement through their respective "
        "signature blocks. Matching signature copies identify the same residential instrument "
        "and add no new party, date, premises reference, or financial term."
    )
    document = f"{header}\n\n{operative_facts}\n\n{clauses}\n\n{signature}\n"
    sanity_check_document(document, gold, evidence)
    return {
        "index": index + 1,
        "gold": gold,
        "document": document,
        "evidence": evidence,
        "easy_labeled": easy_labeled,
        "layout": layout,
        "decoy_markers": {
            "representative": representative_name,
            "money": money_marker,
            "building": buildings[index],
            "date": decoy_date_rendered,
            "parking": parking_bay,
        },
        "typo_applied": typo_applied,
    }


def build_fixture_payloads(seed: int) -> list[dict[str, Any]]:
    """Render all documents and their in-memory consistency evidence."""

    rng = random.Random(seed)
    names = list(PERSON_NAMES)
    representatives = list(REPRESENTATIVE_NAMES)
    communities = list(COMMUNITIES)
    buildings = list(BUILDINGS)
    rents = list(RENT_VALUES)
    for values in (names, representatives, communities, buildings, rents):
        rng.shuffle(values)

    absence_patterns = _balanced_absence_patterns(rng)
    layouts = ["numbered", "prose", "schedule"]
    date_styles = ["slash", "long", "iso"]
    money_styles = ["aed_prefix", "aed_suffix", "dhs", "words_digits"]
    name_styles = ["plain", "caps", "honorific", "role"]
    payment_cycle = list(PAYMENT_COUNTS)
    derivation_cycle = list(DERIVABLE_FIELDS)
    for values in (layouts, date_styles, money_styles, name_styles, payment_cycle, derivation_cycle):
        rng.shuffle(values)
    easy_indexes = set(rng.sample(range(TRAIN_COUNT), 1))
    easy_indexes.update(rng.sample(range(TRAIN_COUNT, DOCUMENT_COUNT), 1))

    payloads: list[dict[str, Any]] = []
    for index in range(DOCUMENT_COUNT):
        doc_rng = random.Random(rng.getrandbits(64))
        payloads.append(
            _build_payload(
                index=index,
                rng=doc_rng,
                names=names,
                representatives=representatives,
                communities=communities,
                buildings=buildings,
                rents=rents,
                absence=absence_patterns[index],
                layout=layouts[index % len(layouts)],
                date_style=date_styles[index % len(date_styles)],
                money_style=money_styles[index % len(money_styles)],
                name_styles=(
                    name_styles[index % len(name_styles)],
                    name_styles[(index + 1) % len(name_styles)],
                ),
                payment_count=payment_cycle[index % len(payment_cycle)],
                easy_labeled=index in easy_indexes,
                primary_derivation=derivation_cycle[index % len(derivation_cycle)],
            )
        )
    return payloads


def _output_paths(out_root: Path, index: int) -> tuple[Path, Path]:
    split = "train" if index <= TRAIN_COUNT else "holdout"
    return (
        out_root / "docs" / split / f"doc-{index:02d}.txt",
        out_root / "gold" / f"doc-{index:02d}.json",
    )


def generate_fixtures(seed: int, out_root: Path | str) -> list[Path]:
    """Generate all fixture files and return their paths relative to ``out_root``."""

    root = Path(out_root)
    for directory in (root / "docs" / "train", root / "docs" / "holdout", root / "gold"):
        directory.mkdir(parents=True, exist_ok=True)
    payloads = build_fixture_payloads(seed)
    written: list[Path] = []
    manifests: list[tuple[Path, Path, Mapping[str, Mapping[str, Any]]]] = []
    for payload in payloads:
        document_path, gold_path = _output_paths(root, payload["index"])
        document_path.write_text(payload["document"], encoding="utf-8", newline="\n")
        gold_path.write_text(
            json.dumps(payload["gold"], ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        written.extend((document_path.relative_to(root), gold_path.relative_to(root)))
        manifests.append((document_path, gold_path, payload["evidence"]))

    for document_path, gold_path, evidence in manifests:
        sanity_check_document(
            document_path.read_text(encoding="utf-8"),
            json.loads(gold_path.read_text(encoding="utf-8")),
            evidence,
        )
    return sorted(written, key=lambda path: path.as_posix())


def _fixture_files(root: Path) -> list[Path]:
    paths = list((root / "gold").glob("doc-*.json"))
    paths.extend((root / "docs" / "train").glob("doc-*.txt"))
    paths.extend((root / "docs" / "holdout").glob("doc-*.txt"))
    return sorted((path.relative_to(root) for path in paths), key=lambda path: path.as_posix())


def check_fixtures(seed: int, committed_root: Path | str) -> tuple[bool, list[str]]:
    """Regenerate in a temporary directory and byte-compare committed outputs."""

    committed = Path(committed_root)
    with tempfile.TemporaryDirectory(prefix="tenancy-fixture-check-") as temp_dir:
        generated = Path(temp_dir) / "fixtures"
        expected_paths = generate_fixtures(seed, generated)
        actual_paths = _fixture_files(committed)
        expected_names = [path.as_posix() for path in expected_paths]
        actual_names = [path.as_posix() for path in actual_paths]
        report: list[str] = []
        report.extend(f"missing: {name}" for name in expected_names if name not in actual_names)
        report.extend(f"unexpected: {name}" for name in actual_names if name not in expected_names)
        for relative_path in expected_paths:
            committed_path = committed / relative_path
            if committed_path.is_file() and (
                generated / relative_path
            ).read_bytes() != committed_path.read_bytes():
                report.append(f"different: {relative_path.as_posix()}")
        return not report, report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--out-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="fixture root (default: parent of generator/)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate temporarily and compare with files at --out-root",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.check:
        clean, report = check_fixtures(args.seed, args.out_root)
        if clean:
            print("OK: all 32 generated fixture files match byte-for-byte")
            return 0
        print("Fixture check failed:", file=sys.stderr)
        for line in report:
            print(f"  {line}", file=sys.stderr)
        return 1
    paths = generate_fixtures(args.seed, args.out_root)
    print(f"Generated {len(paths) // 2} documents and {len(paths) // 2} gold records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
