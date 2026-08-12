# Frozen mechanical evaluator

`grader.py` scores prediction JSON against the 12-field frozen schema using only Python 3's
standard library. It reports exact per-field accuracy after the registered normalization and
separately reports five counters:

- `unparseable`: a prediction file exists but is not strict JSON.
- `wrong_shape`: strict JSON is valid but its root is not an object.
- `missing`: the prediction file is absent; it scores zero but is not unparseable.
- `hallucinated_absent`: a non-null value was supplied for a gold-null field.
- `missed_present`: a valid object used null or omitted the key for a gold-present field.

Single file:

```sh
python3 projects/autoresearch-skill-loop/02-evaluator/grader.py \
  --pred out.json --gold projects/autoresearch-skill-loop/01-fixtures/gold/doc-01.json
```

Batch mode matches flat `.json` files by basename and scores every file in the gold directory:

```sh
python3 projects/autoresearch-skill-loop/02-evaluator/grader.py \
  --pred-dir outputs/ --gold-dir projects/autoresearch-skill-loop/01-fixtures/gold/
python3 -m pytest projects/autoresearch-skill-loop/02-evaluator/tests/ -q
```

Extra prediction keys are ignored. `grader.py` is deliberately strict and does not remove markdown
fences.

`score.py` is the candidate-score entry point. It reads the runner manifest, refuses incomplete or
transport-failed batches before grading, filters the shared gold directory by manifest document ID,
and pools every expected repetition:

```sh
python3 projects/autoresearch-skill-loop/02-evaluator/score.py \
  --batch-dir projects/autoresearch-skill-loop/05-runs/NAME \
  --gold-root projects/autoresearch-skill-loop/01-fixtures/gold
```

Its JSON includes pooled and per-repetition means, per-field and per-document breakdowns, all five
counters, and the number of runner records whose outer fence was stripped.

**Freeze warning:** these files freeze at G1 — see SPEC §8–9. After G1, changes require the logged
amendment and re-scoring process.
