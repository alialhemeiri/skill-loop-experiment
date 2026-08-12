# G1R2 contract — surgical pre-freeze fixes from the focused re-review (engine: GPT 5.6 Sol)

Read, in order: `projects/autoresearch-skill-loop/00-control/SPEC.md` Amendments **A2** (your
requirements list), `00-control/reviews/G1-opus-rereview.md` (findings BLOCKER A, MAJOR B,
MAJOR D, MAJOR E, MINOR L — the ones you are fixing), then the current
`04-runner/run.py` + `04-runner/test_run.py`, `02-evaluator/score.py` +
`02-evaluator/tests/test_score.py`, `01-fixtures/generator/generate.py`.

**Scope:** ONLY `01-fixtures/`, `02-evaluator/`, `04-runner/`, and `05-runs/g1-cal-5*`. Do
NOT touch: SPEC.md, PLAN.md, `00-control/` (worker.json was already updated by the
orchestrator — the runner picks the new `--disallowedTools` args up from `args_template`
automatically), `03-skill/`, `05-runs/` existing batches, `06-log/`. Python 3 stdlib only;
`python3` (no `python` on this box). The claude CLI is available and networked.

## Fix 1 — holdout ledger re-key (A2.1; re-review BLOCKER A)

`04-runner/run.py`: the ledger guard must be per candidate skill, not per single batch:
- REFUSE a holdout batch whose `skill_sha256` already appears in the ledger under a
  different batch-id (that skill's shot is spent).
- ALLOW resuming the same batch-id with the same skill (no duplicate ledger line).
- ALLOW a new batch-id with a skill_sha256 not in the ledger.
- REFUSE a fifth distinct skill_sha256 (SPEC §7.5 registers exactly four finalists).
- Ledger line format may gain fields but stays append-only, one line per consumed shot.
Flip `test_holdout_ledger_allows_same_batch_resume_and_refuses_different_batch` and add
tests for all four behaviours above.

## Fix 2 — score.py fixture-identity assertion (A2.3; re-review MAJOR B)

In `assert_complete_batch` (or equivalent): for every manifest `documents[doc_id]`, hash the
file at its recorded path and REFUSE to score (exit 2, clear message naming the mismatched
docs) if any SHA-256 differs. Test: doctor a temp copy of a batch manifest to a wrong hash →
refusal; untouched batch → scores. Demonstrate on `05-runs/g1-cal-1` (must now REFUSE — its
corpus was regenerated away) and `05-runs/g1-cal-4` (must still score 0.900).

## Fix 3 — turn-check forensics (A2.5; re-review MAJOR D)

`04-runner/run.py`: when the single-turn check rejects a successful CLI envelope
(`num_turns != 1` or non-empty `permission_denials`), persist that envelope byte-exact as
`raw/<doc-id>-rep<k>-attempt<N>.rejected.json` before retrying. `02-evaluator/score.py`:
report `turn_check_retries` (count of retry-log entries whose reason is the turn check) in
the output JSON. Tests for both.

## Fix 4 — run-dir fixture snapshots (A2.4; re-review MAJOR E)

`04-runner/run.py`: at batch start (new manifest only), copy the exact selected documents to
`05-runs/<batch-id>/fixtures/docs/` and their gold records to
`05-runs/<batch-id>/fixtures/gold/`. On resume, verify the snapshot still hash-matches the
manifest (refuse otherwise). NOTE: this is the runner reading gold files for archival — the
WORKER prompt construction must remain untouched by this change (gold must never enter the
prompt path; keep the copy step clearly separate). Tests: snapshot created; resume with
doctored snapshot refused.

## Fix 5 — cheque-clause grammar (re-review MINOR L)

`01-fixtures/generator/generate.py`: fix the singular case — "One post-dated cheque,
each separately identified …, constitute …" must become grammatical (e.g. "One post-dated
cheque, separately identified in the delivery record, constitutes the complete set of rent
instruments."). Plural phrasing stays. Regenerate all fixtures; run `--check`.

## Acceptance (run everything yourself; report actual output)

1. `python3 01-fixtures/generator/generate.py --check` → exit 0.
2. `python3 -m pytest 02-evaluator/tests/ -q` and `python3 04-runner/test_run.py` → all pass
   (report counts).
3. score.py on `g1-cal-1` → REFUSES (fixture mismatch); on `g1-cal-4` → 0.900 as before...
   CAREFUL: if Fix 5's regeneration changed any of the 10 training documents' bytes, then
   g1-cal-4 must now also REFUSE (that is correct behaviour — say so and skip step 4's
   comparison), and the fresh band check in step 4 is the binding evidence.
4. Fresh calibration batch `g1-cal-5`: v0 (`03-skill/versions/v0/SKILL.md`, read-only) × 10
   train docs × 1 rep via the CURRENT runner + worker.json (now includes --disallowedTools).
   Score with score.py (fixture-identity assertion passing). Required: pooled mean in
   [0.55, 0.90]; `unparseable + wrong_shape + missing = 0`; snapshot dir present; quote the
   score.py JSON summary.
5. Confirm `05-runs/g1-cal-5/manifest.json` records the new worker.json hash and that every
   run shows `num_turns` handling per A2.5 (any rejected envelopes persisted).

Final message: files changed, test counts, acceptance outputs verbatim (score.py summaries,
refusal messages), the g1-cal-5 per-field table, and any deviation or ambiguity flagged
rather than silently chosen.
