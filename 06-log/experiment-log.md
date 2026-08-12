# Experiment log — chronological record of protocol events

> Iteration entries (P3) will follow the format: iteration #, diff, score, keep/revert.
> Protocol events (reviews, amendments, gate decisions) are logged here too, per SPEC §9.

## 2026-08-11 — G1 Opus cross-review: DO NOT FREEZE (pre-freeze, no amendment needed yet)

Full review: `00-control/reviews/G1-opus-review.md`. 2 BLOCKER / 9 MAJOR / 13 MINOR.

Measured facts that change the plan (both measured by the reviewer through the exact frozen
invocation, training docs only):

1. **Zero headroom** — v0 scores 120/120 fields (mean 1.0) on the full training set once
   fences are stripped: every gold value sits on an English-labeled line. H1 unfalsifiable as
   built.
2. **Fence artifact dominates** — 29/35 live runs (83%) wrap JSON in markdown fences despite
   two explicit instructions; as-graded v0 ≈ 0.17 and per-20-run SD ≈ 8.4pp. The metric as
   frozen would measure fence suppression, not extraction.

Also material: train/holdout null-rate mismatch (45% vs 67%); holdout transport failures
unrecoverable (runner reads SPEC §7 "no retries" as covering transport); holdout single-shot
enforced per batch-id only; alias model pin unverifiable; SPEC §5 score aggregation
unimplemented; missing-file conflated with unparseable.

**Corrections to earlier records (per MAJOR 3):** the P2 session-log claim that runner
hardening explained the fence-free final dry run is WRONG — the clean 2/2 was a ≈3% lucky
draw; the current runner reproduces fences at 83%. n=2 was insufficient acceptance evidence.

**Status:** build paused at the G1 ⏸ gate. Decisions D5 (fence handling), D6 (fixture
difficulty regeneration), D7 (G1 fix bundle) put to Ali with recommendations. Fixtures,
grader, runner remain UNFROZEN — changes before freeze are logged here but need no §9
amendment; any accepted change to SPEC §4's registered fixture description gets an explicit
pre-G1 SPEC amendment note signed by Ali.

## 2026-08-11 — D5–D7 signed by Ali; SPEC amendment A1 appended

Ali accepted all three recommendations at the gate: D5 registered runner fence-strip +
system-prompt line; D6 regenerate fixtures harder with empirical v0 headroom target
[0.55, 0.90]; D7 full fix bundle + focused Opus re-review. SPEC.md gains append-only
"Amendments — A1" (items 1–7). Remediation round launching on GPT 5.6 Sol (contract
`00-control/contracts/G1R-remediation.md`). v0 remains byte-untouched throughout.

## 2026-08-11 — G1R remediation record (written after the fact; flagged by re-review MAJOR E)

Calibration rounds (each 10 train docs × 1 rep, v0 byte-frozen, per codex's report — the
per-round generator states for rounds 1–2 were not snapshotted, a process-audit gap the
re-review could not close; the FINAL generator was independently read in full and certified
corpus-generic, no targeted traps):

- g1-cal-1 — 0.975 — action after: increased generic prose + derivation difficulty
- g1-cal-2 — 0.917 — action after: deposit derivation applied uniformly to hard documents
  (global knob `deposit_is_derived = present and not easy_labeled`; certified non-targeted)
- g1-cal-3 — 0.892 — in band; fixtures thereafter UNCHANGED (cal-3/cal-4 docs hash-identical)
- g1-cal-4 — 0.900 — confirmation re-run after ledger hardening; same corpus, same skill →
  **same-corpus single-rep noise datapoint: 0.83pp (one field)**

**Correction to the G1R checkpoint characterization (PLAN session log, 2026-08-11):** v0's
end-date misses are NOT wrong-convention answers. Stored predictions show v0 emits null
(declines to derive); its only two non-null derived end dates were CORRECT under
day-before-anniversary. Same for deposit misses (nulls, not wrong arithmetic). Headroom =
"will the skill derive at all" (9 end-date + 3 deposit nulls = 12/120 fields).
[SUPERSEDED in part, 2026-08-11 closure check: g1-cal-5 produced the first observed
naive-anniversary error (doc-01: predicted 2027-08-21, gold 2027-08-20). Updated tally over
30 corpus-matched end-date opportunities: 27 null, 2 correct derivations, 1 naive error.
Failure mode = predominantly declines-to-derive, occasionally naive-anniversary.]

