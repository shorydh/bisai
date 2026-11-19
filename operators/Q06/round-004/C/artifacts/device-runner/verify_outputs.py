#!/usr/bin/env python3
"""Strict acceptance verifier for the four R002 legal-edge cases.

The verifier never discovers cases by scanning directories. It follows only
manifest["variants"], validates each fixture contract, and compares exactly
three FP32 output values without broadcasting or accepting NaN.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


EXPECTED_CASE_IDS = (
    "int32-contiguous",
    "int32-split",
    "int64-contiguous",
    "int64-split",
)
EXPECTED_X_SHA256 = "3579185fcbb48197725ba969c688363da3e791e77245b011307e62339aa85e26"
EXPECTED_GOLDEN_SHA256 = "15ec7bf0b50732b49f8228e07d24365338f9e3ab994b00af08e5a3bffe55fd8b"
EXPECTED_X_SHAPE = [1, 1, 1, 5]
EXPECTED_Y_SHAPE = [1, 1, 1, 3]
RTOL = 1e-4
ATOL = 1e-4
STALE_MTIME_GRACE_NS = 1_000_000_000


class ContractError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON root is not an object: {path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def first_tensor(case: dict[str, Any], input_name: str | None, output: bool = False) -> dict[str, Any]:
    section = "outputs" if output else "inputs"
    for item in case.get(section, []):
        if output or item.get("name") == input_name:
            tensors = item.get("tensors")
            require(isinstance(tensors, list) and len(tensors) == 1,
                    f"{section} entry {input_name or 'output'} must contain exactly one tensor")
            require(isinstance(tensors[0], dict), f"invalid tensor metadata for {input_name or 'output'}")
            return tensors[0]
    raise ContractError(f"missing {section} entry {input_name or 'output'}")


def expected_padding_dtype(case_id: str) -> str:
    return "int32" if case_id.startswith("int32-") else "int64"


def expected_contiguous(case_id: str) -> bool:
    return case_id.endswith("-contiguous")


def validate_manifest(cases_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_path = cases_dir / "manifest.json"
    manifest = load_json(manifest_path)
    variants = manifest.get("variants")
    require(isinstance(variants, list), "manifest.variants must be a list")
    ids = [variant.get("case_id") for variant in variants if isinstance(variant, dict)]
    require(len(ids) == len(variants), "every manifest variant must be an object")
    require(len(ids) == len(set(ids)), "manifest contains duplicate case_id values")
    require(set(ids) == set(EXPECTED_CASE_IDS),
            f"manifest case IDs differ from required set: {ids}")
    return manifest, variants


def validate_case_fixture(
    cases_dir: Path, expected: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    case_id = expected.get("case_id")
    require(isinstance(case_id, str) and case_id in EXPECTED_CASE_IDS,
            f"unexpected case_id: {case_id!r}")
    case_dir = cases_dir / case_id
    require(case_dir.is_dir(), f"case directory missing: {case_dir}")
    case = load_json(case_dir / "case.json")
    attrs = case.get("attributes", {})
    require(attrs.get("mode") == "edge", f"{case_id}: mode must be edge")
    require(attrs.get("paddings_contiguous") is expected_contiguous(case_id),
            f"{case_id}: paddings_contiguous does not match case_id")

    x = first_tensor(case, "x")
    padding = first_tensor(case, "paddings")
    y = first_tensor(case, None, output=True)
    dtype = expected_padding_dtype(case_id)
    padding_shape = [4, 2] if expected_contiguous(case_id) else [2, 4]
    padding_bytes = 32 if dtype == "int32" else 64

    require(x.get("dtype") == "float32" and x.get("shape") == EXPECTED_X_SHAPE and
            x.get("bytes") == 20, f"{case_id}: invalid x metadata")
    require(padding.get("dtype") == dtype and padding.get("shape") == padding_shape and
            padding.get("bytes") == padding_bytes, f"{case_id}: invalid paddings metadata")
    require(y.get("dtype") == "float32" and y.get("shape") == EXPECTED_Y_SHAPE and
            y.get("bytes") == 12, f"{case_id}: invalid y metadata")
    require(y.get("rtol") == RTOL and y.get("atol") == ATOL,
            f"{case_id}: tolerance must be rtol=atol=1e-4")

    x_path = case_dir / "input" / "x.bin"
    padding_path = case_dir / "input" / "paddings.bin"
    golden_path = case_dir / "golden" / "y.bin"
    for path, size in ((x_path, 20), (padding_path, padding_bytes), (golden_path, 12)):
        require(path.is_file(), f"{case_id}: fixture missing {path.name}")
        require(path.stat().st_size == size,
                f"{case_id}: {path.name} size {path.stat().st_size}, expected {size}")

    actual_hashes = {
        "x": sha256_file(x_path),
        "paddings": sha256_file(padding_path),
        "golden": sha256_file(golden_path),
    }
    require(actual_hashes["x"] == expected.get("input_x_sha256") == EXPECTED_X_SHA256,
            f"{case_id}: x SHA256 mismatch")
    require(actual_hashes["paddings"] == expected.get("paddings_sha256"),
            f"{case_id}: paddings SHA256 mismatch")
    require(actual_hashes["golden"] == expected.get("golden_y_sha256") == EXPECTED_GOLDEN_SHA256,
            f"{case_id}: golden SHA256 mismatch")
    require(expected.get("golden_y") == [0.0, 0.0, 0.0],
            f"{case_id}: manifest golden is not [0,0,0]")

    golden = np.frombuffer(golden_path.read_bytes(), dtype="<f4")
    require(golden.shape == (3,), f"{case_id}: golden is not three FP32 values")
    require(np.array_equal(golden, np.zeros(3, dtype=np.float32)),
            f"{case_id}: golden bytes are not exactly three zero FP32 values")
    return case, actual_hashes


def parse_cmake_cache(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ContractError(f"CMake cache missing: {path}")
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line or line.startswith(("#", "//")) or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key] = value
    return result


def same_path(left: str, right: str) -> bool:
    try:
        return Path(left).resolve() == Path(right).resolve()
    except (OSError, RuntimeError):
        return False


def validate_device_credentials(run_record_path: Path) -> tuple[str, int]:
    record = load_json(run_record_path)
    require(record.get("execution_mode") == "device", "run record is not device execution")
    device_id = record.get("device_id")
    require(isinstance(device_id, int) and device_id >= 0, "run record has invalid device_id")
    project_source = record.get("project_source", {})
    require(project_source.get("recognized") is True, "selected project source is not P or F")
    project_dir = record.get("project_dir_requested")
    vendor_root = record.get("vendor_root")
    expected_library = record.get("expected_library")
    cmake_cache_path = record.get("cmake_cache")
    vendor_config_path = record.get("vendor_config")
    require(isinstance(project_dir, str) and project_dir, "run record lacks project_dir_requested")
    require(isinstance(vendor_root, str) and vendor_root, "run record lacks vendor_root")
    require(isinstance(expected_library, str) and expected_library, "run record lacks expected_library")
    require(isinstance(cmake_cache_path, str) and cmake_cache_path, "run record lacks cmake_cache")
    require(isinstance(vendor_config_path, str) and vendor_config_path, "run record lacks vendor_config")

    cache = parse_cmake_cache(Path(cmake_cache_path))
    require(same_path(cache.get("PAD_V3_GRAD_PROJECT_DIR:PATH", ""), project_dir),
            "CMake cache project path does not match requested project")
    require(same_path(cache.get("PAD_V3_GRAD_RESOLVED_VENDOR_ROOT:INTERNAL", ""), vendor_root),
            "CMake cache vendor root does not match selected project")
    vendor_config = load_json(Path(vendor_config_path))
    require(same_path(vendor_config.get("resolved_project_dir", ""), project_dir),
            "vendor config project path does not match requested project")
    require(same_path(vendor_config.get("op_api_library", ""), expected_library),
            "vendor config library does not match expected library")
    expected_library_path = Path(expected_library)
    require(expected_library_path.is_file(), "expected vendor library is missing")
    require(sha256_file(expected_library_path) == vendor_config.get("library_sha256"),
            "vendor library bytes do not match configured SHA256")
    expected_header = Path(project_dir) / "build/packages/vendors/pad_v3_grad_custom/op_api/include/aclnn_pad_v3_grad.h"
    expected_version = Path(project_dir) / "build/packages/vendors/pad_v3_grad_custom/version.info"
    require(same_path(vendor_config.get("op_api_header", ""), str(expected_header)),
            "vendor config header is not under the selected project")
    require(expected_header.is_file() and sha256_file(expected_header) == vendor_config.get("header_sha256"),
            "vendor header bytes do not match configured SHA256")
    require(same_path(vendor_config.get("version_info", ""), str(expected_version)),
            "vendor version file is not under the selected project")
    require(expected_version.is_file() and sha256_file(expected_version) == vendor_config.get("version_info_sha256"),
            "vendor version bytes do not match configured SHA256")
    return expected_library, device_id


def compare_case(
    cases_dir: Path,
    run_root: Path,
    variant: dict[str, Any],
    execution_mode: str,
    expected_library: str | None,
    expected_device_id: int | None,
) -> dict[str, Any]:
    case_id = variant["case_id"]
    result: dict[str, Any] = {"case_id": case_id, "status": "FAIL"}
    try:
        _, input_hashes = validate_case_fixture(cases_dir, variant)
        case_run_dir = run_root / case_id
        output_path = case_run_dir / "output" / "y.bin"
        case_run_path = case_run_dir / "case-run.json"
        case_run: dict[str, Any] = {}
        if case_run_path.is_file():
            case_run = load_json(case_run_path)

        require(output_path.is_file(), "missing_output")
        size = output_path.stat().st_size
        require(size == 12, f"output_size_mismatch:{size}!=12")
        if case_run.get("started_at_ns") is not None:
            require(output_path.stat().st_mtime_ns + STALE_MTIME_GRACE_NS >=
                    int(case_run["started_at_ns"]),
                    "stale_output")
            require(int(case_run["started_at_ns"]) <= int(case_run.get("ended_at_ns", -1)),
                    "invalid_case_run_times")

        actual_bytes = output_path.read_bytes()
        actual = np.frombuffer(actual_bytes, dtype="<f4")
        require(actual.shape == (3,), f"output_shape_mismatch:{actual.shape}!= (3,)")
        require(not np.isnan(actual).any(), "output_contains_nan")
        golden = np.frombuffer(
            (cases_dir / case_id / "golden" / "y.bin").read_bytes(), dtype="<f4"
        )
        abs_error = np.abs(actual.astype(np.float64) - golden.astype(np.float64))
        close = np.isclose(actual.astype(np.float64), golden.astype(np.float64),
                           rtol=RTOL, atol=ATOL, equal_nan=False)

        result.update({
            "execution_mode": execution_mode,
            "device_execution": execution_mode == "device",
            "input_sha256": input_hashes,
            "output_path": str(output_path),
            "output_bytes": size,
            "output_sha256": sha256_bytes(actual_bytes),
            "actual": [float(value) for value in actual],
            "golden": [float(value) for value in golden],
            "abs_error": [float(value) for value in abs_error],
            "max_abs_error": float(abs_error.max()),
            "rtol": RTOL,
            "atol": ATOL,
        })
        if case_run:
            result["runner_exit_code"] = case_run.get("runner_exit_code")
            result["synchronized"] = case_run.get("synchronized")
            result["loaded_library"] = case_run.get("loaded_library")
            result["stdout_log"] = case_run.get("stdout_log")
            result["stderr_log"] = case_run.get("stderr_log")

        if execution_mode == "device":
            require(case_run, "missing_case_run_record")
            require(case_run.get("execution_mode") == "device", "case is not device execution")
            require(case_run.get("runner_exit_code") == 0, "runner_exit_code_nonzero")
            require(case_run.get("device_id") == expected_device_id, "case_device_id_mismatch")
            require(case_run.get("synchronized") is True, "device_stream_not_synchronized")
            loaded = case_run.get("loaded_library")
            require(isinstance(loaded, str) and loaded, "loaded_library_missing")
            require(expected_library is not None and same_path(loaded, expected_library),
                    "loaded_library_mismatch")
            require(case_run.get("output_sha256") == result["output_sha256"],
                    "output_sha256_does_not_match_run_record")
            for log_name, hash_name in (("stdout_log", "stdout_sha256"),
                                        ("stderr_log", "stderr_sha256")):
                log_path = case_run.get(log_name)
                require(isinstance(log_path, str) and Path(log_path).is_file(),
                        f"{log_name}_missing")
                require(sha256_file(Path(log_path)) == case_run.get(hash_name),
                        f"{log_name}_sha256_mismatch")

        if not bool(close.all()):
            result["status"] = "FAIL"
            result["reason"] = "value_out_of_tolerance"
        else:
            result["status"] = "PASS"
            result["reason"] = None
    except ContractError as exc:
        result["reason"] = str(exc)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--execution-mode", required=True, choices=("synthetic", "device"))
    parser.add_argument("--run-record", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    report: dict[str, Any] = {
        "schema_version": 1,
        "task_id": "Q06-R004-C-RUNNER-VALIDATION",
        "execution_mode": args.execution_mode,
        "device_execution": args.execution_mode == "device",
        "synthetic_fixture": args.execution_mode == "synthetic",
        "cases_root": str(args.cases.resolve()),
        "run_root": str(args.run_root.resolve()),
    }
    try:
        manifest, variants = validate_manifest(args.cases.resolve())
        report["manifest_sha256"] = sha256_file(args.cases.resolve() / "manifest.json")
        expected_library = None
        expected_device_id = None
        if args.execution_mode == "device":
            require(args.run_record is not None, "device mode requires --run-record")
            expected_library, expected_device_id = validate_device_credentials(
                args.run_record.resolve()
            )
            report["run_record"] = str(args.run_record.resolve())
            report["expected_library"] = expected_library
        cases = [
            compare_case(args.cases.resolve(), args.run_root.resolve(), variant,
                         args.execution_mode, expected_library, expected_device_id)
            for variant in variants
        ]
        report["cases"] = cases
        report["all_pass"] = all(case["status"] == "PASS" for case in cases)
        report["contract_ok"] = True
        report["manifest_variant_count"] = len(manifest["variants"])
    except (ContractError, OSError, ValueError) as exc:
        report["cases"] = []
        report["all_pass"] = False
        report["contract_ok"] = False
        report["contract_error"] = str(exc)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if report["all_pass"] and report["contract_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
