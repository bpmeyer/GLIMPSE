"""Run DRIPS PVS segmentation (https://github.com/joseabernal/DRIPS) on T1w
images over every session in a BIDS project.

For each subject/session with FreeSurfer synthseg output, this:
  1. Resamples synthseg into T1 space with `mri_label2vol` (same as
     segment_pvs.py).
  2. Copies the T1w image into the output dir with `fslmaths` (DRIPS needs
     its inputs bind-mounted from a single directory).
  3. Runs the `drips_latest` apptainer image with --hyperintense 0 (PVS are
     dark on T1w), writing the posterior probability map and a binary mask
     at the lowest requested threshold.
  4. Binarizes the posterior at each remaining threshold. DRIPS's binary mask
     is just `posterior > threshold` on the saved (already masked) posterior,
     so this matches re-running the model at that threshold.

Expects the project to already have:
  - T1w images at `{project}/data/sourcedata/nifti/sub-*/ses-*/anat/*run-01_T1w.nii.gz`
  - FreeSurfer output at `{project}/data/derivatives/freesurfer/sub-*_ses-*/mri/`
    (as produced by recon_all_parallel.py), including `synthseg.rca.mgz` and
    `rawavg.mgz`.

Writes output to `{project}/data/derivatives/drips/sub-*/ses-*/`, with every
file prefixed `sub-{subject}_ses-{session}_`:
  - `..._T1.nii.gz`, `..._synthseg.nii.gz`: DRIPS inputs
  - `..._drips_posterior.nii.gz`: posterior probability map
  - `..._drips_seg_thr_{thr}.nii.gz`: binary PVS mask, one per threshold

Sessions without FreeSurfer synthseg output are skipped. Sessions that
already have a posterior only get any missing threshold masks written.

Usage:
    python segment_pvs_drips.py PROJECT [--subj 001 002] [--ses 101 102] [--threads N]
    python segment_pvs_drips.py PROJECT --thresholds 0.05 0.1 0.2
    python segment_pvs_drips.py PROJECT --nifti-dir nifti_uw
    pixi run segment-pvs-drips PROJECT
"""

import argparse
import subprocess
from pathlib import Path

import nibabel as nib
import numpy as np

from segment_pvs import PROJECTS_ROOT, run_with_freesurfer_env

DRIPS_SIF = "/mnt/cina/lib/drips_latest.sif"
DEFAULT_THRESHOLDS = [0.05, 0.1]


def threshold_posterior(posterior_fn, seg_fn, threshold):
    '''Binarize a DRIPS posterior map the same way DRIPS does (posterior > threshold).

    Parameters:
    -----------
        posterior_fn (Path | str): Path to the DRIPS posterior probability map.
        seg_fn (Path | str): Output path for the binary mask.
        threshold (float): Posterior probability threshold.
    '''
    posterior = nib.load(str(posterior_fn))
    seg = (posterior.get_fdata(dtype=np.float32) > np.float32(threshold)).astype(np.uint8)
    seg_img = nib.Nifti1Image(seg, posterior.affine, posterior.header)
    seg_img.set_data_dtype(np.uint8)
    nib.save(seg_img, str(seg_fn))


