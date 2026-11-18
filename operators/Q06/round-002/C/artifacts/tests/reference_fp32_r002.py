#!/usr/bin/env python3
"""Clean FP32 reference replay and legality separation for Q06 round-002.

The round-001 driver installed a fake bfloat16 equal to float32. This driver
requires the real ml_dtypes dependency, prevents the reference BF16 branch,
derives all summaries from actual arrays, and separates the old periodic-pad
candidate from a legal edge candidate.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
import time
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

import ml_dtypes
import numpy as np
import torch


REFERENCE_SHA256 = "1542d63e602aa3aaa60242e91ea0d6a8ac038bab788c6898dc4777557f040ed3"
R6_PACKAGE_SHA256 = "18679dad71f9ea7723ca524599b0d9363861aeadf8f8032202f6391199a5a85a"
R6_SEVEN_SOURCE_SHA256 = (
    "d0b680d59d1dfa088dd24fff5d3128feb2758251bcd8d3b34b39635bad68f949"
)
OLD_INPUT_SHA256 = (
    "daa2b4341c6f1f56616b24a8195cbfd4bdd8ede0201f9370f72d415c7e4559b7"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_metadata(name: str) -> dict[str, Any]:
    distribution = importlib.metadata.distribution(name)
    metadata_path = Path(str(distribution._path)) / "METADATA"
    return {
        "name": distribution.metadata.get("Name"),
        "version": distribution.version,
        "dist_info": str(distribution._path),
        "metadata_path": str(metadata_path),
        "metadata_sha256": sha256_file(metadata_path)
        if metadata_path.is_file()
        else None,
    }


def f32(value: float | np.floating) -> np.float32:
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        return np.float32(value)


def add_scalar32(values: Iterable[float]) -> np.float32:
    """Mirror the frozen r6 AddScalar source; not a device execution."""
    largest = f32(3.402823466e38)
    total = f32(0)
    correction = f32(0)
    scale = f32(1)
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        for raw in values:
            value = f32(f32(raw) * scale)
            next_value = f32(total + value)
            if (
                (next_value > largest or next_value < -largest)
                and -largest <= total <= largest
                and -largest <= value <= largest
            ):
                scale = f32(scale * f32(0.5))
                total = f32(total * f32(0.5))
                correction = f32(correction * f32(0.5))
                value = f32(value * f32(0.5))
                next_value = f32(total + value)
            if (
                -largest <= next_value <= largest
                and -largest <= total <= largest
                and -largest <= value <= largest
            ):
                abs_sum = f32(-total if total < 0 else total)
                abs_value = f32(-value if value < 0 else value)
                delta = (
                    f32(f32(total - next_value) + value)
                    if abs_sum >= abs_value
                    else f32(f32(value - next_value) + total)
                )
                correction = f32(correction + delta)
            else:
                correction = f32(0)
            total = next_value
        return f32(f32(total + correction) / scale)


def exact_float32_sum(values: list[np.float32]) -> float:
    return float(
        sum(
            (Fraction.from_float(float(value)) for value in values),
            start=Fraction(0, 1),
        )
    )


def sequential_fp64_sum(values: list[np.float32]) -> float:
    total = np.float64(0.0)
    for value in values:
        total = np.float64(total + np.float64(value))
    return float(total)


def make_padding_layouts(
    pads: list[tuple[int, int]], dtype: type[np.integer]
) -> list[tuple[bool, np.ndarray]]:
    rank = len(pads)
    contiguous = np.asarray(pads, dtype=dtype)
    split = np.asarray(
        [[row[0] for row in pads], [row[1] for row in pads]],
        dtype=dtype,
    ).reshape(2, rank)
    return [(True, contiguous), (False, split)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run_started_at = datetime.now(timezone.utc).isoformat()
    run_started_counter = time.perf_counter()

    reference_root = Path(args.reference_root).resolve()
    reference_path = reference_root / "reference.py"
    reference_hash = sha256_file(reference_path)
    if reference_hash != REFERENCE_SHA256:
        raise RuntimeError(
            f"reference.py SHA256 mismatch: {reference_hash} != {REFERENCE_SHA256}"
        )

    sys.path.insert(0, str(reference_root))
    import reference  # type: ignore  # noqa: E402

    if reference.bfloat16 is not ml_dtypes.bfloat16:
        raise RuntimeError("reference.bfloat16 is not the real ml_dtypes.bfloat16")

    bfloat_branch_attempts: list[str] = []
    original_tensor_callable = reference.torch.tensor

    def forbidden_bf16_conversion(*call_args: Any, **call_kwargs: Any) -> Any:
        bfloat_branch_attempts.append(
            f"torch.tensor({call_args!r}, {call_kwargs!r})"
        )
        raise AssertionError("reference entered its bfloat16 conversion branch")

    cases = [
        {
            "case_id": "reflect-periodic-old-candidate",
            "mode": "reflect",
            "input_values": [0.0, 1.7e38, 0.0, 1.0, 0.0, -1.7e38],
            "shape": [1, 1, 1, 6],
            "pads": [(0, 0), (0, 0), (0, 0), (1, 3)],
            "legality": {
                "status": "invalid-for-formal-legal-matrix",
                "reason": (
                    "Current CANN ops-math reflect validation requires each "
                    "pad to be less than inferredOutputShape; back pad 3 is "
                    "not less than output dimension 2."
                ),
                "rule_source": (
                    "gitcode.com/cann/ops-math@3b2baac63624c32e03781bd9f0290f1a4584f0c7:"
                    "conversion/pad_v3_grad/op_host/arch35/"
                    "pad_v3_grad_tiling_arch35.cpp:548-558"
                ),
            },
        },
        {
            "case_id": "edge-legal-cancellation",
            "mode": "edge",
            "input_values": [1.7e38, 1.0, -1.7e38, 0.0, 0.0],
            "shape": [1, 1, 1, 5],
            "pads": [(0, 0), (0, 0), (0, 0), (2, 0)],
            "legality": {
                "status": "legal-candidate",
                "reason": (
                    "Edge mode; front pad 2 is less than inferred output "
                    "dimension 3 and back pad is 0."
                ),
                "rule_source": (
                    "conversion/pad_v3_grad_replicate/README.md and "
                    "aclnnReplicationPad2dBackward.md"
                ),
            },
        },
    ]

    reference.torch.tensor = forbidden_bf16_conversion
    try:
        for case in cases:
            x = np.asarray(case["input_values"], dtype=np.float32).reshape(
                case["shape"]
            )
            case["input_sha256"] = hashlib.sha256(x.tobytes()).hexdigest()
            if case["case_id"] == "reflect-periodic-old-candidate":
                if case["input_sha256"] != OLD_INPUT_SHA256:
                    raise RuntimeError("Old candidate input SHA256 changed")
            output_dimension = (
                x.shape[-1] - case["pads"][-1][0] - case["pads"][-1][1]
            )
            mapped = reference._pad_index(
                output_dimension,
                case["pads"][-1][0],
                case["pads"][-1][1],
                case["mode"],
            )
            sources = [
                index
                for index, target in enumerate(np.asarray(mapped).tolist())
                if target == 0
            ]
            values = x.reshape(-1)[sources]
            case["inferred_output_dimension"] = output_dimension
            case["output_0_sources"] = sources
            case["output_0_values_in_source_order"] = [
                float(value) for value in values
            ]
            case["reference_runs"] = []
            for dtype in (np.int32, np.int64):
                for contiguous, paddings in make_padding_layouts(
                    case["pads"], dtype
                ):
                    output = reference.impl(
                        x,
                        paddings,
                        mode=case["mode"],
                        paddings_contiguous=contiguous,
                    )
                    case["reference_runs"].append(
                        {
                            "paddings_dtype": np.dtype(dtype).name,
                            "paddings_contiguous": contiguous,
                            "paddings": paddings.tolist(),
                            "output_shape": list(output.shape),
                            "output_dtype": np.dtype(output.dtype).name,
                            "output": [
                                float(value) for value in output.reshape(-1)
                            ],
                            "output_sha256": hashlib.sha256(
                                output.tobytes()
                            ).hexdigest(),
                        }
                    )

            outputs = [
                np.asarray(run["output"], dtype=np.float32)
                for run in case["reference_runs"]
            ]
            first_output = outputs[0]
            independent_fp64 = sequential_fp64_sum(values.tolist())
            exact_real = exact_float32_sum(values.tolist())
            source_model = add_scalar32(values.tolist())
            error = abs(float(source_model) - float(first_output[0]))
            case["derived_summary"] = {
                "all_runs_returned": len(outputs) == 4,
                "all_shapes_expected": all(
                    run["output_shape"]
                    == [1, 1, 1, case["inferred_output_dimension"]]
                    for run in case["reference_runs"]
                ),
                "all_output_dtypes_float32": all(
                    run["output_dtype"] == "float32"
                    for run in case["reference_runs"]
                ),
                "all_actual_outputs_equal": all(
                    np.array_equal(first_output, output)
                    for output in outputs[1:]
                ),
                "actual_reference_output_0": float(first_output[0]),
                "exact_real_sum_of_float32_sources": exact_real,
                "sequential_fp64_source_sum": independent_fp64,
                "r6_scalar_model_output_0": float(source_model),
                "candidate_abs_error": error,
                "candidate_within_tolerance": bool(error <= 1e-4),
            }
    finally:
        reference.torch.tensor = original_tensor_callable

    all_runs_ok = all(
        all(
            case["derived_summary"][key]
            for key in (
                "all_runs_returned",
                "all_shapes_expected",
                "all_output_dtypes_float32",
                "all_actual_outputs_equal",
            )
        )
        for case in cases
    )
    legal_cases = [
        case
        for case in cases
        if case["legality"]["status"] == "legal-candidate"
    ]
    legal_candidates_match = all(
        case["derived_summary"]["candidate_within_tolerance"]
        for case in legal_cases
    )
    result = {
        "task_id": "Q06-R002-C-REFERENCE-DEVICE-20261117",
        "case_family": "clean-fp32-reference-and-legality",
        "source": {
            "r6_package_sha256": R6_PACKAGE_SHA256,
            "r6_seven_source_sha256": R6_SEVEN_SOURCE_SHA256,
            "reference_path": str(reference_path),
            "reference_sha256": reference_hash,
        },
        "dependencies": {
            "python": {
                "version": platform.python_version(),
                "implementation": platform.python_implementation(),
                "executable": sys.executable,
            },
            "numpy": {
                "version": np.__version__,
                "module_path": str(Path(np.__file__).resolve()),
                "metadata": package_metadata("numpy"),
            },
            "torch": {
                "version": torch.__version__,
                "module_path": str(Path(torch.__file__).resolve()),
                "metadata": package_metadata("torch"),
            },
            "ml_dtypes": {
                "version": ml_dtypes.__version__,
                "module_path": str(Path(ml_dtypes.__file__).resolve()),
                "metadata": package_metadata("ml_dtypes"),
                "bfloat16_type": repr(ml_dtypes.bfloat16),
                "float32_equals_bfloat16": bool(
                    np.dtype("float32") == ml_dtypes.bfloat16
                ),
            },
        },
        "dispatch_checks": {
            "reference_bfloat16_is_real_dependency": True,
            "forbidden_bfloat16_branch_calls": len(bfloat_branch_attempts),
            "bfloat16_branch_not_taken": len(bfloat_branch_attempts) == 0,
        },
        "cases": cases,
        "derived_summary": {
            "reference_execution_ok": all_runs_ok,
            "legal_candidate_count": len(legal_cases),
            "all_legal_candidates_within_tolerance": legal_candidates_match,
            "device_execution": False,
            "process_exit_code": (
                0 if all_runs_ok and legal_candidates_match else 1
            ),
        },
        "cpu_run": {
            "started_at_utc": run_started_at,
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": time.perf_counter() - run_started_counter,
        },
        "scope": {
            "official_judge_submission": False,
            "interpretation": (
                "Real dependency and CPU official reference only. The "
                "periodic reflect candidate is retained but is outside the "
                "current formal reflect padding constraint. The edge case is "
                "a legal CPU-model counterexample candidate and still needs "
                "an NPU result."
            ),
        },
    }
    Path(args.output).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return int(result["derived_summary"]["process_exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
