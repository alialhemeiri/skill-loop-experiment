# P1 contract — fixtures generator + grader

You are building the frozen test bed for a pre-registered skill-improvement experiment. Read
`projects/autoresearch-skill-loop/00-control/SPEC.md` first — it is the authority. This contract
adds implementation detail. Work ONLY inside `projects/autoresearch-skill-loop/01-fixtures/` and
`projects/autoresearch-skill-loop/02-evaluator/`. Python 3 stdlib only. No network. Do not edit
SPEC.md or PLAN.md.

## Deliverable 1 — `01-fixtures/generator/generate.py`

Generates 16 synthetic UAE residential tenancy contracts + their gold records from a seeded RNG.

- CLI: `python generate.py [--seed 20260811] [--out-root ..]`; default seed 20260811. Same seed
  ⇒ byte-identical outputs (no set iteration, no dict-order hazards, no timestamps, no
  randomness outside the seeded `random.Random` instance).
- Outputs: `01-fixtures/gold/doc-01.json … doc-16.json` (the 12-field schema from SPEC §4,
  exact key names, correct JSON types, `null` for absent fields) and document texts
  `01-fixtures/docs/train/doc-01.txt … doc-10.txt`, `01-fixtures/docs/holdout/doc-11.txt …
  doc-16.txt`. Fixed split by index.
- Each document is a plausible 400–900-word plain-text tenancy contract built from one gold
  record. Requirements per SPEC §4: every present field appears exactly once as one consistent
  value (words+digits amounts must agree); 1–3 of the four nullable fields (security deposit,
  notice period, early-termination penalty, furnished status) are entirely absent from the text;
  seeded variety across the messiness menu — date formats (DD/MM/YYYY, "1 September 2026",
  ISO), AED formats ("AED 85,000", "85000 AED", "Dhs. 85,000/-", words+digits), payment
  phrasings ("four (4) post-dated cheques", "quarterly instalments" = 4, "two equal
  instalments" = 2), distractor clauses (agent commission, DEWA/chiller, Ejari registration,
  maintenance, arbitration — content that must NOT leak into gold fields), at least 3 distinct
  overall layouts across the 16 (numbered clauses / prose / a text "Schedule A" table), name
  variance (ALL CAPS, "Mr./Mrs.", "(the Landlord)" suffixes), occasional Arabic labels beside
  English ("الإيجار السنوي / Annual Rent"), sparse seeded typos in non-critical words only —
  never inside a gold value's digits.
- Invented entities only: fictitious person names (Emirati + expat mix), buildings,
  communities (Dubai/Abu Dhabi flavored but invented, e.g. "Al Nakheel Gardens"). No real
  companies or people.
- Sanity guard built in: after generating, the script re-reads each document and asserts every
  non-null gold value is actually present in the text in at least one of its rendered formats,
  and absent fields are truly absent (no stray mention). Fail loudly if violated.
- `--check` mode: regenerates to a temp dir and diffs byte-for-byte against the committed
  outputs; exit 0 clean / exit 1 with a report.
- Also RUN it once so the fixtures exist on disk.

## Deliverable 2 — `02-evaluator/grader.py`

Plain mechanical grader, no AI.

- CLI (single): `python grader.py --pred out.json --gold gold.json` → JSON report to stdout.
  CLI (batch): `python grader.py --pred-dir DIR --gold-dir DIR` → aggregate report (mean field
  accuracy, per-field breakdown, per-doc breakdown, hallucinated-absent count, unparseable
  count).
- Rules (SPEC §5): per-field exact match after normalization. Strings: casefold, collapse
  whitespace, strip surrounding punctuation, strip leading honorifics (mr, mrs, ms, dr, eng)
  and trailing parenthetical role suffixes like "(the landlord)". Dates: must be exact
  `YYYY-MM-DD` strings. Numbers: must be JSON numbers (`annual_rent_aed`,
  `security_deposit_aed`, `number_of_payments`, `notice_period_days` integers;
  `early_termination_penalty_months` int or float). `furnished_status`: one of the three enum
  strings or null, casefolded. Missing key, wrong type, or extra formatting ⇒ incorrect.
- Prediction file unparseable as JSON ⇒ score 0 for that doc, counted in `unparseable`.
- Hallucinated-absent: gold is null but prediction is non-null ⇒ incorrect AND counted in
  `hallucinated_absent`.
- Score = correct fields / 12, per doc; aggregate = mean over docs. Deterministic, pure stdlib.

## Deliverable 3 — `02-evaluator/tests/test_grader.py`

Pytest suite, ≥25 tests: every normalization rule (positive + negative), each field type, null
handling both directions, hallucinated-absent counting, unparseable JSON, missing keys, wrong
types, batch aggregation math, and at least 2 end-to-end tests grading a handcrafted prediction
against a real generated gold file. Also `02-evaluator/tests/test_generator.py`, ≥8 tests:
determinism (two runs same seed ⇒ identical), split sizes, schema validity of gold, sanity guard
catches a planted violation, nullable-absence bounds (1–3 per doc).

## Deliverable 4 — READMEs

Short `01-fixtures/README.md` and `02-evaluator/README.md`: what lives there, how to run, the
freeze warning ("these files freeze at G1 — see SPEC §8–9").

## Acceptance (run these yourself; report actual output)

1. `python 01-fixtures/generator/generate.py --check` → exit 0.
2. `python -m pytest projects/autoresearch-skill-loop/02-evaluator/tests/ -q` → all pass.
3. 16 docs + 16 gold files exist at the stated paths; eyeball one train doc and confirm the
   messiness menu is visibly present.

Final message: list files created, test counts + pass state, acceptance results, and any
deviation from this contract with its reason. Flag anything in SPEC §4–5 you found ambiguous
rather than silently choosing.
