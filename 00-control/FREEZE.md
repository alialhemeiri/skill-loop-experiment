# FREEZE.md — G1 freeze record

**Frozen: 2026-08-11.** Gate owner: Ali (approved after schema + document skim, same day).
From this point, any change to a hashed file is a logged §9 amendment: a grader/scorer fix
re-scores all stored raw outputs; a fixture or protocol change voids affected results —
rerun or reported as voided, never silently replaced. Review trail:
`00-control/reviews/G1-opus-review.md` → `G1-opus-rereview.md` → `G1-opus-closure.md`
(final verdict FREEZE-READY). Pre-freeze amendments: SPEC.md §Amendments A1 (Ali, after
review 1) and A2 (Ali, after review 2) — both append-only.

## 1. Frozen hashes (SHA-256)

| Hash | File |
|---|---|
| `fe82ccb33e4c2eacf58338ad232fac4fae1f463e4d301ea3832d2485c424e4ec` | `01-fixtures/generator/generate.py` |
| `8ec4d29f75721c8c23a8f0408dcc151f9986bfa94cf5415397e7238d344b2b87` | AGGREGATE, 16 documents (sha256 over path-sorted per-file sha256s; per-file hashes reproducible via `generate.py --check`) |
| `146d6ca29b3602f339bddb13764283eba394e74293ddc7832cfb1188ec9223df` | AGGREGATE, 16 gold records (same construction) |
| `7b2ebe8715b79269b65cc1321082b4ba17c02250814b2dd0cea7224a1a50f820` | `02-evaluator/grader.py` |
| `49f4083fabb3e83e78355a08dedecf5d1d82c2ddbec0e9c834b3854578d169e9` | `02-evaluator/score.py` |
| `0d71817f9e72ba3ff0dcac97a21e411273ca08919d34afcff91aaf298a5c8f4c` | `04-runner/run.py` |
| `57585893fe94b546ceb76f43f204828903e4e0ee285310f699f6b6e99f681174` | `03-skill/versions/v0/SKILL.md` |
| `1f8e3cda93cc7985cedcbec46f911a0251c4cf81fdd25cabc9513872486a6e94` | `00-control/worker-system-prompt.txt` |
| `ecd944962b1ba0fc24a8cfe2eb266618438956a7426d814780b4969742eb3e2f` | `00-control/worker.json` |
| `499e8d23c034d4d17c078bf086016501e08603cb7d07795810e1a1562713cd9a` | `04-runner/evidence.py` (informational — pack builder; not score-affecting) |

Worker invocation (pinned in worker.json): `claude -p` on `claude-sonnet-5`, CLI 2.1.227,
custom 2-line system prompt, `--exclude-dynamic-system-prompt-sections`,
`--no-session-persistence`, `--disallowedTools <all standard tools>`, `--output-format
json`, prompt via stdin, empty neutral cwd `/tmp/autoresearch-worker-cwd`. Fixed context
~18.9k tokens (isolation probes in worker.json).

## 2. Noise floor and thresholds (SPEC §7.1 + A1.5)

- v0 evaluated 4 × (10 train docs × 2 reps): **0.900000, 0.887500, 0.895833, 0.900000**
  (batches `nf-1`, `nf-2`, `nf-3`, `nf-4b`; every run completed, zero infrastructure
  failures).
- **v0 reference score = noise-floor mean = 0.895833.** Sample SD = 0.005893.
- **Keep/revert threshold (training) = max(1 SD, 1.5pp) = 0.015000.** An iteration is kept
  iff `candidate_score − current_best_reference > 0.015`; a kept candidate's reference
  becomes its own 20-run evaluation score.
- **H1 held-out comparison threshold = 0.015 × √(10/6) = 0.019365.**
- Infrastructure event registered: original batch `nf-4` lost its final 3 runs to a
  subscription lapse at renewal (transport failures, terminal, error on CLI stdout);
  preserved unscoreable; replaced whole by `nf-4b`. Log:
  `06-log/experiment-log.md` (2026-08-11 infrastructure event).

## 3. Fixture facts (registered)

1. Null rates: 50%/50% train/holdout on all four nullable fields (0.0pp difference).
2. Derivation coverage: `contract_end_date` derived 16/16 docs; `annual_rent_aed` words-only
   16/16 (gold digits never appear in text); `number_of_payments` derived 14/16;
   `security_deposit_aed` derived 8/8 present cases. Load on the two fields v0 fails:
   exactly 12.5% of fields on BOTH splits.
