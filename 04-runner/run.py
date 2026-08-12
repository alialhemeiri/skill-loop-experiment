#!/usr/bin/env python3
"""Run one frozen extraction skill against a batch of fixture documents."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, BinaryIO, Iterator, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKER_CONFIG_PATH = Path("00-control/worker.json")
HOLDOUT_LEDGER_PATH = Path("00-control/holdout-usage.log")
FIXTURE_GOLD_ROOT = Path("01-fixtures/gold")
WORKER_CWD = Path("/tmp/autoresearch-worker-cwd")
SYSTEM_PROMPT_PLACEHOLDER = "<contents of system_prompt_file>"
MAX_TRANSPORT_RETRIES = 2
MAX_HOLDOUT_SKILLS = 4
_OPENING_FENCE_RE = re.compile(r"^```[A-Za-z0-9]*$")

FIXED_SCHEMA_INSTRUCTION = (
    "Extract the following 12 fields from the document above and output ONLY a single JSON "
    "object — no markdown fences, no commentary. Keys and types: landlord_name (string), "
    "tenant_name (string), unit_number (string), community (string), contract_start_date "
    "(string, YYYY-MM-DD), contract_end_date (string, YYYY-MM-DD), annual_rent_aed (integer), "
    "security_deposit_aed (integer or null), number_of_payments (integer), notice_period_days "
    "(integer or null), early_termination_penalty_months (number or null), furnished_status "
    '(one of "furnished", "semi-furnished", "unfurnished", or null). Use null for any field the '
    "document does not state."
)


class RunnerError(Exception):
    """A user-facing runner configuration or setup error."""


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    """Atomically replace a file with bytes on the same filesystem."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temp_path.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def write_json(path: Path, value: Any) -> None:
    encoded = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    atomic_write(path, encoded)


