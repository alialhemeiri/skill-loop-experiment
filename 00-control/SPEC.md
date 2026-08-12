# SPEC — Autoresearch Skill Loop (Article 2 experiment)

**Status:** FROZEN at G0, 2026-08-11 (Ali greenlight in session). Post-G1 changes only via the
amendment rule (§9).

**Purpose:** Satisfy the publication gate of article 2 in
`research/topics/agentic-workflows-and-infrastructure/findings.md` ("Autoresearch beyond LLM
training: build systems that improve against a score"): a repeatable experiment with a frozen
metric, logged attempts, reversions, and a held-out result, compared against manual and blind
baselines.

## 1. Editorial framing (founder directive, 2026-08-11)

Primary audience: agentic-AI builders. The article's protagonist is the transferable controller
pattern — bounded mutation, fixed budget, frozen evaluator, keep-or-revert — applied beyond LLM
training. The extraction task is the demonstration vehicle. Secondary audience: document-heavy
operators (real-estate flavored specimen chosen for them). The build MUST produce: score
trajectory with kept/reverted markers, the skill file's diff evolution, the raw experiment log,
and a reusable statement of the pattern.

## 2. Pre-registered commitments

- **Publish-regardless rule (Ali, 2026-08-11):** results publish as they land — win, tie, or
  null. No spinning, no shelving. Ali still approves the final article (G3/G4).
- **H1 (directional):** the loop's final skill beats v0 on the held-out set by more than the
  noise threshold.
- **H2, H3 (no prediction):** loop vs. best-of-12 blind rewrites; loop vs. manual edit. Reported
  either way.
- Secondary metrics reported: hallucinated-field rate, skill length growth, iterations to
  plateau, revert count.

## 3. The specimen

One skill file, `03-skill/versions/vN/SKILL.md`, teaching an agent to extract structured fields
from synthetic UAE residential tenancy contracts. Hard cap: **150 lines / 10 KB**. The loop may
change nothing else.

**v0 non-sandbagging rule:** v0 must be a reasonable first attempt a practitioner would write in
ten minutes — plain instructions, no deliberate flaws. A sandbagged baseline fakes improvement.

## 4. Fixtures (frozen before any loop run)

16 synthetic contracts: **10 training / 6 held-out**, generated from gold records by a seeded,
stdlib-only Python generator (`01-fixtures/generator/generate.py`, default seed `20260811`,
byte-reproducible). Documents are plain text (`.txt`). All entities invented. The article
discloses synthetic data as a methods fact.

**Extraction schema (12 fields):**

| # | Field | Type |
|---|---|---|
| 1 | `landlord_name` | string |
| 2 | `tenant_name` | string |
| 3 | `unit_number` | string |
| 4 | `community` | string |
| 5 | `contract_start_date` | ISO date `YYYY-MM-DD` |
| 6 | `contract_end_date` | ISO date |
| 7 | `annual_rent_aed` | integer |
| 8 | `security_deposit_aed` | integer \| null |
| 9 | `number_of_payments` | integer |
| 10 | `notice_period_days` | integer \| null |
| 11 | `early_termination_penalty_months` | number \| null |
| 12 | `furnished_status` | `furnished` \| `semi-furnished` \| `unfurnished` \| null |

Fields 8, 10, 11, 12 are nullable; each document omits 1–3 of them (absent from the text
entirely). Every present field has exactly one consistent value in the text — **no contradiction
traps** in v1.

**Messiness menu (seeded per document):** mixed date formats (DD/MM/YYYY, "1 September 2026",
ISO); AED formats ("AED 85,000", "85000 AED", "Dhs. 85,000/-", words + digits, always
consistent); payment phrasings ("four (4) post-dated cheques", "quarterly instalments" → 4);
distractor clauses (agent commission, DEWA/chiller, Ejari line, maintenance, arbitration); layout
variance (numbered clauses / prose / text tables); name variance (caps, honorifics, "(the
Landlord)" suffixes); light bilingual labels (Arabic beside English); sparse seeded typos.

## 5. Grading (frozen before any loop run)

`02-evaluator/grader.py`, plain Python, no AI, no network. Per field: exact match after
normalization — strings casefolded, whitespace collapsed, honorifics and role suffixes stripped;
dates must be exact ISO; numbers must be numeric types. Missing key or wrong type = incorrect.
Whole output unparseable as JSON = 0 for that run, tracked separately. **Hallucinated-absent**
(non-null value for a field the document omits) = incorrect AND separately counted.

**Score of a candidate = mean field accuracy over 10 training docs × 2 reps** (20 runs).
Raw worker outputs are stored for every run, so any grader fix can re-score history.

## 6. Roles and engines (subscription CLIs only — no pay-per-token APIs)

- **Worker** (runs the skill; the controlled variable is the skill file only): Sonnet via
  `claude -p`, exact model string pinned at G1 after a headroom check; identical invocation every
  run; sees ONLY skill + document + fixed schema instruction. Never sees gold, other docs, or
  scores. Batches run overnight to avoid colliding with Ali's usage.
- **Patcher** (proposes changes): GPT 5.6 Sol via codex CLI, pinned; sees current skill + a
  training-set evidence pack (per-field scores + the worker's wrong outputs). Never sees held-out
  docs or any gold values beyond the training evidence pack. One bounded diff per iteration.
- **Blind rewriters** (baseline): same engine as patcher; see v0 + schema + a generic task
  description. NO failure data.
- **Build engines:** GPT 5.6 Sol builds tooling; Opus cross-reviews; Fable orchestrates thin
  (per Ali's standing directive).

## 7. Protocol

1. **Noise floor:** evaluate v0 four times (4 × 20 runs). The keep/revert threshold is set from
   observed variance (guidance: max(1 SD, 1.5 percentage points)) and **frozen at G1**.
2. **Loop:** up to **12 iterations**. Each: evidence pack → patcher proposes one diff → evaluate
   → keep iff Δ > threshold, else revert. Early stop after **4 consecutive reverts**. Every
   iteration appended to `06-log/experiment-log.md`: diff, score, decision.
3. **Manual baseline:** Ali edits v0 once (≤30 min), seeing only the iteration-1 evidence pack —
   never the loop's patches. Evaluated like any candidate.
4. **Best-of-12:** twelve independent blind rewrites, each evaluated on training; best one
   advances.
5. **Held-out, once:** the four finalists (v0, loop-final, manual, best-of-12) run the 6
   held-out docs × 2 reps each. No retries, no re-rolls. Results lock = **G2**.

Run budget ≈ 630 worker executions total (~80 noise floor, ~240 loop, ~240 blind, ~20 manual,
~48 held-out). Each run is small (one document in, one JSON out).

## 8. Freeze mechanics

At G1, `00-control/FREEZE.md` records SHA-256 hashes of: generator, all 16 documents, all gold
records, grader, runner, v0 skill, and the pinned worker invocation. Anyone can verify the test
never moved mid-experiment.

## 9. Amendment rule

Post-G1 changes to any frozen file require a logged amendment in `06-log/experiment-log.md`
stating what changed and why. A grader fix re-scores all stored raw outputs. A fixture or
protocol change voids affected results, which are rerun or reported as voided — never silently
replaced.

## 10. Gates

| Gate | Meaning | Owner |
|---|---|---|
| G0 | Scope, specimen, rules frozen (this document) | Ali — DONE 2026-08-11 |
| G1 | Fixtures + grader + runner + v0 built, Opus cross-review passed, Ali skims schema + one document, FREEZE.md written, threshold set | Ali (light) |
| G2 | All runs complete, held-out evaluated once, `07-analysis/RESULTS.md` locked | Orchestrator (mechanical) |
| G3 | Article draft + claim-source map approved | Ali |
| G4 | Publication (site PR + LinkedIn) | Ali, explicit |

## 11. Out of scope (v1)

OCR / PDF input, live-web anything, multiple document types, contradiction traps, n8n execution,
cross-model skill transfer (noted as a possible follow-up), any client data.

---

## Amendments (append-only; original sections above are never edited)

### A1 — 2026-08-11, pre-G1 (decided by Ali at the G1 review gate)

Trigger: Opus cross-review verdict DO NOT FREEZE (`00-control/reviews/G1-opus-review.md`) —
measured zero headroom (v0 = 120/120 on train) and an 83% markdown-fence rate that made the
as-graded metric measure fencing, not extraction. Nothing was frozen and no experiment runs
were consumed before this amendment.

1. **§4 fixtures (difficulty raised, D6):** documents are regenerated. In addition to the
   registered messiness menu: a seeded majority of key values are rendered inside prose
   clauses rather than labeled key-terms lines; label-adjacent decoys are added (agent /
   property-manager names near landlord context, chiller-guarantee / agent-commission amounts
   near deposit and rent context, building vs community adjacency, handover / Ejari dates near
   the start date) — decoys are always attributed to their true (non-gold) subject, so the
   no-contradiction rule stands; each document contains at least one field whose value
   requires unambiguous derivation rather than copy (e.g. end date from "a term of twelve
   months commencing <date>", payment count from enumerated cheques). "Every present field
   appears exactly once as one consistent value" is amended to: exactly one consistent
   rendering OR one unambiguous derivation; never two conflicting statements. Per-field null
   rates must match between train and holdout within 10 percentage points (registered in
   FREEZE.md). Difficulty calibration before freeze targets a v0 training score in
   [0.55, 0.90]; calibration may adjust generic rendering difficulty only — never content
   targeted at specific observed v0 error patterns (anti-anti-sandbagging rule).
2. **§5 fence handling (D5):** the runner applies one registered mechanical normalization to
   the worker's result text before writing the prediction file: trim outer whitespace; if the
   first line matches `^```[A-Za-z0-9]*$` and the last line is ```` ``` ````, remove exactly
   those two lines and re-trim. One pair maximum. The raw stored output keeps the original
   bytes; the manifest records `fence_stripped` per run. Output that is still not valid JSON
   scores 0 (model failure). The grader itself remains strict and unchanged in its parsing.
   The frozen worker system prompt gains one line: "Never wrap output in markdown code
   fences."
3. **§6/§7 transport vs model failures (D7):** worker.json's transport-retry rule (max 2
   logged retries on nonzero exit / empty stdout / invalid CLI envelope) applies to ALL runs
   including held-out. SPEC §7.5's "no retries, no re-rolls" governs delivered model outputs,
   which are never retried anywhere. A worker run with `num_turns != 1` or non-empty
   `permission_denials` is classified as a transport failure (retry-eligible, logged).
4. **§7.5 holdout single-shot:** enforced by an append-only ledger
   (`00-control/holdout-usage.log`) written by the runner; a holdout batch is refused if the
   ledger already records a different batch. Resuming the same batch-id remains allowed.
5. **§7.1 threshold for H1:** the frozen keep/revert threshold is calibrated on the training
   noise floor; the H1 held-out comparison uses that threshold scaled by √(10/6) ≈ 1.29 to
   match the smaller sample's standard error.
6. **§5 scoring implementation:** the candidate score is computed by a frozen
   `02-evaluator/score.py` (asserts batch completeness from the manifest — all runs terminal,
   zero transport failures — before scoring; reports per-rep and pooled means). The grader
   report gains three counters: `missing` (prediction file absent — infrastructure, distinct
   from unparseable), `wrong_shape` (valid JSON, non-object), `missed_present` (gold non-null,
   predicted null or key absent). `furnished_status` receives the same whitespace
   normalization as other strings before its enum comparison.
7. **§8 freeze list extended:** FREEZE.md additionally hashes `02-evaluator/score.py`,
   `00-control/worker-system-prompt.txt`, and `00-control/worker.json`, and records the
   resolved per-run model identifier limitation (alias pin) plus the train/holdout null-rate
   table.

### A2 — 2026-08-11, pre-G1 (erratum to A1.4 + registrations; trigger: focused re-review,
`00-control/reviews/G1-opus-rereview.md`)

1. **A1.4 erratum (re-review BLOCKER A):** the holdout ledger is keyed per candidate skill,
   not per single batch. The runner refuses a holdout batch whose `skill_sha256` already
   appears in the ledger (resuming the same batch-id remains allowed), permits distinct
   finalist skills, and refuses a fifth distinct skill (§7.5 registers exactly four
   finalists). Each finalist's single shot is per-skill, exactly as §7.5 intends.
2. **Terminal holdout transport failure (re-review MINOR G):** if a holdout run remains a
   transport failure after the full retry budget, one logged §9 amendment may authorize
   re-running that candidate's holdout batch. Model outputs are still never re-rolled.
3. **score.py fixture-identity assertion (re-review MAJOR B):** before scoring, score.py
   verifies each document hash recorded in the batch manifest against the file on disk and
   refuses to score on mismatch.
4. **Run-dir fixture snapshots (re-review MAJOR E):** every future batch directory stores a
   copy of the exact documents (and their gold records) it ran against.
5. **Turn-check forensics (re-review MAJOR D):** worker envelopes rejected by the
   single-turn check are persisted (`raw/<id>-attempt<N>.rejected.json`); score.py reports a
   `turn_check_retries` count. If the CLI supports disallowing tools, the pinned invocation
   disallows them (belt to the empty-cwd + turn-check braces).
6. **Pre-holdout drift canary (re-review, prior finding 4):** immediately before the P4
   holdout batches, v0 is re-run on the training set (1 rep) and compared against the noise
   floor band as a model-drift check; the alias-pin limitation is restated in RESULTS.md.

### A3 — 2026-08-11, pre-G2 (manual baseline waived)

§7.3's manual baseline is WAIVED. Sequence, logged in full in `06-log/experiment-log.md`:
the orchestrator's status reporting had already contaminated Ali's independence (registered
confound, same day); Ali then twice declined to perform the 30-minute edit and asked the
orchestrator to author it for him (including in draft-then-human-tweak form); the
orchestrator refused both forms — a model-authored edit, especially by the orchestrator that
has read the loop's kept patch, cannot be labeled a human baseline. Consequences: H3
(loop vs manual) is reported as NOT RUN in RESULTS.md and the article; the held-out
evaluation runs with three finalists (v0, loop-final v1, best-of-12 winner); the holdout
ledger's four-skill cap is unaffected. Reversible until the holdout batches start: an
actual human edit (Ali, or Khalifa with only the iteration-1 pack) may reinstate the
fourth finalist under the already-registered contamination caveat.
