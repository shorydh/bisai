#!/usr/bin/env python3
"""Run the reproducible no-device acceptance and routing test suite."""

from __future__ import annotations

import json
import os
import py_compile
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROUND = Path(__file__).resolve().parents[1]
EVIDENCE = ROUND / "r004" / "synth"
TESTS = ROUND / "tests"
RUNNER = ROUND / "device-runner"


def run(name: str, command: list[str]) -> dict:
    completed = subprocess.run(
        command,
        cwd=ROUND.parents[2],
        text=True,
        capture_output=True,
        check=False,
        env=os.environ.copy(),
    )
    log = EVIDENCE / f"final-{name}.log"
    log.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    return {
        "name": name,
        "command": command,
        "exit_code": completed.returncode,
        "log": str(log),
        "skip_observed": "skipped" in (completed.stdout + completed.stderr).lower(),
    }


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    checks = []
    checks.append(run("acceptance", [
        sys.executable, "-m", "unittest", "-v",
        str(TESTS / "test_r004_runner.py"),
    ]))
    checks.append(run("vendor-switch", [
        sys.executable, "-m", "unittest", "-v",
        str(TESTS / "test_vendor_switch.py"),
    ]))
    checks.append(run("baseline-audit", [
        sys.executable, str(TESTS / "audit_r004_baseline.py"),
        "--round", str(ROUND.parent),
        "--output", str(ROUND / "results" / "R004-baseline-audit.json"),
    ]))

    compile_errors = []
    for path in sorted(list(RUNNER.glob("*.py")) + list(TESTS.glob("*.py"))):
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            compile_errors.append(str(exc))
    checks.append({
        "name": "py-compile",
        "exit_code": 0 if not compile_errors else 1,
        "errors": compile_errors,
    })

    legacy = json.loads(
        (EVIDENCE / "legacy-repro-v1" / "summary.json").read_text(encoding="utf-8")
    )
    checks.append({
        "name": "legacy-defect-reproduction",
        "exit_code": 0 if legacy["observations"] == {
            "legacy_with_manifest_exit": 1,
            "legacy_truncated_exit": 0,
            "strict_correct_with_manifest_exit": 0,
            "strict_after_truncate_exit": 1,
        } else 1,
        "evidence": str(EVIDENCE / "legacy-repro-v1" / "summary.json"),
    })

    summary = {
        "schema_version": 1,
        "task_id": "Q06-R004-C-RUNNER-VALIDATION",
        "execution_mode": "synthetic",
        "device_execution": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "all_pass": all(check["exit_code"] == 0 for check in checks),
    }
    path = EVIDENCE / "suite-summary.json"
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