## 2026-08-11 — Focused Opus re-review: DO NOT FREEZE (1 new BLOCKER); end-date ruled fair

Full text: `00-control/reviews/G1-opus-rereview.md`. Original blockers resolved on the
merits (fence pipeline dead; corpus difficulty real, null rates 50/50, derivation load
12.5%/12.5% train/holdout). New pre-freeze fixes required: BLOCKER A (holdout ledger permits
only ONE batch ever — must be per-skill so the four §7.5 finalists can run) and MAJOR B
(score.py must assert fixture identity — demonstrated silently re-scoring stale cal-1 at
0.667 vs its 0.975). End-date derivation ruled FAIR AS-IS (register in FREEZE.md, with the
corrected failure-mode statement). SPEC amendment A2 appended (erratum A1.4 + registrations).
G1R2 surgical fix round launching on GPT 5.6 Sol.

## 2026-08-11 — G1R2 verified; Opus closure check: FREEZE-READY

All five G1R2 fixes confirmed closed by the same reviewer thread via direct code exercise
(`00-control/reviews/G1-opus-closure.md`, incl. the consolidated 21-item FREEZE.md
registration list). Binding v0 baseline = g1-cal-5: 0.883333 (106/120; 9 end-date + 5
deposit misses; zero infrastructure failures; fence rate now 18% vs 83% pre-fix, fully
absorbed by the registered strip). Three new registered MINORs: string-coupled turn-check
classifiers; run-dir gold snapshots must be excluded from evidence-pack/patcher context like
`01-fixtures/gold/`; pre-G1R2 batches historical-only. Status: paused at the G1 ⏸ — Ali
skims schema + a regenerated document and sets noise-floor timing; then noise floor →
threshold → FREEZE.md.

## 2026-08-11 — G1 gate passed by Ali; noise floor started; evidence-pack format registered

Ali approved the freeze after his skim and green-lit immediate runs. Noise floor launched
(nf-1..nf-4, v0 × 10 train docs × 2 reps each). Pre-registered before the loop, as a
protocol clarification of SPEC §6's "evidence pack": the pack = batch header + per-field
accuracy table + per wrong instance (worker answer verbatim, training gold value) + up to 2
full exemplar TRAINING documents per wrong field + training-only footer; gold for fields
answered correctly never appears; holdout never appears (hard guard in evidence.py). The
P4 manual baseline sees the identical iteration-1 pack format. Patcher jail: codex runs
with cd into a scratchpad dir containing only the filled prompt (skill + pack embedded);
registered anti-memorization defenses: 150-line/10KB cap, published diff trail, P5 audit,
and train-gold hardcoding being structurally useless on holdout. Template:
`00-control/contracts/P3-patcher-template.md`.

## 2026-08-11 — Infrastructure event during the noise floor: subscription lapse; nf-4 replaced by nf-4b

