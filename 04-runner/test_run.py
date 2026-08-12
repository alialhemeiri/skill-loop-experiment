#!/usr/bin/env python3
"""Stdlib integration tests for the frozen autoresearch batch runner."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock


RUNNER_PATH = Path(__file__).with_name("run.py")

EXPECTED_SCHEMA_INSTRUCTION = (
    "Extract the following 12 fields from the document above and output ONLY a single JSON "
    "object — no markdown fences, no commentary. Keys and types: landlord_name (string), "
    "tenant_name (string), unit_number (string), community (string), contract_start_date "
    "(string, YYYY-MM-DD), contract_end_date (string, YYYY-MM-DD), annual_rent_aed (integer), "
    "security_deposit_aed (integer or null), number_of_payments (integer), notice_period_days "
    "(integer or null), early_termination_penalty_months (number or null), furnished_status "
    '(one of "furnished", "semi-furnished", "unfurnished", or null). Use null for any field the '
    "document does not state."
)

FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

log_path = Path(os.environ["FAKE_CLAUDE_LOG"])

if sys.argv[1:] == ["--version"]:
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"kind": "version", "cwd": os.getcwd()}) + "\n")
    print("9.9.9 (Claude Code)")
    raise SystemExit(0)

prompt = sys.stdin.buffer.read().decode("utf-8")
with log_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({
        "kind": "worker",
        "args": sys.argv[1:],
        "cwd": os.getcwd(),
        "prompt": prompt,
    }, ensure_ascii=False) + "\n")

state_path = Path(os.environ["FAKE_CLAUDE_STATE"])
attempt = int(state_path.read_text(encoding="utf-8")) if state_path.exists() else 0
state_path.write_text(str(attempt + 1), encoding="utf-8")
sequence = os.environ.get("FAKE_CLAUDE_SEQUENCE", "success").split(",")
action = sequence[min(attempt, len(sequence) - 1)]

if action == "nonzero":
    print("simulated transport error", file=sys.stderr)
    raise SystemExit(7)
if action == "empty":
    raise SystemExit(0)
if action == "malformed":
    sys.stdout.write("not-cli-json")
    raise SystemExit(0)
if action == "empty-envelope":
    sys.stdout.write("{}")
    raise SystemExit(0)
if action == "array-envelope":
    sys.stdout.write("[]")
    raise SystemExit(0)

result_text = os.environ.get("FAKE_CLAUDE_RESULT", '{"landlord_name":"CAMILA DUARTE"}\n')
if action == "model-invalid":
    result_text = "not-model-json"

payload = {
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "duration_ms": 1200,
    "duration_api_ms": 900,
    "result": result_text,
    "num_turns": 1,
    "usage": {"input_tokens": 123, "output_tokens": 45},
    "modelUsage": {
        "claude-sonnet-5": {
            "inputTokens": 123,
            "outputTokens": 45,
            "cacheReadInputTokens": 0,
            "cacheCreationInputTokens": 0,
            "webSearchRequests": 0,
            "costUSD": 0,
            "contextWindow": 200000,
            "maxOutputTokens": 64000,
        }
    },
    "permission_denials": [],
    "session_id": "fake-session",
    "uuid": "fake-uuid",
    "stop_reason": None,
    "terminal_reason": None,
    "api_error_status": None,
    "fast_mode_state": "off",
    "fast_mode_disabled_reason": None,
    "time_to_request_ms": 10,
    "ttft_ms": 20,
    "ttft_stream_ms": 15,
    "total_cost_usd": 0,
}
if action == "cli-error-envelope":
    payload["subtype"] = "error_during_execution"
    payload["is_error"] = True
if action == "turns-two":
    payload["num_turns"] = 2
if action == "permission-denied":
    payload["permission_denials"] = [{"tool_name": "Read", "reason": "denied"}]
if action == "model-metadata":
    payload["canonicalModel"] = "claude-sonnet-5-20260801"
    payload["provider"] = "anthropic"
envelope_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
if action in {"turns-two", "permission-denied"}:
    envelope_text = "\n  " + envelope_text + " \n"
sys.stdout.write(envelope_text)
'''


def load_runner():
    spec = importlib.util.spec_from_file_location("autoresearch_runner_under_test", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not create import spec for run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RunnerIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(RUNNER_PATH.is_file(), "run.py must exist before runner tests can pass")
        self.runner = load_runner()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name) / "project"
        self.worker_cwd = Path(self.temp_dir.name) / "worker-cwd"
        self.log_path = Path(self.temp_dir.name) / "claude-log.jsonl"
        self.state_path = Path(self.temp_dir.name) / "claude-state.txt"

        (self.root / "00-control").mkdir(parents=True)
        (self.root / "03-skill" / "versions" / "v0").mkdir(parents=True)
        (self.root / "01-fixtures" / "docs" / "train").mkdir(parents=True)
        (self.root / "01-fixtures" / "gold").mkdir(parents=True)
        (self.root / "04-runner").mkdir(parents=True)
        (self.root / "05-runs").mkdir(parents=True)

        self.skill_rel = Path("03-skill/versions/v0/SKILL.md")
        self.docs_rel = Path("01-fixtures/docs/train")
        self.skill_text = "Extract tenancy terms carefully.\n"
        self.document_text = "The Landlord is CAMILA DUARTE.\n"
        (self.root / self.skill_rel).write_text(self.skill_text, encoding="utf-8")
        (self.root / self.docs_rel / "doc-01.txt").write_text(
            self.document_text, encoding="utf-8"
        )
        self.gold_bytes = b'{"landlord_name":"CAMILA DUARTE"}\n'
        for doc_id in ("doc-01", "doc-02", "doc-11", "doc-12"):
            (self.root / "01-fixtures" / "gold" / f"{doc_id}.json").write_bytes(
                self.gold_bytes
            )
        (self.root / "00-control" / "worker-system-prompt.txt").write_text(
            "SYSTEM\nPROMPT", encoding="utf-8"
        )

        self.fake_claude = Path(self.temp_dir.name) / "fake-claude"
        self.fake_claude.write_text(FAKE_CLAUDE, encoding="utf-8")
        self.fake_claude.chmod(0o755)
        self.worker_config = {
            "cli": str(self.fake_claude),
            "cli_version": "9.9.9 (Claude Code)",
            "model": "claude-sonnet-5",
            "system_prompt_file": "00-control/worker-system-prompt.txt",
            "invocation": {
                "prompt_via": "stdin",
                "args_template": [
                    "-p",
                    "--model",
                    "claude-sonnet-5",
                    "--system-prompt",
                    "<contents of system_prompt_file>",
                    "--exclude-dynamic-system-prompt-sections",
                    "--no-session-persistence",
                    "--output-format",
                    "json",
                ],
            },
            "transport_retry_rule": "Retry max 2 only on transport failures.",
        }
        self.worker_path = self.root / "00-control" / "worker.json"
        self.worker_path.write_text(
            json.dumps(self.worker_config, indent=2) + "\n", encoding="utf-8"
        )

    def invoke(
        self,
        *,
        sequence: str = "success",
        result_text: str | None = None,
        argv: list[str] | None = None,
    ):
        env = {
            "FAKE_CLAUDE_LOG": str(self.log_path),
            "FAKE_CLAUDE_STATE": str(self.state_path),
            "FAKE_CLAUDE_SEQUENCE": sequence,
        }
        if result_text is not None:
            env["FAKE_CLAUDE_RESULT"] = result_text
        stdout = io.StringIO()
        stderr = io.StringIO()
        if argv is None:
            argv = [
                "--skill",
                str(self.skill_rel),
                "--docs-dir",
                str(self.docs_rel),
                "--reps",
                "1",
                "--batch-id",
                "test-batch",
                "--sleep-between",
                "0",
            ]
        with mock.patch.dict(os.environ, env, clear=False):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = self.runner.main(
                    argv, project_root=self.root, worker_cwd=self.worker_cwd
                )
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def read_cli_log(self) -> list[dict]:
        return [
            json.loads(line)
            for line in self.log_path.read_text(encoding="utf-8").splitlines()
        ]

    def holdout_argv(self, batch_id: str, *, skill_rel: Path | None = None) -> list[str]:
        return [
            "--skill",
            str(skill_rel or self.skill_rel),
            "--docs-dir",
            "01-fixtures/docs/holdout",
            "--reps",
            "1",
            "--batch-id",
            batch_id,
            "--sleep-between",
            "0",
            "--allow-holdout",
        ]

    def write_finalist_skill(self, number: int) -> Path:
        relative = Path(f"03-skill/versions/finalist-{number}/SKILL.md")
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"Finalist skill {number}.\n", encoding="utf-8")
        return relative

    def test_successful_batch_uses_frozen_invocation_and_writes_exact_artifacts(self) -> None:
        model_text = '{"landlord_name":"CAMILA DUARTE","note":"café"}\n'

        exit_code, stdout, stderr = self.invoke(result_text=model_text)

        self.assertEqual(exit_code, 0, stderr)
        self.assertEqual(stderr, "")
        self.assertIn("1 completed", stdout)
        calls = self.read_cli_log()
        self.assertEqual([call["kind"] for call in calls], ["version", "worker"])
        self.assertEqual(calls[0]["cwd"], str(self.worker_cwd))
        worker_call = calls[1]
        self.assertEqual(worker_call["cwd"], str(self.worker_cwd))
        self.assertEqual(
            worker_call["args"],
            [
                "-p",
                "--model",
                "claude-sonnet-5",
                "--system-prompt",
                "SYSTEM\nPROMPT",
                "--exclude-dynamic-system-prompt-sections",
                "--no-session-persistence",
                "--output-format",
                "json",
            ],
        )
        self.assertEqual(
            worker_call["prompt"],
            self.skill_text
            + "\n\n---\n\nDOCUMENT:\n\n"
            + self.document_text
            + "\n\n---\n\n"
            + EXPECTED_SCHEMA_INSTRUCTION,
        )

        batch_dir = self.root / "05-runs" / "test-batch"
        raw_text_path = batch_dir / "raw" / "doc-01-rep1.raw.txt"
        pred_path = batch_dir / "preds" / "rep1" / "doc-01.json"
        result_path = batch_dir / "raw" / "doc-01-rep1.result.json"
        self.assertEqual(raw_text_path.read_bytes(), model_text.encode("utf-8"))
        self.assertEqual(
            pred_path.read_bytes(),
            b'{"landlord_name":"CAMILA DUARTE","note":"caf\xc3\xa9"}',
        )
        cli_result = json.loads(result_path.read_bytes())
        self.assertEqual(cli_result["num_turns"], 1)
        self.assertIn("claude-sonnet-5", cli_result["modelUsage"])
        self.assertEqual(cli_result["result"], model_text)

        manifest = json.loads((batch_dir / "manifest.json").read_bytes())
        self.assertEqual(manifest["batch_id"], "test-batch")
        self.assertEqual(manifest["model"], "claude-sonnet-5")
        self.assertEqual(manifest["cli"]["version"], "9.9.9 (Claude Code)")
        self.assertEqual(manifest["skill"]["path"], self.skill_rel.as_posix())
        self.assertEqual(
            manifest["skill"]["sha256"],
            hashlib.sha256(self.skill_text.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(
            manifest["worker"]["sha256"],
            hashlib.sha256(self.worker_path.read_bytes()).hexdigest(),
        )
        self.assertIn("runner", manifest)
        self.assertEqual(
            manifest["runner"],
            {
                "path": str(RUNNER_PATH.resolve()),
                "sha256": hashlib.sha256(RUNNER_PATH.read_bytes()).hexdigest(),
            },
        )
        self.assertIn("fixed_schema_sha256", manifest)
        self.assertEqual(
            manifest["fixed_schema_sha256"],
            hashlib.sha256(EXPECTED_SCHEMA_INSTRUCTION.encode("utf-8")).hexdigest(),
        )
        system_prompt_path = self.root / "00-control" / "worker-system-prompt.txt"
        self.assertIn("system_prompt", manifest)
        self.assertEqual(
            manifest["system_prompt"],
            {
                "path": "00-control/worker-system-prompt.txt",
                "sha256": hashlib.sha256(system_prompt_path.read_bytes()).hexdigest(),
            },
        )
        document_path = self.root / self.docs_rel / "doc-01.txt"
        self.assertIn("documents", manifest)
        self.assertEqual(
            manifest["documents"],
            {
                "doc-01": {
                    "path": f"{self.docs_rel.as_posix()}/doc-01.txt",
                    "sha256": hashlib.sha256(document_path.read_bytes()).hexdigest(),
                }
            },
        )
        self.assertEqual(manifest["wall_clock_seconds"] >= 0, True)
        self.assertRegex(manifest["started_at"], re.compile(r"^\d{4}-\d\d-\d\dT"))
        self.assertRegex(manifest["finished_at"], re.compile(r"Z$"))
        self.assertEqual(manifest["summary"]["completed"], 1)
        self.assertEqual(manifest["summary"]["transport_failures"], 0)
        self.assertEqual(len(manifest["runs"]), 1)
        run = manifest["runs"][0]
        self.assertEqual(run["doc_id"], "doc-01")
        self.assertEqual(run["rep"], 1)
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["attempts"], 1)
        self.assertEqual(len(run["retry_log"]), 1)
        self.assertEqual(run["retry_log"][0]["status"], "success")
        self.assertEqual(run["fence_stripped"], False)
        self.assertEqual(run["model_usage_keys"], ["claude-sonnet-5"])

    def test_new_batch_snapshots_exact_document_and_gold_bytes(self) -> None:
        exit_code, _stdout, stderr = self.invoke()

        self.assertEqual(exit_code, 0, stderr)
        batch_dir = self.root / "05-runs" / "test-batch"
        document_bytes = self.document_text.encode("utf-8")
        self.assertEqual(
            (batch_dir / "fixtures" / "docs" / "doc-01.txt").read_bytes(),
            document_bytes,
        )
        self.assertEqual(
            (batch_dir / "fixtures" / "gold" / "doc-01.json").read_bytes(),
            self.gold_bytes,
        )
        snapshots = json.loads((batch_dir / "manifest.json").read_bytes())[
            "fixture_snapshots"
        ]
        self.assertEqual(
            snapshots,
            {
                "documents": {
                    "doc-01": {
                        "path": "fixtures/docs/doc-01.txt",
                        "sha256": hashlib.sha256(document_bytes).hexdigest(),
                    }
                },
                "gold": {
                    "doc-01": {
                        "path": "fixtures/gold/doc-01.json",
                        "sha256": hashlib.sha256(self.gold_bytes).hexdigest(),
                    }
                },
            },
        )

    def test_resume_refuses_doctored_document_or_gold_snapshot(self) -> None:
        for batch_id, relative in (
            ("doctored-doc-snapshot", Path("fixtures/docs/doc-01.txt")),
            ("doctored-gold-snapshot", Path("fixtures/gold/doc-01.json")),
        ):
            with self.subTest(relative=relative.as_posix()):
                argv = [
                    "--skill",
                    str(self.skill_rel),
                    "--docs-dir",
                    str(self.docs_rel),
                    "--reps",
                    "1",
                    "--batch-id",
                    batch_id,
                    "--sleep-between",
                    "0",
                ]
                first_code, _first_stdout, first_stderr = self.invoke(argv=argv)
                self.assertEqual(first_code, 0, first_stderr)
                snapshot_path = self.root / "05-runs" / batch_id / relative
                snapshot_path.write_bytes(snapshot_path.read_bytes() + b"doctored")
                worker_calls_before = len(
                    [call for call in self.read_cli_log() if call["kind"] == "worker"]
                )

                resumed_code, _resumed_stdout, resumed_stderr = self.invoke(argv=argv)

                self.assertEqual(resumed_code, 2)
                self.assertIn("fixture snapshot mismatch", resumed_stderr)
                self.assertIn("doc-01", resumed_stderr)
                worker_calls_after = len(
                    [call for call in self.read_cli_log() if call["kind"] == "worker"]
                )
                self.assertEqual(worker_calls_after, worker_calls_before)

    def test_fenced_valid_result_strips_one_plain_fence_only_from_prediction(self) -> None:
        original = '  ```\n{"landlord_name":"CAMILA DUARTE"}\n```  \n'

        exit_code, _stdout, stderr = self.invoke(result_text=original)

        self.assertEqual(exit_code, 0, stderr)
        batch_dir = self.root / "05-runs" / "test-batch"
        self.assertEqual(
            (batch_dir / "preds" / "rep1" / "doc-01.json").read_bytes(),
            b'{"landlord_name":"CAMILA DUARTE"}',
        )
        self.assertEqual(
            (batch_dir / "raw" / "doc-01-rep1.raw.txt").read_bytes(),
            original.encode("utf-8"),
        )
        envelope = json.loads(
            (batch_dir / "raw" / "doc-01-rep1.result.json").read_bytes()
        )
        self.assertEqual(envelope["result"], original)
        run = json.loads((batch_dir / "manifest.json").read_bytes())["runs"][0]
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["fence_stripped"], True)

    def test_fenced_invalid_result_is_model_failure_after_strip(self) -> None:
        original = "```\nnot json\n```"

        exit_code, stdout, stderr = self.invoke(result_text=original)

        self.assertEqual(exit_code, 0, stderr)
        self.assertIn("1 model failures", stdout)
        batch_dir = self.root / "05-runs" / "test-batch"
        self.assertEqual(
            (batch_dir / "preds" / "rep1" / "doc-01.json").read_bytes(), b"not json"
        )
        self.assertEqual(
            (batch_dir / "raw" / "doc-01-rep1.raw.txt").read_bytes(),
            original.encode("utf-8"),
        )
        run = json.loads((batch_dir / "manifest.json").read_bytes())["runs"][0]
        self.assertEqual(run["status"], "model_failure")
        self.assertEqual(run["model_output_valid_json"], False)
        self.assertEqual(run["fence_stripped"], True)

    def test_unfenced_result_is_trimmed_without_fence_flag(self) -> None:
        original = ' \r\n\t{"landlord_name":"CAMILA DUARTE"}\r\n '

        exit_code, _stdout, stderr = self.invoke(result_text=original)

        self.assertEqual(exit_code, 0, stderr)
        batch_dir = self.root / "05-runs" / "test-batch"
        self.assertEqual(
            (batch_dir / "preds" / "rep1" / "doc-01.json").read_bytes(),
            b'{"landlord_name":"CAMILA DUARTE"}',
        )
        self.assertEqual(
            (batch_dir / "raw" / "doc-01-rep1.raw.txt").read_bytes(),
            original.encode("utf-8"),
        )
        run = json.loads((batch_dir / "manifest.json").read_bytes())["runs"][0]
        self.assertEqual(run["fence_stripped"], False)

    def test_language_tagged_fence_is_stripped(self) -> None:
        original = '```json\n{"landlord_name":"CAMILA DUARTE"}\n```'

        exit_code, _stdout, stderr = self.invoke(result_text=original)

        self.assertEqual(exit_code, 0, stderr)
        batch_dir = self.root / "05-runs" / "test-batch"
        self.assertEqual(
            (batch_dir / "preds" / "rep1" / "doc-01.json").read_bytes(),
            b'{"landlord_name":"CAMILA DUARTE"}',
        )
        run = json.loads((batch_dir / "manifest.json").read_bytes())["runs"][0]
        self.assertEqual(run["fence_stripped"], True)

    def test_nested_fences_strip_only_one_pair_and_remain_model_failure(self) -> None:
        original = '```json\n```\n{"landlord_name":"CAMILA DUARTE"}\n```\n```'

        exit_code, _stdout, stderr = self.invoke(result_text=original)

        self.assertEqual(exit_code, 0, stderr)
        batch_dir = self.root / "05-runs" / "test-batch"
        self.assertEqual(
            (batch_dir / "preds" / "rep1" / "doc-01.json").read_bytes(),
            b'```\n{"landlord_name":"CAMILA DUARTE"}\n```',
        )
        run = json.loads((batch_dir / "manifest.json").read_bytes())["runs"][0]
        self.assertEqual(run["status"], "model_failure")
        self.assertEqual(run["fence_stripped"], True)

    def test_model_provenance_fields_are_recorded_when_envelope_provides_them(self) -> None:
        exit_code, _stdout, stderr = self.invoke(sequence="model-metadata")

        self.assertEqual(exit_code, 0, stderr)
        run = json.loads(
            (self.root / "05-runs" / "test-batch" / "manifest.json").read_bytes()
        )["runs"][0]
        self.assertEqual(run["model_usage_keys"], ["claude-sonnet-5"])
        self.assertEqual(run["canonical_model"], "claude-sonnet-5-20260801")
        self.assertEqual(run["provider"], "anthropic")

    def test_prompt_preserves_crlf_bytes_from_all_three_input_files(self) -> None:
        skill_bytes = b"Skill line one\r\nSkill line two\r\n"
        document_bytes = b"Document line one\r\nDocument line two\r\n"
        system_prompt_bytes = b"System line one\r\nSystem line two\r\n"
        (self.root / self.skill_rel).write_bytes(skill_bytes)
        (self.root / self.docs_rel / "doc-01.txt").write_bytes(document_bytes)
        (self.root / "00-control" / "worker-system-prompt.txt").write_bytes(
            system_prompt_bytes
        )

        exit_code, _stdout, stderr = self.invoke()

        self.assertEqual(exit_code, 0, stderr)
        worker_call = [call for call in self.read_cli_log() if call["kind"] == "worker"][0]
        system_index = worker_call["args"].index("--system-prompt") + 1
        self.assertEqual(
            worker_call["args"][system_index], system_prompt_bytes.decode("utf-8")
        )
        self.assertEqual(
            worker_call["prompt"],
            skill_bytes.decode("utf-8")
            + "\n\n---\n\nDOCUMENT:\n\n"
            + document_bytes.decode("utf-8")
            + "\n\n---\n\n"
            + EXPECTED_SCHEMA_INSTRUCTION,
        )

    def test_retries_nonzero_and_empty_transport_failures_then_succeeds(self) -> None:
        exit_code, _stdout, stderr = self.invoke(sequence="nonzero,empty,success")

        self.assertEqual(exit_code, 0, stderr)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 3)
        manifest = json.loads(
            (self.root / "05-runs" / "test-batch" / "manifest.json").read_bytes()
        )
        run = manifest["runs"][0]
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["attempts"], 3)
        self.assertEqual(
            [entry["status"] for entry in run["retry_log"]],
            ["transport_failure", "transport_failure", "success"],
        )
        self.assertEqual(run["retry_log"][0]["reason"], "nonzero CLI exit (7)")
        self.assertEqual(run["retry_log"][1]["reason"], "empty stdout")

    def test_retries_unparseable_cli_result_json(self) -> None:
        exit_code, _stdout, stderr = self.invoke(sequence="malformed,success")

        self.assertEqual(exit_code, 0, stderr)
        manifest = json.loads(
            (self.root / "05-runs" / "test-batch" / "manifest.json").read_bytes()
        )
        run = manifest["runs"][0]
        self.assertEqual(run["attempts"], 2)
        self.assertEqual(
            run["retry_log"][0]["reason"], "stdout unparseable as CLI result JSON"
        )
        self.assertEqual(run["retry_log"][1]["status"], "success")

    def test_retries_json_that_is_not_a_claude_result_envelope(self) -> None:
        exit_code, _stdout, stderr = self.invoke(
            sequence="empty-envelope,array-envelope,success"
        )

        self.assertEqual(exit_code, 0, stderr)
        manifest = json.loads(
            (self.root / "05-runs" / "test-batch" / "manifest.json").read_bytes()
        )
        run = manifest["runs"][0]
        self.assertEqual(run["attempts"], 3)
        self.assertEqual(
            [entry["reason"] for entry in run["retry_log"]],
            [
                "stdout unparseable as CLI result JSON",
                "stdout unparseable as CLI result JSON",
                None,
            ],
        )
        self.assertEqual(run["status"], "completed")

    def test_retries_claude_error_envelope_even_when_process_exits_zero(self) -> None:
        exit_code, _stdout, stderr = self.invoke(
            sequence="cli-error-envelope,success"
        )

        self.assertEqual(exit_code, 0, stderr)
        manifest = json.loads(
            (self.root / "05-runs" / "test-batch" / "manifest.json").read_bytes()
        )
        run = manifest["runs"][0]
        self.assertEqual(run["attempts"], 2)
        self.assertEqual(
            run["retry_log"][0]["reason"],
            "stdout unparseable as CLI result JSON",
        )
        self.assertEqual(run["retry_log"][1]["status"], "success")

    def test_retries_success_envelope_with_more_than_one_turn(self) -> None:
        exit_code, _stdout, stderr = self.invoke(
            sequence="turns-two,success",
            result_text='{"note":"café"}',
        )

        self.assertEqual(exit_code, 0, stderr)
        batch_dir = self.root / "05-runs" / "test-batch"
        run = json.loads((batch_dir / "manifest.json").read_bytes())["runs"][0]
        self.assertEqual(run["attempts"], 2)
        self.assertEqual(run["retry_log"][0]["status"], "transport_failure")
        self.assertEqual(run["retry_log"][0]["reason"], "CLI result used 2 turns")
        self.assertEqual(run["retry_log"][1]["status"], "success")
        rejected = (
            batch_dir / "raw" / "doc-01-rep1-attempt1.rejected.json"
        ).read_bytes()
        self.assertTrue(rejected.startswith(b"\n  {"))
        self.assertTrue(rejected.endswith(b"} \n"))
        self.assertIn('café'.encode("utf-8"), rejected)
        self.assertEqual(json.loads(rejected)["num_turns"], 2)

    def test_retries_success_envelope_with_permission_denials(self) -> None:
        exit_code, _stdout, stderr = self.invoke(sequence="permission-denied,success")

        self.assertEqual(exit_code, 0, stderr)
        batch_dir = self.root / "05-runs" / "test-batch"
        run = json.loads((batch_dir / "manifest.json").read_bytes())["runs"][0]
        self.assertEqual(run["attempts"], 2)
        self.assertEqual(run["retry_log"][0]["status"], "transport_failure")
        self.assertEqual(
            run["retry_log"][0]["reason"], "CLI result contained permission denials"
        )
        self.assertEqual(run["retry_log"][1]["status"], "success")
        rejected = (
            batch_dir / "raw" / "doc-01-rep1-attempt1.rejected.json"
        ).read_bytes()
        self.assertTrue(rejected.startswith(b"\n  {"))
        self.assertTrue(rejected.endswith(b"} \n"))
        self.assertEqual(
            json.loads(rejected)["permission_denials"],
            [{"tool_name": "Read", "reason": "denied"}],
        )

    def test_invalid_model_json_is_stored_as_model_failure_without_retry(self) -> None:
        exit_code, stdout, stderr = self.invoke(sequence="model-invalid")

        self.assertEqual(exit_code, 0, stderr)
        self.assertIn("1 model failures", stdout)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 1)
        batch_dir = self.root / "05-runs" / "test-batch"
        self.assertEqual(
            (batch_dir / "raw" / "doc-01-rep1.raw.txt").read_bytes(), b"not-model-json"
        )
        self.assertEqual(
            (batch_dir / "preds" / "rep1" / "doc-01.json").read_bytes(),
            b"not-model-json",
        )
        manifest = json.loads((batch_dir / "manifest.json").read_bytes())
        run = manifest["runs"][0]
        self.assertEqual(run["status"], "model_failure")
        self.assertEqual(run["attempts"], 1)
        self.assertEqual(run["model_output_valid_json"], False)
        self.assertEqual(manifest["summary"]["model_failures"], 1)
        self.assertEqual(manifest["summary"]["transport_failures"], 0)

    def test_missing_model_failure_artifacts_abort_instead_of_rerolling(self) -> None:
        first_code, _first_stdout, first_stderr = self.invoke(sequence="model-invalid")
        self.assertEqual(first_code, 0, first_stderr)
        batch_dir = self.root / "05-runs" / "test-batch"
        for path in [
            batch_dir / "raw" / "doc-01-rep1.result.json",
            batch_dir / "raw" / "doc-01-rep1.raw.txt",
            batch_dir / "preds" / "rep1" / "doc-01.json",
        ]:
            path.unlink()

        second_code, _second_stdout, second_stderr = self.invoke(sequence="success")

        self.assertEqual(second_code, 2)
        self.assertIn("terminal model result artifacts are missing", second_stderr)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 1)

    def test_missing_completed_artifacts_abort_instead_of_rerolling(self) -> None:
        first_code, _first_stdout, first_stderr = self.invoke()
        self.assertEqual(first_code, 0, first_stderr)
        batch_dir = self.root / "05-runs" / "test-batch"
        for path in [
            batch_dir / "raw" / "doc-01-rep1.result.json",
            batch_dir / "raw" / "doc-01-rep1.raw.txt",
            batch_dir / "preds" / "rep1" / "doc-01.json",
        ]:
            path.unlink()

        second_code, _second_stdout, second_stderr = self.invoke(sequence="success")

        self.assertEqual(second_code, 2)
        self.assertIn("terminal model result artifacts are missing", second_stderr)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 1)

    def test_terminal_transport_failure_stops_after_two_retries_and_exits_nonzero(self) -> None:
        exit_code, stdout, stderr = self.invoke(sequence="nonzero")

        self.assertEqual(exit_code, 1, stderr)
        self.assertIn("1 transport failures", stdout)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 3)
        batch_dir = self.root / "05-runs" / "test-batch"
        self.assertFalse((batch_dir / "raw" / "doc-01-rep1.raw.txt").exists())
        self.assertFalse((batch_dir / "raw" / "doc-01-rep1.result.json").exists())
        self.assertFalse((batch_dir / "preds" / "rep1" / "doc-01.json").exists())
        manifest = json.loads((batch_dir / "manifest.json").read_bytes())
        run = manifest["runs"][0]
        self.assertEqual(run["status"], "transport_failure")
        self.assertEqual(run["attempts"], 3)
        self.assertEqual(
            [entry["will_retry"] for entry in run["retry_log"]], [True, True, False]
        )
        self.assertEqual(manifest["summary"]["transport_failures"], 1)

    def test_terminal_transport_failure_is_not_given_a_new_budget_on_resume(self) -> None:
        first_code, _first_stdout, first_stderr = self.invoke(sequence="nonzero")
        self.assertEqual(first_code, 1, first_stderr)

        second_code, _second_stdout, second_stderr = self.invoke(sequence="success")

        self.assertEqual(second_code, 1, second_stderr)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 3)
        manifest = json.loads(
            (self.root / "05-runs" / "test-batch" / "manifest.json").read_bytes()
        )
        run = manifest["runs"][0]
        self.assertEqual(run["status"], "transport_failure")
        self.assertEqual(run["attempts"], 3)
        self.assertEqual(len(run["retry_log"]), 3)
        self.assertEqual(run["retry_budget_exhausted_resumes"], 1)

    def test_resume_logs_interrupted_attempt_and_uses_only_remaining_budget(self) -> None:
        first_code, _first_stdout, first_stderr = self.invoke(sequence="nonzero")
        self.assertEqual(first_code, 1, first_stderr)
        manifest_path = self.root / "05-runs" / "test-batch" / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        run = manifest["runs"][0]
        run["status"] = "retrying"
        run["finished_at"] = None
        run["attempts"] = 2
        run["retry_log"] = run["retry_log"][:1]
        run["active_attempt"] = {"attempt": 2, "started_at": run["started_at"]}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        second_code, _second_stdout, second_stderr = self.invoke(sequence="success")

        self.assertEqual(second_code, 0, second_stderr)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 4)
        resumed_run = json.loads(manifest_path.read_bytes())["runs"][0]
        self.assertEqual(resumed_run["status"], "completed")
        self.assertEqual(resumed_run["attempts"], 3)
        self.assertEqual(len(resumed_run["retry_log"]), 3)
        self.assertEqual(
            resumed_run["retry_log"][1]["reason"],
            "interrupted before a CLI result was persisted",
        )
        self.assertEqual(resumed_run["retry_log"][1]["recovered_on_resume"], True)
        self.assertEqual(resumed_run["retry_log"][2]["status"], "success")

    def test_existing_raw_text_is_skipped_on_idempotent_resume(self) -> None:
        first_code, _first_stdout, first_stderr = self.invoke()
        self.assertEqual(first_code, 0, first_stderr)
        batch_dir = self.root / "05-runs" / "test-batch"
        first_manifest = json.loads((batch_dir / "manifest.json").read_bytes())
        first_result_bytes = (batch_dir / "raw" / "doc-01-rep1.result.json").read_bytes()
        pred_path = batch_dir / "preds" / "rep1" / "doc-01.json"
        expected_pred_bytes = pred_path.read_bytes()
        pred_path.unlink()

        second_code, second_stdout, second_stderr = self.invoke()

        self.assertEqual(second_code, 0, second_stderr)
        self.assertIn("1 skipped", second_stdout)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 1)
        self.assertEqual(
            (batch_dir / "raw" / "doc-01-rep1.result.json").read_bytes(),
            first_result_bytes,
        )
        self.assertEqual(pred_path.read_bytes(), expected_pred_bytes)
        resumed_manifest = json.loads((batch_dir / "manifest.json").read_bytes())
        self.assertEqual(len(resumed_manifest["runs"]), 1)
        self.assertEqual(resumed_manifest["runs"][0]["status"], "completed")
        self.assertEqual(
            resumed_manifest["runs"][0]["retry_log"],
            first_manifest["runs"][0]["retry_log"],
        )
        self.assertEqual(resumed_manifest["summary"]["skipped_existing"], 1)
        self.assertEqual(resumed_manifest["runs"][0]["resume_skips"], 1)

    def test_raw_sentinel_reconciles_a_stale_retrying_manifest_after_crash(self) -> None:
        first_code, _first_stdout, first_stderr = self.invoke()
        self.assertEqual(first_code, 0, first_stderr)
        manifest_path = self.root / "05-runs" / "test-batch" / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["runs"][0]["status"] = "retrying"
        manifest["runs"][0]["finished_at"] = None
        manifest["runs"][0]["model_output_valid_json"] = False
        manifest["runs"][0]["retry_log"] = []
        manifest["runs"][0]["attempts"] = 1
        manifest["runs"][0]["active_attempt"] = {
            "attempt": 1,
            "started_at": manifest["runs"][0]["started_at"],
        }
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        second_code, _second_stdout, second_stderr = self.invoke()

        self.assertEqual(second_code, 0, second_stderr)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 1)
        reconciled = json.loads(manifest_path.read_bytes())
        run = reconciled["runs"][0]
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["model_output_valid_json"], True)
        self.assertEqual(run["recovered_from_raw"], True)
        self.assertIsNotNone(run["finished_at"])
        self.assertEqual(len(run["retry_log"]), 1)
        self.assertEqual(run["retry_log"][0]["attempt"], 1)
        self.assertEqual(run["retry_log"][0]["status"], "success")
        self.assertEqual(run["retry_log"][0]["recovered_from_raw"], True)
        self.assertEqual(run["retry_log"][0]["will_retry"], False)
        self.assertEqual(reconciled["summary"]["completed"], 1)

    def test_resume_recovers_raw_and_prediction_from_forensic_result_without_rerun(self) -> None:
        first_code, _first_stdout, first_stderr = self.invoke()
        self.assertEqual(first_code, 0, first_stderr)
        batch_dir = self.root / "05-runs" / "test-batch"
        raw_path = batch_dir / "raw" / "doc-01-rep1.raw.txt"
        pred_path = batch_dir / "preds" / "rep1" / "doc-01.json"
        expected_result = raw_path.read_bytes()
        raw_path.unlink()
        pred_path.unlink()
        manifest_path = batch_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        run = manifest["runs"][0]
        run["status"] = "running"
        run["finished_at"] = None
        run["retry_log"] = []
        run["attempts"] = 1
        run["active_attempt"] = {"attempt": 1, "started_at": run["started_at"]}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        second_code, _second_stdout, second_stderr = self.invoke()

        self.assertEqual(second_code, 0, second_stderr)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 1)
        self.assertEqual(raw_path.read_bytes(), expected_result)
        self.assertEqual(pred_path.read_bytes(), expected_result.strip())
        recovered = json.loads(manifest_path.read_bytes())["runs"][0]
        self.assertEqual(recovered["status"], "completed")
        self.assertEqual(recovered["recovered_from_result_json"], True)
        self.assertEqual(recovered["retry_log"][0]["recovered_from_result_json"], True)

    def test_raw_sentinel_refuses_a_missing_forensic_result(self) -> None:
        first_code, _first_stdout, first_stderr = self.invoke()
        self.assertEqual(first_code, 0, first_stderr)
        batch_dir = self.root / "05-runs" / "test-batch"
        (batch_dir / "raw" / "doc-01-rep1.result.json").unlink()

        second_code, _second_stdout, second_stderr = self.invoke()

        self.assertEqual(second_code, 2)
        self.assertIn("raw sentinel has no forensic CLI result", second_stderr)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 1)

    def test_raw_sentinel_refuses_a_mismatched_forensic_result(self) -> None:
        first_code, _first_stdout, first_stderr = self.invoke()
        self.assertEqual(first_code, 0, first_stderr)
        batch_dir = self.root / "05-runs" / "test-batch"
        result_path = batch_dir / "raw" / "doc-01-rep1.result.json"
        envelope = json.loads(result_path.read_bytes())
        envelope["result"] = '{"landlord_name":"DIFFERENT"}'
        result_path.write_text(json.dumps(envelope), encoding="utf-8")

        second_code, _second_stdout, second_stderr = self.invoke()

        self.assertEqual(second_code, 2)
        self.assertIn("raw sentinel does not match forensic CLI result", second_stderr)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 1)

    def test_nonempty_batch_without_manifest_is_not_adopted(self) -> None:
        first_code, _first_stdout, first_stderr = self.invoke()
        self.assertEqual(first_code, 0, first_stderr)
        batch_dir = self.root / "05-runs" / "test-batch"
        manifest_path = batch_dir / "manifest.json"
        manifest_path.unlink()

        second_code, _second_stdout, second_stderr = self.invoke()

        self.assertEqual(second_code, 2)
        self.assertIn("non-empty batch directory has no manifest", second_stderr)
        self.assertFalse(manifest_path.exists())
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 1)

    def test_artifacts_without_a_manifest_run_record_are_not_adopted(self) -> None:
        first_code, _first_stdout, first_stderr = self.invoke()
        self.assertEqual(first_code, 0, first_stderr)
        manifest_path = self.root / "05-runs" / "test-batch" / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["runs"] = []
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        second_code, _second_stdout, second_stderr = self.invoke()

        self.assertEqual(second_code, 2)
        self.assertIn("artifacts exist without a manifest run record", second_stderr)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 1)

    def test_resume_refuses_to_mix_a_changed_skill_into_an_existing_batch(self) -> None:
        first_code, _first_stdout, first_stderr = self.invoke()
        self.assertEqual(first_code, 0, first_stderr)
        (self.root / self.skill_rel).write_text("Changed skill\n", encoding="utf-8")

        second_code, _second_stdout, second_stderr = self.invoke()

        self.assertEqual(second_code, 2)
        self.assertIn("existing batch manifest does not match", second_stderr)
        self.assertIn("skill.sha256", second_stderr)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 1)

    def test_resume_refuses_to_mix_changed_document_bytes(self) -> None:
        first_code, _first_stdout, first_stderr = self.invoke()
        self.assertEqual(first_code, 0, first_stderr)
        (self.root / self.docs_rel / "doc-01.txt").write_text(
            "Changed document\n", encoding="utf-8"
        )

        second_code, _second_stdout, second_stderr = self.invoke()

        self.assertEqual(second_code, 2)
        self.assertIn("existing batch manifest does not match", second_stderr)
        self.assertIn("documents", second_stderr)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 1)

    def test_resume_refuses_to_mix_changed_system_prompt_bytes(self) -> None:
        first_code, _first_stdout, first_stderr = self.invoke()
        self.assertEqual(first_code, 0, first_stderr)
        (self.root / "00-control" / "worker-system-prompt.txt").write_text(
            "Changed system prompt\n", encoding="utf-8"
        )

        second_code, _second_stdout, second_stderr = self.invoke()

        self.assertEqual(second_code, 2)
        self.assertIn("existing batch manifest does not match", second_stderr)
        self.assertIn("system_prompt", second_stderr)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 1)

    def test_resume_refuses_changed_runner_or_fixed_schema_identity(self) -> None:
        first_code, _first_stdout, first_stderr = self.invoke()
        self.assertEqual(first_code, 0, first_stderr)
        manifest_path = self.root / "05-runs" / "test-batch" / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["runner"] = {"path": "changed", "sha256": "0" * 64}
        manifest["fixed_schema_sha256"] = "f" * 64
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        second_code, _second_stdout, second_stderr = self.invoke()

        self.assertEqual(second_code, 2)
        self.assertIn("existing batch manifest does not match", second_stderr)
        self.assertIn("runner", second_stderr)
        self.assertIn("fixed_schema_sha256", second_stderr)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 1)

    def test_runtime_cli_version_must_match_worker_pin(self) -> None:
        self.worker_config["cli_version"] = "8.8.8 (Claude Code)"
        self.worker_path.write_text(
            json.dumps(self.worker_config, indent=2) + "\n", encoding="utf-8"
        )

        exit_code, _stdout, stderr = self.invoke()

        self.assertEqual(exit_code, 2)
        self.assertIn("runtime CLI version does not match worker.json", stderr)
        self.assertIn("8.8.8 (Claude Code)", stderr)
        self.assertIn("9.9.9 (Claude Code)", stderr)
        calls = self.read_cli_log()
        self.assertEqual([call["kind"] for call in calls], ["version"])
        self.assertFalse((self.root / "05-runs" / "test-batch").exists())

    def test_holdout_path_is_refused_before_claude_is_invoked(self) -> None:
        holdout_rel = Path("01-fixtures/docs/holdout")
        (self.root / holdout_rel).mkdir(parents=True)
        (self.root / holdout_rel / "doc-11.txt").write_text(
            "Held-out fixture", encoding="utf-8"
        )
        argv = [
            "--skill",
            str(self.skill_rel),
            "--docs-dir",
            str(holdout_rel),
            "--reps",
            "1",
            "--batch-id",
            "holdout-refusal",
            "--sleep-between",
            "0",
        ]

        exit_code, _stdout, stderr = self.invoke(argv=argv)

        self.assertEqual(exit_code, 2)
        self.assertIn("refusing docs directory containing 'holdout'", stderr)
        self.assertFalse(self.log_path.exists())
        self.assertFalse((self.root / "05-runs" / "holdout-refusal").exists())

        allowed_argv = [*argv, "--allow-holdout"]
        allowed_code, _allowed_stdout, allowed_stderr = self.invoke(argv=allowed_argv)
        self.assertEqual(allowed_code, 0, allowed_stderr)
        self.assertTrue(
            (
                self.root
                / "05-runs"
                / "holdout-refusal"
                / "preds"
                / "rep1"
                / "doc-11.json"
            ).is_file()
        )

    def test_holdout_transport_failure_uses_retry_budget_without_resume_reset(self) -> None:
        holdout_rel = Path("01-fixtures/docs/holdout")
        (self.root / holdout_rel).mkdir(parents=True)
        (self.root / holdout_rel / "doc-11.txt").write_text(
            "Held-out fixture", encoding="utf-8"
        )
        argv = [
            "--skill",
            str(self.skill_rel),
            "--docs-dir",
            str(holdout_rel),
            "--reps",
            "1",
            "--batch-id",
            "heldout-once",
            "--sleep-between",
            "0",
            "--allow-holdout",
        ]

        first_code, _first_stdout, first_stderr = self.invoke(
            sequence="nonzero", argv=argv
        )

        self.assertEqual(first_code, 1, first_stderr)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 3)
        batch_dir = self.root / "05-runs" / "heldout-once"
        first_manifest = json.loads((batch_dir / "manifest.json").read_bytes())
        first_run = first_manifest["runs"][0]
        self.assertEqual(first_run["status"], "transport_failure")
        self.assertEqual(first_run["attempts"], 3)
        self.assertEqual(len(first_run["retry_log"]), 3)
        self.assertEqual(
            [entry["will_retry"] for entry in first_run["retry_log"]],
            [True, True, False],
        )

        second_code, _second_stdout, second_stderr = self.invoke(
            sequence="success", argv=argv
        )

        self.assertEqual(second_code, 1, second_stderr)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 3)
        resumed_manifest = json.loads((batch_dir / "manifest.json").read_bytes())
        self.assertEqual(resumed_manifest["runs"][0]["status"], "transport_failure")
        self.assertEqual(resumed_manifest["runs"][0]["attempts"], 3)
        self.assertEqual(
            resumed_manifest["runs"][0]["retry_budget_exhausted_resumes"], 1
        )
        self.assertFalse((batch_dir / "raw" / "doc-11-rep1.raw.txt").exists())

    def test_holdout_ledger_allows_same_batch_resume_and_new_skill_batch(self) -> None:
        holdout_rel = Path("01-fixtures/docs/holdout")
        (self.root / holdout_rel).mkdir(parents=True)
        (self.root / holdout_rel / "doc-11.txt").write_text(
            "Held-out fixture", encoding="utf-8"
        )
        argv = self.holdout_argv("heldout-ledger")

        first_code, _first_stdout, first_stderr = self.invoke(argv=argv)
        self.assertEqual(first_code, 0, first_stderr)
        ledger_path = self.root / "00-control" / "holdout-usage.log"
        ledger_lines = ledger_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(ledger_lines), 1)
        ledger_entry = json.loads(ledger_lines[0])
        self.assertEqual(ledger_entry["batch_id"], "heldout-ledger")
        self.assertEqual(ledger_entry["skill_sha256"], hashlib.sha256(
            self.skill_text.encode("utf-8")
        ).hexdigest())
        self.assertEqual(ledger_entry["doc_ids"], ["doc-11"])
        self.assertRegex(ledger_entry["started_at"], re.compile(r"Z$"))

        resume_code, _resume_stdout, resume_stderr = self.invoke(argv=argv)
        self.assertEqual(resume_code, 0, resume_stderr)
        self.assertEqual(len(ledger_path.read_text(encoding="utf-8").splitlines()), 1)

        second_skill = self.write_finalist_skill(2)
        different_argv = self.holdout_argv(
            "heldout-other", skill_rel=second_skill
        )
        different_code, _different_stdout, different_stderr = self.invoke(
            argv=different_argv
        )
        self.assertEqual(different_code, 0, different_stderr)
        ledger_entries = [
            json.loads(line)
            for line in ledger_path.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(len(ledger_entries), 2)
        self.assertEqual(
            [entry["batch_id"] for entry in ledger_entries],
            ["heldout-ledger", "heldout-other"],
        )
        self.assertEqual(len({entry["skill_sha256"] for entry in ledger_entries}), 2)

    def test_holdout_ledger_refuses_same_skill_under_different_batch_id(self) -> None:
        holdout_rel = Path("01-fixtures/docs/holdout")
        (self.root / holdout_rel).mkdir(parents=True)
        (self.root / holdout_rel / "doc-11.txt").write_text(
            "Held-out fixture", encoding="utf-8"
        )
        first_argv = self.holdout_argv("heldout-first")
        first_code, _first_stdout, first_stderr = self.invoke(argv=first_argv)
        self.assertEqual(first_code, 0, first_stderr)
        worker_calls_before = len(
            [call for call in self.read_cli_log() if call["kind"] == "worker"]
        )

        refused_code, _refused_stdout, refused_stderr = self.invoke(
            argv=self.holdout_argv("heldout-reroll")
        )

        self.assertEqual(refused_code, 2)
        self.assertIn("skill_sha256", refused_stderr)
        self.assertIn("heldout-first", refused_stderr)
        ledger_path = self.root / "00-control" / "holdout-usage.log"
        self.assertEqual(len(ledger_path.read_text(encoding="utf-8").splitlines()), 1)
        worker_calls_after = len(
            [call for call in self.read_cli_log() if call["kind"] == "worker"]
        )
        self.assertEqual(worker_calls_after, worker_calls_before)
        self.assertFalse((self.root / "05-runs" / "heldout-reroll").exists())

    def test_holdout_ledger_refuses_fifth_distinct_skill(self) -> None:
        holdout_rel = Path("01-fixtures/docs/holdout")
        (self.root / holdout_rel).mkdir(parents=True)
        (self.root / holdout_rel / "doc-11.txt").write_text(
            "Held-out fixture", encoding="utf-8"
        )
        skills = [self.skill_rel]
        skills.extend(self.write_finalist_skill(number) for number in range(2, 6))
        for number, skill_rel in enumerate(skills[:4], start=1):
            exit_code, _stdout, stderr = self.invoke(
                argv=self.holdout_argv(
                    f"heldout-finalist-{number}", skill_rel=skill_rel
                )
            )
            self.assertEqual(exit_code, 0, stderr)
        ledger_path = self.root / "00-control" / "holdout-usage.log"
        self.assertEqual(len(ledger_path.read_text(encoding="utf-8").splitlines()), 4)
        worker_calls_before = len(
            [call for call in self.read_cli_log() if call["kind"] == "worker"]
        )

        fifth_code, _fifth_stdout, fifth_stderr = self.invoke(
            argv=self.holdout_argv("heldout-finalist-5", skill_rel=skills[4])
        )

        self.assertEqual(fifth_code, 2)
        self.assertIn("fifth distinct skill_sha256", fifth_stderr)
        self.assertEqual(len(ledger_path.read_text(encoding="utf-8").splitlines()), 4)
        worker_calls_after = len(
            [call for call in self.read_cli_log() if call["kind"] == "worker"]
        )
        self.assertEqual(worker_calls_after, worker_calls_before)
        self.assertFalse((self.root / "05-runs" / "heldout-finalist-5").exists())

    def test_holdout_ledger_refuses_same_id_when_manifest_is_lost(self) -> None:
        holdout_rel = Path("01-fixtures/docs/holdout")
        (self.root / holdout_rel).mkdir(parents=True)
        (self.root / holdout_rel / "doc-11.txt").write_text(
            "Held-out fixture", encoding="utf-8"
        )
        argv = [
            "--skill",
            str(self.skill_rel),
            "--docs-dir",
            str(holdout_rel),
            "--reps",
            "1",
            "--batch-id",
            "heldout-lost",
            "--sleep-between",
            "0",
            "--allow-holdout",
        ]
        first_code, _first_stdout, first_stderr = self.invoke(argv=argv)
        self.assertEqual(first_code, 0, first_stderr)
        batch_dir = self.root / "05-runs" / "heldout-lost"
        batch_dir.rename(self.root / "05-runs" / "heldout-lost-archived")
        worker_calls_before = len(
            [call for call in self.read_cli_log() if call["kind"] == "worker"]
        )

        resumed_code, _resumed_stdout, resumed_stderr = self.invoke(argv=argv)

        self.assertEqual(resumed_code, 2)
        self.assertIn("ledger entry has no existing batch manifest", resumed_stderr)
        worker_calls_after = len(
            [call for call in self.read_cli_log() if call["kind"] == "worker"]
        )
        self.assertEqual(worker_calls_after, worker_calls_before)
        self.assertFalse(batch_dir.exists())

    def test_holdout_ledger_binds_same_id_to_skill_and_document_ids(self) -> None:
        holdout_rel = Path("01-fixtures/docs/holdout")
        (self.root / holdout_rel).mkdir(parents=True)
        (self.root / holdout_rel / "doc-11.txt").write_text(
            "Held-out fixture eleven", encoding="utf-8"
        )
        (self.root / holdout_rel / "doc-12.txt").write_text(
            "Held-out fixture twelve", encoding="utf-8"
        )
        initial_argv = [
            "--skill",
            str(self.skill_rel),
            "--docs-dir",
            str(holdout_rel),
            "--doc-filter",
            "doc-11",
            "--reps",
            "1",
            "--batch-id",
            "heldout-bound",
            "--sleep-between",
            "0",
            "--allow-holdout",
        ]
        first_code, _first_stdout, first_stderr = self.invoke(argv=initial_argv)
        self.assertEqual(first_code, 0, first_stderr)
        batch_dir = self.root / "05-runs" / "heldout-bound"
        batch_dir.rename(self.root / "05-runs" / "heldout-bound-archived")
        (self.root / self.skill_rel).write_text("Changed skill.\n", encoding="utf-8")
        changed_argv = list(initial_argv)
        changed_argv[changed_argv.index("doc-11")] = "doc-12"
        worker_calls_before = len(
            [call for call in self.read_cli_log() if call["kind"] == "worker"]
        )

        resumed_code, _resumed_stdout, resumed_stderr = self.invoke(argv=changed_argv)

        self.assertEqual(resumed_code, 2)
        self.assertIn("holdout ledger identity mismatch", resumed_stderr)
        self.assertIn("skill_sha256", resumed_stderr)
        self.assertIn("doc_ids", resumed_stderr)
        worker_calls_after = len(
            [call for call in self.read_cli_log() if call["kind"] == "worker"]
        )
        self.assertEqual(worker_calls_after, worker_calls_before)
        self.assertFalse(batch_dir.exists())

    def test_holdout_ledger_lock_refuses_a_concurrent_process(self) -> None:
        ledger_path = self.root / "00-control" / "holdout-usage.log"
        with self.runner.lock_holdout_ledger(ledger_path):
            with self.assertRaisesRegex(
                self.runner.RunnerError, "another holdout batch is already active"
            ):
                with self.runner.lock_holdout_ledger(ledger_path):
                    self.fail("a second ledger lock must not be acquired")

    def test_holdout_initial_manifest_precedes_the_ledger_claim(self) -> None:
        holdout_rel = Path("01-fixtures/docs/holdout")
        (self.root / holdout_rel).mkdir(parents=True)
        (self.root / holdout_rel / "doc-11.txt").write_text(
            "Held-out fixture", encoding="utf-8"
        )
        argv = [
            "--skill",
            str(self.skill_rel),
            "--docs-dir",
            str(holdout_rel),
            "--reps",
            "1",
            "--batch-id",
            "heldout-order",
            "--sleep-between",
            "0",
            "--allow-holdout",
        ]
        with mock.patch.object(
            self.runner,
            "register_holdout_start",
            side_effect=self.runner.RunnerError("simulated interruption before ledger claim"),
        ):
            first_code, _first_stdout, first_stderr = self.invoke(argv=argv)

        self.assertEqual(first_code, 2)
        self.assertIn("simulated interruption", first_stderr)
        batch_dir = self.root / "05-runs" / "heldout-order"
        manifest_path = batch_dir / "manifest.json"
        self.assertTrue(manifest_path.is_file())
        initial_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(initial_manifest["batch_id"], "heldout-order")
        self.assertEqual(initial_manifest["runs"], [])
        ledger_path = self.root / "00-control" / "holdout-usage.log"
        self.assertEqual(ledger_path.read_bytes(), b"")
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(worker_calls, [])

        resumed_code, _resumed_stdout, resumed_stderr = self.invoke(argv=argv)

        self.assertEqual(resumed_code, 0, resumed_stderr)
        self.assertEqual(len(ledger_path.read_text(encoding="utf-8").splitlines()), 1)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 1)

    def test_doc_filter_and_repetitions_select_only_requested_runs(self) -> None:
        (self.root / self.docs_rel / "doc-02.txt").write_text(
            "The Tenant is SAEED NASSER.", encoding="utf-8"
        )
        argv = [
            "--skill",
            str(self.skill_rel),
            "--docs-dir",
            str(self.docs_rel),
            "--doc-filter",
            "doc-02",
            "--reps",
            "2",
            "--batch-id",
            "filtered",
            "--sleep-between",
            "0",
        ]

        exit_code, _stdout, stderr = self.invoke(argv=argv)

        self.assertEqual(exit_code, 0, stderr)
        worker_calls = [call for call in self.read_cli_log() if call["kind"] == "worker"]
        self.assertEqual(len(worker_calls), 2)
        self.assertTrue(
            (self.root / "05-runs" / "filtered" / "preds" / "rep1" / "doc-02.json").is_file()
        )
        self.assertTrue(
            (self.root / "05-runs" / "filtered" / "preds" / "rep2" / "doc-02.json").is_file()
        )
        self.assertFalse(
            (self.root / "05-runs" / "filtered" / "preds" / "rep1" / "doc-01.json").exists()
        )
        manifest = json.loads(
            (self.root / "05-runs" / "filtered" / "manifest.json").read_bytes()
        )
        self.assertEqual(manifest["doc_ids"], ["doc-02"])
        self.assertEqual(
            [(run["doc_id"], run["rep"]) for run in manifest["runs"]],
            [("doc-02", 1), ("doc-02", 2)],
        )


if __name__ == "__main__":
    unittest.main()
