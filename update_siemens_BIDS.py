#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

from heudiconv import utils


def load_json(json_file):
    with open(json_file, "r") as f:
        return json.load(f)


def write_json(json_file, meta):
    utils.set_readonly(json_file, read_only=False)

    with open(json_file, "w") as f:
        json.dump(meta, f, indent=4)

    utils.set_readonly(json_file, read_only=True)


def update_bold_files(bold_files):
    for bold_file in bold_files:
        json_file = bold_file.with_suffix("").with_suffix(".json")

        if not json_file.exists():
            continue

        sub = bold_file.parts[-4]
        ses = bold_file.parts[-3]

        meta = load_json(json_file)

        # Siemens DICOMs already carry correct SliceTiming and
        # PhaseEncodingDirection -- only the fmap<->func B0Field linkage
        # needs to be added.
        meta["B0FieldSource"] = f"acq-func-{sub}-{ses}"
        meta["B0FieldIdentifier"] = f"acq-func-{sub}-{ses}"

        write_json(json_file, meta)

        print(f"Updated BOLD JSON: {json_file}")


def update_func_fmap_files(fmap_files):
    for fmap_file in fmap_files:
        json_file = fmap_file.with_suffix("").with_suffix(".json")

        if not json_file.exists():
            continue

        sub = fmap_file.parts[-4]
        ses = fmap_file.parts[-3]

        meta = load_json(json_file)

        meta["B0FieldIdentifier"] = f"acq-func-{sub}-{ses}"

        write_json(json_file, meta)

        print(f"Updated func fmap JSON: {json_file}")


def update_siemens_bids(project_dir, nifti_subdir="nifti"):
    project_dir = Path(project_dir)
    base_dir = project_dir / "sourcedata" / nifti_subdir

    bold_files = sorted(base_dir.glob("sub-*/ses-*/func/*bold.nii.gz"))
    # PhaseEncodingDirection is already correct from the Siemens header, so
    # AP/PA func fieldmaps don't need to be handled separately here.
    fmap_func_files = sorted(base_dir.glob("sub-*/ses-*/fmap/*acq-func_dir-*.nii.gz"))

    update_bold_files(bold_files)
    update_func_fmap_files(fmap_func_files)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Update Siemens BIDS JSON sidecars (B0FieldSource/B0FieldIdentifier "
        "metadata linking func bold files to their fieldmap) for a BIDS project's "
        "sourcedata/nifti directory. Unlike Philips data, SliceTiming and "
        "PhaseEncodingDirection are already correct from the Siemens DICOM headers "
        "and are left untouched."
    )
    parser.add_argument("project_dir", help="Path to the BIDS project directory")
    parser.add_argument(
        "--nifti-subdir",
        default="nifti",
        help="Name of the sourcedata subdirectory holding the BIDS nifti tree (default: nifti)",
    )
    args = parser.parse_args()

    update_siemens_bids(args.project_dir, nifti_subdir=args.nifti_subdir)
