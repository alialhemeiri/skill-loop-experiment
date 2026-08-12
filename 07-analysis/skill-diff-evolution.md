# Skill diff evolution — v0 → v1 (the only kept change), annotated

Full files preserved under `03-skill/versions/`. v0 sha `57585893…9174` (96 lines,
5,297 B) → v1 sha `d3c67d99…efef1` (86 lines, 5,888 B).

## The kept diff (iteration 1) — one principle, three touchpoints

The patcher saw the iteration-1 evidence pack: end-date 1/10 with nine "worker answered
null, gold has a date" instances, deposit 5/10, everything else perfect. Its one bounded
change: **"a value defined by an explicit deterministic relationship counts as stated —
compute it."**

1. **Output rules** — added the general principle:
   > Treat a value as stated when it appears directly or is defined by an explicit
   > deterministic relationship whose required inputs are stated in the agreement.
   > Perform only that calculation; if the relationship or any input is missing or
   > ambiguous, return JSON `null`.
2. **Dates section** — added the derivation the evidence demanded, including the exact
   convention v0 kept missing:
   > If no end date is printed but the agreement explicitly states both the commencement
   > date and a tenancy duration, derive the inclusive end date by advancing the
   > commencement date by the stated calendar duration and subtracting one day.
3. **Money section** — the same principle for the deposit:
   > If the deposit is explicitly defined as a percentage or other arithmetic formula of
   > the stated annual rent, calculate that formula and return the resulting whole-dirham
   > amount. Do not apply a customary deposit rate that the agreement itself does not
   > state.

No hardcoded values, dates, names, or document references (audited). The change is
general, and generalized: +10.4pp training, +9.72pp holdout.

## The four reverted diffs (iterations 2–5) — one attractor, four variants

With a zero-defect evidence pack, the patcher had no gradient. All four proposals were
independent variants of the SAME idea — resolve duplicate/conflicting field values via
explicit amendment-precedence, else null — an idea the corpus cannot reward (no
contradiction traps exist, by construction, and the patcher was never told that). Each
scored exactly 1.0 (harmless), failed the Δ > 0.015 keep rule, and was reverted. The
controller's revert-by-default rule, not judgment about the patches' content, is what
kept the skill stable.

Observations worth keeping:
- A capable model under no-signal conditions doesn't produce diverse mutations — it
  reconverges on the most plausible-sounding unfalsifiable improvement.
- None of the four blind mutations damaged the skill (all 1.0) — but the best-of-12
  control shows what LARGER no-signal rewrites do: all 8 qualifiers regressed below
  baseline. Bounded mutation limited the blast radius; the threshold did the rest.