def segment_pvs_drips_session(
    subject,
    session,
    t1w_file,
    fs_deriv_dir,
    out_dir,
    sif,
    thresholds=DEFAULT_THRESHOLDS,
    n_threads=32,
):
    '''Run DRIPS PVS segmentation on a T1w image for a single subject/session.

    Parameters:
    -----------
        subject (str): Subject ID, without the "sub-" prefix.
        session (str): Session ID, without the "ses-" prefix.
        t1w_file (Path | str): Path to the subject/session's T1w nifti.
        fs_deriv_dir (Path | str): Path to the subject/session's FreeSurfer
            derivatives dir (contains mri/synthseg.rca.mgz and mri/rawavg.mgz).
        out_dir (Path | str): Directory to write DRIPS inputs/outputs to.
            Bind-mounted as /data in the container.
        sif (Path | str): Path to the DRIPS apptainer image.
        thresholds (list[float]): Posterior thresholds to write binary masks
            at. DRIPS itself runs at the lowest; the rest are made from the
            posterior. Default [0.05, 0.1].
        n_threads (int | None): Passed to DRIPS as --threads. Pass None to
            use DRIPS's default.

    Returns:
    --------
        dict: {"subject", "session", "t1w_file", "returncode"} summarizing the run.
    '''
    t1w_file = Path(t1w_file)
    fs_deriv_dir = Path(fs_deriv_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    thresholds = sorted(thresholds)

    prefix = f"sub-{subject}_ses-{session}"
    synthseg_fn = out_dir / f"{prefix}_synthseg.nii.gz"
    t1_fn = out_dir / f"{prefix}_T1.nii.gz"
    posterior_fn = out_dir / f"{prefix}_drips_posterior.nii.gz"

    def seg_fn(thr):
        return out_dir / f"{prefix}_drips_seg_thr_{thr}.nii.gz"

    returncode = 0
    if not posterior_fn.exists():
        run_with_freesurfer_env(
            [
                "mri_label2vol",
                "--seg",
                str(fs_deriv_dir / "mri" / "synthseg.rca.mgz"),
                "--temp",
                str(fs_deriv_dir / "mri" / "rawavg.mgz"),
                "--o",
                str(synthseg_fn),
                "--regheader",
                str(fs_deriv_dir / "mri" / "synthseg.rca.mgz"),
            ]
        )

        subprocess.run(["fslmaths", str(t1w_file), "-mul", "1", str(t1_fn)])

        cmd = [
            "apptainer",
            "run",
            "--bind",
            f"{out_dir}:/data",
            str(sif),
            "--in",
            f"/data/{t1_fn.name}",
            "--out",
            f"/data/{seg_fn(thresholds[0]).name}",
            "--posterior",
            f"/data/{posterior_fn.name}",
            "--hyperintense",
            "0",
            "--threshold",
            str(thresholds[0]),
            "--synthseg",
            f"/data/{synthseg_fn.name}",
        ]
        if n_threads is not None:
            cmd += ["--threads", str(n_threads)]

        returncode = subprocess.run(cmd).returncode

    if returncode == 0 and posterior_fn.exists():
        for thr in thresholds:
            if not seg_fn(thr).exists():
                threshold_posterior(posterior_fn, seg_fn(thr), thr)

    return {
        "subject": subject,
        "session": session,
        "t1w_file": str(t1w_file),
        "returncode": returncode,
    }


def segment_pvs_drips_project(
    project,
    sif=DRIPS_SIF,
    subjects=None,
    sessions=None,
    thresholds=DEFAULT_THRESHOLDS,
    n_threads=32,
    nifti_dir="nifti",
):
    '''Run DRIPS PVS segmentation for every session in a project.

    Wrapper that finds T1w files under a project's sourcedata/nifti, matches
    each to its FreeSurfer derivatives, skips sessions that aren't ready or
    are already done, and calls segment_pvs_drips_session for the rest.

    Parameters:
    -----------
        project (str): Project directory name under PROJECTS_ROOT, e.g. "GLIMPSE_OSA".
        sif (Path | str): Path to the DRIPS apptainer image. Default DRIPS_SIF.
        subjects (list[str] | None): Only process these subjects, e.g.
            ["sub-001", "sub-002"] or ["001", "002"] (the "sub-" prefix is
            optional). Default None (all subjects).
        sessions (list[str] | None): Only process these sessions, e.g.
            ["ses-01", "ses-02"] or ["01", "02"] (the "ses-" prefix is
            optional). Default None (all sessions).
        thresholds (list[float]): See segment_pvs_drips_session. Default [0.05, 0.1].
        n_threads (int | None): See segment_pvs_drips_session. Default 32.
        nifti_dir (str): Name of the sourcedata subdirectory to find T1w
            files under, e.g. "nifti" or "nifti_uw" for sites with a
            separate sourcedata tree. Default "nifti".
    '''
    project_dir = Path(PROJECTS_ROOT) / project / "data"
    nifti_dir = project_dir / "sourcedata" / nifti_dir
    fs_deriv_root = project_dir / "derivatives" / "freesurfer"
    drips_root = project_dir / "derivatives" / "drips"

    if subjects:
        subj_patterns = [s if s.startswith("sub-") else f"sub-{s}" for s in subjects]
    else:
        subj_patterns = ["sub-*"]
    if sessions:
        ses_patterns = [s if s.startswith("ses-") else f"ses-{s}" for s in sessions]
    else:
        ses_patterns = ["ses-*"]
    t1w_files = sorted(
        f
        for subj in subj_patterns
        for ses in ses_patterns
        for f in nifti_dir.glob(f"{subj}/{ses}/anat/*run-01_T1w.nii.gz")
    )
    print(f"Found {len(t1w_files)} T1w files")

    for t1w_file in t1w_files:
        sub = t1w_file.parts[-4].split("-", 1)[1]
        ses = t1w_file.parts[-3].split("-", 1)[1]

        fs_deriv_dir = fs_deriv_root / f"sub-{sub}_ses-{ses}"
        out_dir = drips_root / f"sub-{sub}" / f"ses-{ses}"
        prefix = f"sub-{sub}_ses-{ses}"

        if not (fs_deriv_dir / "mri" / "synthseg.rca.mgz").exists() or not (
            fs_deriv_dir / "mri" / "rawavg.mgz"
        ).exists():
            print(f"SKIP {prefix}: missing FreeSurfer synthseg/rawavg outputs")
            continue

        if all(
            (out_dir / f"{prefix}_drips_seg_thr_{thr}.nii.gz").exists() for thr in thresholds
        ):
            print(f"SKIP {prefix}: already segmented")
            continue

        print(f"Running DRIPS PVS segmentation for {prefix}")
        result = segment_pvs_drips_session(
            sub,
            ses,
            t1w_file,
            fs_deriv_dir,
            out_dir,
            sif,
            thresholds=thresholds,
            n_threads=n_threads,
        )

        if result["returncode"] == 0:
            print(f"DONE {prefix}")
        else:
            print(f"FAILED {prefix}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run DRIPS PVS segmentation on T1w images over a BIDS project's sessions."
    )
    parser.add_argument(
        "project", help=f"Project directory name under {PROJECTS_ROOT}, e.g. GLIMPSE_OSA"
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
    parser.add_argument(
        "--sif",
        default=DRIPS_SIF,
        help=f"Path to the DRIPS apptainer image (default: {DRIPS_SIF})",
    )
    parser.add_argument(
        "--thresholds",
        nargs="+",
        type=float,
        default=DEFAULT_THRESHOLDS,
        help=(
            "Posterior probability thresholds to write binary masks at "
            f"(default: {' '.join(str(t) for t in DEFAULT_THRESHOLDS)})"
        ),
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=32,
        dest="n_threads",
        help="Number of CPU threads passed to DRIPS --threads (default: 32)",
    )
    parser.add_argument(
        "--nifti-dir",
        default="nifti",
        help=(
            "Name of the sourcedata subdirectory to find T1w files under, "
            "e.g. 'nifti' or 'nifti_uw' for sites with a separate "
            "sourcedata tree (default: nifti)"
        ),
    )
    args = parser.parse_args()

    segment_pvs_drips_project(
        args.project,
        sif=args.sif,
        subjects=args.subjects,
        sessions=args.sessions,
        thresholds=args.thresholds,
        n_threads=args.n_threads,
        nifti_dir=args.nifti_dir,
    )
