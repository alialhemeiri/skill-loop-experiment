# G1R contract — remediation round after the G1 review (engine: GPT 5.6 Sol)

You are remediating a pre-registered experiment's test bed after an adversarial review, BEFORE
anything freezes. Read, in order: `projects/autoresearch-skill-loop/00-control/SPEC.md`
**including its Amendments section A1** (A1 is your requirements list; this contract adds
implementation detail), then `00-control/reviews/G1-opus-review.md` (the findings you are
fixing), then the current code (`01-fixtures/generator/generate.py`, `02-evaluator/grader.py`,
`04-runner/run.py`, both test suites, `04-runner/test_run.py`).

**Scope:** work ONLY inside `01-fixtures/`, `02-evaluator/`, `04-runner/`, `05-runs/`
(calibration batches named `g1-cal-*`), plus exactly one append to
`00-control/worker-system-prompt.txt`. Do NOT touch: `03-skill/` (v0 is byte-frozen for you),
SPEC.md, PLAN.md, worker.json, `00-control/reviews/`, `06-log/`. Python 3 stdlib only
(`python3` — there is no `python` on this box). The claude CLI is available and networked for
calibration runs.

## Deliverable 1 — generator v2 (A1.1; review BLOCKER 1, MAJORs 7, MINORs 15/17/18/23)

Rewrite document rendering for difficulty while keeping: 16 docs, 10/6 split by index, seed
20260811, byte-reproducibility, 400–900 words, the sanity guard, `--check` mode, invented
entities, the original messiness menu (date/AED/payment formats, layouts, name variance,
Arabic labels).

New difficulty requirements, seeded per document:
- A majority of gold values appear inside prose clauses, not on labeled key-terms lines. Keep
  2–3 docs in the easier labeled style (difficulty gradient); the rest carry at most a partial
  key-terms block.
- Label-adjacent decoys, each attributed clearly to its true non-gold subject (never a second
  value for a gold field): agent / property-manager names in the same sentence or clause as
  landlord references; chiller-guarantee and agent-commission AED amounts near rent/deposit
  language; a building name adjacent to the community; a handover or Ejari registration date
  near the start date; a parking-bay identifier near the unit number.
- ≥1 field per document requiring unambiguous DERIVATION rather than copy, e.g.: end date from
  "a term of twelve months commencing 26/08/2026"; `number_of_payments` from enumerated
  cheques ("four post-dated cheques of AED 21,000 each") or from per-instalment amounts whose
  count is unambiguous; annual rent written in words only. Never two conflicting statements of
  the same fact (no-contradiction rule stands).
- Per-field null rates for the 4 nullable fields must match between train and holdout within
  10 percentage points (A1.1). Print the per-field table in your final report.
- Sanity guard update: for copied fields assert the rendered value appears; for derived fields
  assert every derivation input appears and the derivation is stated in one place only; absent
  fields remain entirely absent (no stray mention of that concept for the doc).
- Determinism fixes: hardcoded English month-name tuple instead of `strftime('%B')`; typos
  actually seeded via the RNG across all docs (sparse, never inside gold value digits or
  derivation inputs); remove the "For this fixture" phrasing; pad the Schedule A table cells
  to the border widths.

## Deliverable 2 — runner v2 (A1.2, A1.3, A1.4; review BLOCKER 2, MAJORs 4/5/6/11)

- **Fence-strip (exact registered rule):** after extracting `.result`: trim outer whitespace;
  if the first line matches `^```[A-Za-z0-9]*$` AND the last line is exactly ```` ``` ````,
  remove those two lines and re-trim. One pair maximum. The stripped bytes go ONLY to the
  `preds/` file; `raw.txt` and `result.json` keep the ORIGINAL bytes (forensics). Manifest
  per-run field `fence_stripped: bool`. Model-failure classification (invalid JSON) is
  decided on the STRIPPED text.
- **Holdout retries:** remove the `1 if holdout_mode` override — the transport retry budget
  (max 2 retries) applies everywhere. Delivered model outputs are still never retried.
- **Holdout ledger:** before executing any holdout batch, read
  `00-control/holdout-usage.log`; if it records a different batch-id, refuse loudly. Append
  one line per holdout batch start: ISO timestamp, batch-id, skill sha256, doc ids. Resuming
  the same batch-id is allowed and does not append a duplicate.
- **Turn check:** a successful CLI envelope with `num_turns != 1` or non-empty
  `permission_denials` is classified as a transport failure (retry-eligible, reason logged).
- **Model recording:** store per-run in the manifest the envelope's `modelUsage` key list and
  the `canonicalModel`/provider fields if present.
