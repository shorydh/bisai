#!/usr/bin/env python3
"""Validate the published PadV3Grad round-002/A evidence without network access.

This checks internal consistency and exact source bytes, not judge correctness,
unpublished measurement methods, stable performance, or central baseline approval.
Default use is read-only. After reviewing an intentional change, maintainers may
use --write-report --write-manifest to refresh the two generated integrity files.
Requires Python 3.10 or newer and only its standard library.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

FIELDS = "experiment_id operator round_id agent_id task_id base_version candidate_version hypothesis change official_task_id official_result_ref evaluated_at evaluation_protocol official_status official_metrics baseline_official_result_ref comparison finding_status applicability artifacts notes".split()
TASK = "Q06-R002-A-OFFICIAL-COMPARABILITY-20261117"
PROBLEM = "6ad9ab403ff2fef7e80e2a1d"
HEX = re.compile(r"^[0-9a-f]{64}$")
SID = re.compile(r"^[0-9a-f]{24}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
OFFICIAL_FIELDS = set("_id ID problem_id create_time status judge_revision public_only valid theory_score total_testcase_count judge_missing_cases result msg files _publication".split())
RANK_FIELDS = set("rank submission_id submission status create_time score result".split())
CONFIG_FIELDS = "_id name title version_no version_label code_template cann_version judge_revision score_mode use_baseline iterations ranking_submission_mode ranking_testcase_count judge_baseline_verified difficulty".split()
REQUIRED_CONFIG = set("_id version_no version_label code_template cann_version judge_revision score_mode use_baseline iterations ranking_submission_mode".split())
REQUIRED_CHECKS = set("both_pass both_valid same_problem same_judge_revision same_public_only same_total_testcase_count same_visible_case_ids_and_best_time same_before_after_problem_config same_readonly_template both_bound_numeric_ranking_scores same_ranking_public_scoring_scale ranking_scale_matches_terminal both_visible_cases_pass".split())
PUBLIC_SCALE_FIELDS = {"_id", "id", "ID", "baseline", "tbest", "type"}
EXPECTED = {
    "Q06-R002-A-E001": "d0b680d59d1dfa088dd24fff5d3128feb2758251bcd8d3b34b39635bad68f949",
    "Q06-R002-A-E002": "988e491ec2d8d758adac5caa0e304cc81cb500ade732aadc9427fa1254267d41",
    "Q06-R002-A-E003": "700af8da3ef6679f48ebf8bbfa9d2f145d9357e9b6fd2e4f288542c662a1969b",
    "Q06-R002-A-E004": "d3174f99553a7ba700a726f77370e1e287e1084cd2bc9768d4bbbcbd66ce9d24",
}
ARMS = dict(zip(EXPECTED, ("P", "PL", "F", "L")))
TERMINAL = {"Pass", "Accepted", "Fail", "Wrong Answer", "Compile Error", "Runtime Error", "Time Limit Exceeded", "Memory Limit Exceeded", "System Error"}
EDITABLE = {
    "op_host/pad_v3_grad_def.cpp", "op_host/pad_v3_grad_infershape.cpp",
    "op_host/pad_v3_grad_tiling.cpp", "op_kernel/pad_v3_grad_tiling_data.h",
    "op_kernel/pad_v3_grad_tiling_key.h", "op_kernel/pad_v3_grad.cpp",
    "op_kernel/pad_v3_grad.h",
}


class Invalid(Exception):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def safe_path(root, ref, exists=True):
    require(isinstance(ref, str) and ref, "Missing path reference")
    p = PurePosixPath(ref)
    require(not p.is_absolute() and ":" not in ref and "\\" not in ref and all(v not in {"", ".", ".."} for v in ref.split("/")), f"Unsafe reference: {ref}")
    path = root.joinpath(*p.parts)
    require(path.resolve().is_relative_to(root.resolve()), f"Reference escapes package: {ref}")
    require(not exists or path.exists(), f"Missing reference: {ref}")
    require(not path.is_symlink(), f"Symlink not supported in evidence package: {ref}")
    return path


def check_ref(root, ref):
    if ref is None:
        return
    require(isinstance(ref, str), "Reference must be a string or null")
    if ref.startswith("https://"):
        return
    safe_path(root, ref.split("#", 1)[0])


def version_identity(root, version):
    require(isinstance(version, dict), "Recoverable version must be an object")
    tree = version["editable_text_tree_sha256"]
    sid = version["official_submission_id"]
    require(HEX.fullmatch(tree) and SID.fullmatch(sid), "Malformed version identity")
    require(version["all_official_files_count"] == 38, f"Version lacks full 38-file identity: {sid}")
    require(COMMIT.fullmatch(version["source_git_commit"]), f"Missing precise source publication commit: {sid}")
    manifest = read(safe_path(root, version["manifest"]))
    require(manifest["submission_id"] == sid and manifest["editable_text_tree_sha256"] == tree and manifest["all_official_files_count"] == 38, f"Version/manifest mismatch: {sid}")
    require(manifest.get("source_git_commit") == version["source_git_commit"], f"Source commit differs between version and manifest: {sid}")
    entries = {e["path"]: e for e in manifest["files"]}
    require(len(entries) == len(manifest["files"]) == 38, f"Manifest entries missing or repeated: {sid}")
    require({p for p, e in entries.items() if e["editable"]} == EDITABLE, f"Wrong editable set: {sid}")
    for path, entry in entries.items():
        safe_path(root, path, exists=False)
        require(isinstance(entry["editable"], bool) and HEX.fullmatch(entry["sha256"]), f"Malformed file identity: {sid}/{path}")
    snapshot = safe_path(root, version["snapshot"])
    require({p.relative_to(snapshot).as_posix() for p in snapshot.rglob("*") if p.is_file()} == EDITABLE, f"Snapshot contains extra or missing files: {tree}")
    material = ""
    content = {}
    for path in sorted(EDITABLE):
        data = safe_path(snapshot, path).read_bytes()
        require(sha(data) == entries[path]["sha256"], f"Snapshot hash mismatch: {sid}/{path}")
        content[path] = data.decode("utf-8")
        material += path + "\0" + sha(data) + "\n"
    require(sha(material.encode("utf-8")) == tree, f"Seven-source tree differs: {sid}")
    return manifest, content


def visible_scale(official):
    return [(r.get("testcase_id"), r.get("type"), r.get("best_time")) for r in (official.get("result") or []) if r.get("testcase_status") != "Hidden"]


def readonly_identity(manifest):
    return sorted((f["path"], f["sha256"]) for f in manifest["files"] if not f["editable"])


def validate(root):
    records = [json.loads(line) for line in (root / "experiments.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    require(records, "No experiments present")
    require({r["experiment_id"] for r in records} == set(EXPECTED), "The four planned frozen experiments are not all present")
    require(len({r["experiment_id"] for r in records}) == len(records), "Duplicate experiment identifiers")
    require(len({r["official_task_id"] for r in records}) == len(records), "One official submission was counted as multiple experiments")
    officials, manifests, configs, by_sid, ranking_scales = {}, {}, {}, {}, {}
    rank_refs = set()
    for record in records:
        require(set(record) == set(FIELDS), f"Fixed 21-field schema differs: {record.get('experiment_id')}")
        eid, sid = record["experiment_id"], record["official_task_id"]
        require(re.fullmatch(r"Q06-R002-A-E\d{3}", eid), f"Invalid new experiment ID: {eid}")
        require(record["operator"] == "PadV3Grad" and record["round_id"] == "round-002" and record["agent_id"] == "A" and record["task_id"] == TASK, f"Task labels differ: {eid}")
        require(record["evaluated_at"] is None, f"No official completion timestamp is available: {eid}")
        require(record["finding_status"] in {"verified", "pending", "invalid"}, f"Invalid finding status: {eid}")
        require(isinstance(sid, str) and SID.fullmatch(sid), f"Missing official submission ID: {eid}")
        official = read(safe_path(root, record["official_result_ref"]))
        require(set(official) <= OFFICIAL_FIELDS, f"Unexpected profile or unofficial fields in official excerpt: {eid}")
        require(official["_id"] == sid and official["problem_id"] == PROBLEM, f"Official task identity differs: {eid}")
        require(official["status"] == record["official_status"], f"Official status differs: {eid}")
        require(official["status"] in TERMINAL, f"Unfinished official task cannot be finalized: {eid}")
        require(HEX.fullmatch(official["_publication"]["source_sha256"]), f"Missing original response hash: {eid}")
        endpoint = official["_publication"].get("official_endpoint")
        require(endpoint == f"https://cannjudge.cn/api/submissions/{sid}", f"Missing or incorrect official endpoint: {eid}")
        manifest, content = version_identity(root, record["candidate_version"])
        require(record["candidate_version"]["editable_text_tree_sha256"] == EXPECTED[eid], f"Task-specified frozen source differs: {eid}")
        require(record["candidate_version"]["official_submission_id"] == sid, f"Candidate version belongs to another task: {eid}")
        source_files = {f["path"]: f["content"] for f in official["files"]}
        require(len(official["files"]) == 7 and source_files == content, f"Published source is not actual official submitted content: {eid}")
        metrics = record["official_metrics"]
        for key in ("theory_score", "total_testcase_count", "judge_missing_cases", "result"):
            require(metrics[key] == official.get(key), f"Raw metric altered: {eid}/{key}")
        observations = metrics["ranking_observations"]
        require(isinstance(observations, list), f"Rank observations must be a list: {eid}")
        seen = set()
        scales = []
        for observation in observations:
            ref = observation["ref"]
            require(ref not in seen, f"Ranking observation counted twice: {eid}")
            seen.add(ref); rank_refs.add(ref)
            rank = read(safe_path(root, ref)); row = rank["row"]
            require(set(row) <= RANK_FIELDS and row["submission_id"] == sid, f"Ranking is not an exact task projection: {eid}")
            if "submission" in row:
                require(set(row["submission"]) <= {"_id", "ID", "status", "create_time"} and row["submission"]["_id"] == sid, f"Ranking nested submission differs: {eid}")
            require(row["status"] == official["status"], f"Ranking status differs: {eid}")
            require(observation["score"] == row["score"] and observation["observed_at"] == rank["observed_at"], f"Ranking observation altered: {eid}")
            require(HEX.fullmatch(rank["_publication"]["source_sha256"]), f"Ranking original source hash missing: {eid}")
            scale = rank["public_scoring_scale"]
            require(HEX.fullmatch(rank["source_response_sha256"]) and scale["source_response_sha256"] == rank["source_response_sha256"], f"Ranking scale is not bound to the same original HTTP response: {eid}")
            require(HEX.fullmatch(scale["stored_response_sha256"]), f"Ranking saved-response byte hash missing: {eid}")
            require(isinstance(scale["machine_A_raw_file"], str) and scale["machine_A_raw_file"], f"Ranking raw response locator missing: {eid}")
            cases = scale["testcases"]
            require(isinstance(cases, list) and len(cases) == 5, f"Ranking scale must retain the five public cases: {eid}")
            require(all(set(c) == PUBLIC_SCALE_FIELDS and c["_id"] == c["id"] for c in cases), f"Ranking public scale fields or identities differ: {eid}")
            public_ids = {r["testcase_id"] for r in (official.get("result") or []) if r.get("testcase_status") != "Hidden"}
            require(len({c["_id"] for c in cases}) == 5 and {c["_id"] for c in cases} == public_ids, f"Ranking public case IDs do not match this task's terminal result: {eid}")
            scales.append(sorted(cases, key=lambda c: c["_id"]))
        ranking_scales[sid] = scales
        require(metrics["total_score"] == (observations[0]["score"] if observations else None), f"Total score has no first bound ranking observation: {eid}")
        protocol = record["evaluation_protocol"]
        require(protocol["problem_id"] == PROBLEM, f"Protocol problem differs: {eid}")
        require(protocol["submitted_at"] == official["create_time"], f"Submission timestamp differs: {eid}")
        require(protocol.get("evaluation_completion_timestamp") is None, f"Completion time was inferred: {eid}")
        for key in ("judge_revision", "public_only"):
            if key in protocol:
                require(protocol[key] == official.get(key), f"Protocol task attribute differs: {eid}/{key}")
        before = read(safe_path(root, protocol["problem_configuration_before_ref"]))
        after = read(safe_path(root, protocol["problem_configuration_after_ref"]))
        require(before["_id"] == after["_id"] == PROBLEM, f"Configuration belongs to another problem: {eid}")
        require(REQUIRED_CONFIG <= set(before) and REQUIRED_CONFIG <= set(after), f"Required public configuration fields absent: {eid}")
        for key, ref in protocol.items():
            if key.endswith("_ref"):
                check_ref(root, ref)
        configs[sid] = (before, after)
        for ref in record["artifacts"]:
            check_ref(root, ref)
        if record["baseline_official_result_ref"] is not None:
            check_ref(root, record["baseline_official_result_ref"])
        request_path = root / "artifacts" / "submissions" / eid / "request_files.json"
        request = read(request_path)
        require(len(request) == 7 and {f["path"]: f["content"] for f in request} == content, f"Submitted payload differs: {eid}")
        receipt = read(safe_path(root, f"artifacts/submissions/{eid}/receipt.json"))
        require(receipt["submission_id"] == sid and receipt["editable_tree_sha256"] == EXPECTED[eid], f"Submission receipt differs: {eid}")
        require(receipt["version"] == record["notes"]["arm"] == ARMS[eid], f"Frozen arm label differs: {eid}")
        verification = read(safe_path(root, f"artifacts/submissions/{eid}/verification.json"))
        require(verification["official_task_id"] == sid and verification["all_38_match"] is True and verification["editable_match"] is True, f"Official source readback did not match frozen sources: {eid}")
        require(verification["status"] == official["status"] and verification.get("valid") == official.get("valid") and verification.get("judge_revision") == official.get("judge_revision"), f"Source verification and official terminal identity disagree: {eid}")
        officials[sid], manifests[sid], by_sid[sid] = official, manifest, record

    baseline_records = [r for r in records if r["experiment_id"] == "Q06-R002-A-E001"]
    require(len(baseline_records) == 1, "The explicit E001 local control is missing")
    baseline_record = baseline_records[0]
    baseline_sid = baseline_record["official_task_id"]
    baseline = officials[baseline_sid]
    baseline_score = baseline_record["official_metrics"]["total_score"]

    def conditions(candidate_sid, control_sid):
        candidate, control = officials[candidate_sid], officials[control_sid]
        candidate_score = by_sid[candidate_sid]["official_metrics"]["total_score"]
        control_score = by_sid[control_sid]["official_metrics"]["total_score"]
        common_config = all(config.get(k) == configs[control_sid][0].get(k) for config in (*configs[candidate_sid], *configs[control_sid]) for k in CONFIG_FIELDS)
        cscales, bscales = ranking_scales[candidate_sid], ranking_scales[control_sid]
        matches_terminal = bool(cscales) and bool(bscales) and all(
            sorted((c["_id"], c["type"], c["tbest"]) for c in scale) == sorted(visible_scale(officials[sid]))
            for sid in (candidate_sid, control_sid) for scale in ranking_scales[sid][:1]
        )
        return {
            "both_pass": control["status"] == candidate["status"] == "Pass",
            "both_valid": control.get("valid") is True and candidate.get("valid") is True,
            "same_problem": control["problem_id"] == candidate["problem_id"],
            "same_judge_revision": control.get("judge_revision") == candidate.get("judge_revision") and control.get("judge_revision") is not None,
            "same_public_only": control.get("public_only") == candidate.get("public_only"),
            "same_total_testcase_count": control.get("total_testcase_count") == candidate.get("total_testcase_count"),
            "no_missing_cases": control.get("judge_missing_cases") is False and candidate.get("judge_missing_cases") is False,
            "same_visible_case_ids_and_best_time": bool(visible_scale(control)) and visible_scale(control) == visible_scale(candidate),
            "same_ranking_public_scoring_scale": bool(cscales) and bool(bscales) and cscales[0] == bscales[0],
            "ranking_scale_matches_terminal": matches_terminal,
            "both_visible_cases_pass": all(r.get("testcase_status") == "Pass" for o in (control, candidate) for r in (o.get("result") or []) if r.get("testcase_status") != "Hidden"),
            "same_configuration": common_config,
            "same_before_after_problem_config": common_config,
            "same_readonly_template": readonly_identity(manifests[candidate_sid]) == readonly_identity(manifests[control_sid]),
            "both_bound_numeric_ranking_scores": type(control_score) in (int, float) and type(candidate_score) in (int, float),
        }

    for sid, record in by_sid.items():
        comparison = record["comparison"]
        require(REQUIRED_CHECKS <= set(comparison["checks"]), f"Required public comparability checks missing: {sid}")
        require(comparison["baseline_official_task_id"] == baseline_sid, f"Local comparison control changed: {sid}")
        require(comparison["candidate_score_raw"] == record["official_metrics"]["total_score"] and comparison["baseline_score_raw"] == baseline_score, f"Comparison raw scores differ: {sid}")
        require(comparison["stability"] is None, f"Unsubstantiated stable-performance result: {sid}")
        require(comparison["performance_gain"] is None, f"Score differences must not be promoted to an operator speedup: {sid}")
        require(comparison["formal_baseline_qualification"] == "pending", f"Central baseline was implicitly approved: {sid}")
        require(record["baseline_official_result_ref"] == baseline_record["official_result_ref"], f"Comparison reference is not E001: {sid}")
        if record["base_version"] is not None:
            version_identity(root, record["base_version"])
            require(record["base_version"]["official_submission_id"] == baseline_sid, f"Base version is not the declared local control: {sid}")
        candidate = officials[sid]
        observed_checks = conditions(sid, baseline_sid)
        for key, value in comparison["checks"].items():
            if key in observed_checks:
                require(value == observed_checks[key], f"Claimed comparison condition disagrees: {sid}/{key}")
        require(comparison["comparison_status"] in {"verified", "pending", "invalid"}, f"Unknown bounded comparison status: {sid}")
        if comparison["comparison_status"] == "verified":
            require(all(observed_checks.values()), f"Verified bounded comparison lacks required public-condition evidence: {sid}")
            require(comparison["observed_conditions_status"] == "matched", f"Verified comparison must label matched observable conditions: {sid}")
        delta = comparison["observed_total_score_delta"]
        if delta is not None:
            require(all(observed_checks.values()), f"Observed score difference lacks consistent visible protocol: {sid}")
            require(Decimal(str(delta)) == Decimal(str(comparison["candidate_score_raw"])) - Decimal(str(baseline_score)), f"Score difference arithmetic differs: {sid}")
        if candidate.get("valid") is not True or candidate.get("status") != "Pass":
            require(delta is None, f"Failed or invalid task claims a performance difference: {sid}")
            require(comparison["comparison_status"] != "verified" and record["finding_status"] == "invalid", f"Failed or invalid task claimed verification: {sid}")

    four_arm = read(safe_path(root, "artifacts/audit/bounded_comparison.json"))
    require(four_arm["task_id"] == TASK and four_arm["stable_best"] is None, "Four-arm audit changed task or claimed a stable best")
    arms = {r["notes"]["arm"]: r for r in records}
    require(set(arms) == {"P", "PL", "F", "L"}, "Four-arm source labels differ")
    require({(p["candidate"], p["control"]) for p in four_arm["pairs"]} == {("PL", "P"), ("L", "F"), ("P", "F"), ("PL", "F")} and len(four_arm["pairs"]) == 4, "Four-arm comparison pairs differ")
    for pair in four_arm["pairs"]:
        candidate_record, control_record = arms[pair["candidate"]], arms[pair["control"]]
        csid, bsid = candidate_record["official_task_id"], control_record["official_task_id"]
        cscore, bscore = candidate_record["official_metrics"]["total_score"], control_record["official_metrics"]["total_score"]
        require(pair["candidate_task"] == csid and pair["control_task"] == bsid, "Four-arm comparison task binding differs")
        require(pair["candidate_score"] == cscore and pair["control_score"] == bscore, "Four-arm comparison raw score differs")
        checks = conditions(csid, bsid)
        require(REQUIRED_CHECKS <= set(pair["checks"]), "Four-arm required public checks absent")
        for key, value in pair["checks"].items():
            if key in checks:
                require(value == checks[key], f"Four-arm public condition disagrees: {pair['candidate']}/{pair['control']}/{key}")
        require(pair["bounded_comparison_status"] in {"verified", "pending", "invalid"}, "Four-arm bounded comparison status invalid")
        if pair["bounded_comparison_status"] == "verified":
            require(all(checks.values()), "Four-arm verified comparison lacks required public evidence")
        if pair["observed_score_difference"] is not None:
            require(all(checks.values()), "Four-arm score difference lacks comparable public conditions")
            require(Decimal(str(pair["observed_score_difference"])) == Decimal(str(cscore)) - Decimal(str(bscore)), "Four-arm difference arithmetic differs")
    all_observations = four_arm["all_observations"]
    require(len(all_observations) == 4 and {o["experiment_id"] for o in all_observations} == set(EXPECTED), "Four-arm observations omit or duplicate an experiment")
    for observation in all_observations:
        record = arms[observation["arm"]]
        sid = record["official_task_id"]
        require(observation["experiment_id"] == record["experiment_id"] and observation["official_task_id"] == sid, "Four-arm observation task differs")
        require(observation["ranking_observations"] == record["official_metrics"]["ranking_observations"], "Four-arm audit dropped or altered repeated rank observations")
        require(observation["public_case_and_tbest_signature"] == [list(v) for v in visible_scale(officials[sid])], "Four-arm public case/TBest signature differs")

    ranking_dir = root / "artifacts" / "ranking"
    published_ranks = {p.relative_to(root).as_posix() for p in ranking_dir.rglob("*.json")} if ranking_dir.exists() else set()
    require(rank_refs == published_ranks, "Published ranking observations were dropped or are unreferenced")
    for document in (root / "README.md", root / "summary.md"):
        for ref in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
            if ref in {"validation.json", "publication-manifest.json"} or ref.startswith("#"):
                continue
            check_ref(root, ref)
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(), "status": "PASS",
        "scope": "Offline evidence consistency only; no official evaluation, timing-rule verification, stable-gain proof, or baseline approval",
        "records": len(records), "fixed_fields": FIELDS,
        "status_counts": dict(Counter(r["official_status"] for r in records)),
        "unique_editable_versions": len({r["candidate_version"]["editable_text_tree_sha256"] for r in records}),
        "official_manifest_entries": 38 * len(records), "editable_content_checks": 7 * len(records),
        "ranking_observations": len(rank_refs), "local_control_official_task_id": baseline_sid,
        "central_baseline_approved_by_this_validator": False,
        "bounded_official_score_comparisons_verified": sum(r["comparison"]["comparison_status"] == "verified" for r in records),
        "four_arm_pair_comparisons": len(four_arm["pairs"]),
        "limitations": ["The omitted 31 template files require a matching official template for restoration.", "Hashes of original responses provide provenance; this tool validates published projections and cannot independently attest the server.", "Matched public conditions support bounded official score observations, not stable causal improvement or operator speedup.", "Exact backend timing and hidden-case values remain unknown; obtaining them is not a prerequisite invented by this validator.", "C's original-dependency reference and NPU judgment remain unresolved; no central baseline is approved."],
    }


def package_entries(root):
    entries = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p == root / "publication-manifest.json":
            continue
        require(not p.is_symlink() and "__pycache__" not in p.parts, "Do not publish symlinks or Python cache files")
        ref = p.relative_to(root).as_posix()
        safe_path(root, ref)
        entries.append({"path": ref, "sha256": sha(p.read_bytes()), "size": p.stat().st_size})
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--write-manifest", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        require(not args.write_report or args.write_manifest, "--write-report requires --write-manifest so hashes remain consistent")
        report = validate(root)
        if args.write_report:
            write(root / "validation.json", report)
        entries = package_entries(root)
        if args.write_manifest:
            write(root / "publication-manifest.json", {"created_at": datetime.now(timezone.utc).isoformat(), "algorithm": "SHA256 of exact file bytes", "excluded": ["publication-manifest.json (self-reference)"], "files": entries})
        else:
            require(read(root / "publication-manifest.json")["files"] == entries, "Publication manifest differs; review before regenerating")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (Invalid, OSError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
