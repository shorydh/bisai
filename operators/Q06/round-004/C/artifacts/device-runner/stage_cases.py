#!/usr/bin/env python3
"""Stage only the four manifest-authorized cases into a fresh run directory."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from verify_outputs import sha256_file, validate_case_fixture, validate_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    args = parser.parse_args()

    cases_root = args.cases.resolve()
    run_root = args.run_root.resolve()
    if run_root.exists() and any(path.is_dir() for path in run_root.iterdir()):
        raise SystemExit(f"refusing to reuse non-empty run root: {run_root}")
    run_root.mkdir(parents=True, exist_ok=True)

    _, variants = validate_manifest(cases_root)
    case_ids = []
    for variant in variants:
        case_id = variant["case_id"]
        validate_case_fixture(cases_root, variant)
        source = cases_root / case_id
        target = run_root / case_id
        shutil.copytree(source / "input", target / "input")
        (target / "output").mkdir(parents=True)
        shutil.copy2(source / "case.json", target / "case.json")
        shutil.copy2(source / "manifest.json", target / "manifest.json")
        case_ids.append(case_id)

    (run_root / "case-ids.txt").write_text("\n".join(case_ids) + "\n", encoding="utf-8")
    (run_root / "staged-input-sha256.txt").write_text(
        "".join(
            f"{sha256_file(run_root / case_id / 'input' / name)}  {case_id}/{name}\n"
            for case_id in case_ids
            for name in ("x.bin", "paddings.bin")
        ),
        encoding="utf-8",
    )
    print("\n".join(case_ids))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
