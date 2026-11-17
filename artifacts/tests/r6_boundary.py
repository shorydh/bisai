#!/usr/bin/env python3
"""Independent CPU boundary checks for PadV3Grad r6.

This script mirrors the index helpers and the r6 outer-prefix state machine
from the frozen source. It does not execute the Ascend kernel and therefore
cannot establish a device or official pass.
"""

from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np


CONSTANT, EDGE, REFLECT, SYMMETRIC, CIRCULAR = range(5)
MODE_NAMES = {
    CONSTANT: "constant",
    EDGE: "edge/replicate",
    REFLECT: "reflect",
    SYMMETRIC: "symmetric",
    CIRCULAR: "circular",
}


@dataclass(frozen=True)
class Contributors:
    first: tuple[int, int]
    count: tuple[int, int]
    step: int

    @property
    def size(self) -> int:
        return self.count[0] + self.count[1]

    def at(self, slot: int) -> int:
        if slot < self.count[0]:
            return self.first[0] + slot * self.step
        return self.first[1] + (slot - self.count[0]) * self.step


def positive_mod(value: int, period: int) -> int:
    if 0 <= value < period:
        return value
    if -period <= value < 0:
        return value + period
    remainder = value % period
    return remainder + period if remainder < 0 else remainder


def add_mod(left: int, right: int, period: int) -> int:
    return left - (period - right) if left >= period - right else left + right


