#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    results = []
    for case_dir in sorted(Path(args.cases).iterdir()):
        actual_path = case_dir / "output" / "y.bin"
        golden_path = case_dir / "golden" / "y.bin"
        if not actual_path.is_file():
            results.append(
                {
                    "case": case_dir.name,
                    "status": "missing_output",
                    "actual_path": str(actual_path),
                }
            )
            continue
        actual = np.frombuffer(actual_path.read_bytes(), dtype=np.float32)
        golden = np.frombuffer(golden_path.read_bytes(), dtype=np.float32)
        close = np.isclose(
            actual.astype(np.float64),
            golden.astype(np.float64),
            rtol=1e-4,
            atol=1e-4,
            equal_nan=True,
        )
        results.append(
            {
                "case": case_dir.name,
                "status": "PASS" if bool(close.all()) else "FAIL",
                "actual": [float(v) for v in actual],
                "golden": [float(v) for v in golden],
                "abs_error": [float(v) for v in np.abs(actual - golden)],
                "rtol": 1e-4,
                "atol": 1e-4,
            }
        )
    report = {
        "device_execution": True,
        "cases": results,
        "all_pass": all(result["status"] == "PASS" for result in results),
    }
    Path(args.output).write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
