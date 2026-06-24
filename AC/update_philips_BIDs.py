#!/usr/bin/env python3

import json
import subprocess
import tempfile
from pathlib import Path

import nibabel as nib
from heudiconv import utils

BASE_DIR = Path("/mnt/cina/AC/sourcedata/nifti_uw")
PREPARE_SCRIPT = Path("/mnt/cina/lib/prepare_philips_multiband_slice_order_file.py")

bold_files = sorted(BASE_DIR.glob("sub-*/ses-*/func/*bold.nii.gz"))
fmap_func_ap_files = sorted(BASE_DIR.glob("sub-*/ses-*/fmap/*acq-func_dir-AP*.nii.gz"))
fmap_func_pa_files = sorted(BASE_DIR.glob("sub-*/ses-*/fmap/*acq-func_dir-PA*.nii.gz"))
fmap_dwi_pa_files = sorted(BASE_DIR.glob("sub-*/ses-*/fmap/*acq-dwi_dir-PA*.nii.gz"))


def load_json(json_file):
    with open(json_file, "r") as f:
        return json.load(f)


def write_json(json_file, meta):
    utils.set_readonly(json_file, read_only=False)

    with open(json_file, "w") as f:
        json.dump(meta, f, indent=4)

    utils.set_readonly(json_file, read_only=True)


for bold_file in bold_files:
    json_file = bold_file.with_suffix("").with_suffix(".json")

    if not json_file.exists():
        continue

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
            str(PREPARE_SCRIPT),
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
    meta["B0FieldSource"] = "acq-func"

    write_json(json_file, meta)

    print(f"Updated BOLD JSON: {json_file}")


for fmap_file in fmap_func_ap_files:
    json_file = fmap_file.with_suffix("").with_suffix(".json")

    if not json_file.exists():
        continue

    sub = fmap_file.parts[-4]
    ses = fmap_file.parts[-3]

    meta = load_json(json_file)

    meta["PhaseEncodingDirection"] = "j"
    meta["B0FieldIdentifier"] = "acq-func"

    meta.pop("SliceTiming", None)
    meta.pop("B0FieldSource", None)

    write_json(json_file, meta)

    print(f"Updated func AP fmap JSON: {json_file}")


for fmap_file in fmap_func_pa_files:
    json_file = fmap_file.with_suffix("").with_suffix(".json")

    if not json_file.exists():
        continue

    sub = fmap_file.parts[-4]
    ses = fmap_file.parts[-3]

    meta = load_json(json_file)

    meta["PhaseEncodingDirection"] = "j-"
    meta["B0FieldIdentifier"] = "acq-func"

    meta.pop("SliceTiming", None)
    meta.pop("B0FieldSource", None)

    write_json(json_file, meta)

    print(f"Updated func PA fmap JSON: {json_file}")