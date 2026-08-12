# P3 contract — evidence-pack builder (engine: GPT 5.6 Sol)

Read first: `projects/autoresearch-skill-loop/00-control/SPEC.md` §6–§7 (patcher's allowed
context) and `02-evaluator/score.py` + `02-evaluator/grader.py` (import these; do not
reimplement scoring).

**Scope:** create ONLY `04-runner/evidence.py` and `04-runner/test_evidence.py` (+ a short
section appended to `04-runner/README.md`). Read-only everywhere else. Do NOT touch frozen
files, `03-skill/`, `05-runs/` contents, SPEC, PLAN, logs. Python 3 stdlib only; `python3`.

## Deliverable — `04-runner/evidence.py`

Builds the per-iteration evidence pack the patcher sees. Registered pack definition
(pre-registered before the loop starts; the manual baseline at P4 sees the same format):

- CLI: `python3 evidence.py --batch-dir 05-runs/<id> --gold-root 01-fixtures/gold --out
  <path.md>`.
- HARD GUARD: refuse (exit 2) if the batch's docs dir or any manifest doc path contains
  `holdout` — evidence packs are training-set only, ever.
- Reuse score.py's completeness + fixture-identity assertions (import; refuse if they fail).
- Pack content (markdown, deterministic ordering):
  1. Header: batch id, skill path + sha256 (from manifest), pooled score, per-rep scores,
     counters (unparseable, wrong_shape, missing, hallucinated_absent, missed_present,
     fence_stripped, turn_check_retries).
  2. Per-field accuracy table (all 12 fields, correct/total over all runs in the batch).
  3. For every WRONG (doc, field, rep) instance, grouped by field: doc id, rep, the worker's
     answer verbatim (from the stripped prediction; `MISSING KEY` / `null` shown as such),
     and the training gold value.
  4. Exemplar documents: for each field with ≥1 wrong instance, include the FULL TEXT of up
     to 2 training documents where it was wrong (fewest-correct docs first; deterministic
     tie-break by doc id; each document's text included at most once per pack, with a list
     of which wrong fields it exemplifies).
  5. Footer note, verbatim: "This pack contains training-set data only. Holdout documents
     and holdout gold exist but are never shown to you."
- The pack must NEVER include: holdout anything, generator source, other skill versions,
  scores of other candidates, or gold values for fields the worker got RIGHT.

## Tests — `04-runner/test_evidence.py` (unittest, mock batches on tmp dirs)

≥8 tests: holdout refusal; completeness/identity refusal passthrough; wrong-instance
listing correctness (missing key vs null vs wrong value rendering); right-answer gold never
leaks into the pack; exemplar selection determinism and the ≤2-per-field cap; single
inclusion of a doc used by multiple fields; footer present.

## Acceptance (run yourself; report actual output)

1. `python3 04-runner/test_evidence.py` → all pass (report count).
2. Live run against `05-runs/g1-cal-5` → pack generated; quote its header + per-field table
   + the first wrong-instance group verbatim in your final message.
3. Confirm byte-determinism: two consecutive runs on g1-cal-5 produce identical files.

Final message: files created, test count, acceptance outputs, any ambiguity flagged rather
than silently chosen.
