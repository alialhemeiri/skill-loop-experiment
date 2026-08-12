# P6 contract — assemble the public experiment repo (D8)

> Worker: GPT 5.6 Sol via codex. Written by the orchestrator 2026-08-12. D8 (Ali,
> 2026-08-12): the public artifact is the full experiment as a GitHub repo — assembled and
> secrets/PII-scanned during P6, pushed PRIVATE, flipped public only at G4 with the
> article link. This contract covers ASSEMBLY ONLY: the orchestrator verifies fidelity,
> runs the scan, and performs all git/gh operations afterwards.

## Target

Create `09-public-repo/` at the experiment project root
as the working tree of the future public repo (default name
`autoresearch-skill-loop`, default owner `aperion-ae` — Ali confirms both at G3).

## Copy (byte-preserving)

Copy these directories VERBATIM from the project root into `09-public-repo/`, preserving
relative structure and file bytes exactly:

`00-control/` `01-fixtures/` `02-evaluator/` `03-skill/` `04-runner/` `05-runs/`
`06-log/` `07-analysis/`

Exclusions:

- Do NOT copy: `08-article/` (editorial workspace), `PLAN.md`, `GOAL.md`,
  `GOAL-P6P7.md` (workspace-internal), `09-public-repo/` itself.
- Omit from the copy any `__pycache__/`, `.pytest_cache/`, `.ruff_cache/` directories
  (build junk, not evidence). Omit nothing else — `.log` files (e.g.
  `00-control/holdout-usage.log`) are evidence and MUST be included.
- Modify NOTHING in the sources. The experiment tree is read-only. Every copied file must
  be byte-identical to its source (the orchestrator will `diff -r` afterwards).

## Write exactly two new files inside `09-public-repo/`

### 1. `README.md`

Audience: a skeptical engineer landing from the article. Sections:

1. **What this is** — a pre-registered skill-improvement experiment: Karpathy's
   autoresearch controller pattern (bounded mutation, fixed budget, frozen evaluator,
   keep-or-revert) transferred from LLM training to an agent skill file, run 2026-08-11/12.
   Companion article (live at publication):
   `https://aperion.ae/articles/autoresearch-beyond-llm-training`. State synthetic data
   as a fact: all 16 tenancy contracts are generated, every entity invented.
2. **Headline result** — small table from RESULTS.md §1 (v0 0.902778 · v1 1.000000 ·
   bo12-04 0.875000 on the held-out set; H1 supported +9.72pp vs 1.94pp threshold; H2
   +12.5pp over the best blind rewrite; H3 not run per amendment A3). One sentence per
   hypothesis, no more.
3. **Repo map** — one line per top-level dir (00-control = protocol/freeze/reviews/
   ledger; 01-fixtures = generator + corpus + gold; 02-evaluator = grader + scorer;
   03-skill = every skill version v0–v5 + bo12 attempts; 04-runner = pinned worker
   invocation, evidence-pack builder, tests; 05-runs = every raw worker output +
   manifests, preserved byte-exact; 06-log = the chronological experiment log;
   07-analysis = locked RESULTS.md + trajectory + diff evolution + gaming audit).
4. **Verify the freeze** — exact commands: re-hash the frozen files against
   `00-control/FREEZE.md` §1 (`sha256sum` per file), and
   `python3 01-fixtures/generator/generate.py --check` for the byte-reproducible corpus
   aggregates. Note that batch manifests in `05-runs/` bind skill/doc/runner hashes per
   batch.
5. **Rerun it** — honest caveats first: results were produced on a pinned alias model
   (`claude-sonnet-5`, claude CLI 2.1.227 — an alias pin, no dated snapshot; see
   FREEZE.md §5) via subscription CLIs, so a rerun is a new experiment, not a replay.
   Then the mechanics: worker invocation per `00-control/worker.json` +
   `worker-system-prompt.txt`, runner per `04-runner/README.md`, scoring per
   `02-evaluator/`. Point at SPEC.md for the full protocol and amendment trail.
6. **Registered caveats** — bullet the RESULTS.md §6 / FREEZE.md registered limitations
   factually (alias pin; headroom concentrated in two derivation rules; decoys
   contribute zero measured difficulty; deposit is a constant ratio corpus-wide —
   observationally equivalent strategies, see `07-analysis/evaluator-missed-audit.md`;
   synthetic data; H3 waived + contamination confound per SPEC A3). Do not soften.
7. **Attribution** — per `08-article/attribution-notes.md` (read it; do not copy it in):
   the controller pattern is Karpathy's
   (`https://github.com/karpathy/autoresearch`, plus the Verifiability post
   `https://karpathy.bearblog.dev/verifiability/`); the evidentiary layer (noise floor +
   threshold, held-out single shot, baselines, pre-registration, hash freeze,
   cross-review) is this experiment's addition and must not be attributed to the repo.

Numeric authority: `07-analysis/RESULTS.md`, `00-control/FREEZE.md`,
`06-log/experiment-log.md` ONLY. Invent nothing; no numbers from memory. No hype: the
README never says "self-improving" without the experiment's own qualifiers.

### 2. `.gitignore`

Exactly this content (log files stay tracked — the holdout ledger is evidence):

```
__pycache__/
*.py[cod]
.pytest_cache/
.DS_Store
Thumbs.db
```

## Hard boundaries

- NO git operations (no init, no commit) — the orchestrator does those after verification.
- Write only inside `09-public-repo/`; read-only everywhere else; do not touch
  `08-article/` at all (another worker is writing there right now).
- No LICENSE file (founder decision pending at G3).
- Final message: report file/dir counts copied, the two files written, and any source
  file you could not copy (say NONE if none).
