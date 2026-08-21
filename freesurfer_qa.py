#functions to QA freesurfer outputs and preform troubleshooting tasks.

import argparse
import csv
import getpass
import shlex
import subprocess
from datetime import date
from pathlib import Path


FREESURFER_HOME = "/usr/local/freesurfer/stable8"
PROJECTS_ROOT = "/mnt/cina"


def run_with_freesurfer_env(cmd, **kwargs):
    shell_cmd = (
        f"export FREESURFER_HOME={shlex.quote(FREESURFER_HOME)} && "
        f"source ${{FREESURFER_HOME}}/SetUpFreeSurfer.sh && "
        f"{shlex.join(cmd)}"
    )
    return subprocess.run(["bash", "-c", shell_cmd], **kwargs)


def open_freeview(project, subject_id):
    project_dir = Path(PROJECTS_ROOT) / project
    fs_deriv_dir = project_dir / "data"/ "derivatives" / "freesurfer"
    subject_dir = fs_deriv_dir / subject_id

    cmd = [
        "freeview",
        "-v",
        str(subject_dir / "mri" / "T1.mgz"),
        str(subject_dir / "mri" / "brainmask.mgz"),
        str(subject_dir / "mri" / "aparc+aseg.mgz"),
        "-f",
        f"{subject_dir / 'surf' / 'lh.white'}:edgecolor=yellow",
        f"{subject_dir / 'surf' / 'lh.pial'}:edgecolor=red",
        f"{subject_dir / 'surf' / 'rh.white'}:edgecolor=yellow",
        f"{subject_dir / 'surf' / 'rh.pial'}:edgecolor=red",
    ]

    return run_with_freesurfer_env(cmd)


def prompt_qa_result():
    while True:
        result = input("QA result (pass/fail): ").strip().lower()
        if result in ("pass", "fail"):
            break
        print("Please enter 'pass' or 'fail'.")

    comment = ""
    if result == "fail":
        while not comment:
            comment = input("Comment is required for a failed QA: ").strip()

    return result, comment


def log_qa_result(fs_deriv_dir, subject_id, result, comment):
    fs_deriv_dir.mkdir(parents=True, exist_ok=True)
    qa_log_csv = fs_deriv_dir / "qa_log.csv"
    write_header = not qa_log_csv.exists()

    with open(qa_log_csv, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["subject_id", "date", "reviewer", "result", "comment"])
        writer.writerow(
            [subject_id, date.today().isoformat(), getpass.getuser(), result, comment]
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Open a subject's FreeSurfer derivatives in freeview for QA."
    )
    parser.add_argument(
        "project", help=f"Project directory name under {PROJECTS_ROOT}, e.g. AC"
    )
    parser.add_argument(
        "--subject",
        required=True,
        help="Subject/session id to QA, e.g. sub-01_ses-01",
    )
    args = parser.parse_args()

    open_freeview(args.project, args.subject)

    result, comment = prompt_qa_result()

    fs_deriv_dir = Path(PROJECTS_ROOT) / args.project / "data" / "derivatives" / "freesurfer"
    log_qa_result(fs_deriv_dir, args.subject, result, comment)
