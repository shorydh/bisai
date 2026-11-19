#!/usr/bin/env python3
"""Record provenance for the R004 device runner without inventing results."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from verify_outputs import load_json, sha256_file, validate_case_fixture, validate_manifest


SEVEN_SOURCES = (
    "op_host/pad_v3_grad_def.cpp",
    "op_host/pad_v3_grad_infershape.cpp",
    "op_host/pad_v3_grad_tiling.cpp",
    "op_kernel/pad_v3_grad.cpp",
    "op_kernel/pad_v3_grad.h",
    "op_kernel/pad_v3_grad_tiling_data.h",
    "op_kernel/pad_v3_grad_tiling_key.h",
)
KNOWN_PROJECTS = {
    "d0b680d59d1dfa088dd24fff5d3128feb2758251bcd8d3b34b39635bad68f949": "P/r6",
    "700af8da3ef6679f48ebf8bbfa9d2f145d9357e9b6fd2e4f288542c662a1969b": "F",
}


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def fixture_snapshot(cases_root: Path) -> dict[str, Any]:
    _, variants = validate_manifest(cases_root)
    cases = {}
    for variant in variants:
        _, hashes = validate_case_fixture(cases_root, variant)
        cases[variant["case_id"]] = hashes
    return {
        "manifest_sha256": sha256_file(cases_root / "manifest.json"),
        "cases": cases,
    }


def project_snapshot(project_dir: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    hashes = {}
    for relative in SEVEN_SOURCES:
        file_hash = sha256_file(project_dir / relative)
        hashes[relative] = file_hash
        digest.update(f"{relative}\0{file_hash}\n".encode("utf-8"))
    tree_hash = digest.hexdigest()
    return {
        "seven_source_sha256": tree_hash,
        "identified_as": KNOWN_PROJECTS.get(tree_hash),
        "recognized": tree_hash in KNOWN_PROJECTS,
        "files": hashes,
    }


def begin(args: argparse.Namespace) -> None:
    cases_root = args.cases.resolve()
    record = {
        "schema_version": 1,
        "task_id": "Q06-R004-C-RUNNER-VALIDATION",
        "execution_mode": "device",
        "run_id": args.run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "device_id": args.device_id,
        "project_dir_requested": str(args.project_dir.resolve()),
        "project_source": project_snapshot(args.project_dir.resolve()),
        "vendor_root": str(args.vendor_root.resolve()),
        "expected_library": str(args.expected_library.resolve()),
        "cmake_cache": str(args.cmake_cache.resolve()),
        "vendor_config": str(args.vendor_config.resolve()),
        "runner_binary": str(args.runner_binary.resolve()),
        "cases_root": str(cases_root),
        "run_root": str(args.run_root.resolve()),
        "npu_smi_log": str(args.npu_smi_log.resolve()),
        "npu_smi_log_sha256": (
            sha256_file(args.npu_smi_log.resolve()) if args.npu_smi_log.is_file() else None
        ),
        "npu_smi_exit_code": args.npu_smi_exit_code,
        "environment": {
            key: os.environ.get(key)
            for key in ("ASCEND_HOME_PATH", "ASCEND_CUSTOM_OPP_PATH", "LD_LIBRARY_PATH",
                        "DEVICE_ID", "CANNJUDGE_COMPILE_JOBS")
        },
        "fixtures_before": fixture_snapshot(cases_root),
        "build": {
            "package_build_exit_code": None,
            "configure_exit_code": None,
            "compile_exit_code": None,
        },
        "device_execution_started": False,
    }
    write_json(args.run_root.resolve() / "run-record.json", record)


def case_record(args: argparse.Namespace) -> None:
    root = args.case_root.resolve()
    invocation_path = root / "invocation.json"
    invocation = load_json(invocation_path) if invocation_path.is_file() else {}
    output_path = root / "output" / "y.bin"
    stdout_path = args.stdout.resolve()
    stderr_path = args.stderr.resolve()
    result = {
        "schema_version": 1,
        "case_id": args.case_id,
        "execution_mode": "device",
        "started_at_ns": args.started_at_ns,
        "ended_at_ns": args.ended_at_ns,
        "runner_exit_code": args.exit_code,
        "command": args.command,
        "device_id": arg_device(invocation),
        "synchronized": invocation.get("synchronized") is True,
        "expected_library": invocation.get("expected_library"),
        "loaded_library": invocation.get("loaded_library"),
        "output_path": str(output_path),
        "output_exists": output_path.is_file(),
        "output_bytes": output_path.stat().st_size if output_path.is_file() else None,
        "output_sha256": sha256_file(output_path) if output_path.is_file() else None,
        "stdout_log": str(stdout_path),
        "stdout_sha256": sha256_file(stdout_path) if stdout_path.is_file() else None,
        "stderr_log": str(stderr_path),
        "stderr_sha256": sha256_file(stderr_path) if stderr_path.is_file() else None,
        "invocation_record": str(invocation_path) if invocation_path.is_file() else None,
    }
    write_json(root / "case-run.json", result)


def arg_device(invocation: dict[str, Any]) -> int | None:
    value = invocation.get("device_id")
    return value if isinstance(value, int) else None


def finalize(args: argparse.Namespace) -> None:
    run_root = args.run_root.resolve()
    record_path = run_root / "run-record.json"
    record = load_json(record_path)
    record["finished_at"] = datetime.now(timezone.utc).isoformat()
    record["build"]["configure_exit_code"] = args.configure_exit_code
    record["build"]["compile_exit_code"] = args.compile_exit_code
    record["build"]["package_build_exit_code"] = args.package_build_exit_code
    record["device_execution_started"] = args.device_execution_started
    record["verification_exit_code"] = args.verify_exit_code
    record["npu_smi_before_cases"] = {
        "path": str(args.npu_smi_before_cases.resolve()),
        "exit_code": args.npu_smi_before_cases_exit_code,
        "sha256": (
            sha256_file(args.npu_smi_before_cases.resolve())
            if args.npu_smi_before_cases.is_file() else None
        ),
    }
    record["npu_smi_after_cases"] = {
        "path": str(args.npu_smi_after_cases.resolve()),
        "exit_code": args.npu_smi_after_cases_exit_code,
        "sha256": (
            sha256_file(args.npu_smi_after_cases.resolve())
            if args.npu_smi_after_cases.is_file() else None
        ),
    }
    record["fixtures_after"] = fixture_snapshot(Path(record["cases_root"]))
    record["fixtures_unchanged"] = (
        record["fixtures_before"] == record["fixtures_after"]
    )
    record["project_source_after"] = project_snapshot(
        Path(record["project_dir_requested"])
    )
    record["project_source_unchanged"] = (
        record["project_source"] == record["project_source_after"]
    )
    write_json(record_path, record)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    begin_parser = subparsers.add_parser("begin")
    begin_parser.add_argument("--run-root", required=True, type=Path)
    begin_parser.add_argument("--run-id", required=True)
    begin_parser.add_argument("--project-dir", required=True, type=Path)
    begin_parser.add_argument("--vendor-root", required=True, type=Path)
    begin_parser.add_argument("--expected-library", required=True, type=Path)
    begin_parser.add_argument("--cmake-cache", required=True, type=Path)
    begin_parser.add_argument("--vendor-config", required=True, type=Path)
    begin_parser.add_argument("--runner-binary", required=True, type=Path)
    begin_parser.add_argument("--cases", required=True, type=Path)
    begin_parser.add_argument("--device-id", required=True, type=int)
    begin_parser.add_argument("--npu-smi-log", required=True, type=Path)
    begin_parser.add_argument("--npu-smi-exit-code", required=True, type=int)
    begin_parser.set_defaults(func=begin)

    case_parser = subparsers.add_parser("case")
    case_parser.add_argument("--case-root", required=True, type=Path)
    case_parser.add_argument("--case-id", required=True)
    case_parser.add_argument("--started-at-ns", required=True, type=int)
    case_parser.add_argument("--ended-at-ns", required=True, type=int)
    case_parser.add_argument("--exit-code", required=True, type=int)
    case_parser.add_argument("--command", required=True)
    case_parser.add_argument("--stdout", required=True, type=Path)
    case_parser.add_argument("--stderr", required=True, type=Path)
    case_parser.set_defaults(func=case_record)

    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--run-root", required=True, type=Path)
    finalize_parser.add_argument("--configure-exit-code", required=True, type=int)
    finalize_parser.add_argument("--compile-exit-code", required=True, type=int)
    finalize_parser.add_argument("--package-build-exit-code", required=True, type=int)
    finalize_parser.add_argument("--device-execution-started", action="store_true")
    finalize_parser.add_argument("--verify-exit-code", required=True, type=int)
    finalize_parser.add_argument("--npu-smi-before-cases", required=True, type=Path)
    finalize_parser.add_argument("--npu-smi-before-cases-exit-code", required=True, type=int)
    finalize_parser.add_argument("--npu-smi-after-cases", required=True, type=Path)
    finalize_parser.add_argument("--npu-smi-after-cases-exit-code", required=True, type=int)
    finalize_parser.set_defaults(func=finalize)

    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
