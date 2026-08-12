# G1 closure check — Opus (same reviewer thread), 2026-08-11 — verdict: FREEZE-READY

> Continuation of G1-opus-review.md → G1-opus-rereview.md, after the G1R2 fix round.
> All five mandated fixes CONFIRMED CLOSED by direct exercise (not test-trusting):
> BLOCKER A (ledger per-skill: 8-step live exercise incl. fifth-skill refusal and per-skill
> resume), MAJOR B (identity assertion: cal-1 refuses all 10 docs, cal-4 refuses exactly
> doc-01+doc-06 — precisely the two docs the grammar fix touched; cal-5 scores 0.883333),
> MAJOR D (rejected-envelope persistence byte-exact incl. UTF-8; turn_check_retries counts
> only turn-guard entries; --disallowedTools in pinned args), MAJOR E (snapshots 10+10
> triple-verified; gold-copy step proven isolated from build_prompt; audit gap disclosed),
> MINOR L (singular/plural cheque clause + test). Baseline re-verified: --check clean,
> 98 + 44 tests, v0 SHA unchanged, ledger absent.

## Material new evidence (refines, does not overturn, the end-date ruling)

cal-5 doc-01: first observed naive-anniversary error (predicted 2027-08-21, gold 2027-08-20,
start 2026-08-21). Tally across corpus-matched batches: 27/30 end-date opportunities = null,
2 correct day-before derivations, 1 naive-anniversary error. FREEZE.md failure-mode wording:
"predominantly null — declines to derive — with occasional naive-anniversary answers."
Supersedes the experiment-log claim that all non-null derivations were correct.
Also: cal-5 doc-03 tenant "KOFI MENSIMA" scored correct — live casefold confirmation.

## New MINORs introduced by the fixes (register, none block)

1. Turn-check classification duplicated as string matching in run.py and score.py — a
   locked coupling once both are hash-frozen; register it.
2. `05-runs/<batch>/fixtures/gold/` widens the gold footprint — evidence-pack builder and
   patcher context must exclude `05-runs/**/fixtures/gold/` exactly like `01-fixtures/gold/`.
3. Pre-G1R2 batches (p2-dry*, g1-cal-1..4) are not resumable (no snapshots) and cal-1..4
   are not re-scorable (corpora regenerated away). Historical only; fails closed.

## Consolidated FREEZE.md registration list (verbatim from the reviewer)

A. Hashes: generate.py, 16 docs, 16 gold, grader.py, score.py, run.py, v0/SKILL.md
   (5758…9174), worker-system-prompt.txt, worker.json.
B. Fixture facts: (1) null rates 50/50 all four fields, 0.0pp; (2) derivation coverage —
   end_date 16/16, annual_rent 16/16 words-only (gold digits never appear),
   number_of_payments 14/16, deposit 8/8 present; load on the two v0-failed fields = 12.5%
   both splits; (3) end-date rule D + 1y − 1d uniform, ruled fair; (4) deposit = rent // 20
   in 100% of present cases — flag for P5 gaming audit; (5) decoys present in every doc but
   contribute zero measured difficulty (each neutralised by a disclaimer clause); (6) dead
   branches under the frozen seed — copied-rent/copied-deposit never execute, AED-format
   menu never applies to annual rent.
C. Baseline facts: (7) v0 draws cal-3 0.8917 / cal-4 0.9000 / cal-5 0.8833 — cal-5 is the
   binding figure (only identity-passing batch); same-skill spread 1.7pp across single-rep
   draws; (8) cal-5 headroom: 14/120 wrong = 9 end-date + 5 deposit, ten fields 10/10,
   hallucinated_absent 0; (9) failure mode: predominantly null (27/30), one naive error,
   two correct derivations; (10) deposit carries most run-to-run variance; (11) fence rate
   9/50 (18%, was 83%) with 0 unparseable / wrong_shape / missing.
D. Protocol/limitations: (12) alias pin + A2.6 drift canary + RESULTS.md restatement;
   (13) --disallowedTools in pinned args — record the post-change ~18.9k isolation probe;
   (14) turn-check = transport class, retry-eligible, rejected envelope persisted, counted;
   model re-draw under transport label, incidence 1/50; string-coupled classifiers;
   (15) fence-strip semantics; (16) ledger per-skill, cap 4, same-batch resume, A2.2
   recovery rule; (17) holdout path-substring heuristic — operator discipline; (18) grader
   punctuation frozen to ASCII + em-dash (registered narrowing); (19) run-dir gold
   footprint exclusion rule; (20) cal-1..4 not re-scorable, pre-G1R2 batches not
   resumable, rounds-1–2 audit gap disclosed, final generator certified corpus-generic;
   (21) √(10/6) threshold scaling for H1.
