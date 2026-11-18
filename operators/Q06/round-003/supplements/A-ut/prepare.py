"""Create a fresh runnable UT project from the published R003 A handoff."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile


SUBMISSIONS = {
    'PL': ('6afda28385ad43bbe043bf1c', 'da28938e1300d6dbaf5424ec38f34191d3b18d288225b6dedfa6f6cce2b2e5bd'),
    'PL-lazy': ('6afda34285ad43bbe045172e', '2d0d05a4770c22a30789581f20db81a965a1281f63e618007d222b3db13dc8da'),
}


def prepare(handoff: Path, version: str, destination: Path) -> None:
    submission, expected_hash = SUBMISSIONS[version]
    manifest_path = handoff / 'artifacts/manifests' / (submission + '.json')
    manifest_bytes = manifest_path.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != expected_hash:
        raise ValueError(f'Unexpected R003 A manifest for {version}: {manifest_path}')
    manifest = json.loads(manifest_bytes)
    source = handoff / 'artifacts/code' / manifest['source_tree_sha256']
    if manifest['version'] != version or len(manifest['files']) != 38:
        raise ValueError('The supplied handoff does not match the R003 A project')
    if destination.exists():
        raise FileExistsError(f'Choose a fresh destination: {destination}')
    overlay = Path(__file__).resolve().parent / 'overlay'
    replacements = sorted(p for p in overlay.rglob('*') if p.is_file())
    if not replacements or any(p.relative_to(overlay).parts[:2] != ('tests', 'ut') for p in replacements):
        raise ValueError('Expected the repair files under overlay/tests/ut')

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        project = Path(temporary) / 'project'
        for row in manifest['files']:
            src = (source / row['path']).resolve()
            relative = src.relative_to(source.resolve())
            data = src.read_bytes()
            if hashlib.sha256(data).hexdigest() != row['sha256']:
                raise ValueError(f'Frozen source mismatch: {relative}')
            dst = project / relative
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
        for src in replacements:
            dst = project / src.relative_to(overlay)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        project.rename(destination)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--handoff', type=Path, required=True, help='Extracted R003 A handoff directory')
    parser.add_argument('--version', choices=SUBMISSIONS, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.handoff, args.version, args.destination)
    print(args.destination.resolve())