nf-1/nf-2/nf-3 completed clean (0.9000 / 0.8875 / 0.8958, zero failures of any kind).
During nf-4's final three runs (doc-08/09/10 rep 2) Ali's Claude subscription briefly
lapsed at renewal; every attempt exited rc=1 (error text on stdout, rejected by the runner
as not-a-result-envelope → transport failures, 3 retries each, terminal). Ali renewed;
a worker probe confirms access restored. Handling per the pre-registered transport/model
distinction and the fail-closed design: nf-4 (17 completed runs + 3 terminal transport
failures) is permanently unscoreable and is PRESERVED as-is; a full replacement batch
nf-4b runs in its place. Rationale: this is a training-set measurement (no single-shot
constraint), the noise-floor statistic requires complete 20-run batches, no delivered
model output is deleted (nf-4's 17 raws remain on disk), and the event + replacement are
logged here before the threshold is computed. The noise floor = nf-1, nf-2, nf-3, nf-4b.

## 2026-08-11 — G1 CLOSED. FREEZE.md written; loop begins

Noise floor final: 0.900000 / 0.887500 / 0.895833 / 0.900000 → v0 reference 0.895833,
sample SD 0.005893 → threshold floor applies: **0.015 training keep/revert, 0.019365
holdout (×√(10/6))**. FREEZE.md records the full hash table (generator, 16+16 fixtures via
aggregates, grader, score.py, runner, v0, system prompt, worker.json; evidence.py
informational) and all 21 registrations. Comparison rule registered: keep iff
candidate − current_best_reference > 0.015; kept candidate's reference = its own 20-run
score. P3 iteration 1 starting: pack from nf-4b → patcher (GPT 5.6 Sol, jailed cwd,
read-only sandbox) → v1 → it-1 batch → keep/revert.

### Iteration log

| It | Skill | Score | Δ vs best ref | Decision | Notes |
|---|---|---|---|---|---|
| — | v0 | 0.895833 (nf mean) | — | baseline | reference locked at freeze |
| 1 | v1 | 1.000000 (it-1, 240/240) | +0.104167 | **KEEP** | one bounded change: "explicit deterministic relationships count as stated — compute them" (+ end-date day-before rule, + deposit formula rule). All counters 0. New best ref = 1.000000. |

| 2 | v2 | 1.000000 (it-2) | +0.000000 | REVERT | blind mutation (conflict/amendment rule — corpus has no conflicts by construction); harmless but no gain; consecutive reverts: 1 |
| 3 | v3 | 1.000000 (it-3) | +0.000000 | REVERT | patcher independently re-derived nearly the same conflict-precedence rule (annotated itself "v2" — no memory across iterations); consecutive reverts: 2 |
| 4 | v4 | 1.000000 (it-4) | +0.000000 | REVERT | third independent variant of the same conflict rule — a strong attractor under zero failure signal; consecutive reverts: 3 |
| 5 | v5 | 1.000000 (it-5) | +0.000000 | REVERT | fourth variant of the same rule; **4th consecutive revert → EARLY STOP (SPEC §7.2)** |

## 2026-08-11 — P3 LOOP COMPLETE (early stop at iteration 5)

**Loop-final = v1** (86 lines / 5,888 bytes, sha `d3c67d99…`). Trajectory: one kept
iteration (+10.4pp, the derivation principle) closed the entire training headroom in a
single step; four subsequent no-signal mutations — all four independently converging on
the same conflict-precedence rule the corpus cannot reward — were each correctly reverted
by the controller. Total loop cost: 5 patcher calls + 100 evaluation runs, zero
infrastructure failures, every raw output preserved. Iterations-to-plateau: 1. Next per
plan: P4 — best-of-12 blind rewrites (no failure data), ⏸ Ali's manual edit
(iteration-1 pack only), pre-holdout drift canary, single-shot holdout, RESULTS.md = G2.

## 2026-08-11 — REGISTERED CONFOUND (orchestrator error): manual baseline contaminated

SPEC §7.3 requires Ali's manual edit to see only the iteration-1 evidence pack, never the
loop's patches. The orchestrator's in-chat status reports to Ali during P3 described the
kept patch's substance (derive the end date day-before-anniversary from the stated term;
compute the percentage-defined deposit) before his edit. His baseline is therefore NOT
independent of the loop's solution. Handling: the edit still runs as registered (residual
question: does a briefed human + 30 min also reach the training ceiling?), and H3
(loop vs manual) carries this caveat permanently in RESULTS.md and the article. Lesson
logged for the methods section: in autoresearch with a human baseline, status reporting to
the human IS an information channel — brief them only after their baseline is in.

## 2026-08-11 — Infrastructure event: claude CLI auto-updated mid-pipeline; pin guard fired; downgraded

