# Batch runner

`run.py` executes one skill version against fixture documents through the invocation pinned in
`00-control/worker.json`. It uses Python 3's standard library and runs workers sequentially.

Run it from the project root:

```bash
python3 04-runner/run.py \
  --skill 03-skill/versions/v0/SKILL.md \
  --docs-dir 01-fixtures/docs/train \
  --reps 2 \
  --batch-id v0-train
```

All relative paths are resolved from `projects/autoresearch-skill-loop/`, regardless of the shell's
current directory. Optional flags:

- `--doc-filter doc-01,doc-02` selects document IDs without the `.txt` suffix.
- `--sleep-between SECONDS` controls the delay between worker invocations; the default is 2 seconds.
- `--allow-holdout` bypasses the held-out-data guard. Do not use it before the single P4 held-out run.

The runtime output of `claude --version` must exactly match the CLI version pinned in
`worker.json`; a mismatch stops before any document is sent.

Any docs-directory path containing `holdout` is refused unless `--allow-holdout` is explicit. The
runner reads the worker system prompt at runtime, substitutes the one literal placeholder in
`args_template`, sends the combined skill/document/schema prompt through stdin, and launches Claude
from `/tmp/autoresearch-worker-cwd`. That neutral directory must be empty; the runner creates it when
missing and refuses a non-empty directory instead of deleting unknown files.

For an allowed holdout directory, the ordinary two-retry transport budget still applies; delivered
model outputs are never retried. Before a holdout batch starts, the runner consults the append-only
`00-control/holdout-usage.log`. It permits an idempotent resume of the recorded batch ID and refuses
any different holdout batch ID. An exclusive ledger lock is held for the complete holdout
invocation. A same-ID resume must retain its matching manifest and must match the skill hash and
document IDs already claimed in the ledger; loss of that manifest fails closed instead of granting
a re-roll.

## Output layout

For batch `v0-train`, outputs are stored as:

```text
05-runs/v0-train/
├── manifest.json
├── raw/
│   ├── doc-01-rep1.result.json
│   └── doc-01-rep1.raw.txt
└── preds/
    └── rep1/
        └── doc-01.json
```

`result.json` preserves the complete Claude CLI stdout bytes, and `raw.txt` preserves the original
extracted `.result` bytes. For `preds/` only, the runner trims outer whitespace and removes at most
one registered outer markdown-fence pair. The manifest records `fence_stripped`, the envelope's
`modelUsage` key list, optional canonical-model/provider fields, runtime CLI version, pinned model,
skill, worker, runner, fixed-schema, system-prompt and document hashes, attempt logs, statuses, and
wall-clock totals.

The presence of `raw/<doc-id>-rep<k>.raw.txt` is the completion sentinel. Re-running the same batch
skips that worker call, verifies it against the stored CLI result, and repairs a missing or mismatched
normalized prediction from the raw bytes. If the CLI result was persisted immediately before an interruption,
the runner can reconstruct the missing raw and prediction files without another model call. It fails
closed when terminal model-result artifacts are missing or inconsistent, so a resume cannot silently
re-roll a completed or model-failure output.

An existing batch refuses a changed runner, fixed schema, skill, worker, system prompt, model, CLI
version, selected document bytes, selection, or repetition count so results cannot be mixed
accidentally. Transport-attempt budgets are cumulative across resumes; re-invocation does not grant a
failed run a fresh retry budget.

The runner also refuses a non-empty batch directory with no manifest, or output artifacts that have
no matching run record in an existing manifest. These states have no trustworthy input provenance and
are never adopted as results.

## Retry and exit behavior

A run gets at most two retries (three attempts total), and only when the Claude process exits nonzero,
returns empty stdout, or returns stdout that cannot be parsed as the Claude CLI result JSON. Each
attempt and retry decision is written to the manifest. A nominally successful envelope with
`num_turns != 1` or non-empty `permission_denials` is also a retry-eligible transport failure. A
delivered `.result` that remains invalid JSON after the registered fence normalization is a model
failure: it is stored, never retried, and remains available for the grader to score as zero.

The runner continues sequentially after a terminal transport failure, prints the batch summary, and
exits 1 if any run has terminal transport failure. Setup or CLI-argument errors exit 2. Completed
batches, including model failures, exit 0.

Run the stdlib integration tests and inspect the CLI without starting workers:

```bash
python3 -m unittest -v 04-runner/test_run.py
python3 04-runner/run.py --help
```

## Training evidence packs

Build the deterministic evidence pack shown to the patcher from a complete training batch:

```bash
python3 04-runner/evidence.py \
  --batch-dir 05-runs/<id> \
  --gold-root 01-fixtures/gold \
  --out /path/to/evidence.md
```

The builder imports the frozen scorer and grader, refuses incomplete or fixture-mismatched batches,
and exits 2 before writing output if the manifest's docs directory or any document path contains
`holdout`. Its pack contains the current skill identity and scores, wrong training instances, and
at most two ranked exemplar documents per wrong field. Run its stdlib tests with
`python3 04-runner/test_evidence.py`.

## Freeze warning

At G1, the runner, v0 skill, fixtures, grader, and pinned worker invocation are hash-frozen. Do not
edit a frozen file or invocation mid-experiment. Any post-G1 change must follow the amendment and
re-run rules in `00-control/SPEC.md`.
