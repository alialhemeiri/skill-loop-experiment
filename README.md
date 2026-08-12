# Skill loop experiment

## What this is

This repository contains a pre-registered skill-improvement experiment run on 2026-08-11 and 2026-08-12. It transfers the controller pattern from Andrej Karpathy's [autoresearch](https://github.com/karpathy/autoresearch)—bounded mutation, a fixed budget, a frozen evaluator, and keep-or-revert selection—from LLM training to a single agent skill file.

Companion article (live at publication): [The Cost of Unmeasured Change](https://aperion.ae/articles/the-cost-of-unmeasured-change).

The data are synthetic: all 16 tenancy contracts were generated, and every entity in them is invented.

## Headline result

| Finalist | Held-out score |
|---|---:|
| v0 (starting skill) | 0.902778 |
| v1 (loop-final) | 1.000000 |
| bo12-04 (best blind rewrite) | 0.875000 |

H1 was supported: v1 beat v0 by +9.72pp, above the pre-registered 1.94pp held-out threshold.

H2 had no directional prediction: v1 beat the best blind rewrite, bo12-04, by +12.5pp.

H3 was not run under SPEC amendment A3.

## Repo map

- `00-control/` — protocol, freeze record, reviews, and holdout ledger.
- `01-fixtures/` — generator, synthetic corpus, and gold records.
- `02-evaluator/` — mechanical grader and scorer.
- `03-skill/` — every skill version from v0 through v5 plus all bo12 attempts.
- `04-runner/` — runner for the pinned worker invocation, evidence-pack builder, and tests.
- `05-runs/` — every raw worker output and manifest, preserved byte-exact.
- `06-log/` — chronological experiment log.
- `07-analysis/` — locked `RESULTS.md`, trajectory, diff evolution, and gaming audit.

## Verify the freeze

From the repository root, re-hash each frozen file and compare the output with [`00-control/FREEZE.md` §1](00-control/FREEZE.md#1-frozen-hashes-sha-256):

```bash
sha256sum 01-fixtures/generator/generate.py
sha256sum 02-evaluator/grader.py
sha256sum 02-evaluator/score.py
sha256sum 04-runner/run.py
sha256sum 03-skill/versions/v0/SKILL.md
sha256sum 00-control/worker-system-prompt.txt
sha256sum 00-control/worker.json
sha256sum 04-runner/evidence.py
```

Regenerate the corpus in a temporary directory and byte-compare all committed documents and gold records:

```bash
python3 01-fixtures/generator/generate.py --check
```

The batch manifests in `05-runs/` bind the skill, document, and runner hashes for each batch.

## Rerun it

The published results were produced through subscription CLIs with the worker pinned to the alias model string `claude-sonnet-5` and Claude Code CLI 2.1.227. That is an alias pin, not a dated model snapshot; see [`FREEZE.md` §5](00-control/FREEZE.md#5-protocol-registrations-and-limitations). A rerun is therefore a new experiment, not a replay.

Use the worker invocation in [`00-control/worker.json`](00-control/worker.json) together with [`00-control/worker-system-prompt.txt`](00-control/worker-system-prompt.txt). Follow [`04-runner/README.md`](04-runner/README.md) to execute batches and use [`02-evaluator/`](02-evaluator/) to score them. [`00-control/SPEC.md`](00-control/SPEC.md) contains the full protocol and append-only amendment trail.

## Registered caveats

- The model pin is an alias; no dated snapshot was exposed.
- Measured headroom is concentrated in two derivation rules: `contract_end_date` and `security_deposit_aed`.
- The decoys contribute zero measured difficulty because each is neutralized by an explicit disclaimer clause.
- The deposit is a constant ratio corpus-wide, so clause-reading and constant-memorization strategies are observationally equivalent on this corpus; see [`07-analysis/evaluator-missed-audit.md`](07-analysis/evaluator-missed-audit.md).
- All experiment data are synthetic.
- H3 was waived under SPEC amendment A3: status reporting contaminated the founder's independence, so the manual baseline was confounded and not run.

## Attribution

The controller pattern is Karpathy's: [autoresearch](https://github.com/karpathy/autoresearch) supplies the bounded mutable surface, fixed budget, frozen evaluation, and keep-or-discard loop, while [Verifiability](https://karpathy.bearblog.dev/verifiability/) provides the broader framing for tasks that can be efficiently attempted and mechanically rewarded. This experiment transfers that pattern from training code to an agent skill file.

The evidentiary layer—noise-floor calibration and a keep threshold, held-out single-shot evaluation, independent baselines, pre-registration with amendments, hash-freeze manifests, and adversarial cross-review—is this experiment's addition. It is not attributed to the autoresearch repository.

## License

[MIT](LICENSE).
