import argparse
import json
from pathlib import Path

import nibabel as nib
from heudiconv import utils

from prepare_philips_multiband_slice_order_file import (
    prepare_philips_multiband_slice_order_file,
)

PROJECTS_ROOT = "/mnt/cina"


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

        if meta.get("ParallelAcquisitionTechnique") != "MBSENSE":
            continue

        mb_factor = int(meta["ParallelReductionFactorOutOfPlane"])
        tr_sec = float(meta["RepetitionTime"])

        img = nib.load(str(bold_file))
        n_slices = img.shape[2]

        n_slices_per_mb = n_slices // mb_factor
        ta_sec = tr_sec / n_slices_per_mb

        acquisition_groups = prepare_philips_multiband_slice_order_file(
            n_slices, mb_factor
        )

        slice_times = [(group - 1) * ta_sec for group in acquisition_groups]

        meta["SliceTiming"] = slice_times
        meta["PhaseEncodingDirection"] = "j"
        meta["B0FieldSource"] = f"acq-func-{sub}-{ses}"

        write_json(json_file, meta)

        print(f"Updated BOLD JSON: {json_file}")


def update_dwi_files(dwi_files):
    for dwi_file in dwi_files:
        json_file = dwi_file.with_suffix("").with_suffix(".json")

        if not json_file.exists():
            continue

        sub = dwi_file.parts[-4]
        ses = dwi_file.parts[-3]

        meta = load_json(json_file)

        meta["PhaseEncodingDirection"] = "j"
        meta["B0FieldSource"] = f"acq-dwi-{sub}-{ses}"
        meta["B0FieldIdentifier"] = f"acq-dwi-{sub}-{ses}"

        if "EstimatedTotalReadoutTime" in meta:
            meta["TotalReadoutTime"] = meta["EstimatedTotalReadoutTime"]

        write_json(json_file, meta)

        print(f"Updated DWI JSON: {json_file}")


def update_fmap_files(fmap_files, phase_encoding_direction, acq):
    for fmap_file in fmap_files:
        json_file = fmap_file.with_suffix("").with_suffix(".json")

        if not json_file.exists():
            continue

        sub = fmap_file.parts[-4]
        ses = fmap_file.parts[-3]

        meta = load_json(json_file)

        meta["PhaseEncodingDirection"] = phase_encoding_direction
        meta["B0FieldIdentifier"] = f"acq-{acq}-{sub}-{ses}"

        if acq == "dwi" and "EstimatedTotalReadoutTime" in meta:
            meta["TotalReadoutTime"] = meta["EstimatedTotalReadoutTime"]

        write_json(json_file, meta)

        print(f"Updated {acq} {phase_encoding_direction} fmap JSON: {json_file}")


def update_philips_bids(project, nifti_subdir="nifti", subjects=None, sessions=None):
    project_dir = Path(PROJECTS_ROOT) / project / "data"
    base_dir = project_dir / "sourcedata" / nifti_subdir

    if subjects:
        sub_dirs = [f"sub-{s.removeprefix('sub-')}" for s in subjects]
    else:
        sub_dirs = ["sub-*"]

    if sessions:
        ses_dirs = [f"ses-{s.removeprefix('ses-')}" for s in sessions]
    else:
        ses_dirs = ["ses-*"]

    def find(pattern):
        return sorted(
            f
            for sub in sub_dirs
            for ses in ses_dirs
            for f in base_dir.glob(f"{sub}/{ses}/{pattern}")
        )

    bold_files = find("func/*bold.nii.gz")
    fmap_func_ap_files = find("fmap/*acq-func_dir-AP*.nii.gz")
    fmap_func_pa_files = find("fmap/*acq-func_dir-PA*.nii.gz")
    dwi_files = find("dwi/*dwi.nii.gz")
    fmap_dwi_pa_files = find("fmap/*acq-dwi_dir-PA*.nii.gz")

    update_bold_files(bold_files)
    update_fmap_files(fmap_func_ap_files, "j", "func")
    update_fmap_files(fmap_func_pa_files, "j-", "func")
    update_dwi_files(dwi_files)
    update_fmap_files(fmap_dwi_pa_files, "j-", "dwi")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Update Philips BIDS JSON sidecars (slice timing, phase encoding direction, "
        "B0 field metadata) for a BIDS project's sourcedata/nifti directory."
    )
    parser.add_argument(
        "project", help=f"Project directory name under {PROJECTS_ROOT}, e.g. AC"
    )
    parser.add_argument(
        "--nifti-subdir",
        default="nifti",
        help="Name of the sourcedata subdirectory holding the BIDS nifti tree (default: nifti)",
    )
    parser.add_argument(
        "--subjects",
        nargs="+",
        help="Subject labels to process, with or without the sub- prefix (default: all)",
    )
    parser.add_argument(
        "--sessions",
        nargs="+",
        help="Session labels to process, with or without the ses- prefix (default: all)",
    )
    args = parser.parse_args()

    update_philips_bids(
        args.project,
        nifti_subdir=args.nifti_subdir,
        subjects=args.subjects,
        sessions=args.sessions,
    )