def set_residue(
    first: list[int],
    count: list[int],
    slot: int,
    residue: int,
    input_length: int,
    front: int,
    step: int,
) -> None:
    first[slot] = add_mod(positive_mod(front, step), residue, step)
    if first[slot] < input_length:
        distance = input_length - 1 - first[slot]
        count[slot] = (
            1
            if distance < step
            else (2 if distance - step < step else 1 + distance // step)
        )


def make_contributors(
    output_coordinate: int,
    input_length: int,
    output_length: int,
    front: int,
    mode: int,
) -> Contributors:
    """Exact Python mirror of PadV3GradIndex::MakeContributors."""
    first = [0, 0]
    count = [0, 0]
    step = 1
    if (
        input_length <= 0
        or output_length <= 0
        or output_coordinate < 0
        or output_coordinate >= output_length
    ):
        return Contributors(tuple(first), tuple(count), step)
    if (
        input_length == output_length
        and front == 0
        and CONSTANT <= mode <= CIRCULAR
    ):
        first[0] = output_coordinate
        count[0] = 1
        return Contributors(tuple(first), tuple(count), step)
    if mode == CONSTANT:
        if front <= input_length - 1 - output_coordinate and front >= -output_coordinate:
            first[0] = front + output_coordinate
            count[0] = 1
        return Contributors(tuple(first), tuple(count), step)
    if output_length == 1:
        count[0] = input_length
        return Contributors(tuple(first), tuple(count), step)
    if mode == EDGE:
        if output_coordinate == 0:
            end = front if front < input_length - 1 else input_length - 1
            count[0] = 0 if end < 0 else end + 1
        elif output_coordinate == output_length - 1:
            if front <= input_length - 1 - output_coordinate:
                first[0] = 0 if front < -output_coordinate else front + output_coordinate
                count[0] = input_length - first[0]
        elif front >= -output_coordinate and front <= input_length - 1 - output_coordinate:
            first[0] = front + output_coordinate
            count[0] = 1
        return Contributors(tuple(first), tuple(count), step)
    if mode == CIRCULAR:
        step = output_length
        set_residue(first, count, 0, output_coordinate, input_length, front, step)
    elif mode == REFLECT:
        step = 2 * (output_length - 1)
        set_residue(first, count, 0, output_coordinate, input_length, front, step)
        if output_coordinate not in (0, output_length - 1):
            set_residue(
                first,
                count,
                1,
                step - output_coordinate,
                input_length,
                front,
                step,
            )
    elif mode == SYMMETRIC:
        step = 2 * output_length
        set_residue(first, count, 0, output_coordinate, input_length, front, step)
        set_residue(
            first,
            count,
            1,
            step - 1 - output_coordinate,
            input_length,
            front,
            step,
        )
    return Contributors(tuple(first), tuple(count), step)


def reference_padded_positions(
    output_length: int, front: int, back: int, mode: int
) -> tuple[np.ndarray, np.ndarray] | None:
    """Return padded-input positions and the original coordinate each updates."""
    padded_length = output_length + front + back
    if output_length <= 0 or padded_length <= 0:
        return None
    positions = np.arange(padded_length, dtype=np.int64)
    j = np.arange(-front, output_length + back, dtype=np.int64)
    if mode == CONSTANT:
        mapped = j
    elif mode == EDGE:
        mapped = np.clip(j, 0, output_length - 1)
    elif output_length == 1:
        mapped = np.zeros(padded_length, dtype=np.int64)
    elif mode == REFLECT:
        period = 2 * (output_length - 1)
        folded = np.mod(j, period)
        mapped = np.where(folded < output_length, folded, period - folded)
    elif mode == SYMMETRIC:
        period = 2 * output_length
        folded = np.mod(j, period)
        mapped = np.where(folded < output_length, folded, period - 1 - folded)
    elif mode == CIRCULAR:
        mapped = np.mod(j, output_length)
    else:
        raise ValueError(mode)
    return positions, mapped


class R6OuterState:
    """Mirror of InitOuterPrefix/InitOuter/NextOuter in pad_v3_grad.h."""

    def __init__(
        self,
        input_shape: Sequence[int],
        output_shape: Sequence[int],
        front: Sequence[int],
        mode: int,
        optimized: bool,
    ) -> None:
        self.input_shape = tuple(int(v) for v in input_shape)
        self.output_shape = tuple(int(v) for v in output_shape)
        self.front = tuple(int(v) for v in front)
        self.mode = mode
        self.rank = len(self.input_shape)
        self.strides = self._strides(self.input_shape)
        self.optimized = optimized
        self.outer_start = 0
        if optimized:
            while (
                self.outer_start < self.rank - 1
                and self.front[self.outer_start] == 0
                and self.input_shape[self.outer_start] == self.output_shape[self.outer_start]
            ):
                self.outer_start += 1
        self.cached_row = -1
        self.cached_base = 0
        self.cached_valid = False
        self.position = [0] * self.rank
        self.outer: list[Contributors | None] = [None] * self.rank
        self.base = 0

    @staticmethod
    def _strides(shape: Sequence[int]) -> list[int]:
        strides = [1] * len(shape)
        running = 1
        for axis in range(len(shape) - 1, -1, -1):
            strides[axis] = running
            running *= shape[axis]
        return strides

    def init_outer(self, row: int) -> bool:
        if row == self.cached_row:
            if not self.cached_valid:
                return False
            self.base = self.cached_base
            for axis in range(self.rank - 2, self.outer_start - 1, -1):
                self.position[axis] = 0
            return True
        self.cached_row = row
        self.cached_valid = False
        self.base = 0
        for axis in range(self.rank - 2, self.outer_start - 1, -1):
            coordinate = row % self.output_shape[axis]
            row //= self.output_shape[axis]
            contributors = make_contributors(
                coordinate,
                self.input_shape[axis],
                self.output_shape[axis],
                self.front[axis],
                self.mode,
            )
            self.outer[axis] = contributors
            self.position[axis] = 0
            if contributors.size == 0:
                return False
            self.base += contributors.at(0) * self.strides[axis]
        if self.outer_start != 0:
            self.base += row * self.strides[self.outer_start - 1]
        self.cached_base = self.base
        self.cached_valid = True
        return True

    def next_outer(self) -> bool:
        for axis in range(self.rank - 2, self.outer_start - 1, -1):
            contributors = self.outer[axis]
            assert contributors is not None
            old = contributors.at(self.position[axis])
            self.position[axis] += 1
            if self.position[axis] < contributors.size:
                self.base += (
                    contributors.at(self.position[axis]) - old
                ) * self.strides[axis]
                return True
            self.position[axis] = 0
            self.base += (contributors.at(0) - old) * self.strides[axis]
        return False


def ordered_outer_bases(
    input_shape: Sequence[int],
    output_shape: Sequence[int],
    front: Sequence[int],
    mode: int,
    row: int,
    optimized: bool,
) -> list[int]:
    state = R6OuterState(input_shape, output_shape, front, mode, optimized)
    if not state.init_outer(row):
        return []
    result = [state.base]
    while state.next_outer():
        result.append(state.base)
    return result


def full_r6_sources(
    input_shape: Sequence[int],
    output_shape: Sequence[int],
    front: Sequence[int],
    mode: int,
    output_flat: int,
) -> list[int]:
    rank = len(input_shape)
    if rank == 0:
        return [0]
    width_out = output_shape[-1]
    row, column = divmod(output_flat, width_out)
    last = make_contributors(
        column,
        input_shape[-1],
        output_shape[-1],
        front[-1],
        mode,
    )
    if last.size == 0:
        return []
    bases = ordered_outer_bases(
        input_shape, output_shape, front, mode, row, optimized=True
    )
    return [base + last.at(slot) for base in bases for slot in range(last.size)]


def check_index_matrix() -> dict:
    cases = 0
    mismatches: list[dict] = []
    reference_ambiguous_cases = 0
    signed_exploratory_cases = 0
    signed_exploratory_mismatches: list[dict] = []
    for mode in MODE_NAMES:
        for output_length in range(1, 13):
            for front in range(-12, 13):
                for back in range(-12, 13):
                    padded_length = output_length + front + back
                    if padded_length <= 0:
                        continue
                    # The published reference takes a Python/Torch slice for
                    # constant mode. With a negative front, that slice can
                    # silently change shape; the题面 does not declare whether
                    # this family is legal. Keep it out of the formal matrix.
                    if mode == CONSTANT and (front < 0 or back < 0):
                        reference_ambiguous_cases += 1
                        continue
                    reference = reference_padded_positions(
                        output_length, front, back, mode
                    )
                    if reference is None:
                        continue
                    positions, mapped = reference
                    for coordinate in range(output_length):
                        expected = [
                            int(position)
                            for position, target in zip(positions, mapped)
                            if int(target) == coordinate
                        ]
                        got_contributors = make_contributors(
                            coordinate,
                            padded_length,
                            output_length,
                            front,
                            mode,
                        )
                        got = [
                            got_contributors.at(slot)
                            for slot in range(got_contributors.size)
                        ]
                        if front < 0 or back < 0:
                            signed_exploratory_cases += 1
                            if sorted(got) != sorted(expected):
                                if len(signed_exploratory_mismatches) < 20:
                                    signed_exploratory_mismatches.append(
                                        {
                                            "mode": MODE_NAMES[mode],
                                            "input_length": padded_length,
                                            "output_length": output_length,
                                            "front": front,
                                            "back": back,
                                            "coordinate": coordinate,
                                            "expected_sorted": sorted(expected)[:16],
                                            "actual_sorted": sorted(got)[:16],
                                        }
                                    )
                            continue
                        cases += 1
                        if sorted(got) != sorted(expected):
                            if len(mismatches) < 20:
                                mismatches.append(
                                    {
                                        "mode": MODE_NAMES[mode],
                                        "input_length": padded_length,
                                        "output_length": output_length,
                                        "front": front,
                                        "back": back,
                                        "coordinate": coordinate,
                                        "expected_sorted": sorted(expected)[:16],
                                        "actual_sorted": sorted(got)[:16],
                                    }
                                )
    return {
        "name": "E001-index-and-outer-state",
        "kind": "cpu-model",
        "index_cases": cases,
        "constant_signed_reference_ambiguous_cases": reference_ambiguous_cases,
        "signed_exploratory_cases": signed_exploratory_cases,
        "signed_exploratory_mismatches": signed_exploratory_mismatches,
        "index_mismatches": mismatches,
    }


def check_outer_prefix_matrix() -> dict:
    rng = np.random.default_rng(20261117)
    cases = 0
    mismatches: list[dict] = []
    for rank in range(2, 6):
        for _ in range(180):
            input_shape = [int(v) for v in rng.integers(1, 5, size=rank)]
            front = [int(v) for v in rng.integers(-1, 4, size=rank)]
            back = [int(v) for v in rng.integers(-1, 4, size=rank)]
            output_shape = [
                input_shape[d] - front[d] - back[d] for d in range(rank)
            ]
            if any(v <= 0 for v in output_shape):
                continue
            if np.prod(output_shape[:-1], dtype=np.int64) > 256:
                continue
            mode = int(rng.integers(0, 5))
            for row in range(int(np.prod(output_shape[:-1], dtype=np.int64))):
                original = ordered_outer_bases(
                    input_shape, output_shape, front, mode, row, optimized=False
                )
                optimized = ordered_outer_bases(
                    input_shape, output_shape, front, mode, row, optimized=True
                )
                cases += 1
                if original != optimized:
                    if len(mismatches) < 20:
                        mismatches.append(
                            {
                                "input_shape": input_shape,
                                "output_shape": output_shape,
                                "front": front,
                                "mode": MODE_NAMES[mode],
                                "row": row,
                                "original": original[:32],
                                "optimized": optimized[:32],
                            }
                        )
    # Exercise cached state after an invalid row and after repeating a row.
    sequences = [
        (
            [3, 5, 7],
            [2, 3, 4],
            [1, 2, 2],
            CONSTANT,
            [5, 2, 5, 0, 0, 2],
        ),
        (
            [1, 2, 4, 8],
            [1, 1, 3, 5],
            [0, 1, 1, 3],
            REFLECT,
            [0, 1, 2, 2, 1, 0],
        ),
    ]
    for input_shape, output_shape, front, mode, rows in sequences:
        for optimized in (False, True):
            state = R6OuterState(
                input_shape, output_shape, front, mode, optimized
            )
            for row in rows:
                bases: list[int] = []
                if state.init_outer(row):
                    bases.append(state.base)
                    while state.next_outer():
                        bases.append(state.base)
                expected = ordered_outer_bases(
                    input_shape,
                    output_shape,
                    front,
                    mode,
                    row,
                    optimized=optimized,
                )
                cases += 1
                if bases != expected and len(mismatches) < 20:
                    mismatches.append(
                        {
                            "type": "state-sequence",
                            "input_shape": input_shape,
                            "output_shape": output_shape,
                            "front": front,
                            "mode": MODE_NAMES[mode],
                            "row": row,
                            "expected": expected[:32],
                            "actual": bases[:32],
                        }
                    )
    return {
        "name": "E001-index-and-outer-state",
        "kind": "cpu-model",
        "state_cases": cases,
        "state_mismatches": mismatches,
    }


def f32(value: float | np.floating) -> np.float32:
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        return np.float32(value)


def add_scalar32(values: Iterable[float]) -> np.float32:
    """Exact scalar fallback accumulation from r6 AddScalar."""
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


def official_float_close(actual: np.float32, expected: np.float32) -> bool:
    if np.isnan(expected):
        return bool(np.isnan(actual))
    if not np.isfinite(expected):
        return bool(actual == expected)
    return bool(
        abs(float(actual) - float(expected))
        <= 1e-4 + 1e-4 * abs(float(expected))
    )


def reference_scalar_sum(values: Sequence[np.float32]) -> np.float32:
    return f32(np.sum(np.asarray(values, dtype=np.float64), dtype=np.float64))


def check_float_scalar_search() -> dict:
    rng = np.random.default_rng(2026111701)
    pool = np.asarray(
        [
            3.0e38,
            -3.0e38,
            1.7e38,
            -1.7e38,
            1.0,
            -1.0,
            1.0e-10,
            -1.0e-10,
        ],
        dtype=np.float32,
    )
    sequences: list[list[np.float32]] = [
        [f32(3.0e38), f32(3.0e38), f32(-3.0e38), f32(-3.0e38)],
        [f32(1.0e30), f32(1.0e-10), f32(-1.0e30), f32(1.0e-10)],
        [f32(3.0e38), f32(-3.0e38), f32(3.0e38), f32(-3.0e38)],
    ]
    for length in range(1, 10):
        for _ in range(4000):
            sequences.append(list(pool[rng.integers(0, len(pool), size=length)]))
    failures: list[dict] = []
    finite_cases = 0
    for values in sequences:
        expected = reference_scalar_sum(values)
        if not np.isfinite(expected):
            continue
        actual = add_scalar32(values)
        finite_cases += 1
        if not official_float_close(actual, expected):
            if len(failures) < 20:
                failures.append(
                    {
                        "values": [float(v) for v in values],
                        "reference": float(expected),
                        "r6_scalar_model": float(actual),
                    }
                )
    return {
        "name": "E002-fp32-overflow-cancellation",
        "kind": "cpu-model",
        "finite_sequences": finite_cases,
        "tolerance_failures": failures,
    }


def check_numeric_layout_cases() -> dict:
    cases = 0
    failures: list[dict] = []
    scenarios = []
    for mode in MODE_NAMES:
        for front, back in ((0, 0), (3, 3), (0, 9), (-1, 5), (7, 0)):
            scenarios.append(([1, 1, 1, 2], [front, back], mode))
    for pattern in ("cancel", "overflow-cancel", "mixed", "tiny"):
        scenarios.append(([1, 1, 1, 6], [1, 3], REFLECT, pattern))
    for scenario in scenarios:
        input_shape, (front, back), mode = scenario[:3]
        explicit_pattern = scenario[3] if len(scenario) == 4 else None
        output_shape = [1, 1, 1, input_shape[-1] - front - back]
        if output_shape[-1] <= 0 or input_shape[-1] <= 0:
            continue
        patterns = (explicit_pattern,) if explicit_pattern else (
            "cancel",
            "overflow-cancel",
            "mixed",
            "tiny",
        )
        for pattern in patterns:
            rng = np.random.default_rng(
                2026111702 + front * 17 + back * 31 + mode * 101
            )
            if pattern == "cancel":
                raw = rng.uniform(-1.0, 1.0, input_shape).astype(np.float32)
            elif pattern == "overflow-cancel":
                raw = rng.choice(
                    np.asarray([3.0e38, -3.0e38], dtype=np.float32),
                    size=input_shape,
                )
            elif pattern == "mixed":
                raw = rng.choice(
                    np.asarray([1.0e30, -1.0e30, 1.0, -1.0], dtype=np.float32),
                    size=input_shape,
                )
            else:
                raw = rng.choice(
                    np.asarray([1.0e-20, -1.0e-20], dtype=np.float32),
                    size=input_shape,
                )
            if explicit_pattern == "cancel":
                raw = np.asarray(
                    [0.0, 1.7e38, 0.0, 1.0, 0.0, -1.7e38],
                    dtype=np.float32,
                ).reshape(input_shape)
            for output_flat in range(int(np.prod(output_shape, dtype=np.int64))):
                sources = full_r6_sources(
                    input_shape,
                    output_shape,
                    [0, 0, 0, front],
                    mode,
                    output_flat,
                )
                values = raw.reshape(-1)[sources]
                expected = reference_scalar_sum(values.tolist())
                actual = add_scalar32(values.tolist())
                cases += 1
                if not official_float_close(actual, expected):
                    if len(failures) < 20:
                        failures.append(
                            {
                                "input_shape": input_shape,
                                "output_shape": output_shape,
                                "front_back": [front, back],
                                "mode": MODE_NAMES[mode],
                                "pattern": pattern,
                                "output": output_flat,
                                "sources": sources[:40],
                                "reference": float(expected),
                                "r6_scalar_model": float(actual),
                            }
                        )
    return {
        "name": "E002-fp32-overflow-cancellation",
        "kind": "cpu-model",
        "layout_cases": cases,
        "numeric_failures": failures,
    }


def check_large_index_symbolic() -> dict:
    checks = 0
    mismatches: list[dict] = []
    maximum_byte_index = 0
    for element_size in (2, 4):
        input_shape = [4_097, 1, 65_537, 1, 257]
        output_shape = list(input_shape)
        front = [0] * len(input_shape)
        strides = R6OuterState._strides(input_shape)
        row_limit = 4_097 * 65_537 - 1
        for row in (0, 1, 65_536, row_limit):
            original = ordered_outer_bases(
                input_shape, output_shape, front, REFLECT, row, optimized=False
            )
            optimized = ordered_outer_bases(
                input_shape, output_shape, front, REFLECT, row, optimized=True
            )
            checks += 1
            if original != optimized:
                mismatches.append(
                    {
                        "row": row,
                        "original": original,
                        "optimized": optimized,
                    }
                )
            for base in optimized:
                byte_index = base * element_size
                maximum_byte_index = max(maximum_byte_index, byte_index)
                checks += 1
                if byte_index < 0 or byte_index > np.iinfo(np.int64).max:
                    mismatches.append(
                        {
                            "row": row,
                            "base": base,
                            "byte_index": byte_index,
                        }
                    )
    return {
        "name": "E003-large-index-symbolic",
        "kind": "cpu-model-no-allocation",
        "checks": checks,
        "maximum_byte_index": maximum_byte_index,
        "exceeds_uint32_bytes": maximum_byte_index > 0xFFFFFFFF,
        "below_int64_bytes": maximum_byte_index <= np.iinfo(np.int64).max,
        "mismatches": mismatches,
        "note": "No NPU allocation or device execution was performed.",
    }


def merge_e001(index_result: dict, state_result: dict) -> dict:
    return {
        "name": "E001-index-and-outer-state",
        "kind": "cpu-model",
        "index_cases": index_result["index_cases"],
        "constant_signed_reference_ambiguous_cases": index_result[
            "constant_signed_reference_ambiguous_cases"
        ],
        "signed_exploratory_cases": index_result["signed_exploratory_cases"],
        "signed_exploratory_mismatches": index_result[
            "signed_exploratory_mismatches"
        ],
        "state_cases": state_result["state_cases"],
        "mismatches": index_result["index_mismatches"]
        + state_result["state_mismatches"],
    }


def merge_e002(search_result: dict, layout_result: dict) -> dict:
    failures = search_result["tolerance_failures"] + layout_result["numeric_failures"]
    unique_failures = {}
    for failure in failures:
        key = json.dumps(failure, sort_keys=True, ensure_ascii=False)
        unique_failures[key] = failure
    return {
        "name": "E002-fp32-overflow-cancellation",
        "kind": "cpu-model",
        "finite_sequences": search_result["finite_sequences"],
        "layout_cases": layout_result["layout_cases"],
        "failures": list(unique_failures.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    e001 = merge_e001(check_index_matrix(), check_outer_prefix_matrix())
    e002 = merge_e002(check_float_scalar_search(), check_numeric_layout_cases())
    e003 = check_large_index_symbolic()
    report = {
        "source": {
            "operator": "PadV3Grad",
            "r6_official_task_id": 1367774,
            "r6_seven_source_sha256": "d0b680d59d1dfa088dd24fff5d3128feb2758251bcd8d3b34b39635bad68f949",
            "r6_package_sha256": "18679dad71f9ea7723ca524599b0d9363861aeadf8f8032202f6391199a5a85a",
        },
        "limits": {
            "device_execution": False,
            "official_submission": False,
            "reason": "No local Ascend/CANN device was detected; model checks are not device evidence.",
        },
        "experiments": [e001, e002, e003],
    }
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if any(experiment.get("mismatches") or experiment.get("failures") for experiment in report["experiments"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