Between bo12-08 and bo12-09 the claude CLI auto-updated 2.1.227 → 2.1.228. The runner's
runtime version-pin check refused to execute the worker ("runtime CLI version does not
match worker.json") — the freeze doing its job against silent harness drift; no run was
executed on the unpinned binary. bo12-09 and bo12-11 therefore went unevaluated (no
manifests created). Remedy: `claude install 2.1.227` restored the pinned version (verified);
all remaining worker batches run with `DISABLE_AUTOUPDATER=1`; bo12-09 and bo12-11
evaluated fresh after the restore. No amendment needed — the pin was never violated.

**Second occurrence, same day:** the CLI re-updated to 2.1.228 between bo12-09 (completed
clean on 2.1.227, 0.858333) and bo12-11 — the env var did not prevent it; the guard fired
again, bo12-11 unevaluated, pin never violated. Durable remedy: all remaining batches
resolve `claude` through a pin directory symlinked to the standalone versioned binary
`~/.local/share/claude/versions/2.1.227` (PATH-prepended per batch command; worker.json
untouched — it still invokes `claude`, and the runner's version guard independently
verifies 2.1.227 at every batch start, with an added assert after each holdout batch).

**Pre-declared before running (drift canary, SPEC A2.6):** canary = v0 × 10 train docs ×
1 rep on the pinned invocation. PASS band = noise-floor mean ± training threshold =
[0.880833, 0.910833]. On FAIL: stop before any holdout batch, investigate, log.

## 2026-08-12 — Canary FAIL (0.875) → investigation → pre-declared confirmation batch

g2-canary scored 0.875000, 0.58pp below the band floor; the chain stopped before holdout
as declared. Best-of-12 finalized first: winner bo12-04 at 0.875000 (8 qualifiers, range
0.858–0.875, ALL below v0's 0.8958; 4 disqualified on caps; H2 control complete).

Investigation findings:
1. Error profile identical to all prior v0 measurements — misses are 100% nulls on the
   same two fields (end-date 0/10, deposit 5/10), hallucinated_absent 0, no new error
   types. The shortfall is entirely end-date derivation successes going 0/10 where the
   noise floor caught 1–4 per 20 runs (a low-probability Bernoulli; 0 successes in a
   10-run rep is unremarkable).
2. The canary is a single rep: observed single-rep SD ≈ 1.0pp, so the ±1.5pp band trips
   on ~13% of clean draws by design — the tripwire is intentionally oversensitive.
3. Cross-check against drift: bo12-family scores measured before and after the CLI-update
   window are statistically identical (0.858–0.875 both sides) — no harness- or
   model-wide shift visible in same-day data.

**Pre-declared confirmation rule (before running):** g2-canary2 = v0 × 10 train docs ×
2 reps (identical shape to a noise-floor batch, 20 runs). PASS iff pooled score ∈
[0.880833, 0.910833] (same band; for a 20-run batch this is ±2.5 batch-SDs — a strong
test). On PASS: canary trip attributed to single-rep sampling noise, holdout proceeds.
On FAIL: full stop, Ali pause, drift amendment discussion. Both results report in
RESULTS.md either way.

**Confirmation result: PASS — 0.900000** (per-rep 0.9167 / 0.8833; 20/20 runs clean),
band center, identical error profile (end-date 4/20, deposit 12/20, all misses nulls,
hallucinated_absent 0). Canary trip attributed to single-rep sampling noise per the
pre-declared rule. Drift check closed: v0 stable on the pinned invocation. HOLDOUT
PROCEEDS with three finalists: v0, loop-final v1, bo12-04 (best qualifying blind rewrite,
0.875 train).

## 2026-08-12 — G2: HOLDOUT COMPLETE, RESULTS LOCKED. Experiment over.

Single shot per finalist, 6 docs × 2 reps, version-asserted 2.1.227 before and after
every batch, per-skill ledger consumed exactly three entries, zero infrastructure
failures: **v0 0.902778 · v1 1.000000 · bo12-04 0.875000.** H1 SUPPORTED (+9.72pp against
the 1.94pp scaled threshold). H2: loop beats the best blind rewrite by +12.5pp — the
entire 8-strong blind-rewrite pool landed below v0. H3 not run (A3). RESULTS.md written
and LOCKED at `07-analysis/RESULTS.md`; P5 analysis artifacts: `trajectory.md`,
`skill-diff-evolution.md`, `evaluator-missed-audit.md` (verdict: no metric gaming found).
This log remains the amendment channel per SPEC §9; the goal-run (P1–P5) is complete.

## 2026-08-11 — Manual baseline WAIVED (SPEC amendment A3); H3 not run

Ali twice declined the 30-minute edit and proposed the orchestrator write it for him with a
human review pass afterward ("a human is still going to interact with the text").
Orchestrator refused both the ghost-write and the draft-then-tweak variant: authorship, not
interaction, is what the baseline measures, and the orchestrator has read v1 verbatim — any
draft it produced would be the loop's answer relabeled as human work. Resolution: A3
appended to SPEC — baseline waived, H3 reported NOT RUN, holdout proceeds with three
finalists (v0, loop-final v1, best-of-12 winner). Reversible by a real human edit any time
before the holdout batches start.

Iteration-1 detail: patch authored by GPT 5.6 Sol (max) in the jailed cwd from pack-it1
(nf-4b evidence) — v1 = 86 lines / 5,888 bytes, diff vs v0 = general derivation principle
in Output rules + derived-end-date rule + deposit-formula rule; no hardcoded values, no doc
references. Note for the record: with best ref at the 1.0 ceiling, keep (Δ > 0.015) is
mathematically unsatisfiable; per the registered protocol the loop continues until 4
consecutive reverts fire the early stop (expected at iteration 5) — run as registered, not
short-circuited, because the controller's revert behavior under no-signal mutations is
itself the object of study.
