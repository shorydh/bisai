#!/usr/bin/env python3
"""Restore an exact evaluated project using its official template and seven sources.

Only Python's standard library is required. The output directory must not exist.
No files are deleted or overwritten. A failed copy leaves its partial output for
inspection; choose a different output directory after resolving the error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
from pathlib import Path, PurePosixPath


class RestoreError(Exception):
    """A restore precondition or verification failed."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_no_links(path: Path) -> None:
    """Reject symlinks, junctions and other Windows reparse points in the path."""
    for component in (*reversed(path.parents), path):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        attributes = getattr(info, "st_file_attributes", 0)
        reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if stat.S_ISLNK(info.st_mode) or attributes & reparse_point:
            raise RestoreError(f"Symbolic link/reparse point is not allowed: {component}")


def checked_absolute(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if ".." in path.parts:
        raise RestoreError(f"Parent traversal is not allowed: {value}")
    path = path.absolute()
    check_no_links(path)
    return path.resolve(strict=False)


def relative_file(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise RestoreError(f"Invalid manifest path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ("", ".", "..") for p in value.split("/")):
        raise RestoreError(f"Unsafe manifest path: {value!r}")
    return path.as_posix()


def inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def load_manifest(path: Path) -> dict:
    check_no_links(path)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise RestoreError(f"Cannot read manifest {path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise RestoreError(f"Manifest must be a JSON object: {path}")
    entries = manifest.get("files")
    if not isinstance(entries, list) or len(entries) != 38:
        raise RestoreError(f"Expected 38 files in manifest: {path}")
    if manifest.get("all_official_files_count") != 38:
        raise RestoreError(f"Incorrect official file count in manifest: {path}")
    seen = set()
    editable_count = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise RestoreError(f"Manifest file entry must be an object: {path}")
        name = relative_file(entry.get("path"))
        if name in seen:
            raise RestoreError(f"Duplicate manifest path: {name}")
        seen.add(name)
        if not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256", ""))):
            raise RestoreError(f"Invalid SHA256 for {name}")
        if not isinstance(entry.get("editable"), bool):
            raise RestoreError(f"Missing boolean editable flag for {name}")
        editable_count += entry["editable"]
    if editable_count != 7:
        raise RestoreError(f"Expected seven editable files; found {editable_count}")
    if not re.fullmatch(r"[0-9a-f]{64}", str(manifest.get("editable_text_tree_sha256", ""))):
        raise RestoreError("Invalid editable tree hash")
    if not re.fullmatch(r"[0-9a-f]{24}", str(manifest.get("submission_id", ""))):
        raise RestoreError("Invalid official submission ID")
    return manifest


def select_manifest(package: Path, submission: str | None, version: str | None) -> dict:
    directory = package / "artifacts" / "manifests"
    if submission:
        if not re.fullmatch(r"[0-9a-f]{24}", submission):
            raise RestoreError("--submission must be a complete 24-character official task ID")
        selected = load_manifest(directory / (submission + ".json"))
        if selected["submission_id"] != submission:
            raise RestoreError("Manifest filename and submission_id disagree")
        return selected
    if not version or not re.fullmatch(r"[0-9a-f]{64}", version):
        raise RestoreError("--version must be a complete 64-character editable tree SHA256")
    matches = []
    for path in sorted(directory.glob("*.json")):
        manifest = load_manifest(path)
        if manifest["editable_text_tree_sha256"] == version:
            matches.append(manifest)
    if not matches:
        raise RestoreError("No manifest matches that exact version hash")
    signature = lambda m: sorted((f["path"], f["sha256"], f["editable"]) for f in m["files"])
    if any(signature(m) != signature(matches[0]) for m in matches[1:]):
        raise RestoreError("This editable version used different templates; select --submission instead")
    return matches[0]


def template_root(path: Path) -> Path:
    for candidate in (path, path / "code"):
        check_no_links(candidate)
        if all((candidate / f).is_file() for f in ("build.sh", "CMakeLists.txt")) and all(
            (candidate / d).is_dir() for d in ("op_host", "op_kernel")
        ):
            return candidate
    raise RestoreError("--template must contain build.sh, CMakeLists.txt, op_host and op_kernel (directly or under code/)")


def restore(args: argparse.Namespace) -> dict:
    package = checked_absolute(Path(__file__).parent.parent)
    template_input = checked_absolute(args.template)
    template = template_root(template_input)
    output = checked_absolute(args.output)
    if output.exists():
        raise RestoreError(f"Output already exists; refusing to overwrite: {output}")
    if not output.parent.is_dir():
        raise RestoreError(f"Output parent must already exist: {output.parent}")
    for protected in (package, template_input, template):
        if inside(output, protected) or inside(protected, output):
            raise RestoreError("Output must be separate from both the template and handoff package")
    manifest = select_manifest(package, args.submission, args.version)
    version = manifest["editable_text_tree_sha256"]
    source_root = package / "artifacts" / "code" / version
    data_by_path = {}
    editable_hashes = {}
    for entry in manifest["files"]:
        name = entry["path"]
        source = (source_root if entry["editable"] else template) / name
        check_no_links(source)
        if not source.is_file():
            raise RestoreError(f"Required file is missing: {source}")
        data = source.read_bytes()
        actual = sha256(data)
        if actual != entry["sha256"]:
            kind = "published source" if entry["editable"] else "official template"
            raise RestoreError(
                f"SHA256 mismatch in {kind}: {name}; expected {entry['sha256']}, got {actual}. "
                "If the official template has changed, obtain the matching historical template; "
                "this tool cannot claim an exact restoration with different bytes."
            )
        data_by_path[name] = data
        if entry["editable"]:
            editable_hashes[name] = actual
    calculated = sha256("".join(name + "\0" + editable_hashes[name] + "\n" for name in sorted(editable_hashes)).encode("utf-8"))
    if calculated != version:
        raise RestoreError("Published source bytes do not match the editable tree hash")

    # Every source is validated before creating the new output; no deletion or overwrite.
    output.mkdir()
    try:
        for name, data in data_by_path.items():
            destination = output / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            check_no_links(destination)
            with destination.open("xb") as stream:
                stream.write(data)
        for entry in manifest["files"]:
            if sha256((output / entry["path"]).read_bytes()) != entry["sha256"]:
                raise RestoreError(f"Restored file verification failed: {entry['path']}")
    except (OSError, RestoreError) as exc:
        raise RestoreError(f"Restore failed; partial output retained at {output}: {exc}") from exc
    return {
        "result": "PASS", "submission_id": manifest["submission_id"],
        "editable_text_tree_sha256": version, "output": str(output),
        "official_template_files_verified": 31, "editable_files_verified": 7,
        "restored_files_verified": 38,
        "verification_scope": "Exact source bytes only; no compilation or NPU evaluation performed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--submission", help="Complete official task ID")
    selection.add_argument("--version", help="Complete editable source tree SHA256")
    parser.add_argument("--template", required=True, help="Matching official project template directory")
    parser.add_argument("--output", required=True, help="New, separate output directory; parent must exist")
    try:
        print(json.dumps(restore(parser.parse_args()), ensure_ascii=False, indent=2))
    except (RestoreError, OSError) as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
