#!/usr/bin/env python3
"""Run the official Python reference on the smallest candidate found by E002."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import types
from pathlib import Path

import numpy as np

from r6_boundary import (
    REFLECT,
    add_scalar32,
    full_r6_sources,
    reference_scalar_sum,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    reference_root = Path(args.reference_root).resolve()
    # The problem reference imports bfloat16 unconditionally. This case is
    # FP32, so a stub is enough and avoids a dependency on ml_dtypes.
    if "ml_dtypes" not in sys.modules:
        stub = types.ModuleType("ml_dtypes")
        stub.bfloat16 = np.dtype("float32")
        sys.modules["ml_dtypes"] = stub
    sys.path.insert(0, str(reference_root))
    import reference  # type: ignore  # noqa: E402

    x = np.asarray(
        [0.0, 1.7e38, 0.0, 1.0, 0.0, -1.7e38],
        dtype=np.float32,
    ).reshape(1, 1, 1, 6)
    paddings_contiguous = np.asarray(
        [[0, 0], [0, 0], [0, 0], [1, 3]],
        dtype=np.int32,
    )
    paddings_split = np.asarray(
        [[0, 0, 0, 1], [0, 0, 0, 3]],
        dtype=np.int32,
    )
    output_shape = [1, 1, 1, 2]
    sources = full_r6_sources(
        list(x.shape),
        output_shape,
        [0, 0, 0, 1],
        REFLECT,
        0,
    )
    values = x.reshape(-1)[sources]
    reference_runs = []
    for dtype in (np.int32, np.int64):
        for contiguous, paddings in (
            (True, paddings_contiguous.astype(dtype)),
            (False, paddings_split.astype(dtype)),
        ):
            official = reference.impl(
                x,
                paddings,
                mode="reflect",
                paddings_contiguous=contiguous,
            )
            reference_runs.append(
                {
                    "paddings_dtype": str(np.dtype(dtype)),
                    "paddings_contiguous": contiguous,
                    "paddings": paddings.tolist(),
                    "output_shape": list(official.shape),
                    "output": [float(v) for v in official.reshape(-1)],
                }
            )
    model_value = add_scalar32(values.tolist())
    independent_fp64 = reference_scalar_sum(values.tolist())
    official_zero = 0.0
    report = {
        "case": "minimal-finite-cancellation",
        "source": {
            "r6_official_task_id": 1367774,
            "r6_package_sha256": "18679dad71f9ea7723ca524599b0d9363861aeadf8f8032202f6391199a5a85a",
            "reference_root": str(reference_root),
            "torch_version": __import__("torch").__version__,
        },
        "input": {
            "tensor_shape": list(x.shape),
            "tensor_dtype": "float32",
            "tensor_sha256": hashlib.sha256(x.tobytes()).hexdigest(),
            "mode": "reflect",
            "finite_values": True,
        },
        "reference_runs": reference_runs,
        "output_0_sources": sources,
        "output_0_values_in_source_order": [float(v) for v in values],
        "official_reference_output": [official_zero, official_zero],
        "independent_fp64_sum_before_cast": float(independent_fp64),
        "r6_scalar_model_output_0": float(model_value),
        "official_float_abs_tolerance": 1e-4,
        "candidate_abs_error": abs(float(model_value) - official_zero),
        "candidate_within_tolerance": bool(
            abs(float(model_value) - official_zero) <= 1e-4
        ),
        "scope": (
            "The official Python reference was executed on CPU. "
            "r6_scalar_model is a source-mirror model, not an NPU result."
        ),
        "baseline_relation": (
            "The friend baseline has the same AddScalar and numerical fallback; "
            "r6 differs only by the outer-prefix optimization."
        ),
    }
    Path(args.output).write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["candidate_within_tolerance"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
