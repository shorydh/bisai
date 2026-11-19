#!/usr/bin/env python3
"""Create a portable patch from the preserved R003 runner to the R004 runner."""

from __future__ import annotations

import argparse
import difflib
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    before = args.before.resolve()
    after = args.after.resolve()
    names = sorted(
        {path.name for path in before.iterdir() if path.is_file()} |
        {path.name for path in after.iterdir() if path.is_file()}
    )
    lines: list[str] = []
    for name in names:
        before_path = before / name
        after_path = after / name
        old = before_path.read_text(encoding="utf-8").splitlines(keepends=True) if before_path.is_file() else []
        new = after_path.read_text(encoding="utf-8").splitlines(keepends=True) if after_path.is_file() else []
        lines.extend(difflib.unified_diff(
            old,
            new,
            fromfile=f"a/artifacts/device-runner/{name}",
            tofile=f"b/artifacts/device-runner/{name}",
        ))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(lines), encoding="utf-8", newline="\n")
    print(f"wrote {args.output} ({len(lines)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
