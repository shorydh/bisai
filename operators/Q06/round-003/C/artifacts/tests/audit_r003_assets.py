#!/usr/bin/env python3
"""Verify R002 input reuse, P/F identities, and A CANNLab build evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path


SEVEN = [
    "op_host/pad_v3_grad_def.cpp",
    "op_host/pad_v3_grad_infershape.cpp",
    "op_host/pad_v3_grad_tiling.cpp",
    "op_kernel/pad_v3_grad.cpp",
    "op_kernel/pad_v3_grad.h",
    "op_kernel/pad_v3_grad_tiling_data.h",
    "op_kernel/pad_v3_grad_tiling_key.h",
]

EXPECTED = {
    "P": "d0b680d59d1dfa088dd24fff5d3128feb2758251bcd8d3b34b39635bad68f949",
    "F": "700af8da3ef6679f48ebf8bbfa9d2f145d9357e9b6fd2e4f288542c662a1969b",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seven_tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for name in SEVEN:
        digest.update((name + "\0" + sha256(root / name) + "\n").encode("utf-8"))
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--round-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    started_at = datetime.now(timezone.utc).isoformat()
    started_counter = time.perf_counter()

    root = Path(args.round_root).resolve()
    artifacts = root / "artifacts"
    errors: list[str] = []

    source_results = {}
    for arm in ("P", "F"):
        source_root = artifacts / "source" / arm
        tree_hash = seven_tree_hash(source_root)
        file_count = len([path for path in source_root.rglob("*") if path.is_file()])
        if tree_hash != EXPECTED[arm]:
            errors.append(f"{arm} seven-source hash mismatch: {tree_hash}")
        if file_count != 38:
            errors.append(f"{arm} file count is {file_count}, expected 38")
        source_results[arm] = {
            "seven_source_sha256": tree_hash,
            "expected_ok": tree_hash == EXPECTED[arm],
            "file_count": file_count,
        }

    device_manifest_path = (
        artifacts
        / "device-case"
        / "edge-legal-cancellation"
        / "manifest.json"
    )
    device_manifest = json.loads(device_manifest_path.read_text(encoding="utf-8"))
    variant_results = []
    case_root = device_manifest_path.parent
    for expected in device_manifest["variants"]:
        variant_root = case_root / expected["case_id"]
        actual = {
            "x": sha256(variant_root / "input" / "x.bin"),
            "paddings": sha256(variant_root / "input" / "paddings.bin"),
            "golden": sha256(variant_root / "golden" / "y.bin"),
        }
        matches = {
            "x": actual["x"] == expected["input_x_sha256"],
            "paddings": actual["paddings"] == expected["paddings_sha256"],
            "golden": actual["golden"] == expected["golden_y_sha256"],
        }
        if not all(matches.values()):
            errors.append(f"Device case mismatch: {expected['case_id']} {matches}")
        case_json = json.loads(
            (variant_root / "case.json").read_text(encoding="utf-8")
        )
        if case_json["attributes"]["mode"] != "edge":
            errors.append(f"Wrong mode in {expected['case_id']}")
        variant_results.append(
            {
                "case_id": expected["case_id"],
                "actual": actual,
                "matches_manifest": matches,
                "mode": case_json["attributes"]["mode"],
                "paddings_contiguous": case_json["attributes"][
                    "paddings_contiguous"
                ],
            }
        )

    a_root = artifacts / "reference" / "a-cannlab-facfb39"
    a_p = json.loads((a_root / "completed_P.json").read_text(encoding="utf-8"))
    a_p_log = a_root / "completed_P.log"
    actual_p_files = {
        name: sha256(artifacts / "source" / "P" / name) for name in a_p["source_files_before"]
    }
    source_matches_a = actual_p_files == a_p["source_files_before"]
    log_hash_matches = sha256(a_p_log) == a_p["log_sha256"]
    if not source_matches_a:
        errors.append("P source hashes do not match A CANNLab P build")
    if not log_hash_matches:
        errors.append("A CANNLab P.log hash mismatch")
    if a_p.get("npu_test_executed") is not False:
        errors.append("A CANNLab P record unexpectedly claims NPU test execution")

    result = {
        "task_id": "Q06-R003-C-NUMERICAL-BOUNDARY",
        "observed_at_utc": started_at,
        "audit_duration_seconds": time.perf_counter() - started_counter,
        "source_results": source_results,
        "device_inputs": variant_results,
        "a_cannlab": {
            "reference_commit": "facfb39ece01643fa7f9452d09971f9ca4d2b246",
            "arm": "P",
            "build_exit_code": a_p["exit_code"],
            "build_pass": a_p["build_pass"],
            "source_unchanged": a_p["source_unchanged"],
            "source_hashes_match_local_P": source_matches_a,
            "log_sha256_matches": log_hash_matches,
            "npu_test_executed": a_p["npu_test_executed"],
            "scope": a_p["scope"],
        },
        "errors": errors,
        "verified": not errors,
    }
    Path(args.output).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
