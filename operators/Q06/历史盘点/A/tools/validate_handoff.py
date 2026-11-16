#!/usr/bin/env python3
"""Validate the portable evidence package with Python's standard library.

Default mode is read-only and also verifies the publication manifest. Maintainers
may refresh validation.json and publication-manifest.json with --write-report
--write-manifest after reviewing an intentional evidence change. This validates
published evidence consistency; it does not query or rerun the official judge.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

FIELDS = "experiment_id operator round_id agent_id task_id base_version candidate_version hypothesis change official_task_id official_result_ref evaluated_at evaluation_protocol official_status official_metrics baseline_official_result_ref comparison finding_status applicability artifacts notes".split()
BASE = "6afb1beb6bd0f9be37af3fc5"
CURRENT = "6afb1ca86bd0f9be37b0b7cd"
PROBLEM = "6ad9ab403ff2fef7e80e2a1d"
HEX = re.compile(r"^[0-9a-f]{64}$")
OFFICIAL_FIELDS = set("_id ID problem_id create_time status judge_revision public_only valid theory_score total_testcase_count judge_missing_cases result files _publication".split())
RANK_FIELDS = set("rank submission_id submission status create_time score result".split())


class Invalid(Exception):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def safe_path(root, reference, exists=True):
    require(isinstance(reference, str) and reference, "Missing local reference")
    relative = PurePosixPath(reference)
    require(not relative.is_absolute() and ".." not in relative.parts and "\\" not in reference and ":" not in reference,
            f"Unsafe local reference: {reference}")
    path = root.joinpath(*relative.parts)
    require(path.resolve().is_relative_to(root.resolve()), f"Reference outside package: {reference}")
    require(not exists or path.exists(), f"Missing reference: {reference}")
    return path


def check_version(root, version, manifests):
    require(version is None or isinstance(version, dict), "Version must be null or object")
    if version is None:
        return
    sid = version["official_submission_id"]
    require(sid in manifests, f"Unknown version task {sid}")
    manifest = manifests[sid]
    tree = manifest["editable_text_tree_sha256"]
    require(version["editable_text_tree_sha256"] == tree, f"Version tree mismatch {sid}")
    require(version["all_official_files_count"] == 38 and version["git_commit"] is None,
            f"Unsubstantiated version identity {sid}")
    require(version["snapshot"] == f"artifacts/code/{tree}", f"Snapshot mismatch {sid}")
    require(version["manifest"] == f"artifacts/manifests/{sid}.json", f"Manifest mismatch {sid}")
    safe_path(root, version["snapshot"])
    safe_path(root, version["manifest"])


def validate(root):
    records = [json.loads(line) for line in (root / "experiments.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    require(len(records) == 30, "Expected all 30 archived official records")
    require(len({r["experiment_id"] for r in records}) == 30, "Duplicate experiment IDs")
    by_sid = {r["official_task_id"]: r for r in records}
    require(len(by_sid) == 30, "Duplicate official tasks")
    inventory = read(root / "artifacts/version_inventory.json")
    editable = set(inventory["editable_paths"])
    require(len(editable) == 7, "Expected seven editable paths")
    manifests, officials, readonly_sets, versions = {}, {}, set(), defaultdict(list)
    for sid, record in by_sid.items():
        require(set(record) == set(FIELDS), f"Fixed fields differ: {sid}")
        require(record["operator"] == "06_PadV3Grad" and record["round_id"] == "历史盘点" and record["agent_id"] == "A", f"Task labels differ: {sid}")
        require(record["task_id"] is None and record["evaluated_at"] is None, f"Unknown task/completion fields must remain null: {sid}")
        require(record["finding_status"] in {"verified", "pending", "invalid"}, f"Invalid finding status: {sid}")
        official = read(safe_path(root, record["official_result_ref"]))
        require(set(official) == OFFICIAL_FIELDS, f"Unexpected official fields: {sid}")
        require(official["_id"] == sid and official["problem_id"] == PROBLEM, f"Official identity mismatch: {sid}")
        require(official["status"] == record["official_status"], f"Official status mismatch: {sid}")
        provenance = official["_publication"]
        require(HEX.fullmatch(provenance["source_sha256"]) and provenance["official_endpoint"].endswith("/submissions/" + sid), f"Official provenance missing: {sid}")
        manifest = read(safe_path(root, f"artifacts/manifests/{sid}.json"))
        require(manifest["submission_id"] == sid and manifest["all_official_files_count"] == 38, f"Manifest identity/count mismatch: {sid}")
        entries = {e["path"]: e for e in manifest["files"]}
        require(len(entries) == len(manifest["files"]) == 38, f"Manifest file count/duplicates: {sid}")
        require({p for p, e in entries.items() if e["editable"]} == editable, f"Editable manifest mismatch: {sid}")
        for path, entry in entries.items():
            safe_path(root, path, exists=False)
            require(HEX.fullmatch(entry["sha256"]), f"Invalid SHA256 in {sid}/{path}")
        readonly_sets.add(tuple(sorted((p, e["sha256"]) for p, e in entries.items() if not e["editable"])))
        source_files = {f["path"]: f for f in official["files"]}
        require(len(source_files) == len(official["files"]) == 7 and set(source_files) == editable, f"Official source selection mismatch: {sid}")
        tree = manifest["editable_text_tree_sha256"]
        material = ""
        snapshot = safe_path(root, f"artifacts/code/{tree}")
        require({p.relative_to(snapshot).as_posix() for p in snapshot.rglob("*") if p.is_file()} == editable, f"Extra or missing snapshot files: {tree}")
        for path in sorted(editable):
            data = safe_path(snapshot, path).read_bytes()
            digest = sha(data)
            require(digest == entries[path]["sha256"], f"Snapshot bytes mismatch: {sid}/{path}")
            require(data == source_files[path]["content"].encode("utf-8"), f"Official submitted content mismatch: {sid}/{path}")
            material += path + "\0" + digest + "\n"
        require(sha(material.encode("utf-8")) == tree, f"Tree identity mismatch: {sid}")
        versions[tree].append(sid)
        metrics = record["official_metrics"]
        for key in ("theory_score", "total_testcase_count", "judge_missing_cases", "result"):
            require(metrics[key] == official[key], f"Raw official metric altered: {sid}/{key}")
        rank_ref = metrics.get("ranking_result_ref")
        if rank_ref:
            ranking = read(safe_path(root, rank_ref))
            row = ranking["row"]
            require(set(row) <= RANK_FIELDS, f"Unrelated ranking fields: {sid}")
            require(row["submission_id"] == sid and row["submission"]["_id"] == sid, f"Ranking not bound to exact submission: {sid}")
            require(set(row["submission"]) <= {"_id", "ID", "status", "create_time"}, f"Ranking profile data: {sid}")
            require(row["status"] == official["status"] and row["submission"]["status"] == official["status"], f"Ranking status differs: {sid}")
            require(metrics["row.score"] == row["score"] and metrics["ranking_row"] == row, f"Raw ranking metric altered: {sid}")
            prov = ranking["provenance"]
            require(prov["matching_submission_id"] == sid and HEX.fullmatch(prov["source_sha256"]), f"Missing ranking provenance: {sid}")
        else:
            require(metrics.get("row.score") is None and metrics.get("ranking_row") is None, f"Score without bound official evidence: {sid}")
        protocol = record["evaluation_protocol"]
        require(protocol["problem_id"] == PROBLEM and protocol["endpoint"].endswith("/submissions/" + sid), f"Protocol identity differs: {sid}")
        require(protocol["submitted_at"] == official["create_time"] and protocol["evaluation_completion_timestamp"] is None, f"Official time mapping differs: {sid}")
        for reference in record["artifacts"]:
            safe_path(root, reference)
        safe_path(root, protocol["problem_configuration_ref"])
        safe_path(root, record["baseline_official_result_ref"])
        manifests[sid], officials[sid] = manifest, official
    require(len(versions) == 21 and len(readonly_sets) == 1, "Expected 21 editable versions and one shared readonly template")
    require({p.name for p in (root / "artifacts/code").iterdir()} == set(versions), "Code inventory mismatch")
    require({p.stem for p in (root / "artifacts/manifests").glob("*.json")} == set(by_sid), "Manifest inventory mismatch")
    require({p.stem for p in (root / "artifacts/official").glob("*.json")} == set(by_sid), "Official inventory mismatch")
    inventory_by_tree = {v["editable_text_tree_sha256"]: v for v in inventory["versions"]}
    require(set(inventory_by_tree) == set(versions), "Version inventory differs")
    for tree, ids in versions.items():
        require(set(inventory_by_tree[tree]["official_task_ids"]) == set(ids), f"Inventory task mapping differs: {tree}")
    base_score = by_sid[BASE]["official_metrics"]["row.score"]
    require(base_score == 14.74 and by_sid[CURRENT]["official_metrics"]["row.score"] == 15.51, "Archived baseline/current scores differ")
    for sid, record in by_sid.items():
        check_version(root, record["base_version"], manifests)
        check_version(root, record["candidate_version"], manifests)
        require(record["candidate_version"]["official_submission_id"] == sid, f"Candidate does not identify actual task: {sid}")
        comparison = record["comparison"]
        require(comparison["baseline_official_task_id"] == BASE and comparison["baseline_score_raw"] == base_score, f"Comparison baseline differs: {sid}")
        require(comparison["candidate_score_raw"] == record["official_metrics"].get("row.score"), f"Comparison raw candidate metric differs: {sid}")
        require(comparison["performance_gain"] is None, f"Unprovided speedup inferred: {sid}")
        delta = comparison["total_score_delta"]
        if delta is not None:
            require(sid in {BASE, CURRENT} and record["official_status"] == "Pass", f"Unsupported comparison: {sid}")
            require(Decimal(str(delta)) == Decimal(str(comparison["candidate_score_raw"])) - Decimal(str(base_score)), f"Score arithmetic mismatch: {sid}")
            require(all(comparison["comparison_checks"].values()), f"Comparable conditions not met: {sid}")
            baseline, candidate = officials[BASE], officials[sid]
            for key in ("problem_id", "judge_revision", "public_only", "total_testcase_count"):
                require(baseline[key] == candidate[key], f"Comparison protocol differs: {sid}/{key}")
            visible = lambda o: [(r["testcase_id"], r.get("best_time")) for r in o["result"] if r["testcase_status"] != "Hidden"]
            require(visible(baseline) == visible(candidate), f"Public benchmark protocol differs: {sid}")
        if record["official_status"] != "Pass":
            require(delta is None, f"Failed experiment claims performance gain: {sid}")
    require(by_sid[CURRENT]["comparison"]["total_score_delta"] == 0.77, "Expected observed +0.77 score delta")
    receipt_count = 0
    for directory in (root / "artifacts/submissions").iterdir():
        receipt, verification, submitted = read(directory / "receipt.json"), read(directory / "verification.json"), read(directory / "request_files.json")
        sid = receipt["submission_id"]
        tree = manifests[sid]["editable_text_tree_sha256"]
        require(receipt["tree_sha256"] == tree and verification["sid"] == sid and verification["submitted_equals_official"] is True, f"Receipt/version mismatch: {directory.name}")
        submitted_by_path = {f["path"]: f for f in submitted}
        official_by_path = {f["path"]: f for f in officials[sid]["files"]}
        require(set(submitted_by_path) == editable, f"Request file set differs: {sid}")
        manifest = read(directory / "manifest.json")
        for entry in manifest["files"]:
            path = entry["path"]
            raw = safe_path(directory / "source_raw", path).read_bytes()
            text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
            require(sha(raw) == entry["raw_sha256"] and sha(text.encode("utf-8")) == entry["submitted_utf8_sha256"], f"Pre-submit raw/text hash differs: {sid}/{path}")
            require(text == submitted_by_path[path]["content"] == official_by_path[path]["content"], f"Actual submitted content differs: {sid}/{path}")
        receipt_count += 1
    require(receipt_count == 5, "Expected five original replay receipts")
    coverage = read(root / "artifacts/version_coverage.json")
    require(coverage["issues"] == [] and coverage["official_files_checked"] == 1140, "Source audit has unresolved issues")
    complete, incomplete = 0, 0
    for local in coverage["local"]:
        if local["missing_files"]:
            require(local["tree7"] is None, "Partial backup misleadingly marked complete")
            incomplete += 1
            continue
        require(local["tree7"] in versions and local["official_task_ids"], f"Uncovered complete local version: {local['path']}")
        require(set(local["official_task_ids"]) == set(versions[local["tree7"]]), f"Coverage task association differs: {local['path']}")
        complete += 1
    recheck = read(root / "artifacts/recheck/recheck.json")
    require(recheck["operation"] == "GET only; no new official submissions" and recheck["known_tasks_checked"] == 30 and recheck["new_unknown_task_ids"] == [], "Unexpected live recheck scope")
    require({c["official_task_id"] for c in recheck["checks"]} == set(by_sid), "Recheck task coverage differs")
    for check in recheck["checks"]:
        sid = check["official_task_id"]
        require(all(check[k] is True for k in ("problem_matches", "status_matches_archive", "editable_matches_archive", "all_38_files_match_archive", "results_match_archive")), f"Live official mismatch: {sid}")
        require(check["status"] == officials[sid]["status"] and check["editable_sha256"] == manifests[sid]["editable_text_tree_sha256"], f"Recheck code/status identity differs: {sid}")
        require(check["original_source_response_sha256"] == officials[sid]["_publication"]["source_sha256"], f"Recheck original digest differs: {sid}")
    require(recheck["current_ranking_observation"] is None, "Current ranking anomaly changed; review scope wording")
    for document in (root / "README.md", root / "summary.md"):
        text = document.read_text(encoding="utf-8")
        for reference in re.findall(r"\]\(([^)]+)\)", text):
            if reference in {"validation.json", "publication-manifest.json"}:
                continue  # Generated after structural validation during first publication.
            if not reference.startswith(("https://", "http://", "#")):
                safe_path(root, reference.split("#")[0])
    status_counts = dict(Counter(r["official_status"] for r in records))
    require(status_counts == {"Runtime Error": 5, "Pass": 23, "Wrong Answer": 2}, "Status totals differ")
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(), "status": "PASS",
        "scope": "Offline verification of published excerpts, source snapshots, manifests, receipts, coverage audit, and live GET recheck report; no benchmark execution",
        "records": len(records), "fixed_fields": FIELDS, "unique_editable_versions": len(versions), "status_counts": status_counts,
        "official_manifest_entries": 1140, "editable_content_checks": 210,
        "distinct_published_code_files": 147, "readonly_template_sets": len(readonly_sets),
        "readonly_files_per_task": 31, "original_replay_receipts": receipt_count,
        "complete_local_versions_covered": complete, "incomplete_local_directories_recorded": incomplete,
        "live_get_tasks_checked": 30, "current_ranking_observation": None,
        "archived_baseline_score": base_score, "archived_current_score": 15.51, "archived_single_observation_delta": 0.77,
        "limitations": ["Requires the exact official template to restore the omitted 31 files; their bytes are not distributed here.", "Original full responses are represented by SHA256 provenance; only explicitly selected fields are published.", "This validator checks evidence consistency, not official benchmark correctness or statistical significance.", "The latest ranking scan did not find the current task; saved 14.74/15.51 scores belong to their historical observations."],
    }


def package_entries(root):
    entries = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "publication-manifest.json":
            continue
        require("__pycache__" not in path.parts, "Do not publish Python cache files; run with -B")
        entries.append({"path": path.relative_to(root).as_posix(), "sha256": sha(path.read_bytes()), "size": path.stat().st_size})
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--write-manifest", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        require(not args.write_report or args.write_manifest, "Use --write-report together with --write-manifest to keep published hashes consistent")
        report = validate(root)
        if args.write_report:
            write(root / "validation.json", report)
        manifest_path = root / "publication-manifest.json"
        entries = package_entries(root)
        if args.write_manifest:
            write(manifest_path, {"created_at": datetime.now(timezone.utc).isoformat(), "algorithm": "SHA256 exact file bytes", "excluded": ["publication-manifest.json (self-reference)"], "files": entries})
        else:
            require(read(manifest_path)["files"] == entries, "Publication manifest differs; review modifications before regenerating")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (Invalid, KeyError, TypeError, ValueError, OSError) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
