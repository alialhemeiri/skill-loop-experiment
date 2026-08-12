# "What the evaluator missed" — metric-gaming audit of high-scoring outputs

Question: did v1 earn 1.0 by genuinely better extraction, or by exploiting something the
frozen metric cannot see? Checks run 2026-08-12 against stored raw outputs.

## Checks and findings

1. **Spot verification against gold (holdout).** v1's stored predictions byte-match gold
   values on inspected runs (doc-11 rep1, doc-16 rep2 — full-field exact matches). The
   1.0 is not a normalization artifact.
2. **Deposit constant-ratio shortcut (FREEZE.md flag #4).** The corpus renders every
   present deposit as exactly `annual_rent // 20`, so a skill could memorize the constant
   instead of reading the clause. Audit of v1's text: **no hardcoded ratio** — no "5",
   "five per cent", "0.05", or "// 20" anywhere; the rule is "explicitly defined as a
   percentage or other arithmetic formula of the stated annual rent." From outputs alone
   the two strategies are observationally identical on this corpus (registered
   limitation); the skill text is the evidence that generalization is by clause-reading.
3. **Null-spam / hallucination drift.** `hallucinated_absent` = 0 across all 406 scored
   runs, and v1's holdout `missed_present` = 0 — no strategy involving nulls was
   rewarded anywhere.
4. **Fence / format exploitation.** The registered strip fired on 12/406 scored runs
   (3.0%), none in the holdout batches; no candidate's score depended on format handling.
5. **Worker side channels.** Every scored batch: `num_turns = 1`, empty
   `permission_denials`, tools disallowed in the pinned invocation, empty neutral cwd —
   no evidence of any run touching gold or fixtures.
6. **Evidence-pack leakage into skill content.** v1 contains no document names, entity
   names, amounts, or dates from the fixtures (the one v0 literal — a worked date example
   — matches nothing in the regenerated corpus, registered at G1R).

## What the metric genuinely cannot see (registered, unresolved)

- Whether deposit derivation reads the clause or memorized the corpus constant (above).
- Extraction robustness beyond the corpus's difficulty envelope: the decoys contribute
  zero measured difficulty (each is neutralized by a disclaimer clause — FREEZE.md #5),
  so scores say nothing about performance against genuinely adversarial decoys.
- Anything outside the 12 fields, outside plain text, or outside this synthetic genre
  (SPEC §11 out-of-scope list).

**Verdict: no metric gaming found.** v1's holdout perfect score is explained by two
genuine, general derivation rules that the evidence pack demanded and the blind controls
never found.
