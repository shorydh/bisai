#!/usr/bin/env python3
"""Static decision-matrix checks for PadV3Grad r6 dispatch boundaries."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path


def wide_branch(rank: int, total_input: int, total_output: int, count: int) -> bool:
    return not (
        rank == 0 or total_input > 8192 or total_output > 256 or count > 128
    )


def certified_branch(total_input: int, total_output: int) -> bool:
    return not (total_input > 8192 or total_output > 256)


def small_branch(total_input: int, total_output: int) -> bool:
    return total_input <= 8192 and total_output <= 256


def prefix_outer_start(shape_in: list[int], shape_out: list[int], front: list[int]) -> int:
    result = 0
    while (
        result < len(shape_in) - 1
        and front[result] == 0
        and shape_in[result] == shape_out[result]
    ):
        result += 1
    return result


def decode_padding(rows: list[tuple[int, int]], contiguous: bool, dtype: str) -> list[int]:
    values = (
        [value for row in rows for value in row]
        if contiguous
        else [row[0] for row in rows] + [row[1] for row in rows]
    )
    if dtype == "int32":
        return [int(v) for v in values]
    if dtype == "int64":
        return [int(v) for v in values]
    raise ValueError(dtype)


def read_front(flat: list[int], rank: int, contiguous: bool) -> list[int]:
    return [
        flat[2 * axis] if contiguous else flat[axis]
        for axis in range(rank)
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    checks = 0
    mismatches: list[dict] = []

    boundary_cases = [
        (4, 8191, 255, 127, True),
        (4, 8192, 256, 128, True),
        (4, 8193, 256, 128, False),
        (4, 8192, 257, 128, False),
        (4, 8192, 256, 129, False),
        (0, 1, 1, 1, False),
        (1, 8192, 256, 128, True),
    ]
    for rank, total_input, total_output, count, expected in boundary_cases:
        actual = wide_branch(rank, total_input, total_output, count)
        checks += 1
        if actual != expected:
            mismatches.append(
                {
                    "kind": "wide-boundary",
                    "rank": rank,
                    "total_input": total_input,
                    "total_output": total_output,
                    "count": count,
                    "expected": expected,
                    "actual": actual,
                }
            )
        checks += 1
        if certified_branch(total_input, total_output) != small_branch(
            total_input, total_output
        ):
            mismatches.append(
                {
                    "kind": "small-certified-range",
                    "total_input": total_input,
                    "total_output": total_output,
                }
            )

    prefix_shapes = [
        ([1, 2, 3, 5], [1, 2, 3, 4], [0, 0, 0, 1], 3),
        ([1, 2, 3, 5], [1, 2, 2, 4], [0, 0, 1, 1], 2),
        ([1, 2, 3, 5], [1, 2, 2, 4], [1, 0, 0, 1], 0),
        ([4], [3], [1], 0),
        ([], [], [], 0),
    ]
    for shape_in, shape_out, front, expected in prefix_shapes:
        actual = prefix_outer_start(shape_in, shape_out, front)
        checks += 1
        if actual != expected:
            mismatches.append(
                {
                    "kind": "prefix",
                    "shape_in": shape_in,
                    "shape_out": shape_out,
                    "front": front,
                    "expected": expected,
                    "actual": actual,
                }
            )

    padding_rows = [(-7, 3), (2, -5), (0, 11), (-1, 0)]
    for dtype, contiguous in itertools.product(("int32", "int64"), (True, False)):
        flat = decode_padding(padding_rows, contiguous, dtype)
        actual = read_front(flat, len(padding_rows), contiguous)
        expected = [row[0] for row in padding_rows]
        checks += 1
        if actual != expected:
            mismatches.append(
                {
                    "kind": "padding-layout",
                    "dtype": dtype,
                    "contiguous": contiguous,
                    "expected": expected,
                    "actual": actual,
                }
            )

    # Contribution count thresholds in the wide planner. The kernel has room
    # for exactly 64 contributions per output and selects 32 or 64 lanes.
    for outer_count, last_count, expected_ok, expected_terms in [
        (1, 32, True, 32),
        (1, 64, True, 64),
        (2, 32, True, 64),
        (2, 33, False, None),
        (0, 64, True, None),
        (65, 1, False, None),
    ]:
        product = outer_count * last_count
        ok = outer_count <= 64 and (outer_count == 0 or last_count <= 64 // outer_count)
        terms = 32 if product <= 32 else 64
        checks += 1
        if ok != expected_ok or (ok and expected_terms is not None and terms != expected_terms):
            mismatches.append(
                {
                    "kind": "contributor-threshold",
                    "outer_count": outer_count,
                    "last_count": last_count,
                    "product": product,
                    "ok": ok,
                    "terms": terms,
                }
            )

    # The tiling cache key is shape-only. The kernel must read current padding
    # values for every invocation; verify the model uses them rather than a
    # cached sample's fronts.
    first = read_front(decode_padding([(0, 0), (1, 1)], True, "int32"), 2, True)
    second = read_front(decode_padding([(0, 0), (4, 4)], True, "int32"), 2, True)
    checks += 1
    if first == second:
        mismatches.append(
            {
                "kind": "same-shape-different-padding",
                "first": first,
                "second": second,
            }
        )

    report = {
        "name": "E005-dispatch-boundary-matrix",
        "kind": "static-source-model",
        "checks": checks,
        "mismatches": mismatches,
        "covered": {
            "thresholds": [8192, 256, 128, 64, 32],
            "rank_cases": [0, 1, 4],
            "prefix_cases": ["none", "partial", "all-before-last"],
            "padding_dtypes": ["int32", "int64"],
            "padding_layouts": ["contiguous", "split"],
            "same_shape_different_padding": True,
        },
        "limits": {
            "device_execution": False,
            "official_submission": False,
            "note": "Static decision mirror only; no Ascend compiler or NPU was available.",
        },
    }
    Path(args.output).write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