def resolve_project_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def display_path(project_root: Path, path: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return str(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a frozen extraction skill through the pinned Claude worker."
    )
    parser.add_argument("--skill", required=True, help="Skill file path, relative to project root")
    parser.add_argument(
        "--docs-dir", required=True, help="Fixture document directory, relative to project root"
    )
    parser.add_argument("--reps", required=True, type=int, help="Repetitions per document")
    parser.add_argument("--batch-id", required=True, help="Output directory name under 05-runs")
    parser.add_argument(
        "--doc-filter",
        help="Comma-separated document IDs without .txt, for example doc-01,doc-02",
    )
    parser.add_argument(
        "--sleep-between",
        type=float,
        default=2.0,
        metavar="SECONDS",
        help="Seconds between worker invocations (default: 2)",
    )
    parser.add_argument(
        "--allow-holdout",
        action="store_true",
        help="Permit a docs directory whose path contains 'holdout'",
    )
    return parser.parse_args(argv)


def validate_args(args: argparse.Namespace) -> None:
    if args.reps < 1:
        raise RunnerError("--reps must be at least 1")
    if args.sleep_between < 0:
        raise RunnerError("--sleep-between cannot be negative")
    batch_path = Path(args.batch_id)
    if (
        not args.batch_id
        or batch_path.name != args.batch_id
        or args.batch_id in {".", ".."}
        or "/" in args.batch_id
        or "\\" in args.batch_id
    ):
        raise RunnerError("--batch-id must be one safe path component")


def load_worker(
    project_root: Path,
) -> tuple[dict[str, Any], bytes, list[str], str, Path, bytes]:
    worker_path = project_root / WORKER_CONFIG_PATH
    try:
        worker_bytes = worker_path.read_bytes()
        worker = json.loads(worker_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise RunnerError(f"cannot read valid {WORKER_CONFIG_PATH}: {exc}") from exc

    try:
        cli = worker["cli"]
        system_prompt_rel = worker["system_prompt_file"]
        invocation = worker["invocation"]
        prompt_via = invocation["prompt_via"]
        args_template = invocation["args_template"]
    except (KeyError, TypeError) as exc:
        raise RunnerError(f"worker.json is missing required key: {exc}") from exc
    if not isinstance(cli, str) or not cli:
        raise RunnerError("worker.json cli must be a non-empty string")
    if prompt_via != "stdin":
        raise RunnerError("worker.json invocation.prompt_via must be 'stdin'")
    if not isinstance(args_template, list) or not all(
        isinstance(item, str) for item in args_template
    ):
        raise RunnerError("worker.json invocation.args_template must be a list of strings")
    if args_template.count(SYSTEM_PROMPT_PLACEHOLDER) != 1:
        raise RunnerError("worker.json args_template must contain the system-prompt placeholder once")

    system_prompt_path = resolve_project_path(project_root, system_prompt_rel)
    try:
        system_prompt_bytes = system_prompt_path.read_bytes()
        system_prompt = system_prompt_bytes.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise RunnerError(f"cannot read system prompt {system_prompt_rel}: {exc}") from exc
    worker_args = [
        system_prompt if item == SYSTEM_PROMPT_PLACEHOLDER else item for item in args_template
    ]
    return (
        worker,
        worker_bytes,
        worker_args,
        cli,
        system_prompt_path,
        system_prompt_bytes,
    )


def prepare_worker_cwd(worker_cwd: Path) -> Path:
    try:
        worker_cwd.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RunnerError(f"cannot create worker cwd {worker_cwd}: {exc}") from exc
    if not worker_cwd.is_dir():
        raise RunnerError(f"worker cwd is not a directory: {worker_cwd}")
    try:
        existing = next(worker_cwd.iterdir(), None)
    except OSError as exc:
        raise RunnerError(f"cannot inspect worker cwd {worker_cwd}: {exc}") from exc
    if existing is not None:
        raise RunnerError(f"worker cwd must be empty: {worker_cwd}")
    return worker_cwd


def get_cli_version(cli: str, worker_cwd: Path) -> str:
    try:
        completed = subprocess.run(
            [cli, "--version"],
            cwd=worker_cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise RunnerError(f"cannot execute {cli} --version: {exc}") from exc
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RunnerError(f"{cli} --version exited {completed.returncode}: {stderr}")
    version = completed.stdout.decode("utf-8", errors="replace").strip()
    if not version:
        raise RunnerError(f"{cli} --version returned empty stdout")
    return version


def select_documents(docs_dir: Path, doc_filter: str | None) -> list[tuple[str, Path]]:
    if not docs_dir.is_dir():
        raise RunnerError(f"docs directory does not exist: {docs_dir}")
    documents = sorted((path.stem, path) for path in docs_dir.glob("*.txt") if path.is_file())
    by_id = {doc_id: path for doc_id, path in documents}
    if len(by_id) != len(documents):
        raise RunnerError(f"duplicate document IDs in {docs_dir}")
    if doc_filter is not None:
        requested = [item.strip() for item in doc_filter.split(",") if item.strip()]
        if not requested:
            raise RunnerError("--doc-filter did not contain any document IDs")
        if len(set(requested)) != len(requested):
            raise RunnerError("--doc-filter contains duplicate document IDs")
        missing = [doc_id for doc_id in requested if doc_id not in by_id]
        if missing:
            raise RunnerError("unknown document ID(s): " + ", ".join(missing))
        documents = [(doc_id, by_id[doc_id]) for doc_id in requested]
    if not documents:
        raise RunnerError(f"no .txt documents selected in {docs_dir}")
    return documents


def build_prompt(skill_text: str, document_text: str) -> str:
    return (
        skill_text
        + "\n\n---\n\nDOCUMENT:\n\n"
        + document_text
        + "\n\n---\n\n"
        + FIXED_SCHEMA_INSTRUCTION
    )


def transport_failure_reason(returncode: int, stdout: bytes) -> str | None:
    if returncode != 0:
        return f"nonzero CLI exit ({returncode})"
    if not stdout:
        return "empty stdout"
    try:
        envelope = json.loads(stdout)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return "stdout unparseable as CLI result JSON"
    if (
        not isinstance(envelope, dict)
        or envelope.get("type") != "result"
        or envelope.get("subtype") != "success"
        or envelope.get("is_error") is not False
        or not isinstance(envelope.get("result"), str)
    ):
        return "stdout unparseable as CLI result JSON"
    if envelope.get("num_turns") != 1:
        return f"CLI result used {envelope.get('num_turns')!r} turns"
    if envelope.get("permission_denials"):
        return "CLI result contained permission denials"
    return None


def is_turn_check_failure_reason(reason: str | None) -> bool:
    return bool(
        reason == "CLI result contained permission denials"
        or (
            isinstance(reason, str)
            and reason.startswith("CLI result used ")
            and reason.endswith(" turns")
        )
    )


def strip_registered_fence(result_text: str) -> tuple[str, bool]:
    """Apply A1's one-pair fence rule without changing forensic text."""

    trimmed = result_text.strip()
    lines = trimmed.splitlines(keepends=True)
    if len(lines) >= 2:
        first_line = lines[0].rstrip("\r\n")
        last_line = lines[-1].rstrip("\r\n")
        if _OPENING_FENCE_RE.fullmatch(first_line) and last_line == "```":
            return "".join(lines[1:-1]).strip(), True
    return trimmed, False


def _reject_nonstandard_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def is_valid_json_text(value: str) -> bool:
    try:
        json.loads(value, parse_constant=_reject_nonstandard_json_constant)
    except (json.JSONDecodeError, ValueError):
        return False
    return True


def prediction_bytes_from_result_bytes(result_bytes: bytes) -> tuple[bytes, bool]:
    try:
        result_text = result_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("CLI result contains non-UTF-8 bytes") from exc
    prediction_text, fence_stripped = strip_registered_fence(result_text)
    return prediction_text.encode("utf-8"), fence_stripped


def record_model_provenance(run_record: dict[str, Any], envelope: dict[str, Any]) -> None:
    model_usage = envelope.get("modelUsage")
    run_record["model_usage_keys"] = (
        list(model_usage.keys()) if isinstance(model_usage, dict) else []
    )
    for envelope_key, manifest_key in (
        ("canonicalModel", "canonical_model"),
        ("provider", "provider"),
    ):
        if envelope_key in envelope:
            run_record[manifest_key] = envelope[envelope_key]


@contextmanager
def lock_holdout_ledger(ledger_path: Path) -> Iterator[BinaryIO]:
    """Hold an exclusive, process-wide lock for one complete holdout invocation."""

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = ledger_path.open("a+b")
    except OSError as exc:
        raise RunnerError(f"cannot open holdout ledger {ledger_path}: {exc}") from exc
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RunnerError(
                "another holdout batch is already active; refusing concurrent execution"
            ) from exc
        except OSError as exc:
            raise RunnerError(f"cannot lock holdout ledger {ledger_path}: {exc}") from exc
        yield handle
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def read_holdout_ledger(
    ledger_path: Path, ledger_handle: BinaryIO | None = None
) -> list[dict[str, Any]]:
    if ledger_handle is None and not ledger_path.exists():
        return []
    try:
        if ledger_handle is None:
            ledger_bytes = ledger_path.read_bytes()
        else:
            ledger_handle.flush()
            ledger_handle.seek(0)
            ledger_bytes = ledger_handle.read()
        lines = ledger_bytes.decode("utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise RunnerError(f"cannot read holdout ledger {ledger_path}: {exc}") from exc
    entries: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RunnerError(
                f"holdout ledger {ledger_path} line {line_number} is invalid JSON"
            ) from exc
        if not isinstance(entry, dict) or not isinstance(entry.get("batch_id"), str):
            raise RunnerError(
                f"holdout ledger {ledger_path} line {line_number} is malformed"
            )
        entries.append(entry)
    return entries


def check_holdout_ledger(
    ledger_path: Path,
    batch_id: str,
    ledger_handle: BinaryIO | None = None,
    *,
    skill_sha256: str | None = None,
    doc_ids: list[str] | None = None,
) -> bool:
    entries = read_holdout_ledger(ledger_path, ledger_handle)
    for entry in entries:
        if not isinstance(entry.get("skill_sha256"), str) or not isinstance(
            entry.get("doc_ids"), list
        ):
            raise RunnerError(
                f"holdout ledger {ledger_path} contains a malformed shot identity"
            )
    batch_ids = [entry["batch_id"] for entry in entries]
    skill_hashes = [entry["skill_sha256"] for entry in entries]
    if len(set(batch_ids)) != len(batch_ids) or len(set(skill_hashes)) != len(skill_hashes):
        raise RunnerError(
            f"holdout ledger {ledger_path} contains duplicate consumed-shot entries"
        )

    same_batch = [entry for entry in entries if entry["batch_id"] == batch_id]
    if same_batch:
        entry = same_batch[0]
        mismatches = []
        if skill_sha256 is not None and entry.get("skill_sha256") != skill_sha256:
            mismatches.append("skill_sha256")
        if doc_ids is not None and entry.get("doc_ids") != doc_ids:
            mismatches.append("doc_ids")
        if mismatches:
            raise RunnerError(
                "holdout ledger identity mismatch for same batch-id: "
                + ", ".join(mismatches)
            )
        return True

    spent_batches = sorted(
        entry["batch_id"]
        for entry in entries
        if skill_sha256 is not None and entry["skill_sha256"] == skill_sha256
    )
    if spent_batches:
        raise RunnerError(
            "refusing holdout batch-id because skill_sha256 was already consumed by: "
            + ", ".join(spent_batches)
        )
    if skill_sha256 is not None and len(set(skill_hashes)) >= MAX_HOLDOUT_SKILLS:
        raise RunnerError(
            "refusing fifth distinct skill_sha256; holdout ledger already records "
            "four finalist skills"
        )
    return False


def register_holdout_start(
    ledger_path: Path,
    *,
    batch_id: str,
    skill_sha256: str,
    doc_ids: list[str],
    has_existing_manifest: bool,
    ledger_handle: BinaryIO | None = None,
) -> None:
    if ledger_handle is None:
        with lock_holdout_ledger(ledger_path) as locked_handle:
            register_holdout_start(
                ledger_path,
                batch_id=batch_id,
                skill_sha256=skill_sha256,
                doc_ids=doc_ids,
                has_existing_manifest=has_existing_manifest,
                ledger_handle=locked_handle,
            )
        return

    has_same_batch = check_holdout_ledger(
        ledger_path,
        batch_id,
        ledger_handle,
        skill_sha256=skill_sha256,
        doc_ids=doc_ids,
    )
    if has_same_batch:
        if not has_existing_manifest:
            raise RunnerError(
                "holdout ledger entry has no existing batch manifest; refusing a re-roll"
            )
        return

    entry = {
        "started_at": utc_now(),
        "batch_id": batch_id,
        "skill_sha256": skill_sha256,
        "doc_ids": doc_ids,
    }
    encoded = (
        json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    try:
        ledger_handle.seek(0, os.SEEK_END)
        ledger_handle.write(encoded)
        ledger_handle.flush()
        os.fsync(ledger_handle.fileno())
    except OSError as exc:
        raise RunnerError(f"cannot append holdout ledger {ledger_path}: {exc}") from exc


def result_bytes_from_cli_envelope(envelope_bytes: bytes) -> bytes:
    """Extract UTF-8 .result bytes from a valid stored Claude result envelope."""
    reason = transport_failure_reason(0, envelope_bytes)
    if reason is not None:
        raise ValueError(reason)
    envelope = json.loads(envelope_bytes)
    try:
        return envelope["result"].encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("CLI result contains a non-UTF-8 string") from exc


def completed_summary(
    manifest: dict[str, Any], *, skipped_existing: int = 0
) -> dict[str, int]:
    statuses = [run["status"] for run in manifest["runs"]]
    return {
        "total": len(statuses),
        "completed": statuses.count("completed"),
        "model_failures": statuses.count("model_failure"),
        "transport_failures": statuses.count("transport_failure"),
        "skipped_existing": skipped_existing,
    }


def nested_value(value: dict[str, Any], dotted_key: str) -> Any:
    current: Any = value
    for key in dotted_key.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def check_resume_identity(
    manifest: dict[str, Any], expected: dict[str, Any]
) -> None:
    mismatches = [
        key for key, expected_value in expected.items()
        if nested_value(manifest, key) != expected_value
    ]
    if mismatches:
        raise RunnerError(
            "existing batch manifest does not match this invocation: "
            + ", ".join(mismatches)
        )


def create_fixture_snapshots(
    project_root: Path,
    batch_dir: Path,
    documents: list[tuple[str, Path]],
    document_bytes: dict[str, bytes],
) -> dict[str, dict[str, dict[str, str]]]:
    """Archive fixture bytes without exposing gold records to prompt construction."""

    gold_bytes: dict[str, bytes] = {}
    for doc_id, _doc_path in documents:
        gold_path = project_root / FIXTURE_GOLD_ROOT / f"{doc_id}.json"
        try:
            gold_bytes[doc_id] = gold_path.read_bytes()
        except OSError as exc:
            raise RunnerError(f"cannot read fixture gold record {gold_path}: {exc}") from exc

    snapshots: dict[str, dict[str, dict[str, str]]] = {
        "documents": {},
        "gold": {},
    }
    for doc_id, doc_path in documents:
        document_relative = f"fixtures/docs/{doc_path.name}"
        gold_relative = f"fixtures/gold/{doc_id}.json"
        atomic_write(batch_dir / document_relative, document_bytes[doc_id])
        atomic_write(batch_dir / gold_relative, gold_bytes[doc_id])
        snapshots["documents"][doc_id] = {
            "path": document_relative,
            "sha256": sha256_bytes(document_bytes[doc_id]),
        }
        snapshots["gold"][doc_id] = {
            "path": gold_relative,
            "sha256": sha256_bytes(gold_bytes[doc_id]),
        }
    return snapshots


def _safe_snapshot_path(batch_dir: Path, relative: Any) -> Path | None:
    if not isinstance(relative, str) or not relative:
        return None
    candidate = (batch_dir / relative).resolve()
    try:
        candidate.relative_to(batch_dir.resolve())
    except ValueError:
        return None
    return candidate


def verify_fixture_snapshots(
    batch_dir: Path,
    manifest: dict[str, Any],
    doc_ids: list[str],
) -> None:
    """Refuse a resume unless every archived document and gold record is intact."""

    snapshots = manifest.get("fixture_snapshots")
    documents_manifest = manifest.get("documents")
    if not isinstance(snapshots, dict) or not isinstance(documents_manifest, dict):
        raise RunnerError("fixture snapshot mismatch for: manifest")

    mismatches: list[str] = []
    expected_ids = set(doc_ids)
    for group_name in ("documents", "gold"):
        group = snapshots.get(group_name)
        if not isinstance(group, dict) or set(group) != expected_ids:
            mismatches.append(f"{group_name}/manifest")
            continue
        for doc_id in doc_ids:
            record = group.get(doc_id)
            if not isinstance(record, dict):
                mismatches.append(f"{group_name}/{doc_id}")
                continue
            expected_hash = record.get("sha256")
            snapshot_path = _safe_snapshot_path(batch_dir, record.get("path"))
            if not isinstance(expected_hash, str) or snapshot_path is None:
                mismatches.append(f"{group_name}/{doc_id}")
                continue
            if group_name == "documents":
                source_record = documents_manifest.get(doc_id)
                if (
                    not isinstance(source_record, dict)
                    or source_record.get("sha256") != expected_hash
                ):
                    mismatches.append(f"{group_name}/{doc_id}")
                    continue
            try:
                actual_hash = sha256_bytes(snapshot_path.read_bytes())
            except OSError:
                mismatches.append(f"{group_name}/{doc_id}")
                continue
            if actual_hash != expected_hash:
                mismatches.append(f"{group_name}/{doc_id}")

    if mismatches:
        raise RunnerError(
            "fixture snapshot mismatch for: " + ", ".join(sorted(set(mismatches)))
        )


def new_run_record(doc_id: str, rep: int) -> dict[str, Any]:
    return {
        "doc_id": doc_id,
        "rep": rep,
        "status": "running",
        "started_at": utc_now(),
        "finished_at": None,
        "wall_clock_seconds": 0.0,
        "attempts": 0,
        "retry_log": [],
        "resume_skips": 0,
        "fence_stripped": False,
        "model_usage_keys": [],
        "files": {
            "result_json": f"raw/{doc_id}-rep{rep}.result.json",
            "raw_text": f"raw/{doc_id}-rep{rep}.raw.txt",
            "prediction": f"preds/rep{rep}/{doc_id}.json",
        },
    }


def _run_batch_locked(
    args: argparse.Namespace,
    *,
    project_root: Path,
    worker_cwd: Path,
    holdout_ledger_handle: BinaryIO | None,
) -> int:
    validate_args(args)
    project_root = project_root.resolve()
    skill_path = resolve_project_path(project_root, args.skill)
    docs_dir = resolve_project_path(project_root, args.docs_dir)
    holdout_mode = "holdout" in str(docs_dir).casefold()
    if holdout_mode and not args.allow_holdout:
        raise RunnerError(
            "refusing docs directory containing 'holdout' without --allow-holdout"
        )
    try:
        skill_bytes = skill_path.read_bytes()
        skill_text = skill_bytes.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise RunnerError(f"cannot read UTF-8 skill file {skill_path}: {exc}") from exc

    documents = select_documents(docs_dir, args.doc_filter)
    doc_ids = [doc_id for doc_id, _ in documents]
    holdout_ledger_path = project_root / HOLDOUT_LEDGER_PATH
    ledger_has_same_batch = False
    if holdout_mode:
        if holdout_ledger_handle is None:
            raise RunnerError("internal error: holdout ledger is not locked")
        ledger_has_same_batch = check_holdout_ledger(
            holdout_ledger_path,
            args.batch_id,
            holdout_ledger_handle,
            skill_sha256=sha256_bytes(skill_bytes),
            doc_ids=doc_ids,
        )
    (
        worker,
        worker_bytes,
        worker_args,
        cli,
        system_prompt_path,
        system_prompt_bytes,
    ) = load_worker(project_root)
    document_texts: dict[str, str] = {}
    document_bytes_by_id: dict[str, bytes] = {}
    documents_manifest: dict[str, dict[str, str]] = {}
    for doc_id, doc_path in documents:
        try:
            document_bytes = doc_path.read_bytes()
            document_texts[doc_id] = document_bytes.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise RunnerError(f"cannot read UTF-8 document {doc_path}: {exc}") from exc
        documents_manifest[doc_id] = {
            "path": display_path(project_root, doc_path),
            "sha256": sha256_bytes(document_bytes),
        }
        document_bytes_by_id[doc_id] = document_bytes
    worker_cwd = prepare_worker_cwd(worker_cwd)
    cli_version = get_cli_version(cli, worker_cwd)
    pinned_cli_version = worker.get("cli_version")
    if not isinstance(pinned_cli_version, str) or not pinned_cli_version:
        raise RunnerError("worker.json cli_version must be a non-empty string")
    if cli_version != pinned_cli_version:
        raise RunnerError(
            "runtime CLI version does not match worker.json: "
            f"pinned {pinned_cli_version!r}, runtime {cli_version!r}"
        )

    batch_dir = project_root / "05-runs" / args.batch_id
    manifest_path = batch_dir / "manifest.json"
    has_existing_manifest = manifest_path.exists()
    if holdout_mode and ledger_has_same_batch and not has_existing_manifest:
        raise RunnerError(
            "holdout ledger entry has no existing batch manifest; refusing a re-roll"
        )
    if not manifest_path.exists() and batch_dir.exists():
        try:
            batch_has_entries = next(batch_dir.iterdir(), None) is not None
        except OSError as exc:
            raise RunnerError(f"cannot inspect batch directory {batch_dir}: {exc}") from exc
        if batch_has_entries:
            raise RunnerError(
                f"non-empty batch directory has no manifest: {batch_dir}"
            )
    batch_started_wall = time.monotonic()
    invocation_started_at = utc_now()
    skill_manifest = {
        "path": display_path(project_root, skill_path),
        "sha256": sha256_bytes(skill_bytes),
    }
    worker_manifest = {
        "path": WORKER_CONFIG_PATH.as_posix(),
        "sha256": sha256_bytes(worker_bytes),
    }
    runner_path = Path(__file__).resolve()
    try:
        runner_bytes = runner_path.read_bytes()
    except OSError as exc:
        raise RunnerError(f"cannot read runner {runner_path}: {exc}") from exc
    runner_manifest = {
        "path": display_path(project_root, runner_path),
        "sha256": sha256_bytes(runner_bytes),
    }
    fixed_schema_sha256 = sha256_bytes(FIXED_SCHEMA_INSTRUCTION.encode("utf-8"))
    system_prompt_manifest = {
        "path": display_path(project_root, system_prompt_path),
        "sha256": sha256_bytes(system_prompt_bytes),
    }
    docs_manifest_path = display_path(project_root, docs_dir)
    expected_identity = {
        "batch_id": args.batch_id,
        "model": worker.get("model"),
        "cli.command": cli,
        "cli.version": cli_version,
        "skill.path": skill_manifest["path"],
        "skill.sha256": skill_manifest["sha256"],
        "worker.path": worker_manifest["path"],
        "worker.sha256": worker_manifest["sha256"],
        "runner": runner_manifest,
        "fixed_schema_sha256": fixed_schema_sha256,
        "system_prompt": system_prompt_manifest,
        "documents": documents_manifest,
        "docs_dir": docs_manifest_path,
        "doc_ids": doc_ids,
        "reps": args.reps,
    }
    previous_wall_clock = 0.0
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_bytes())
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RunnerError(f"cannot resume invalid manifest {manifest_path}: {exc}") from exc
        if not isinstance(manifest, dict) or not isinstance(manifest.get("runs"), list):
            raise RunnerError(f"cannot resume malformed manifest {manifest_path}")
        check_resume_identity(manifest, expected_identity)
        verify_fixture_snapshots(batch_dir, manifest, doc_ids)
        prior_wall_value = manifest.get("wall_clock_seconds", 0.0)
        if isinstance(prior_wall_value, (int, float)) and prior_wall_value >= 0:
            previous_wall_clock = float(prior_wall_value)
        manifest["resume_count"] = int(manifest.get("resume_count", 0)) + 1
    else:
        fixture_snapshots = create_fixture_snapshots(
            project_root,
            batch_dir,
            documents,
            document_bytes_by_id,
        )
        manifest = {
            "batch_id": args.batch_id,
            "model": worker.get("model"),
            "cli": {"command": cli, "version": cli_version},
            "skill": skill_manifest,
            "worker": worker_manifest,
            "runner": runner_manifest,
            "fixed_schema_sha256": fixed_schema_sha256,
            "system_prompt": system_prompt_manifest,
            "documents": documents_manifest,
            "fixture_snapshots": fixture_snapshots,
            "docs_dir": docs_manifest_path,
            "doc_ids": doc_ids,
            "reps": args.reps,
            "sleep_between_seconds": args.sleep_between,
            "allow_holdout": args.allow_holdout,
            "holdout_transport_retries": holdout_mode,
            "started_at": invocation_started_at,
            "finished_at": None,
            "wall_clock_seconds": 0.0,
            "resume_count": 0,
            "invocations": [],
            "runs": [],
            "summary": {
                "total": 0,
                "completed": 0,
                "model_failures": 0,
                "transport_failures": 0,
                "skipped_existing": 0,
            },
        }
    if holdout_mode and not has_existing_manifest:
        # Make the batch identity durable before claiming single-shot usage. If
        # registration is interrupted, the same ID can safely resume this manifest.
        write_json(manifest_path, manifest)
    if holdout_mode:
        register_holdout_start(
            holdout_ledger_path,
            batch_id=args.batch_id,
            skill_sha256=skill_manifest["sha256"],
            doc_ids=doc_ids,
            has_existing_manifest=has_existing_manifest,
            ledger_handle=holdout_ledger_handle,
        )
    invocations = manifest.setdefault("invocations", [])
    if not isinstance(invocations, list):
        raise RunnerError(f"cannot resume malformed invocations in {manifest_path}")
    invocation_record: dict[str, Any] = {
        "number": len(invocations) + 1,
        "started_at": invocation_started_at,
        "finished_at": None,
        "wall_clock_seconds": 0.0,
        "skipped_existing": 0,
    }
    invocations.append(invocation_record)
    manifest["finished_at"] = None
    manifest["summary"] = completed_summary(manifest)
    write_json(manifest_path, manifest)
    last_worker_finished_wall: float | None = None
    skipped_existing = 0

    run_index: dict[tuple[str, int], dict[str, Any]] = {}
    for existing_run in manifest["runs"]:
        if not isinstance(existing_run, dict):
            raise RunnerError(f"cannot resume malformed run record in {manifest_path}")
        key = (existing_run.get("doc_id"), existing_run.get("rep"))
        if key in run_index:
            raise RunnerError(f"cannot resume duplicate run record {key!r} in {manifest_path}")
        run_index[key] = existing_run

    def save_progress() -> None:
        elapsed = time.monotonic() - batch_started_wall
        manifest["summary"] = completed_summary(
            manifest, skipped_existing=skipped_existing
        )
        manifest["wall_clock_seconds"] = round(previous_wall_clock + elapsed, 6)
        invocation_record["wall_clock_seconds"] = round(elapsed, 6)
        invocation_record["skipped_existing"] = skipped_existing
        write_json(manifest_path, manifest)

    max_attempts_per_run = MAX_TRANSPORT_RETRIES + 1

    for rep in range(1, args.reps + 1):
        for doc_id, doc_path in documents:
            key = (doc_id, rep)
            files = {
                "result_json": f"raw/{doc_id}-rep{rep}.result.json",
                "raw_text": f"raw/{doc_id}-rep{rep}.raw.txt",
                "prediction": f"preds/rep{rep}/{doc_id}.json",
            }
            raw_text_path = batch_dir / files["raw_text"]
            pred_path = batch_dir / files["prediction"]
            result_path = batch_dir / files["result_json"]
            existing_run = run_index.get(key)
            if existing_run is None and any(
                path.exists() for path in (result_path, raw_text_path, pred_path)
            ):
                raise RunnerError(
                    "artifacts exist without a manifest run record for "
                    f"{doc_id} rep{rep}; refusing to adopt them"
                )
            recovered_from_result_json = False
            if not raw_text_path.exists() and result_path.exists():
                try:
                    stored_envelope = result_path.read_bytes()
                    recovered_result_bytes = result_bytes_from_cli_envelope(stored_envelope)
                    recovered_prediction_bytes, recovered_fence_stripped = (
                        prediction_bytes_from_result_bytes(recovered_result_bytes)
                    )
                except (OSError, ValueError) as exc:
                    raise RunnerError(
                        f"cannot recover from forensic CLI result {result_path}: {exc}"
                    ) from exc
                atomic_write(pred_path, recovered_prediction_bytes)
                atomic_write(raw_text_path, recovered_result_bytes)
                recovered_from_result_json = True
            if raw_text_path.exists():
                try:
                    raw_bytes = raw_text_path.read_bytes()
                except OSError as exc:
                    raise RunnerError(f"cannot read resume sentinel {raw_text_path}: {exc}") from exc
                if not result_path.is_file():
                    raise RunnerError(
                        f"raw sentinel has no forensic CLI result: {result_path}"
                    )
                try:
                    forensic_result_bytes = result_bytes_from_cli_envelope(
                        result_path.read_bytes()
                    )
                except (OSError, ValueError) as exc:
                    raise RunnerError(
                        f"raw sentinel has invalid forensic CLI result {result_path}: {exc}"
                    ) from exc
                if forensic_result_bytes != raw_bytes:
                    raise RunnerError(
                        "raw sentinel does not match forensic CLI result: "
                        f"{raw_text_path}"
                    )
                try:
                    prediction_bytes, fence_stripped = prediction_bytes_from_result_bytes(
                        raw_bytes
                    )
                    prediction_text = prediction_bytes.decode("utf-8")
                    recovered_valid_json = is_valid_json_text(prediction_text)
                    forensic_envelope = json.loads(result_path.read_bytes())
                except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
                    raise RunnerError(
                        f"cannot normalize stored model result {raw_text_path}: {exc}"
                    ) from exc
                recovered_status = "completed" if recovered_valid_json else "model_failure"
                if existing_run is None:
                    existing_run = new_run_record(doc_id, rep)
                    manifest["runs"].append(existing_run)
                    run_index[key] = existing_run
                existing_run.update(
                    {
                        "status": recovered_status,
                        "finished_at": existing_run.get("finished_at") or utc_now(),
                        "recovered_from_raw": not recovered_from_result_json,
                        "model_output_valid_json": recovered_valid_json,
                        "fence_stripped": fence_stripped,
                    }
                )
                record_model_provenance(existing_run, forensic_envelope)
                if recovered_from_result_json:
                    existing_run["recovered_from_result_json"] = True
                active_attempt = existing_run.pop("active_attempt", None)
                if isinstance(active_attempt, dict):
                    attempt_number = active_attempt.get("attempt")
                    retry_log = existing_run.setdefault("retry_log", [])
                    already_logged = isinstance(retry_log, list) and any(
                        isinstance(entry, dict) and entry.get("attempt") == attempt_number
                        for entry in retry_log
                    )
                    if isinstance(retry_log, list) and not already_logged:
                        recovered_attempt = {
                            "attempt": attempt_number,
                            "started_at": active_attempt.get("started_at"),
                            "finished_at": utc_now(),
                            "wall_clock_seconds": None,
                            "status": "success",
                            "returncode": 0,
                            "reason": None,
                            "will_retry": False,
                            "stderr": None,
                            "launch_error": None,
                        }
                        if recovered_from_result_json:
                            recovered_attempt["recovered_from_result_json"] = True
                        else:
                            recovered_attempt["recovered_from_raw"] = True
                        retry_log.append(recovered_attempt)
                repaired_prediction = False
                try:
                    if not pred_path.exists() or pred_path.read_bytes() != prediction_bytes:
                        atomic_write(pred_path, prediction_bytes)
                        repaired_prediction = True
                except OSError as exc:
                    raise RunnerError(f"cannot verify prediction {pred_path}: {exc}") from exc
                existing_run["resume_skips"] = int(existing_run.get("resume_skips", 0)) + 1
                existing_run["last_resume_skip_at"] = utc_now()
                if repaired_prediction:
                    existing_run["prediction_repairs"] = int(
                        existing_run.get("prediction_repairs", 0)
                    ) + 1
                skipped_existing += 1
                save_progress()
                continue

            if existing_run is not None and existing_run.get("status") in {
                "completed",
                "model_failure",
            }:
                raise RunnerError(
                    "terminal model result artifacts are missing for "
                    f"{doc_id} rep{rep}; refusing to re-roll"
                )

            run_started_wall = time.monotonic()
            attempts_consumed = 0
            previous_run_wall_clock = 0.0
            if existing_run is not None:
                retry_log = existing_run.get("retry_log", [])
                if not isinstance(retry_log, list):
                    raise RunnerError(f"cannot resume malformed retry log for {doc_id} rep{rep}")
                attempts_value = existing_run.get("attempts", 0)
                if isinstance(attempts_value, int) and attempts_value >= 0:
                    attempts_consumed = attempts_value
                logged_attempts = [
                    entry.get("attempt")
                    for entry in retry_log
                    if isinstance(entry, dict) and isinstance(entry.get("attempt"), int)
                ]
                if logged_attempts:
                    attempts_consumed = max(attempts_consumed, max(logged_attempts))
                active_attempt = existing_run.pop("active_attempt", None)
                if isinstance(active_attempt, dict):
                    active_number = active_attempt.get("attempt")
                    if isinstance(active_number, int) and active_number > 0:
                        attempts_consumed = max(attempts_consumed, active_number)
                        if not any(
                            isinstance(entry, dict) and entry.get("attempt") == active_number
                            for entry in retry_log
                        ):
                            retry_log.append(
                                {
                                    "attempt": active_number,
                                    "started_at": active_attempt.get("started_at"),
                                    "finished_at": utc_now(),
                                    "wall_clock_seconds": None,
                                    "status": "transport_failure",
                                    "returncode": None,
                                    "reason": "interrupted before a CLI result was persisted",
                                    "will_retry": active_number < max_attempts_per_run,
                                    "stderr": None,
                                    "launch_error": None,
                                    "recovered_on_resume": True,
                                }
                            )
                            save_progress()
                previous_run_wall_value = existing_run.get("wall_clock_seconds", 0.0)
                if isinstance(previous_run_wall_value, (int, float)):
                    previous_run_wall_clock = max(0.0, float(previous_run_wall_value))
                existing_run["attempts"] = attempts_consumed
                if attempts_consumed >= max_attempts_per_run:
                    existing_run["status"] = "transport_failure"
                    existing_run["finished_at"] = existing_run.get("finished_at") or utc_now()
                    marker = "retry_budget_exhausted_resumes"
                    existing_run[marker] = int(existing_run.get(marker, 0)) + 1
                    save_progress()
                    continue
                run_record = existing_run
                run_record["status"] = "running"
                run_record["finished_at"] = None
                run_record["resume_executions"] = int(
                    run_record.get("resume_executions", 0)
                ) + 1
            else:
                run_record = new_run_record(doc_id, rep)
                manifest["runs"].append(run_record)
            run_index[key] = run_record
            document_text = document_texts[doc_id]
            prompt_bytes = build_prompt(skill_text, document_text).encode("utf-8")
            reason: str | None = None
            stdout = b""
            for attempt in range(attempts_consumed + 1, max_attempts_per_run + 1):
                if last_worker_finished_wall is not None and args.sleep_between:
                    elapsed = time.monotonic() - last_worker_finished_wall
                    remaining = args.sleep_between - elapsed
                    if remaining > 0:
                        time.sleep(remaining)
                attempt_started_wall = time.monotonic()
                attempt_started_at = utc_now()
                run_record["attempts"] = attempt
                run_record["active_attempt"] = {
                    "attempt": attempt,
                    "started_at": attempt_started_at,
                }
                save_progress()
                try:
                    completed = subprocess.run(
                        [cli, *worker_args],
                        input=prompt_bytes,
                        cwd=worker_cwd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                    )
                    stdout = completed.stdout
                    stderr = completed.stderr
                    returncode = completed.returncode
                    launch_error = None
                except OSError as exc:
                    stdout = b""
                    stderr = str(exc).encode("utf-8", errors="replace")
                    returncode = 127
                    launch_error = str(exc)
                last_worker_finished_wall = time.monotonic()
                run_record.pop("active_attempt", None)
                reason = transport_failure_reason(returncode, stdout)
                rejected_envelope_rel: str | None = None
                if is_turn_check_failure_reason(reason):
                    rejected_envelope_rel = (
                        f"raw/{doc_id}-rep{rep}-attempt{attempt}.rejected.json"
                    )
                    atomic_write(batch_dir / rejected_envelope_rel, stdout)
                will_retry = reason is not None and attempt < max_attempts_per_run
                attempt_status = "success" if reason is None else "transport_failure"
                attempt_record = {
                    "attempt": attempt,
                    "started_at": attempt_started_at,
                    "finished_at": utc_now(),
                    "wall_clock_seconds": round(
                        time.monotonic() - attempt_started_wall, 6
                    ),
                    "status": attempt_status,
                    "returncode": returncode,
                    "reason": reason,
                    "will_retry": will_retry,
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "launch_error": launch_error,
                }
                if rejected_envelope_rel is not None:
                    attempt_record["rejected_envelope"] = rejected_envelope_rel
                run_record["retry_log"].append(attempt_record)
                if reason is None:
                    break
                if will_retry:
                    run_record["status"] = "retrying"
                    save_progress()
                    continue
                break
            if reason is not None:
                run_record["status"] = "transport_failure"
            else:
                cli_result = json.loads(stdout)
                result_value = cli_result.get("result") if isinstance(cli_result, dict) else None
                if isinstance(result_value, str):
                    result_bytes = result_value.encode("utf-8")
                    prediction_text, fence_stripped = strip_registered_fence(result_value)
                    prediction_bytes = prediction_text.encode("utf-8")
                    model_json_valid = is_valid_json_text(prediction_text)
                else:
                    result_bytes = b""
                    prediction_bytes = b""
                    fence_stripped = False
                    model_json_valid = False
                result_path = batch_dir / run_record["files"]["result_json"]
                pred_path = batch_dir / run_record["files"]["prediction"]
                raw_text_path = batch_dir / run_record["files"]["raw_text"]
                atomic_write(result_path, stdout)
                atomic_write(pred_path, prediction_bytes)
                atomic_write(raw_text_path, result_bytes)
                run_record["model_output_valid_json"] = model_json_valid
                run_record["fence_stripped"] = fence_stripped
                record_model_provenance(run_record, cli_result)
                run_record["status"] = "completed" if model_json_valid else "model_failure"
            run_record["finished_at"] = utc_now()
            run_record["wall_clock_seconds"] = round(
                previous_run_wall_clock + time.monotonic() - run_started_wall, 6
            )
            save_progress()

    finished_at = utc_now()
    invocation_record["finished_at"] = finished_at
    manifest["finished_at"] = finished_at
    save_progress()
    summary = manifest["summary"]
    print(
        f"Batch {args.batch_id}: {summary['completed']} completed, "
        f"{summary['model_failures']} model failures, "
        f"{summary['transport_failures']} transport failures, "
        f"{summary['skipped_existing']} skipped."
    )
    return 1 if summary["transport_failures"] else 0


def run_batch(
    args: argparse.Namespace,
    *,
    project_root: Path,
    worker_cwd: Path,
) -> int:
    """Run a batch, retaining the global ledger lock for any holdout invocation."""

    validate_args(args)
    resolved_root = project_root.resolve()
    docs_dir = resolve_project_path(resolved_root, args.docs_dir)
    holdout_mode = "holdout" in str(docs_dir).casefold()
    if holdout_mode and args.allow_holdout:
        ledger_path = resolved_root / HOLDOUT_LEDGER_PATH
        with lock_holdout_ledger(ledger_path) as ledger_handle:
            return _run_batch_locked(
                args,
                project_root=resolved_root,
                worker_cwd=worker_cwd,
                holdout_ledger_handle=ledger_handle,
            )
    return _run_batch_locked(
        args,
        project_root=resolved_root,
        worker_cwd=worker_cwd,
        holdout_ledger_handle=None,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    project_root: Path = PROJECT_ROOT,
    worker_cwd: Path = WORKER_CWD,
) -> int:
    args = parse_args(argv)
    try:
        return run_batch(args, project_root=Path(project_root), worker_cwd=Path(worker_cwd))
    except RunnerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
