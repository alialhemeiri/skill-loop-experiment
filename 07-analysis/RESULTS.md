# RESULTS.md — locked at G2, 2026-08-12

**Status: LOCKED.** Held-out evaluation executed exactly once per finalist (ledger below).
Per SPEC §9, nothing in this file may be revised — only amended with a logged entry in
`06-log/experiment-log.md`. Protocol: `00-control/SPEC.md` (+ amendments A1–A3), frozen
test bed per `00-control/FREEZE.md`, full chronology in `06-log/experiment-log.md`.

## 1. Held-out results (6 unseen docs × 2 reps per finalist, single shot)

| Finalist | Holdout score | Per-rep | Missed present | Hallucinated absent | Infra failures |
|---|---:|---|---:|---:|---:|
| v0 (starting skill) | **0.902778** | 0.9167 / 0.8889 | 14 | 0 | 0 |
| **v1 (loop-final, 1 kept iteration)** | **1.000000** | 1.0000 / 1.0000 | 0 | 0 | 0 |
| bo12-04 (best of 12 blind rewrites) | **0.875000** | 0.8750 / 0.8750 | 18 | 0 | 0 |

Per-field: v1 = 12/12 fields perfect. v0 missed only `contract_end_date` (4/12) and
`security_deposit_aed` (6/12), all as nulls. bo12-04 missed the same two fields
(end-date 0/12, deposit 6/12), all as nulls.

## 2. Hypotheses (pre-registered in SPEC §2)

- **H1 — SUPPORTED.** Loop-final beats v0 on held-out by **+9.72pp**, against the
  pre-registered scaled threshold of 1.94pp (5.0× the threshold). The loop's single kept
  improvement generalized completely: training +10.4pp → holdout +9.72pp.
- **H2 (no prediction registered).** Loop-final beats the best blind rewrite by
  **+12.50pp**. Twelve blind rewrites by the same engine as the patcher, given v0 + schema
  + a generic task description but NO failure data: 4 disqualified themselves on the
  size caps; the 8 qualifiers scored **0.858–0.875 on training — every one below v0's
  0.896** — and the best transferred to holdout at exactly its training level (0.875).
  Failure evidence, not model capability, was the active ingredient: the same engine that
  produced +10.4pp with an evidence pack produced only regressions without one.
- **H3 — NOT RUN.** Manual human baseline waived (SPEC amendment A3): the orchestrator's
  own status reporting had contaminated the founder's independence (registered confound),
  the founder then declined the edit and asked the orchestrator to ghost-write it, which
  was refused — a model-authored edit cannot be labeled a human baseline.

## 3. Training-side references

- v0 reference: noise floor mean **0.895833** over 4 × (10 docs × 2 reps); sample SD
  0.0059; keep/revert threshold = max(1 SD, 1.5pp) = **0.015**; holdout threshold ×√(10/6)
  = **0.019365** (all frozen pre-loop in FREEZE.md).
- Loop: **iteration 1 KEPT** (+10.4pp → 1.0, the training ceiling); iterations 2–5 all
  reverted at Δ = 0; **early stop after 4 consecutive reverts**. Iterations to plateau: 1.
  All four reverted patches were independent re-derivations of the same conflict-precedence
  rule — a strong attractor for no-signal mutation, and unrewardable by construction (the
  corpus contains no conflicts).
- Generalization symmetry (the A1 rebalancing doing its job): v0 train 0.8958 → holdout
  0.9028 (+0.7pp, within noise); v1 1.0 → 1.0; bo12-04 0.875 → 0.875 (exact).

## 4. Drift canary (SPEC A2.6) — tripped, then cleared by pre-declared rule

Single-rep canary scored 0.8750, 0.58pp below the pre-declared band [0.8808, 0.9108] →
holdout was refused. Investigation: identical error profile to all prior v0 measurements
(all misses nulls on the same two fields; the shortfall was end-date lucky-derivations
going 0/10), single-rep band oversensitive by design (~13% false-alarm rate), and
same-day bo12 scores identical across the drift window. Pre-declared confirmation batch
(20 runs): **0.900 — band center, PASS**. Both results reported; holdout proceeded.

## 5. Secondary metrics (SPEC §2)

- **Hallucinated-absent rate: 0 across all 406 scored runs of the experiment.** No
  null-spam or fabrication drift anywhere.
- Fence-wrapping: 12/406 scored runs (3.0%), every one absorbed by the registered strip;
  0 unparseable / 0 wrong_shape / 0 missing in all scored batches.
- Turn-check retries: 0 in all scored batches (1 occurrence in a superseded calibration
  batch, logged).
- Skill length: v0 96 lines / 5,297 B → v1 86 lines / 5,888 B (−10 lines, +11% bytes).
- Revert count: 4 (consecutive; triggered early stop). Run budget actually consumed:
  ~476 worker runs total including calibration and superseded batches (vs ~630 planned).

## 6. Integrity registry

- Test bed frozen before the loop (FREEZE.md hash table); every batch manifest binds
  skill/runner/worker/doc hashes; fixture-identity assertion refuses superseded corpora.
- Held-out ledger (verbatim below): exactly three shots, one per finalist skill hash;
  runner version-asserted 2.1.227 before AND after every holdout batch.
- Infrastructure events, all logged, none scoring-relevant: one subscription lapse
  (nf-4 → replaced whole by nf-4b, pre-declared transport rules), two CLI auto-updates
  mid-run (version-pin guard refused both; restored via versioned-binary PATH pin).
- Registered caveats carried from FREEZE.md: alias model pin (no dated snapshot exposed);
  headroom concentrated in two derivation rules; decoys contribute zero measured
  difficulty (disclaimer clauses); deposit is a constant ratio corpus-wide (audited in
  `evaluator-missed-audit.md` — v1 contains no hardcoded constant); synthetic data
  throughout (disclosed as a methods fact).

```
{"started_at":"2026-08-11T20:15:34.187Z","batch_id":"g2-v0","skill_sha256":"57585893fe94b546ceb76f43f204828903e4e0ee285310f699f6b6e99f681174","doc_ids":["doc-11","doc-12","doc-13","doc-14","doc-15","doc-16"]}
{"started_at":"2026-08-11T20:18:20.080Z","batch_id":"g2-v1","skill_sha256":"d3c67d993c0847eff5c7e2ede65f7cf8ebfe196dfdb6cfe4f1c9188e74defef1","doc_ids":["doc-11","doc-12","doc-13","doc-14","doc-15","doc-16"]}
{"started_at":"2026-08-11T20:20:22.223Z","batch_id":"g2-bo12","skill_sha256":"912e9105678b9f2acdfbd4e1bf450afca5da331414acac2ae2da06430d73c9f0","doc_ids":["doc-11","doc-12","doc-13","doc-14","doc-15","doc-16"]}
```

## 7. One-paragraph summary

A pre-registered controller loop — bounded mutation of a single skill file against a
frozen mechanical evaluator, keep-or-revert above a noise-calibrated threshold — took a
document-extraction skill from 0.90 to 1.00 on a held-out set in **one evidence-guided
iteration**, then correctly rejected four consecutive no-signal mutations and stopped
itself. The same engine given no failure evidence produced twelve rewrites that were all
worse than the starting point. The loop's edge was not model capability — both roles used
the same model — but the harness: frozen score, failure evidence in, one bounded change
out, revert by default.
