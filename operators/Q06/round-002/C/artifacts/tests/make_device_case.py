#!/usr/bin/env python3
"""Generate the transferable NPU case for the legal edge cancellation candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import ml_dtypes
import numpy as np


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    reference_root = Path(args.reference_root).resolve()
    sys.path.insert(0, str(reference_root))
    import reference  # type: ignore  # noqa: E402

    if reference.bfloat16 is not ml_dtypes.bfloat16:
        raise RuntimeError("Real ml_dtypes is required")

    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=True)
    x = np.asarray(
        [1.7e38, 1.0, -1.7e38, 0.0, 0.0],
        dtype=np.float32,
    ).reshape(1, 1, 1, 5)
    pads = [(0, 0), (0, 0), (0, 0), (2, 0)]
    x_bytes = x.tobytes()
    variants = []

    for dtype in (np.int32, np.int64):
        contiguous = np.asarray(pads, dtype=dtype)
        split = np.asarray(
            [[row[0] for row in pads], [row[1] for row in pads]],
            dtype=dtype,
        )
        for layout, paddings in (("contiguous", contiguous), ("split", split)):
            golden = reference.impl(
                x,
                paddings,
                mode="edge",
                paddings_contiguous=layout == "contiguous",
            )
            if list(golden.shape) != [1, 1, 1, 3] or not np.array_equal(
                golden, np.zeros_like(golden)
            ):
                raise RuntimeError("Unexpected reference golden")
            case_dir = root / f"{np.dtype(dtype).name}-{layout}"
            (case_dir / "input").mkdir(parents=True, exist_ok=True)
            (case_dir / "golden").mkdir(parents=True, exist_ok=True)
            x_path = case_dir / "input" / "x.bin"
            pad_path = case_dir / "input" / "paddings.bin"
            y_path = case_dir / "golden" / "y.bin"
            x_path.write_bytes(x_bytes)
            pad_path.write_bytes(paddings.tobytes())
            y_path.write_bytes(golden.tobytes())
            case = {
                "source_case": "Q06-R002-C legal edge cancellation",
                "function": "impl",
                "attributes": {
                    "mode": "edge",
                    "paddings_contiguous": layout == "contiguous",
                },
                "inputs": [
                    {
                        "name": "x",
                        "kind": "required",
                        "tensors": [
                            {
                                "file": "x.bin",
                                "dtype": "float32",
                                "shape": list(x.shape),
                                "bytes": len(x_bytes),
                                "elements": int(x.size),
                                "range": None,
                                "value": None,
                            }
                        ],
                    },
                    {
                        "name": "paddings",
                        "kind": "required",
                        "tensors": [
                            {
                                "file": "paddings.bin",
                                "dtype": np.dtype(dtype).name,
                                "shape": list(paddings.shape),
                                "bytes": int(paddings.nbytes),
                                "elements": int(paddings.size),
                                "range": None,
                                "value": paddings.tolist(),
                            }
                        ],
                    },
                ],
                "outputs": [
                    {
                        "name": "y",
                        "kind": "required",
                        "tensors": [
                            {
                                "file": "y.bin",
                                "dtype": "float32",
                                "shape": list(golden.shape),
                                "bytes": int(golden.nbytes),
                                "elements": int(golden.size),
                                "rtol": 0.0001,
                                "atol": 0.0001,
                                "tol": 0.0001,
                            }
                        ],
                    }
                ],
            }
            (case_dir / "case.json").write_text(
                json.dumps(case, indent=2) + "\n",
                encoding="utf-8",
            )
            manifest = {
                "case_id": case_dir.name,
                "input_x_sha256": sha256_bytes(x_bytes),
                "paddings_sha256": sha256_bytes(paddings.tobytes()),
                "golden_y_sha256": sha256_bytes(golden.tobytes()),
                "golden_y": [float(value) for value in golden.reshape(-1)],
                "expected_device": "all three FP32 outputs must be within 1e-4",
                "source_model_expectation": (
                    "r6 AddScalar source model is 1 at output 0; "
                    "this is not a device result"
                ),
            }
            (case_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )
            variants.append(manifest)

    summary = {
        "task_id": "Q06-R002-C-REFERENCE-DEVICE-20261117",
        "source": {
            "r6_package_sha256": "18679dad71f9ea7723ca524599b0d9363861aeadf8f8032202f6391199a5a85a",
            "r6_seven_source_sha256": "d0b680d59d1dfa088dd24fff5d3128feb2758251bcd8d3b34b39635bad68f949",
        },
        "variants": variants,
        "device_execution": False,
    }
    (root / "manifest.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
