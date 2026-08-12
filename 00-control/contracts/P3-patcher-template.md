# P3 patcher prompt template (engine: GPT 5.6 Sol via codex, one call per iteration)

> Orchestrator usage: fill {N}, paste the current skill and the iteration's evidence pack,
> launch codex with `--cd` set to a jail directory under the session scratchpad containing
> ONLY this filled prompt (the skill text and pack are embedded in it). The patcher's output
> is its final message. The orchestrator applies it as `03-skill/versions/v{N}/SKILL.md`,
> enforces the caps, runs the batch, scores, and decides keep/revert against the frozen
> threshold. Registered defenses against gold-memorization: the 150-line/10KB cap, the
> published diff trail, the P5 audit, and the fact that train-gold hardcoding cannot move
> the held-out score.

---

You are the patcher in a controlled skill-improvement experiment: bounded mutation against
a frozen evaluator. You see exactly two things: the current skill file and an evidence pack
from its latest scored run on the training set. Nothing else exists for you — do not read
any files; work only from what is in this prompt.

## Your task — iteration {N}

Propose ONE bounded improvement to the skill. One focused change: a rule added, a rule
sharpened, a rule removed. Not a rewrite. The change must be GENERAL — it must plausibly
help on unseen documents of the same kind. Never hardcode a specific document's answer,
name, amount, or date; never reference document filenames.

Hard constraints on the skill file you return:
- Complete markdown file, ≤150 lines and ≤10,000 bytes.
- It is the only thing the extraction worker reads besides the document and a fixed schema
  instruction (which already lists the 12 keys/types and demands bare JSON with null for
  absent fields — do not duplicate the schema listing; spend lines on technique).

## Current skill (v{CURRENT})

<<<SKILL
{SKILL_CONTENT}
SKILL>>>

## Evidence pack (training set, batch {BATCH})

<<<PACK
{PACK_CONTENT}
PACK>>>

## Output format

Your final message: the COMPLETE new skill file content, and nothing else — no preamble, no
explanation, no code fences around the whole file. (A one-line HTML comment at the top of
the file, `<!-- vN: one-sentence change summary -->`, is the only allowed annotation and
counts toward the caps.)
