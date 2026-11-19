#!/usr/bin/env python3
"""Reproduce the two legacy verifier defects on disposable synthetic fixtures."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROUND = Path(__file__).resolve().parents[1]
SOURCE_CASES = ROUND / "device-case" / "edge-legal-cancellation"
ORIGINAL = ROUND / "r004" / "original-device-runner" / "verify_outputs.py"
STRICT = ROUND / "device-runner" / "verify_outputs.py"
CASE_IDS = ("int32-contiguous", "int32-split", "int64-contiguous", "int64-split")


def write_correct_outputs(cases: Path) -> None:
    for case_id in CASE_IDS:
        output = cases / case_id / "output"
        output.mkdir(parents=True)
        shutil.copy2(cases / case_id / "golden" / "y.bin", output / "y.bin")


def run_verifier(script: Path, cases: Path, output: Path, strict: bool) -> int:
    command = [sys.executable, str(script), "--cases", str(cases)]
    if strict:
        command.extend([
            "--run-root", str(cases),
            "--execution-mode", "synthetic",
        ])
    command.extend(["--output", str(output)])
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    output.with_suffix(".stdout.log").write_text(completed.stdout, encoding="utf-8")
    output.with_suffix(".stderr.log").write_text(completed.stderr, encoding="utf-8")
    return completed.returncode


def main() -> int:
    evidence = ROUND / "r004" / "synth" / "legacy-repro-v1"
    if evidence.exists():
        raise SystemExit(f"evidence directory already exists: {evidence}")
    evidence.mkdir(parents=True)

    with_manifest = evidence / "cases-with-manifest"
    without_manifest = evidence / "cases-without-manifest"
    shutil.copytree(SOURCE_CASES, with_manifest)
    shutil.copytree(SOURCE_CASES, without_manifest)
    write_correct_outputs(with_manifest)
    write_correct_outputs(without_manifest)

    old_manifest_exit = run_verifier(
        ORIGINAL, with_manifest, evidence / "legacy-with-manifest.json", strict=False
    )
    (without_manifest / "manifest.json").unlink()
    (without_manifest / "int64-contiguous" / "output" / "y.bin").write_bytes(b"\0" * 4)
    old_truncated_exit = run_verifier(
        ORIGINAL, without_manifest, evidence / "legacy-truncated.json", strict=False
    )
    strict_truncated_exit = run_verifier(
        STRICT, with_manifest, evidence / "strict-correct-with-manifest.json", strict=True
    )
    (with_manifest / "int64-contiguous" / "output" / "y.bin").write_bytes(b"\0" * 4)
    strict_after_truncate_exit = run_verifier(
        STRICT, with_manifest, evidence / "strict-truncated.json", strict=True
    )

    summary = {
        "execution_mode": "synthetic",
        "device_execution": False,
        "observations": {
            "legacy_with_manifest_exit": old_manifest_exit,
            "legacy_truncated_exit": old_truncated_exit,
            "strict_correct_with_manifest_exit": strict_truncated_exit,
            "strict_after_truncate_exit": strict_after_truncate_exit,
        },
    }
    (evidence / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    expected = {
        "legacy_with_manifest_exit": 1,
        "legacy_truncated_exit": 0,
        "strict_correct_with_manifest_exit": 0,
        "strict_after_truncate_exit": 1,
    }
    return 0 if summary["observations"] == expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
