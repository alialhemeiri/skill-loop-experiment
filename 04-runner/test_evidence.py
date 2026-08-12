#!/usr/bin/env python3
"""Stdlib integration tests for the training-only evidence-pack builder."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from typing import Any


EVIDENCE_PATH = Path(__file__).with_name("evidence.py")

FIELDS = (
    "landlord_name",
    "tenant_name",
    "unit_number",
    "community",
    "contract_start_date",
    "contract_end_date",
    "annual_rent_aed",
    "security_deposit_aed",
    "number_of_payments",
    "notice_period_days",
    "early_termination_penalty_months",
    "furnished_status",
)

FOOTER = (
    "This pack contains training-set data only. Holdout documents and holdout gold exist "
    "but are never shown to you."
)


def gold_record(doc_id: str) -> dict[str, Any]:
    suffix = doc_id.rsplit("-", 1)[-1].upper()
    return {
        "landlord_name": f"Landlord {suffix}",
        "tenant_name": f"Tenant {suffix}",
        "unit_number": f"Unit {suffix}",
        "community": f"Community {suffix}",
        "contract_start_date": "2026-01-01",
        "contract_end_date": "2026-12-31",
        "annual_rent_aed": 120000,
        "security_deposit_aed": 6000,
        "number_of_payments": 4,
        "notice_period_days": 90,
        "early_termination_penalty_months": 2,
        "furnished_status": "furnished",
    }


class EvidenceIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name) / "project"
        self.batch_dir = self.root / "05-runs" / "mock-batch"
        self.gold_root = self.root / "01-fixtures" / "gold"
        self.out_path = self.root / "pack.md"
        self.gold_root.mkdir(parents=True)

    def write_batch(
        self,
        *,
        doc_ids: tuple[str, ...] = ("doc-a",),
        reps: int = 1,
        predictions: dict[tuple[str, int], Any] | None = None,
        gold_by_doc: dict[str, dict[str, Any]] | None = None,
        document_texts: dict[str, str] | None = None,
        prediction_texts: dict[tuple[str, int], str] | None = None,
        docs_dir: str = "01-fixtures/docs/train",
        document_paths: dict[str, str] | None = None,
        run_updates: dict[tuple[str, int], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        predictions = predictions or {}
        gold_by_doc = gold_by_doc or {}
        document_texts = document_texts or {}
        prediction_texts = prediction_texts or {}
        document_paths = document_paths or {}
        run_updates = run_updates or {}
        self.batch_dir.mkdir(parents=True)

        documents: dict[str, dict[str, str]] = {}
        resolved_gold: dict[str, dict[str, Any]] = {}
        for doc_id in doc_ids:
            gold = gold_by_doc.get(doc_id, gold_record(doc_id))
            resolved_gold[doc_id] = gold
            (self.gold_root / f"{doc_id}.json").write_text(
                json.dumps(gold, ensure_ascii=False) + "\n", encoding="utf-8"
            )

            relative_path = document_paths.get(
                doc_id, f"01-fixtures/docs/train/{doc_id}.txt"
            )
            document_path = self.root / relative_path
            document_path.parent.mkdir(parents=True, exist_ok=True)
            document_path.write_text(
                document_texts.get(doc_id, f"FULL TEXT FOR {doc_id.upper()}"),
                encoding="utf-8",
            )
            documents[doc_id] = {
                "path": relative_path,
                "sha256": hashlib.sha256(document_path.read_bytes()).hexdigest(),
            }

        runs: list[dict[str, Any]] = []
        for rep in range(1, reps + 1):
            for doc_id in doc_ids:
                prediction = predictions.get((doc_id, rep), resolved_gold[doc_id])
                prediction_rel = f"preds/rep{rep}/{doc_id}.json"
                prediction_path = self.batch_dir / prediction_rel
                prediction_path.parent.mkdir(parents=True, exist_ok=True)
                prediction_path.write_text(
                    prediction_texts.get(
                        (doc_id, rep),
                        json.dumps(
                            prediction,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    ),
                    encoding="utf-8",
                )
                run = {
                    "doc_id": doc_id,
                    "rep": rep,
                    "status": "completed",
                    "fence_stripped": False,
                    "retry_log": [],
                    "files": {"prediction": prediction_rel},
                }
                run.update(run_updates.get((doc_id, rep), {}))
                runs.append(run)

        manifest = {
            "batch_id": "mock-batch",
            "skill": {
                "path": "03-skill/versions/v0/SKILL.md",
                "sha256": "a" * 64,
            },
            "docs_dir": docs_dir,
            "doc_ids": list(doc_ids),
            "reps": reps,
            "documents": documents,
            "runs": runs,
        }
        (self.batch_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return manifest

    def invoke(self, *, out_path: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(EVIDENCE_PATH),
                "--batch-dir",
                str(self.batch_dir),
                "--gold-root",
                str(self.gold_root),
                "--out",
                str(out_path or self.out_path),
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def build_pack(self) -> str:
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")
        return self.out_path.read_text(encoding="utf-8")

    def test_refuses_holdout_docs_dir_before_writing_output(self) -> None:
        self.write_batch(docs_dir="01-fixtures/docs/HOLDOUT")

        result = self.invoke()

        self.assertEqual(result.returncode, 2)
        self.assertIn("holdout", result.stderr.casefold())
        self.assertFalse(self.out_path.exists())

    def test_refuses_manifest_without_a_docs_dir_provenance_field(self) -> None:
        manifest = self.write_batch()
        del manifest["docs_dir"]
        (self.batch_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        result = self.invoke()

        self.assertEqual(result.returncode, 2)
        self.assertIn("docs_dir", result.stderr)
        self.assertFalse(self.out_path.exists())

    def test_refuses_any_holdout_manifest_document_path(self) -> None:
        self.write_batch(
            document_paths={"doc-a": "01-fixtures/docs/not-holdout-safe/doc-a.txt"}
        )

        result = self.invoke()

        self.assertEqual(result.returncode, 2)
        self.assertIn("document path", result.stderr.casefold())
        self.assertFalse(self.out_path.exists())

    def test_completeness_refusal_from_frozen_scorer_passes_through(self) -> None:
        self.write_batch()
        (self.batch_dir / "preds" / "rep1" / "doc-a.json").unlink()

        result = self.invoke()

        self.assertEqual(result.returncode, 2)
        self.assertIn("completeness check failed", result.stderr)
        self.assertIn("missing prediction file for doc-a rep1", result.stderr)
        self.assertFalse(self.out_path.exists())

    def test_fixture_identity_refusal_from_frozen_scorer_passes_through(self) -> None:
        self.write_batch()
        document_path = self.root / "01-fixtures" / "docs" / "train" / "doc-a.txt"
        document_path.write_text("MUTATED AFTER THE MANIFEST", encoding="utf-8")

        result = self.invoke()

        self.assertEqual(result.returncode, 2)
        self.assertIn("fixture identity mismatch for document(s): doc-a", result.stderr)
        self.assertFalse(self.out_path.exists())

    def test_lists_missing_key_null_and_wrong_value_without_normalizing_them(self) -> None:
        gold = gold_record("doc-a")
        missing = dict(gold)
        del missing["landlord_name"]
        null_value = dict(gold, landlord_name=None)
        wrong_value = dict(gold, landlord_name="Worker Wrong")
        self.write_batch(
            reps=3,
            predictions={
                ("doc-a", 1): missing,
                ("doc-a", 2): null_value,
                ("doc-a", 3): wrong_value,
            },
            prediction_texts={
                ("doc-a", 3): json.dumps(
                    wrong_value, ensure_ascii=False, separators=(",", ":")
                ).replace('"Worker Wrong"', '"Worker\\u0020Wrong"')
            },
        )

        pack = self.build_pack()

        group_start = pack.index("### `landlord_name`")
        group_end = pack.index("\n### `tenant_name`", group_start) if "### `tenant_name`" in pack else pack.index("\n## Exemplar documents", group_start)
        group = pack[group_start:group_end]
        self.assertLess(group.index("#### `doc-a`, rep 1"), group.index("#### `doc-a`, rep 2"))
        self.assertLess(group.index("#### `doc-a`, rep 2"), group.index("#### `doc-a`, rep 3"))
        self.assertIn("```text\nMISSING KEY\n```", group)
        self.assertIn("```json\nnull\n```", group)
        self.assertIn('```json\n"Worker\\u0020Wrong"\n```', group)
        self.assertNotIn('```json\n"Worker Wrong"\n```', group)
        self.assertEqual(group.count('```json\n"Landlord A"\n```'), 3)

    def test_does_not_disclose_gold_for_a_right_answer(self) -> None:
        gold = gold_record("doc-a")
        gold["landlord_name"] = "RIGHT-GOLD-MUST-NOT-LEAK"
        prediction = dict(gold, tenant_name="Wrong tenant")
        self.write_batch(
            predictions={("doc-a", 1): prediction},
            gold_by_doc={"doc-a": gold},
            document_texts={"doc-a": "Training prose with no sentinel value."},
        )

        pack = self.build_pack()

        self.assertNotIn("RIGHT-GOLD-MUST-NOT-LEAK", pack)
        self.assertIn('```json\n"Tenant A"\n```', pack)

    def test_header_has_scores_counters_and_all_twelve_field_rows(self) -> None:
        self.write_batch(
            run_updates={
                ("doc-a", 1): {
                    "fence_stripped": True,
                    "retry_log": [
                        {"reason": "CLI result used 2 turns"},
                        {"reason": "nonzero process exit"},
                    ],
                }
            }
        )

        pack = self.build_pack()

        self.assertIn("# Evidence Pack — mock-batch", pack)
        self.assertIn("- **Batch ID:** `mock-batch`", pack)
        self.assertIn("- **Skill:** `03-skill/versions/v0/SKILL.md`", pack)
        self.assertIn("`sha256: " + "a" * 64 + "`", pack)
        self.assertIn("- **Pooled score:** 12/12 (1.000000)", pack)
        self.assertIn("- **Per-rep scores:** rep1 12/12 (1.000000)", pack)
        self.assertIn("fence_stripped=1", pack)
        self.assertIn("turn_check_retries=1", pack)
        for field in FIELDS:
            self.assertIn(f"| `{field}` | 1/1 | 1.000000 |", pack)

    def test_exemplar_selection_is_ranked_deterministically_and_capped_at_two(self) -> None:
        doc_ids = ("doc-a", "doc-b", "doc-c", "doc-d")
        predictions: dict[tuple[str, int], dict[str, Any]] = {}
        wrong_reps = {
            "doc-a": {3},
            "doc-b": {2, 3},
            "doc-c": {1, 3},
            "doc-d": {1, 2, 3},
        }
        for doc_id in doc_ids:
            gold = gold_record(doc_id)
            for rep in range(1, 4):
                predictions[(doc_id, rep)] = (
                    dict(gold, landlord_name=f"Wrong {doc_id} rep{rep}")
                    if rep in wrong_reps[doc_id]
                    else gold
                )
        self.write_batch(
            doc_ids=doc_ids,
            reps=3,
            predictions=predictions,
            document_texts={doc_id: f"EXEMPLAR BODY {doc_id}" for doc_id in doc_ids},
        )

        pack = self.build_pack()
        exemplars = pack[pack.index("## Exemplar documents") :]

        self.assertIn("EXEMPLAR BODY doc-d", exemplars)
        self.assertIn("EXEMPLAR BODY doc-b", exemplars)
        self.assertNotIn("EXEMPLAR BODY doc-a", exemplars)
        self.assertNotIn("EXEMPLAR BODY doc-c", exemplars)
        self.assertLess(
            exemplars.index("EXEMPLAR BODY doc-d"),
            exemplars.index("EXEMPLAR BODY doc-b"),
        )

    def test_document_selected_for_multiple_fields_is_included_once(self) -> None:
        doc_ids = ("doc-a", "doc-b", "doc-c")
        predictions = {}
        for doc_id in doc_ids:
            prediction = gold_record(doc_id)
            if doc_id in ("doc-a", "doc-b"):
                prediction = dict(prediction, landlord_name="Wrong landlord")
            if doc_id in ("doc-a", "doc-c"):
                prediction = dict(prediction, tenant_name="Wrong tenant")
            predictions[(doc_id, 1)] = prediction
        self.write_batch(
            doc_ids=doc_ids,
            predictions=predictions,
            document_texts={
                "doc-a": "SHARED EXEMPLAR BODY",
                "doc-b": "LANDLORD EXEMPLAR BODY",
                "doc-c": "TENANT EXEMPLAR BODY",
            },
        )

        pack = self.build_pack()
        exemplars = pack[pack.index("## Exemplar documents") :]

        self.assertEqual(exemplars.count("SHARED EXEMPLAR BODY"), 1)
        self.assertIn(
            "Wrong fields exemplified: `landlord_name`, `tenant_name`", exemplars
        )

    def test_footer_is_present_verbatim(self) -> None:
        self.write_batch()

        pack = self.build_pack()

        self.assertTrue(pack.endswith(FOOTER + "\n"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