- Update `04-runner/test_run.py` accordingly (fence-strip cases: fenced+valid, fenced+still
  invalid, unfenced, fence-with-language-tag; holdout retry now allowed; ledger refusal +
  same-batch resume; turn-check classification).

## Deliverable 3 — grader v2 + frozen score.py (A1.6; MAJORs 9/10, MINORs 12/13/14/16)

Grader (`02-evaluator/grader.py`) — parsing stays strict (NO fence handling here):
- Distinguish `missing` (prediction file absent — count separately, score 0, NOT counted
  unparseable) from `unparseable` (file exists, invalid JSON).
- Add `wrong_shape` (valid JSON, non-object): score 0, counted.
- Add `missed_present` counter (gold non-null, prediction null or key absent), reported per
  doc and aggregated, alongside `hallucinated_absent`.
- `furnished_status`: collapse whitespace and strip outer whitespace (same string
  normalization pipeline as other strings) before the casefolded enum comparison.
- Replace the `unicodedata.category` punctuation test with an explicit frozen character set
  (ASCII punctuation + the non-ASCII punctuation the generator can emit — enumerate them).
- Flip/extend the tests that locked the old behaviours; add positive+negative cases for every
  new counter.

`02-evaluator/score.py` (new, will be hash-frozen):
- CLI: `python3 score.py --batch-dir <05-runs/NAME> --gold-root <01-fixtures/gold>`.
- Reads the batch manifest; ASSERTS completeness before scoring: every expected (doc × rep)
  run present and terminal, zero transport failures, zero missing prediction files — else exit
  2 with a clear report and NO score.
- Grades every rep against the manifest's doc ids (import grader functions directly; filter
  gold by doc id — never require a pre-filtered gold dir).
- Output JSON: pooled mean field accuracy (the candidate score), per-rep means, per-field and
  per-doc breakdowns, all counters (`unparseable`, `wrong_shape`, `missing`,
  `hallucinated_absent`, `missed_present`), `fence_stripped` count from the manifest.
- Tests: completeness refusal (missing run / transport failure / rep gap), aggregation math on
  a handcrafted 2-rep fixture, counter pass-through.

Also: `01-fixtures/README.md` + `02-evaluator/README.md` — commands to `python3`; document the
new counters and score.py. Add `05-runs/p2-dry-pre-review/NOTE.md` (3 lines: directory renamed
from `p2-dry` after the fact; manifest predates provenance hashes; kept as an honest artifact).
Add a cross-process determinism test: run `generate.py` twice via `subprocess` with different
`LC_ALL` values (e.g. `C` and `C.utf8`) into temp dirs and assert byte-identical trees.

## Deliverable 4 — calibration (A1.1 target band; the anti-gaming rule is absolute)

After Deliverables 1–3 pass their suites: run v0 (`03-skill/versions/v0/SKILL.md`, read-only)
over all 10 training docs, 1 rep, via the NEW runner (`--batch-id g1-cal-1`), score with the
NEW score.py. Target: pooled mean in **[0.55, 0.90]**.
- Above 0.90 → increase generic rendering difficulty (more prose renderings, more derivation
  fields, stronger decoy adjacency) and regenerate; below 0.55 → ease generically.
- **NEVER tune fixtures against specific observed v0 mistakes** (do not inspect which fields
  v0 got wrong and craft renderings targeting them; adjust global difficulty knobs only —
  A1.1's anti-anti-sandbagging rule). You may read the per-field score table to know the
  overall level, not to design targeted traps.
- ≤4 calibration rounds (`g1-cal-1` … `g1-cal-4`), each preserved under `05-runs/`. If still
  outside the band after 4, stop and report — do not keep tuning.
- Keep `--sleep-between` at default; ~10 worker calls per round.

## Acceptance (run everything yourself; report actual output)

1. `python3 01-fixtures/generator/generate.py --check` → exit 0.
2. `python3 -m pytest 02-evaluator/tests/ -q` all pass; `python3 04-runner/test_run.py` all
   pass (report counts).
3. Null-rate table train vs holdout, all four nullable fields within 10pp.
4. Final calibration batch score in [0.55, 0.90] with `unparseable + wrong_shape + missing = 0`
   (fence-strip working) — quote the score.py JSON summary lines.
5. One regenerated train doc quoted in full in your report (for the founder's skim) + state
   which fields in it are prose-rendered, which derived, which decoys present.
6. Word counts all within 400–900; layouts still ≥3 distinct styles.

Final message: files changed, test counts, the null-rate table, every calibration round's
score, the quoted document, and any deviation from this contract or A1 with its reason. Flag
ambiguities rather than silently choosing.
