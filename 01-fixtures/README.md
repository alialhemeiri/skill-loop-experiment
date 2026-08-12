# Frozen tenancy fixtures

This directory contains 16 invented, synthetic UAE residential tenancy contracts and their
12-field gold JSON records. Documents 01–10 are in `docs/train/`; documents 11–16 are in
`docs/holdout/`. `generator/generate.py` is deterministic and uses only the Python 3 standard
library.

From the workspace root:

```sh
python3 projects/autoresearch-skill-loop/01-fixtures/generator/generate.py
python3 projects/autoresearch-skill-loop/01-fixtures/generator/generate.py --check
```

Use `--seed INTEGER` to select a seed and `--out-root PATH` to target another fixture root. The
default seed is `20260811`; the default output root is this directory. Normal generation re-reads
and sanity-checks every document and gold record. `--check` regenerates in a temporary directory
and compares all 32 outputs byte-for-byte.

Generator v2 keeps two easier, substantially labeled documents and renders the remaining
documents primarily as operative prose with at most a partial key-terms block. Every document has
at least one recorded derivation plus representative, external-money, building, date, and parking
decoys attributed to their non-gold subjects. The in-memory evidence plan lets the sanity guard
distinguish copied fields, derivation inputs, and entirely absent nullable concepts.

**Freeze warning:** these files freeze at G1 — see SPEC §8–9. After G1, do not regenerate or edit
them without the logged amendment process.
