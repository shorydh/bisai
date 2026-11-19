#!/usr/bin/env python3
"""Audit copied frozen inputs and identify stale UT fixture assumptions."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


SEVEN = (
    "op_host/pad_v3_grad_def.cpp",
    "op_host/pad_v3_grad_infershape.cpp",
    "op_host/pad_v3_grad_tiling.cpp",
    "op_kernel/pad_v3_grad.cpp",
    "op_kernel/pad_v3_grad.h",
    "op_kernel/pad_v3_grad_tiling_data.h",
    "op_kernel/pad_v3_grad_tiling_key.h",
)
EXPECTED = {
    "P": "d0b680d59d1dfa088dd24fff5d3128feb2758251bcd8d3b34b39635bad68f949",
    "F": "700af8da3ef6679f48ebf8bbfa9d2f145d9357e9b6fd2e4f288542c662a1969b",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seven_hash(root: Path) -> str:
    value = hashlib.sha256()
    for relative in SEVEN:
        value.update(f"{relative}\0{digest(root / relative)}\n".encode("utf-8"))
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    round_root = args.round.resolve()
    artifacts = round_root / "artifacts"

    source_results = {}
    for arm in ("P", "F"):
        root = artifacts / "source" / arm
        source_results[arm] = {
            "seven_source_sha256": seven_hash(root),
            "expected": EXPECTED[arm],
            "matches": seven_hash(root) == EXPECTED[arm],
            "file_count": sum(path.is_file() for path in root.rglob("*")),
        }

    cases = artifacts / "device-case" / "edge-legal-cancellation"
    manifest = json.loads((cases / "manifest.json").read_text(encoding="utf-8"))
    case_results = []
    for item in manifest["variants"]:
        root = cases / item["case_id"]
        actual = {
            "x": digest(root / "input" / "x.bin"),
            "paddings": digest(root / "input" / "paddings.bin"),
            "golden": digest(root / "golden" / "y.bin"),
        }
        case_results.append({
            "case_id": item["case_id"],
            "hashes": actual,
            "matches": (
                actual["x"] == item["input_x_sha256"] and
                actual["paddings"] == item["paddings_sha256"] and
                actual["golden"] == item["golden_y_sha256"]
            ),
        })

    p = artifacts / "source" / "P"
    host_ut = (p / "tests/ut/op_host/test_pad_v3_grad_tiling.cpp").read_text(encoding="utf-8")
    kernel_ut = (p / "tests/ut/op_kernel/test_pad_v3_grad.cpp").read_text(encoding="utf-8")
    tiling = (p / "op_host/pad_v3_grad_tiling.cpp").read_text(encoding="utf-8")
    tiling_data = (p / "op_kernel/pad_v3_grad_tiling_data.h").read_text(encoding="utf-8")
    fixture_findings = {
        "host_ut_old_key_1": "ge::GRAPH_SUCCESS, 1UL" in host_ut,
        "source_fp32_rank_le_8_uses_key_3": bool(re.search(
            r"dtype\s*==\s*ge::DT_FLOAT16.*?PADV3GRAD_TPL_SCH_MODE_2"
            r".*?PADV3GRAD_TPL_SCH_MODE_3",
            tiling,
            flags=re.DOTALL,
        )),
        "kernel_ut_references_removed_totalNum": "tilingData->totalNum" in kernel_ut,
        "tiling_data_defines_totalNum": "totalNum" in tiling_data,
    }
    fixture_findings["requires_fixture_update"] = (
        fixture_findings["host_ut_old_key_1"] and
        fixture_findings["source_fp32_rank_le_8_uses_key_3"] or
        fixture_findings["kernel_ut_references_removed_totalNum"] and
        not fixture_findings["tiling_data_defines_totalNum"]
    )

    reference = p / "samples/reference.py"
    result = {
        "task_id": "Q06-R004-C-RUNNER-VALIDATION",
        "round_id": "round-004",
        "source_results": source_results,
        "device_cases": case_results,
        "reference_sha256": digest(reference),
        "reference_expected_sha256":
            "1542d63e602aa3aaa60242e91ea0d6a8ac038bab788c6898dc4777557f040ed3",
        "fixture_findings": fixture_findings,
        "verified": (
            all(item["matches"] for item in source_results.values()) and
            all(item["matches"] for item in case_results) and
            digest(reference) ==
            "1542d63e602aa3aaa60242e91ea0d6a8ac038bab788c6898dc4777557f040ed3"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
