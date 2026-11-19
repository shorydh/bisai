#!/usr/bin/env python3
"""Produce persistent CMake cache evidence for switching two explicit projects."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from test_vendor_switch import make_project


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    cmake = os.environ.get("CMAKE") or shutil.which("cmake")
    if not cmake:
        raise SystemExit("cmake is required")
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"refusing to reuse non-empty evidence root: {output}")
    output.mkdir(parents=True, exist_ok=True)
    include_path = str((args.runner_dir / "vendor_paths.cmake").resolve()).replace("\\", "/")
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        projects = work / "projects"
        project_a = make_project(projects, "a")
        project_b = make_project(projects, "b")
        probe = work / "probe"
        build = work / "build"
        probe.mkdir()
        (probe / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.16)\n"
            "project(vendor_probe LANGUAGES NONE)\n"
            'set(PAD_V3_GRAD_PROJECT_DIR "" CACHE PATH "selected project")\n'
            'set(PAD_V3_GRAD_CONFIG_OUT "${CMAKE_BINARY_DIR}/vendor-config.json")\n'
            f'include("{include_path}")\n',
            encoding="utf-8",
        )
        command = [cmake, "-S", str(probe), "-B", str(build)]
        if os.environ.get("CMAKE_GENERATOR"):
            command.extend(["-G", os.environ["CMAKE_GENERATOR"]])
        if os.environ.get("CMAKE_MAKE_PROGRAM"):
            command.append(f"-DCMAKE_MAKE_PROGRAM={os.environ['CMAKE_MAKE_PROGRAM']}")

        observations = []
        for project in (project_a, project_b):
            marker = project.name.rsplit("-", 1)[-1]
            completed = subprocess.run(
                command + [f"-DPAD_V3_GRAD_PROJECT_DIR={project}"],
                text=True,
                capture_output=True,
                check=False,
            )
            (output / f"configure-{marker}.log").write_text(
                completed.stdout + completed.stderr, encoding="utf-8"
            )
            if completed.returncode != 0:
                raise SystemExit(f"configure failed for {marker}")
            shutil.copy2(build / "CMakeCache.txt", output / f"CMakeCache-{marker}.txt")
            shutil.copy2(build / "vendor-config.json", output / f"vendor-config-{marker}.json")
            observations.append({
                "marker": marker,
                "project_dir": str(project),
                "configure_exit_code": completed.returncode,
                "cache": str(output / f"CMakeCache-{marker}.txt"),
                "vendor_config": str(output / f"vendor-config-{marker}.json"),
            })

    summary = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "same_build_dir": "temporary ASCII probe directory",
        "cmake": cmake,
        "generator": os.environ.get("CMAKE_GENERATOR"),
        "observations": observations,
        "all_configure_pass": all(item["configure_exit_code"] == 0 for item in observations),
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
