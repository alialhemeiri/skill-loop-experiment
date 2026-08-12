# P2 contract — runner + v0 skill

> Finalized 2026-08-11 after P1 review. Environment note: this box has `python3` only — there
> is no `python` command.

You are building the run harness and the starting skill for a pre-registered skill-improvement
experiment. Read `projects/autoresearch-skill-loop/00-control/SPEC.md` first — it is the
authority. This contract adds implementation detail. Work ONLY inside
`projects/autoresearch-skill-loop/03-skill/`, `04-runner/`, and `05-runs/`.
`01-fixtures/` and `02-evaluator/` are READ-ONLY. Do not edit SPEC.md, PLAN.md, worker.json,
or worker-system-prompt.txt. Python 3 stdlib only. No new dependencies.

## Deliverable 1 — `04-runner/run.py`

Batch runner that executes one skill version against fixture documents via the pinned worker
(`claude -p`), per `00-control/worker.json` (read it; it is the single source of truth for the
invocation).

- CLI: `python3 run.py --skill PATH --docs-dir DIR --reps N --batch-id NAME
  [--doc-filter doc-01,doc-02] [--sleep-between SECONDS(default 2)] [--allow-holdout]`.
  Paths resolve relative to the project root (`projects/autoresearch-skill-loop/`).
- REFUSE to run on any docs-dir containing `holdout` unless `--allow-holdout` is passed
  (protocol guard — held-out docs are touched exactly once, at P4).
- Worker invocation, exactly per worker.json: prompt via **stdin**; args from `args_template`,
  replacing the single element whose value is the literal placeholder string
  `<contents of system_prompt_file>` with the contents of `00-control/worker-system-prompt.txt`
  (read at runtime); subprocess cwd = `/tmp/autoresearch-worker-cwd` (create empty if missing).
  Never pass gold data, scores, or other documents to the worker.
- Prompt layout (exact, frozen):
  `<skill file contents>` + `\n\n---\n\nDOCUMENT:\n\n` + `<document text>` + `\n\n---\n\n` +
  the FIXED SCHEMA INSTRUCTION below, verbatim, as a module-level constant in run.py:

  > Extract the following 12 fields from the document above and output ONLY a single JSON
  > object — no markdown fences, no commentary. Keys and types: landlord_name (string),
  > tenant_name (string), unit_number (string), community (string), contract_start_date
  > (string, YYYY-MM-DD), contract_end_date (string, YYYY-MM-DD), annual_rent_aed (integer),
  > security_deposit_aed (integer or null), number_of_payments (integer), notice_period_days
  > (integer or null), early_termination_penalty_months (number or null), furnished_status
  > (one of "furnished", "semi-furnished", "unfurnished", or null). Use null for any field the
  > document does not state.

- Storage per run under `05-runs/<batch-id>/`:
  - `raw/<doc-id>-rep<k>.result.json` — the full claude CLI result JSON (forensics: num_turns,
    usage, model).
  - `raw/<doc-id>-rep<k>.raw.txt` — the extracted `.result` string, byte-exact.
  - `preds/rep<k>/<doc-id>.json` — same bytes as the raw text, named to pair 1:1 with
    `01-fixtures/gold/<doc-id>.json` so the grader's batch mode consumes it directly.
  - `manifest.json` — model + CLI version (from `claude --version` at runtime), skill path +
    its SHA-256, worker.json SHA-256, per-run status/timestamps/retry log, wall-clock totals.
- Resumable: if a run's `raw.txt` exists, skip it (idempotent re-invocation; overnight-safe).
- Transport retry rule (verbatim from worker.json): retry max 2, logged, ONLY on nonzero CLI
  exit, empty stdout, or stdout unparseable as CLI result JSON. A successful CLI result whose
  `.result` is not valid JSON is a MODEL failure — never retried (grader scores it 0).
- Sequential execution only (no parallel workers). Exit nonzero + print a summary if any run
  ends in terminal transport failure.

## Deliverable 2 — `03-skill/versions/v0/SKILL.md`

The starting skill. **Inputs you may read: SPEC §3–§4 (schema table) and ONE sample document,
`01-fixtures/docs/train/doc-01.txt`. You must NOT read the generator source, anything in
`01-fixtures/gold/`, any other document, or the grader** — v0 must reflect what a practitioner
with the schema and one sample would write in ten minutes (SPEC §3 non-sandbagging rule: no
deliberate flaws, and no fixture reverse-engineering either).

- ≤150 lines and ≤10 KB. Plain markdown instructions to an extraction agent: how to locate the
  parties/unit/community, convert any date format to ISO, parse AED amounts (digits, separators,
  words+digits), map payment phrasings to an integer count, treat distractor clauses (agent
  commission, DEWA, Ejari, maintenance) with caution, and use null when a field is absent.
  Reasonable first-attempt quality — not exhaustive edge-case armor (that is what the loop is
  for).

## Deliverable 3 — dry run

Execute: `python3 04-runner/run.py --skill 03-skill/versions/v0/SKILL.md --docs-dir
01-fixtures/docs/train --doc-filter doc-01,doc-02 --reps 1 --batch-id p2-dry`. Then grade:
the grader's batch mode grades EVERY gold file in `--gold-dir`, so first copy only
`doc-01.json` and `doc-02.json` from `01-fixtures/gold/` into `05-runs/p2-dry/gold/`, then run
`python3 02-evaluator/grader.py --pred-dir 05-runs/p2-dry/preds/rep1 --gold-dir
05-runs/p2-dry/gold`. If the grader interface cannot consume the runner's output layout
without modifying `02-evaluator/`, STOP and report the mismatch — do not touch the grader.

Environment fallback: if invoking the `claude` CLI fails inside your sandbox (auth-store or
home-directory write restrictions), do NOT work around it — deliver the code + READMEs, run
whatever acceptance you can (e.g. `run.py --help`, a mocked-subprocess self-test if you built
one), and report exactly what failed; the orchestrator will execute the live dry run.

## Deliverable 4 — READMEs

`04-runner/README.md` (how to run, storage layout, retry rule, freeze warning) and
`03-skill/README.md` (version-directory convention: `versions/v0/`, `versions/v1/`, … each a
full SKILL.md copy; the loop never edits in place).

## Acceptance (run these yourself; report actual output)

1. Dry-run batch completes: 4 files under `05-runs/p2-dry/raw/`, 2 under
   `05-runs/p2-dry/preds/rep1/`, manifest present and complete.
2. Grader batch report on the dry-run predictions renders (score value is irrelevant here).
3. Every `result.json` shows `num_turns: 1` and the pinned model string.
4. `wc -l` and `wc -c` of v0 SKILL.md within caps.

Final message: files created, dry-run + grader output (verbatim), deviations with reasons, and
anything in SPEC §3–§6 or worker.json you found ambiguous rather than silently choosing.
