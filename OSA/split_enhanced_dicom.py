"""Split a Philips Enhanced MR multi-frame DICOM into one file per
per-frame image type (read from the Philips private tag (2005,140f) ->
(0008,0008)), so downstream heudiconv/dcm2niix conversion produces one
clean 4D NIfTI per type instead of one over-split, mixed-type series.

For an enhanced file with N distinct per-frame image types found, the
original combined file is moved into an "orig/" subfolder next to it,
and N new multi-frame DICOM files (frames in original order, so temporal/
trigger ordering is preserved) are written in its place, each carrying a
homogeneous top-level ImageType. Existing OSA_heuristic.py grouping
already splits files by (series_number, protocol_name, ImageType), so no
heuristic changes are needed once the files are split this way.

Usage:
    python split_enhanced_dicom.py <path> [<path> ...]

<path> may be a single .dcm file or a directory (searched recursively
for *.dcm files).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import pydicom
from pydicom.uid import generate_uid

PHILIPS_PRIVATE_STACK_TAG = (0x2005, 0x140F)
PHILIPS_PRIVATE_IMAGE_TYPE_TAG = (0x0008, 0x0008)


def get_frame_image_type(frame) -> tuple[str, ...] | None:
    priv = frame.get(PHILIPS_PRIVATE_STACK_TAG)
    if not priv:
        return None
    return tuple(priv[0][PHILIPS_PRIVATE_IMAGE_TYPE_TAG].value)


def split_enhanced_dicom(dcm_path: Path, force: bool = False) -> list[Path]:
    orig_dir = dcm_path.parent
    backup_dir = orig_dir / "orig"
    backup_path = backup_dir / dcm_path.name

    if backup_path.exists() and not force:
        print(f"  already split (found {backup_path}), skipping: {dcm_path.name}")
        return []

    source_path = backup_path if backup_path.exists() else dcm_path
    ds = pydicom.dcmread(source_path)

    pf = ds.get("PerFrameFunctionalGroupsSequence")
    if not pf:
        print(f"  not a multi-frame file, skipping: {dcm_path.name}")
        return []

    frame_types = [get_frame_image_type(frame) for frame in pf]
    distinct = sorted({t for t in frame_types if t is not None})

    if len(distinct) <= 1:
        print(f"  only one image type present, nothing to split: {dcm_path.name}")
        return []

    arr = ds.pixel_array  # shape: (n_frames, rows, cols), raw stored values

    backup_dir.mkdir(exist_ok=True)
    if not backup_path.exists():
        shutil.move(str(dcm_path), str(backup_path))

    out_paths = []
    for type_tuple in distinct:
        indices = [i for i, t in enumerate(frame_types) if t == type_tuple]

        new_ds = ds.copy()
        new_ds.PerFrameFunctionalGroupsSequence = pydicom.Sequence(
            [pf[i] for i in indices]
        )
        new_ds.NumberOfFrames = len(indices)
        new_ds.PixelData = arr[indices].tobytes()
        new_ds.ImageType = list(type_tuple)

        new_sop_uid = generate_uid()
        new_ds.SOPInstanceUID = new_sop_uid
        new_ds.file_meta.MediaStorageSOPInstanceUID = new_sop_uid

        suffix = "_".join(type_tuple).replace(" ", "")
        out_path = orig_dir / f"{dcm_path.stem}_{suffix}.dcm"
        new_ds.save_as(out_path)
        out_paths.append(out_path)
        print(f"  wrote {out_path.name}  ({len(indices)} frames, type={type_tuple})")

    return out_paths


def find_dcm_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*.dcm") if "orig" not in p.parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-split even if an orig/ backup already exists",
    )
    args = parser.parse_args()

    for path in args.paths:
        if not path.exists():
            print(f"does not exist, skipping: {path}", file=sys.stderr)
            continue
        for dcm_path in find_dcm_files(path):
            print(f"{dcm_path}")
            try:
                split_enhanced_dicom(dcm_path, force=args.force)
            except Exception as e:
                print(f"  error, skipping: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
