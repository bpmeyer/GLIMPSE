#!/usr/bin/env python3

import subprocess
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

BASE_DIR = Path("/mnt/cina/AC/sourcedata/nifti_uw")
FS_DERIV_DIR = Path("/mnt/cina/AC/derivatives/freesurfer")

N_CPUS = 4

t1w_files = sorted(BASE_DIR.glob("sub-915/ses-*/anat/*_T1w.nii.gz"))


def run_recon_all(t1w_file):
    t1w_file = Path(t1w_file)

    sub = t1w_file.parts[-4]  # sub-*
    ses = t1w_file.parts[-3]  # ses-*

    subjects_dir = FS_DERIV_DIR / sub
    subject_id = ses

    subjects_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "recon-all",
        "-i",
        str(t1w_file),
        "-s",
        subject_id,
        "-sd",
        str(subjects_dir),
        "-all",
    ]

    log_file = subjects_dir / f"{subject_id}_recon-all.log"

    with open(log_file, "w") as log:
        result = subprocess.run(
            cmd,
            stdout=log,
            text=True,
        )

    return {
        "t1w_file": str(t1w_file),
        "subject": sub,
        "session": ses,
        "returncode": result.returncode,
        "log": str(log_file),
    }


if __name__ == "__main__":
    print(f"Found {len(t1w_files)} T1w files")

    with ProcessPoolExecutor(max_workers=N_CPUS) as executor:
        futures = [executor.submit(run_recon_all, f) for f in t1w_files]

        for future in as_completed(futures):
            result = future.result()

            if result["returncode"] == 0:
                print(f"DONE {result['subject']} {result['session']}")
            else:
                print(f"FAILED {result['subject']} {result['session']}")
                print(f"  log: {result['log']}")