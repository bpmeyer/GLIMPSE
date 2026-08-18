#!/usr/bin/env python3

import argparse
import csv
import shlex
import subprocess
from datetime import date
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

FREESURFER_HOME = "/usr/local/freesurfer/stable8"


def run_with_freesurfer_env(cmd, **kwargs):
    shell_cmd = (
        f"export FREESURFER_HOME={shlex.quote(FREESURFER_HOME)} && "
        f"source ${{FREESURFER_HOME}}/SetUpFreeSurfer.sh && "
        f"{shlex.join(cmd)}"
    )
    return subprocess.run(["bash", "-c", shell_cmd], **kwargs)


def get_recon_all_version():
    result = run_with_freesurfer_env(
        ["recon-all", "-version"], capture_output=True, text=True
    )
    return result.stdout.strip()


def run_recon_all(t1w_file, fs_deriv_dir, use_t2):
    t1w_file = Path(t1w_file)
    fs_deriv_dir = Path(fs_deriv_dir)

    sub = t1w_file.parts[-4]  # sub-*
    ses = t1w_file.parts[-3]  # ses-*

    subjects_dir = fs_deriv_dir
    subject_id = f"{sub}_{ses}"

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

    if use_t2:
        t2w_file = t1w_file.with_name(t1w_file.name.replace("_T1w", "_T2w"))
        if t2w_file.exists():
            cmd += ["-T2", str(t2w_file), "-T2pial"]

    result = run_with_freesurfer_env(cmd)

    return {
        "t1w_file": str(t1w_file),
        "subject": sub,
        "session": ses,
        "subject_id": subject_id,
        "returncode": result.returncode,
        "date": date.today().isoformat(),
        "version": get_recon_all_version(),
    }


def recon_all_parallel(project_dir, n_cpus=20, use_t2=False):
    project_dir = Path(project_dir)
    base_dir = project_dir / "sourcedata" / "nifti"
    fs_deriv_dir = project_dir / "derivatives" / "freesurfer"
    status_csv = fs_deriv_dir / "recon_all_status.csv"

    t1w_files = sorted(base_dir.glob("sub-*/ses-*/anat/*run-01_T1w.nii.gz"))
    print(f"Found {len(t1w_files)} T1w files")

    pending = []
    for t1w_file in t1w_files:
        sub = t1w_file.parts[-4]
        ses = t1w_file.parts[-3]
        subject_id = f"{sub}_{ses}"
        completion_flag = fs_deriv_dir / subject_id / "surf" / "lh.white"
        if completion_flag.exists():
            print(f"Already complete, skipping: {subject_id}")
        else:
            pending.append(t1w_file)

    print(f"Running recon-all for {len(pending)} T1w files")
    results = []

    with ProcessPoolExecutor(max_workers=n_cpus) as executor:
        futures = [
            executor.submit(run_recon_all, f, fs_deriv_dir, use_t2)
            for f in pending
        ]

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

            if result["returncode"] == 0:
                print(f"DONE {result['subject']} {result['session']}")
            else:
                print(f"FAILED {result['subject']} {result['session']}")

    fs_deriv_dir.mkdir(parents=True, exist_ok=True)
    with open(status_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sub_ses", "date", "version", "ran_without_errors"])
        for result in results:
            writer.writerow(
                [
                    result["subject_id"],
                    result["date"],
                    result["version"],
                    result["returncode"] == 0,
                ]
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run recon-all in parallel over a BIDS project's sourcedata/nifti T1w images."
    )
    parser.add_argument("project_dir", help="Path to the BIDS project directory")
    parser.add_argument("--n-cpus", type=int, default=4)
    parser.add_argument(
        "--use-t2",
        action="store_true",
        help="Use the matching T2w image with the -T2pial flag, if available",
    )
    args = parser.parse_args()

    recon_all_parallel(args.project_dir, n_cpus=args.n_cpus, use_t2=args.use_t2)
