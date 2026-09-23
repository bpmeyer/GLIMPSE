import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import nibabel as nib
from heudiconv import utils

SLICE_TIME_SCRIPT = Path("/mnt/cina/lib/prepare_philips_multiband_slice_order_file.py")
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

        with tempfile.NamedTemporaryFile(mode="r+", suffix=".txt", delete=True) as tmp:
            cmd = [
                "python",
                str(SLICE_TIME_SCRIPT),
                "--number_of_slices",
                str(n_slices),
                "--multiband_factor",
                str(mb_factor),
                "--output_file_name",
                tmp.name,
            ]

            subprocess.run(cmd, check=True)

            tmp.seek(0)
            acquisition_groups = [int(x.strip()) for x in tmp if x.strip()]

        slice_times = [(group - 1) * ta_sec for group in acquisition_groups]

        meta["SliceTiming"] = slice_times
        meta["PhaseEncodingDirection"] = "j"
        meta["B0FieldSource"] = f"acq-func-{sub}-{ses}"

        write_json(json_file, meta)

        print(f"Updated BOLD JSON: {json_file}")


def update_func_fmap_files(fmap_files, phase_encoding_direction):
    for fmap_file in fmap_files:
        json_file = fmap_file.with_suffix("").with_suffix(".json")

        if not json_file.exists():
            continue

        sub = fmap_file.parts[-4]
        ses = fmap_file.parts[-3]

        meta = load_json(json_file)

        meta["PhaseEncodingDirection"] = phase_encoding_direction
        meta["B0FieldIdentifier"] = f"acq-func-{sub}-{ses}"

        write_json(json_file, meta)

        print(f"Updated func {phase_encoding_direction} fmap JSON: {json_file}")


def update_philips_bids(project, nifti_subdir="nifti"):
    project_dir = Path(PROJECTS_ROOT) / project / "data"
    base_dir = project_dir / "sourcedata" / nifti_subdir

    bold_files = sorted(base_dir.glob("sub-*/ses-*/func/*bold.nii.gz"))
    fmap_func_ap_files = sorted(
        base_dir.glob("sub-*/ses-*/fmap/*acq-func_dir-AP*.nii.gz")
    )
    fmap_func_pa_files = sorted(
        base_dir.glob("sub-*/ses-*/fmap/*acq-func_dir-PA*.nii.gz")
    )

    update_bold_files(bold_files)
    update_func_fmap_files(fmap_func_ap_files, "j")
    update_func_fmap_files(fmap_func_pa_files, "j-")


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
    args = parser.parse_args()

    update_philips_bids(args.project, nifti_subdir=args.nifti_subdir)