3. End-date rule: "a term of twelve months commencing D" ⇒ end = D + 1 year − 1 day,
   uniform 16/16, ruled fair (arithmetically exact; coincides with UAE/Ejari practice; no
   document leaks the end date in any rendered format).
4. Deposit rule: exactly `annual_rent // 20` in 100% of present cases — memorizable
   constant that transfers train→holdout by construction; FLAGGED for the P5
   "what the evaluator missed" audit.
5. Label-adjacent decoys present in every document contribute zero measured difficulty —
   each is neutralised by an explicit disclaimer clause (documents self-annotate traps).
6. Dead branches under the frozen seed: copied-rent / copied-deposit render paths never
   execute; the registered AED-format menu never applies to the annual rent (only to
   decoys and instalment amounts).

## 4. Baseline facts (registered)

7. v0 pre-freeze draws: cal-3 0.8917, cal-4 0.9000 (superseded corpora), cal-5 0.8833
   (frozen corpus, 1 rep); binding reference is the §2 noise-floor mean 0.895833.
8. Headroom composition (stable across draws): wrong fields are `contract_end_date` (~9/10
   docs) + `security_deposit_aed` (~3–5/10); the other ten fields at ceiling;
   `hallucinated_absent` = 0 in all 130 v0 runs to date.
9. v0's failure mode, stated correctly: **predominantly null — declines to derive** (27/30
   end-date opportunities in calibration; consistent in the noise floor), with one observed
   naive-anniversary answer (cal-5 doc-01) and two correct day-before derivations. Not a
   convention disagreement.
10. `security_deposit_aed` carries most run-to-run variance.
11. Fence rate with the frozen system prompt: 18% of calibration runs (was 83% before the
    no-fence line); the registered strip (A1.2) absorbed every instance — 0 unparseable /
    0 wrong_shape / 0 missing across all calibration + noise-floor runs (130 runs).

## 5. Protocol registrations and limitations

12. Alias model pin: `claude-sonnet-5` is an alias; envelopes report it back unresolved.
    Mitigations: per-run model recording in manifests; A2.6 pre-holdout drift canary;
    limitation restated in RESULTS.md.
13. Turn-check: `num_turns != 1` or non-empty `permission_denials` ⇒ transport failure,
    retry-eligible, rejected envelope persisted byte-exact, counted as
    `turn_check_retries` (a model re-draw under a transport label; incidence 1/50
    calibration runs, 0/80 noise floor). The classifier is string-coupled between run.py
    and score.py — a locked coupling; neither may drift alone.
14. Fence-strip semantics (A1.2): one leading/trailing fence pair maximum, preds-only, raw
    bytes preserved, JSON validity decided on the stripped text.
15. Holdout ledger: keyed per `skill_sha256`, capped at 4 distinct finalist skills,
    same-batch resume allowed, A2.2 recovery rule for terminal holdout transport failure.
16. Holdout detection is a path-substring heuristic — operator discipline: never copy
    holdout docs elsewhere.
17. Grader punctuation stripping frozen to an explicit set (ASCII + em-dash) — registered
    narrowing vs the earlier unicodedata behaviour.
18. Run-dir gold footprint: `05-runs/<batch>/fixtures/gold/` holds gold snapshots; the
    evidence-pack builder and every patcher context MUST exclude `05-runs/**/fixtures/gold/`
    exactly as they exclude `01-fixtures/gold/`.
19. Historical batches: `p2-dry*`, `g1-cal-1..4` are not re-scorable / not resumable
    (superseded corpora or pre-snapshot manifests); calibration rounds 1–2 have no corpus
    snapshot — process-audit gap disclosed in the experiment log; the final generator was
    independently read in full and certified corpus-generic (no targeted traps).
20. Evidence-pack format and patcher jail: pre-registered in the experiment log
    (2026-08-11) before any loop iteration; the P4 manual baseline receives the identical
    iteration-1 pack.
21. Score of a candidate: `score.py` pooled mean over 10 train docs × 2 reps, completeness
    + fixture-identity asserted; H1 uses the §2 holdout-scaled threshold.
