# G1 review contract — adversarial cross-review before freeze (engine: Opus)

You are the cross-engine reviewer for a pre-registered skill-improvement experiment, at the
gate where the test bed freezes. Everything you are reviewing was built by a different engine
(GPT 5.6 Sol). Your job is to find problems BEFORE the SHA-256 freeze makes them expensive —
after G1, every fix is a logged amendment and may void results.

## Read, in order

1. `projects/autoresearch-skill-loop/00-control/SPEC.md` — the frozen protocol (authority)
2. `projects/autoresearch-skill-loop/00-control/contracts/P1-fixtures-grader.md`
3. `projects/autoresearch-skill-loop/00-control/contracts/P2-runner-v0.md`
4. `projects/autoresearch-skill-loop/00-control/worker.json` + `worker-system-prompt.txt`
5. The artifacts: `01-fixtures/generator/generate.py`, 2–3 documents from
   `01-fixtures/docs/train/` with their gold records, `02-evaluator/grader.py`, both test
   suites, `04-runner/run.py`, `03-skill/versions/v0/SKILL.md`.

Do NOT modify anything. Review only. Reading holdout documents is permitted for you (you are
not the worker and propose no skill changes), but note that you did.

## Review lenses (work through each)

1. **SPEC conformance** — does each artifact do exactly what SPEC §3–§7 registered? Any silent
   deviation, however sensible, is a finding.
2. **Determinism** — generator: any dict/set iteration hazard, timestamp, locale dependence,
   or randomness outside the seeded instance that could break byte-reproducibility across
   machines/Python versions? Grader: any nondeterminism at all?
3. **Grader fairness + tightness** — ways a CORRECT extraction scores wrong (unfair), and ways
   a WRONG extraction scores right (loose). Check normalization edge cases against the actual
   document renderings (honorifics, role suffixes, Arabic labels, `Dhs. X/-` amounts).
4. **Leakage channels** — can the worker ever see gold, scores, or other docs via the runner's
   prompt construction? Does v0's content betray knowledge it should not have (it was allowed
   only SPEC §3–§4 + doc-01.txt)? Does the runner keep holdout untouchable without
   `--allow-holdout`?
5. **Metric-gaming surfaces** — how could the LOOP later game this metric without genuinely
   better extraction? (E.g. schema-echo tricks, null-spamming strategies given the 1–3 absent
   fields per doc, exploiting normalization looseness.) For each surface: is it blocked,
   measurable (hallucinated-absent counter), or an accepted risk to log?
6. **v0 sanity** — non-sandbagged per SPEC §3? A reasonable ten-minute practitioner attempt —
   neither deliberately weak nor suspiciously optimized? Within 150 lines / 10 KB?
7. **Test-suite adequacy** — vacuous tests, untested grader rules, missing negative cases.
8. **Runner robustness** — resumability correctness (skip logic can't skip a failed run
   silently), transport-vs-model failure rule implemented as registered in worker.json, raw
   outputs stored byte-exact, manifest completeness.

## Output format (your final message)

A findings list, most severe first. Each finding: `SEVERITY (BLOCKER/MAJOR/MINOR) — file:line —
what — why it matters — suggested fix direction (one line)`. BLOCKER = would invalidate or bias
the experiment if frozen; MAJOR = weakens defensibility or a registered guarantee; MINOR =
polish. End with: a one-paragraph overall verdict, and an explicit statement for each of the 8
lenses ("clean" or finding numbers). If you found nothing at all, say so and state what you
checked to conclude that.
