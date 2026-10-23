import argparse
import csv
import shlex
import subprocess
from datetime import date
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

FREESURFER_HOME = "/usr/local/freesurfer/8.0.0"
PROJECTS_ROOT = "/mnt/cina"


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


def run_recon_all(t1w_file, fs_deriv_dir, use_t2, use_flair, autorecon3_pial=False):
    t1w_file = Path(t1w_file)
    fs_deriv_dir = Path(fs_deriv_dir)

    sub = t1w_file.parts[-4]  # sub-*
    ses = t1w_file.parts[-3]  # ses-*

    subjects_dir = fs_deriv_dir
    subject_id = f"{sub}_{ses}"

    subjects_dir.mkdir(parents=True, exist_ok=True)

    if autorecon3_pial:
        # Rerun only the pial-surface stage against an already-completed
        # subject, instead of the full pipeline.
        cmd = ["recon-all", "-s", subject_id, "-sd", str(subjects_dir), "-autorecon3"]

        if use_t2:
            t2w_file = t1w_file.with_name(t1w_file.name.replace("_T1w", "_T2w"))
            cmd += ["-T2", str(t2w_file), "-T2pial"]

        if use_flair:
            flair_file = t1w_file.with_name(t1w_file.name.replace("_T1w", "_FLAIR"))
            cmd += ["-FLAIR", str(flair_file), "-FLAIRpial"]
    else:
        # recon-all refuses -i on a subject dir that already exists (e.g. left
        # behind by a prior run that got killed partway through); in that case
        # resume the existing run instead of re-supplying the input image, per
        # recon-all's own suggested fix.
        resuming = (subjects_dir / subject_id).exists()

        cmd = ["recon-all", "-s", subject_id, "-sd", str(subjects_dir), "-all"]

        if not resuming:
            cmd += ["-i", str(t1w_file)]

            if use_t2:
                t2w_file = t1w_file.with_name(t1w_file.name.replace("_T1w", "_T2w"))
                if t2w_file.exists():
                    cmd += ["-T2", str(t2w_file), "-T2pial"]

            if use_flair:
                flair_file = t1w_file.with_name(t1w_file.name.replace("_T1w", "_FLAIR"))
                if flair_file.exists():
                    cmd += ["-FLAIR", str(flair_file), "-FLAIRpial"]

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


def recon_all_parallel(
    project,
    n_cpus=20,
    use_t2=False,
    use_flair=False,
    autorecon3_pial=False,
    subjects=None,
    sessions=None,
):
    project_dir = Path(PROJECTS_ROOT) / project / "data"
    base_dir = project_dir / "sourcedata" / "nifti"
    fs_deriv_dir = project_dir / "derivatives" / "freesurfer"
    status_csv = fs_deriv_dir / "recon_all_status.csv"

    if subjects:
        subj_patterns = [s if s.startswith("sub-") else f"sub-{s}" for s in subjects]
    else:
        subj_patterns = ["sub-*"]
    if sessions:
        ses_patterns = [s if s.startswith("ses-") else f"ses-{s}" for s in sessions]
    else:
        ses_patterns = ["ses-*"]
    # One T1w per session: run-01 when the project has multiple runs, or the
    # only T1w when filenames carry no run entity.
    t1w_files = sorted(
        f
        for subj in subj_patterns
        for ses in ses_patterns
        for f in base_dir.glob(f"{subj}/{ses}/anat/*_T1w.nii.gz")
        if "_run-" not in f.name or "_run-01_" in f.name
    )
    print(f"Found {len(t1w_files)} T1w files")

    pending = []
    for t1w_file in t1w_files:
        sub = t1w_file.parts[-4]
        ses = t1w_file.parts[-3]
        subject_id = f"{sub}_{ses}"
        completion_flag = fs_deriv_dir / subject_id / "mri" / "wmparc.mgz"

        if autorecon3_pial:
            if not completion_flag.exists():
                print(f"Not yet run, skipping: {subject_id}")
                continue
            if use_t2:
                extra_file = t1w_file.with_name(t1w_file.name.replace("_T1w", "_T2w"))
            else:
                extra_file = t1w_file.with_name(t1w_file.name.replace("_T1w", "_FLAIR"))
            if not extra_file.exists():
                print(f"No matching {extra_file.name}, skipping: {subject_id}")
                continue
            pending.append(t1w_file)
        elif completion_flag.exists():
            print(f"Already complete, skipping: {subject_id}")
        else:
            pending.append(t1w_file)

    verb = "-autorecon3 pial refinement" if autorecon3_pial else "recon-all"
    print(f"Running {verb} for {len(pending)} T1w files")
    results = []

    with ProcessPoolExecutor(max_workers=n_cpus) as executor:
        futures = [
            executor.submit(
                run_recon_all, f, fs_deriv_dir, use_t2, use_flair, autorecon3_pial
            )
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

    if results:
        existing_rows = {}
        if status_csv.exists():
            with open(status_csv, newline="") as f:
                for row in csv.DictReader(f):
                    existing_rows[row["sub_ses"]] = row

        for result in results:
            existing_rows[result["subject_id"]] = {
                "sub_ses": result["subject_id"],
                "date": result["date"],
                "version": result["version"],
                "ran_without_errors": result["returncode"] == 0,
            }

        with open(status_csv, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["sub_ses", "date", "version", "ran_without_errors"]
            )
            writer.writeheader()
            for sub_ses in sorted(existing_rows):
                writer.writerow(existing_rows[sub_ses])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run recon-all in parallel over a BIDS project's sourcedata/nifti T1w images."
    )
    parser.add_argument(
        "project", help=f"Project directory name under {PROJECTS_ROOT}, e.g. AC"
    )
    parser.add_argument(
        "--n-cpus",
        type=int,
        default=8,
        help="Number of parallel recon-all jobs (1-8; values above 8 are capped at 8, since each recon-all instance is itself multi-threaded and memory-heavy)",
    )
    pial_group = parser.add_mutually_exclusive_group()
    pial_group.add_argument(
        "--use-t2",
        action="store_true",
        help="Use the matching T2w image with the -T2pial flag, if available",
    )
    pial_group.add_argument(
        "--use-flair",
        action="store_true",
        help="Use the matching FLAIR image with the -FLAIRpial flag, if available",
    )
    parser.add_argument(
        "--autorecon3-pial",
        action="store_true",
        help=(
            "Only rerun the pial-surface stage (-autorecon3) with the T2/FLAIR "
            "pial flags, on subjects that already completed a full recon-all run. "
            "Requires --use-t2 or --use-flair."
        ),
    )
    parser.add_argument(
        "--subj",
        nargs="+",
        default=None,
        dest="subjects",
        help="Only run for these subjects, e.g. --subj 001 002 (the 'sub-' prefix is optional; default: all subjects)",
    )
    parser.add_argument(
        "--ses",
        nargs="+",
        default=None,
        dest="sessions",
        help="Only run for these sessions, e.g. --ses 101 102 (the 'ses-' prefix is optional; default: all sessions)",
    )
    args = parser.parse_args()

    if args.autorecon3_pial and not (args.use_t2 or args.use_flair):
        parser.error("--autorecon3-pial requires --use-t2 or --use-flair")

    n_cpus = max(1, min(args.n_cpus, 8))
    if n_cpus != args.n_cpus:
        print(f"--n-cpus={args.n_cpus} out of range, using {n_cpus} instead")

    recon_all_parallel(
        args.project,
        n_cpus=n_cpus,
        use_t2=args.use_t2,
        use_flair=args.use_flair,
        autorecon3_pial=args.autorecon3_pial,
        subjects=args.subjects,
        sessions=args.sessions,
    )
