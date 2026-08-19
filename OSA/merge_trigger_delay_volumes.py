"""Merge per-trigger-delay 3D volumes that heudiconv/dcm2niix produced for a
single acquisition (e.g. CSF_QF_retrospectivetrigger magnitude or phase)
back into one 4D volume ordered by cardiac trigger delay time, with a BIDS
.json sidecar carrying the delay times forward.

dcm2niix cannot merge this Philips Enhanced retrospective-trigger data into
4D on its own (see OSA_heuristic.py / split_enhanced_dicom.py for
background), so heudiconv numbers the fragments sequentially
(..._flow1.nii.gz ... _flow15.nii.gz) in dcm2niix's own output order, which
is NOT chronological. Each fragment's JSON sidecar carries its true
TriggerDelayTime (absent/0 for the first, unsuffixed-by-dcm2niix frame) --
that field is what this script sorts and stacks by, not the filename.

Usage:
    python merge_trigger_delay_volumes.py <bids_root> [<bids_root> ...]

<bids_root> is walked recursively for "*_flow1.nii.gz" style fragment
groups (any BIDS suffix, not just "flow" -- whatever heudiconv numbered).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import nibabel as nib
import numpy as np

FRAGMENT_RE = re.compile(r"^(?P<base>.+?)(?P<n>\d+)\.nii\.gz$")


def json_path_for(nii_path: Path) -> Path:
    assert nii_path.name.endswith(".nii.gz")
    return nii_path.with_name(nii_path.name[: -len(".nii.gz")] + ".json")


def find_fragment_groups(root: Path) -> dict[Path, list[Path]]:
    groups: dict[Path, list[Path]] = {}
    for nii_path in root.rglob("*.nii.gz"):
        if "orig_trigger_split" in nii_path.parts:
            continue
        m = FRAGMENT_RE.match(nii_path.name)
        if not m:
            continue
        if not json_path_for(nii_path).exists():
            continue
        base = nii_path.parent / (m.group("base") + ".nii.gz")
        groups.setdefault(base, []).append(nii_path)
    # a lone, unfragmented file (no sibling with the same base) isn't a group to merge
    return {base: files for base, files in groups.items() if len(files) > 1}


def merge_group(fragments: list[Path], merged_nii_path: Path, force: bool = False) -> bool:
    if merged_nii_path.exists() and not force:
        print(f"  already merged, skipping: {merged_nii_path.name}")
        return False

    entries = []
    for f in fragments:
        jf = json_path_for(f)
        meta = json.loads(jf.read_text())
        delay = meta.get("TriggerDelayTime", 0)
        entries.append((delay, f, jf, meta))
    entries.sort(key=lambda e: e[0])

    imgs = [nib.load(str(f)) for _, f, _, _ in entries]
    shapes = {img.shape for img in imgs}
    if len(shapes) > 1:
        raise ValueError(f"fragment shapes differ: {shapes}")

    data = np.stack([np.asarray(img.dataobj) for img in imgs], axis=-1)
    merged_img = nib.Nifti1Image(data, imgs[0].affine, imgs[0].header)
    merged_img.header.set_data_dtype(data.dtype)

    merged_meta = dict(entries[0][3])
    merged_meta.pop("TriggerDelayTime", None)
    merged_meta["TriggerDelayTime"] = [e[0] for e in entries]

    backup_dir = merged_nii_path.parent / "orig_trigger_split"
    backup_dir.mkdir(exist_ok=True)
    for _, f, jf, _ in entries:
        shutil.move(str(f), str(backup_dir / f.name))
        shutil.move(str(jf), str(backup_dir / jf.name))

    nib.save(merged_img, str(merged_nii_path))
    json_path_for(merged_nii_path).write_text(
        json.dumps(merged_meta, indent=2, sort_keys=True) + "\n"
    )

    print(
        f"  wrote {merged_nii_path.name}  "
        f"({data.shape[-1]} volumes, delays={[e[0] for e in entries]})"
    )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-merge even if the merged output already exists",
    )
    args = parser.parse_args()

    for path in args.paths:
        if not path.exists():
            print(f"does not exist, skipping: {path}", file=sys.stderr)
            continue
        for merged_nii_path, fragments in sorted(find_fragment_groups(path).items()):
            print(merged_nii_path)
            try:
                merge_group(sorted(fragments), merged_nii_path, force=args.force)
            except Exception as e:
                print(f"  error, skipping: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
