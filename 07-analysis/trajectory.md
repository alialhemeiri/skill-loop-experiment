# Score trajectory — kept/reverted markers

All scores = pooled mean field accuracy, 10 training docs × 2 reps (20 runs), frozen
grader + scorer. Thresholds frozen pre-loop: keep iff Δ > 0.015 vs current best.

```
score
1.00 ┤                    ● KEEP (v1)   ○ rev   ○ rev   ○ rev   ○ rev
0.99 ┤                   ╱
     │                  ╱
0.90 ┤ ▪▪▪▪ v0 noise floor (0.8875–0.9000, mean 0.8958)
0.89 ┤
     │   [best-of-12 blind rewrites: 0.858 ▬▬▬▬▬▬▬▬ 0.875, all below v0]
0.85 ┤
     └──┬────────────────┬───────┬───────┬───────┬───────┬──────────────
        v0 (baseline)   it-1    it-2    it-3    it-4    it-5 → EARLY STOP
```

| Point | Candidate | Score (20 runs) | Δ vs best ref | Decision |
|---|---|---:|---:|---|
| baseline | v0 | 0.895833 (noise-floor mean; batches 0.9000/0.8875/0.8958/0.9000) | — | reference |
| it-1 | v1 | 1.000000 | +0.104167 | **KEEP** |
| it-2 | v2 | 1.000000 | +0.000000 | revert (1) |
| it-3 | v3 | 1.000000 | +0.000000 | revert (2) |
| it-4 | v4 | 1.000000 | +0.000000 | revert (3) |
| it-5 | v5 | 1.000000 | +0.000000 | revert (4) → **early stop** |

Holdout (single shot, 6 unseen docs × 2 reps): v0 0.9028 · **v1 1.0000** · bo12-04 0.8750.

Blind-rewrite control (no failure data, same engine as the patcher): 12 attempts →
4 disqualified on caps (over 150 lines / 10 KB), 8 scored 0.858–0.875 — the entire pool
below v0. The distribution of blind rewrites sits BELOW the baseline; the single
evidence-guided patch sits at the ceiling.
