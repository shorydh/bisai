#!/usr/bin/env python3
"""Contract tests for the R004 acceptance verifier."""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROUND = Path(__file__).resolve().parents[1]
RUNNER = ROUND / "device-runner"
CASES = ROUND / "device-case" / "edge-legal-cancellation"
VERIFY = RUNNER / "verify_outputs.py"
METADATA = RUNNER / "runner_metadata.py"
CASE_IDS = ("int32-contiguous", "int32-split", "int64-contiguous", "int64-split")


class AcceptanceVerifierTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cases = self.root / "cases"
        self.run_root = self.root / "run"
        shutil.copytree(CASES, self.cases)
        for case_id in CASE_IDS:
            output = self.run_root / case_id / "output"
            output.mkdir(parents=True)
            shutil.copy2(self.cases / case_id / "golden" / "y.bin", output / "y.bin")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def verify(self) -> tuple[int, dict]:
        report_path = self.root / "report.json"
        completed = subprocess.run(
            [
                sys.executable,
                str(VERIFY),
                "--cases",
                str(self.cases),
                "--run-root",
                str(self.run_root),
                "--execution-mode",
                "synthetic",
                "--output",
                str(report_path),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertTrue(report_path.is_file(), completed.stderr)
        return completed.returncode, json.loads(report_path.read_text(encoding="utf-8"))

    def test_correct_four_cases_and_extra_manifest_pass_synthetic(self) -> None:
        (self.cases / "unexpected" / "manifest.json").parent.mkdir()
        (self.cases / "unexpected" / "manifest.json").write_text("{}", encoding="utf-8")
        code, report = self.verify()
        self.assertEqual(code, 0)
        self.assertTrue(report["all_pass"])
        self.assertFalse(report["device_execution"])
        self.assertTrue(report["synthetic_fixture"])
        self.assertEqual([case["case_id"] for case in report["cases"]], list(CASE_IDS))
        self.assertTrue(all(case["output_bytes"] == 12 for case in report["cases"]))

    def test_missing_output_fails(self) -> None:
        (self.run_root / "int32-split" / "output" / "y.bin").unlink()
        code, report = self.verify()
        self.assertNotEqual(code, 0)
        case = next(item for item in report["cases"] if item["case_id"] == "int32-split")
        self.assertEqual(case["status"], "FAIL")
        self.assertEqual(case["reason"], "missing_output")

    def test_truncated_output_is_not_broadcast(self) -> None:
        (self.run_root / "int64-contiguous" / "output" / "y.bin").write_bytes(b"\0" * 4)
        code, report = self.verify()
        self.assertNotEqual(code, 0)
        case = next(item for item in report["cases"] if item["case_id"] == "int64-contiguous")
        self.assertEqual(case["status"], "FAIL")
        self.assertEqual(case["reason"], "output_size_mismatch:4!=12")

    def test_stale_output_fails(self) -> None:
        output = self.run_root / "int32-contiguous" / "output" / "y.bin"
        future = output.stat().st_mtime_ns + 2_000_000_000
        (output.parent.parent / "case-run.json").write_text(
            json.dumps({"started_at_ns": future}), encoding="utf-8"
        )
        code, report = self.verify()
        self.assertNotEqual(code, 0)
        case = next(item for item in report["cases"] if item["case_id"] == "int32-contiguous")
        self.assertEqual(case["reason"], "stale_output")

    def test_out_of_tolerance_fails_with_element_errors(self) -> None:
        (self.run_root / "int64-split" / "output" / "y.bin").write_bytes(
            struct.pack("<ff", 0.0, 0.0) + struct.pack("<f", 0.001)
        )
        code, report = self.verify()
        self.assertNotEqual(code, 0)
        case = next(item for item in report["cases"] if item["case_id"] == "int64-split")
        self.assertEqual(case["reason"], "value_out_of_tolerance")
        self.assertEqual(len(case["actual"]), 3)
        self.assertEqual(len(case["abs_error"]), 3)

    def test_input_metadata_shape_mismatch_is_contract_error(self) -> None:
        case_json = self.cases / "int32-contiguous" / "case.json"
        data = json.loads(case_json.read_text(encoding="utf-8"))
        data["outputs"][0]["tensors"][0]["shape"] = [3]
        case_json.write_text(json.dumps(data), encoding="utf-8")
        code, report = self.verify()
        self.assertNotEqual(code, 0)
        self.assertTrue(report["contract_ok"])
        case = next(item for item in report["cases"] if item["case_id"] == "int32-contiguous")
        self.assertEqual(case["status"], "FAIL")
        self.assertIn("invalid y metadata", case["reason"])

    def test_unexpected_manifest_variant_is_contract_error(self) -> None:
        manifest_path = self.cases / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["variants"].append(dict(manifest["variants"][0], case_id="unexpected-case"))
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        code, report = self.verify()
        self.assertNotEqual(code, 0)
        self.assertFalse(report["contract_ok"])
        self.assertIn("manifest case IDs differ", report["contract_error"])

    def test_project_source_identity_is_recorded(self) -> None:
        run_root = self.root / "provenance"
        npu_log = self.root / "npu-smi.log"
        npu_log.write_text("synthetic provenance test\n", encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                str(METADATA),
                "begin",
                "--run-root", str(run_root),
                "--run-id", "synthetic-provenance",
                "--project-dir", str(ROUND / "source" / "P"),
                "--vendor-root", str(self.root / "vendor"),
                "--expected-library", str(self.root / "vendor/libcust_opapi.so"),
                "--cmake-cache", str(self.root / "CMakeCache.txt"),
                "--vendor-config", str(self.root / "vendor-config.json"),
                "--runner-binary", str(self.root / "edge_case_runner"),
                "--cases", str(self.cases),
                "--device-id", "0",
                "--npu-smi-log", str(npu_log),
                "--npu-smi-exit-code", "0",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        record = json.loads((run_root / "run-record.json").read_text(encoding="utf-8"))
        self.assertEqual(record["project_source"]["identified_as"], "P/r6")
        self.assertTrue(record["project_source"]["recognized"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
