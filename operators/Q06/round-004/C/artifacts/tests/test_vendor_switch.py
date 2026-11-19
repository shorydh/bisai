#!/usr/bin/env python3
"""Verify that CMake cache selection follows two different explicit projects."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROUND = Path(__file__).resolve().parents[1]
RUNNER = ROUND / "device-runner"


def make_project(root: Path, marker: str) -> Path:
    project = root / f"project-{marker}"
    vendor = project / "build/packages/vendors/pad_v3_grad_custom"
    (vendor / "op_api/include").mkdir(parents=True)
    (vendor / "op_api/lib").mkdir(parents=True)
    (vendor / "op_api/include/aclnn_pad_v3_grad.h").write_text(
        f"// {marker}\n", encoding="utf-8"
    )
    (vendor / "op_api/lib/libcust_opapi.so").write_bytes(f"library-{marker}".encode())
    (vendor / "version.info").write_text(f"marker={marker}\n", encoding="utf-8")
    return project


def cache_value(path: Path, key: str) -> str:
    prefix = key + "="
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line[len(prefix):]
    raise AssertionError(f"missing cache key {key}")


class VendorSwitchTest(unittest.TestCase):
    def test_same_build_cache_switches_between_two_projects(self) -> None:
        cmake = os.environ.get("CMAKE") or shutil.which("cmake")
        if not cmake:
            self.skipTest("cmake is not available on this host")
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            project_a = make_project(temp, "a")
            project_b = make_project(temp, "b")
            probe = temp / "probe"
            build = temp / "build"
            probe.mkdir()
            include_path = str(RUNNER / "vendor_paths.cmake").replace("\\", "/")
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
            for project, marker in ((project_a, "a"), (project_b, "b")):
                completed = subprocess.run(
                    command + [f"-DPAD_V3_GRAD_PROJECT_DIR={project}"],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                selected = Path(cache_value(build / "CMakeCache.txt", "PAD_V3_GRAD_PROJECT_DIR:PATH"))
                self.assertEqual(selected.resolve(), project.resolve())
                config = json.loads((build / "vendor-config.json").read_text(encoding="utf-8"))
                self.assertEqual(Path(config["resolved_project_dir"]).resolve(), project.resolve())
                self.assertEqual(
                    Path(config["op_api_library"]).resolve(),
                    (project / "build/packages/vendors/pad_v3_grad_custom/op_api/lib/libcust_opapi.so").resolve(),
                )
                self.assertIn(marker, json.dumps(config))


if __name__ == "__main__":
    unittest.main(verbosity=2)
