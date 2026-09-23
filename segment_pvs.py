"""Run segcsvd PVS segmentation (https://github.com/AICONSlab/segcsvd) over
every session in a BIDS project.

For each subject/session with FreeSurfer synthseg output, this:
  1. Resamples synthseg into T1 space with `mri_label2vol`.
  2. Copies the T1w image into the output dir with `fslmaths` (segcsvd needs
     its inputs bind-mounted from a single directory).
  3. Runs the `segcsvd_pvs` apptainer image's `segment_pvs` entrypoint, which
     brain-masks/bias-corrects the T1, then runs the PVS segmentation model.

Expects the project to already have:
  - T1w images at `{project}/data/sourcedata/nifti/sub-*/ses-*/anat/*run-01_T1w.nii.gz`
  - FreeSurfer output at `{project}/data/derivatives/freesurfer/sub-*_ses-*/mri/`
    (as produced by recon_all_parallel.py), including `synthseg.rca.mgz` and
    `rawavg.mgz`.

Writes segmentation output to
`{project}/data/derivatives/segcsvd/sub-*/ses-*/`, with every file prefixed
`sub-{subject}_ses-{session}_`. Sessions without FreeSurfer synthseg output,
or that already have a `..._seg_pvs.nii.gz`, are skipped.

With --thr-only, skips the full pipeline and instead re-binarizes each
session's existing `..._seg_pvs.nii.gz` at a new --seg-pvs-thr, writing
`..._seg_pvs_thr_{seg_pvs_thr}.nii.gz` without re-running segmentation.

Usage:
    python segment_pvs.py PROJECT [--subj sub-01 sub-02] [--ses ses-01 ses-02] [--n-threads N]
    python segment_pvs.py PROJECT --thr-only --seg-pvs-thr 0.25
    python segment_pvs.py PROJECT --nifti-dir nifti_uw
    pixi run segment-pvs PROJECT
"""

import argparse
import os
import shlex
import subprocess
from pathlib import Path

FREESURFER_HOME = "/usr/local/freesurfer/8.0.0"
PROJECTS_ROOT = "/mnt/cina"
SEGCSVD_SIF = "/mnt/cina/lib/segcsvd_rc03.sif"


def run_with_freesurfer_env(cmd, **kwargs):
    '''Run a command with FREESURFER_HOME set and SetUpFreeSurfer.sh sourced.

    Parameters:
    -----------
        cmd (list[str]): Command and arguments to run, e.g. ["mri_label2vol", ...].
        **kwargs: Passed through to subprocess.run.

    Returns:
    --------
        subprocess.CompletedProcess
    '''
    shell_cmd = (
        f"export FREESURFER_HOME={shlex.quote(FREESURFER_HOME)} && "
        f"source ${{FREESURFER_HOME}}/SetUpFreeSurfer.sh && "
        f"{shlex.join(cmd)}"
    )
    return subprocess.run(["bash", "-c", shell_cmd], **kwargs)


def segment_pvs_session(
    subject,
    session,
    t1w_file,
    fs_deriv_dir,
    out_dir,
    sif,
    skip_mask_and_bias=False,
    cleanup=True,
    seg_pvs_thr=0.35,
    n_threads=32,
):
    '''Run segcsvd PVS segmentation for a single subject/session.

    Parameters:
    -----------
        subject (str): Subject ID, without the "sub-" prefix.
        session (str): Session ID, without the "ses-" prefix.
        t1w_file (Path | str): Path to the subject/session's T1w nifti.
        fs_deriv_dir (Path | str): Path to the subject/session's FreeSurfer
            derivatives dir (contains mri/synthseg.rca.mgz and mri/rawavg.mgz).
        out_dir (Path | str): Directory to write segcsvd inputs/outputs to.
            Used as both the /indir and /outdir apptainer bind mount.
        sif (Path | str): Path to the segcsvd apptainer image.
        skip_mask_and_bias (bool): Skip segcsvd's brain masking/bias correction
            (pass true if the T1 is already masked/bias-corrected). Default False.
        cleanup (bool): Remove segcsvd's temporary working directory when done. Default True.
        seg_pvs_thr (float): Probability threshold used by segcsvd to binarize
            its output (also written as `thr_{out filename}`). Default 0.35.
        n_threads (int | None): If set, caps CPU threads used inside the
            container by setting OMP_NUM_THREADS and
            ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS for the apptainer call.
            Pass None to leave both unset (uses all available cores).

    Returns:
    --------
        dict: {"subject", "session", "t1w_file", "returncode"} summarizing the run.
    '''
    t1w_file = Path(t1w_file)
    fs_deriv_dir = Path(fs_deriv_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    prefix = f"sub-{subject}_ses-{session}"
    synthseg_fn = out_dir / f"{prefix}_synthseg.nii.gz"
    empty_mask_fn = out_dir / f"{prefix}_empty_mask_T1space.nii.gz"
    t1_fn = out_dir / f"{prefix}_T1.nii.gz"
    seg_pvs_fn = out_dir / f"{prefix}_seg_pvs.nii.gz"

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

    subprocess.run(["fslmaths", str(t1w_file), "-mul", "0", str(empty_mask_fn)])
    subprocess.run(["fslmaths", str(t1w_file), "-mul", "1", str(t1_fn)])

    env = os.environ.copy()
    if n_threads is not None:
        env["OMP_NUM_THREADS"] = str(n_threads)
        env["ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS"] = str(n_threads)

    result = subprocess.run(
        [
            "apptainer",
            "run",
            "--bind",
            f"{out_dir}:/indir,{out_dir}:/outdir",
            "--pwd",
            "/",
            str(sif),
            "segment_pvs",
            f"/indir/{t1_fn.name}",
            f"/indir/{synthseg_fn.name}",
            f"/indir/{empty_mask_fn.name}",
            f"/outdir/{seg_pvs_fn.name}",
            "1.0,1.4",
            "0",
            str(skip_mask_and_bias).lower(),
            str(cleanup).lower(),
            str(seg_pvs_thr),
        ],
        env=env,
    )

    # segcsvd writes its binarized output as thr_{out filename} (it prepends
    # "thr_" ahead of the whole basename, not before "seg_pvs"); rename it to
    # our own convention.
    container_thr_fn = out_dir / f"thr_{seg_pvs_fn.name}"
    if container_thr_fn.exists():
        thr_fn = out_dir / f"{prefix}_seg_pvs_thr_{seg_pvs_thr}.nii.gz"
        container_thr_fn.rename(thr_fn)

    return {
        "subject": subject,
        "session": session,
        "t1w_file": str(t1w_file),
        "returncode": result.returncode,
    }


def rethreshold_pvs(subject, session, out_dir, sif, seg_pvs_thr):
    '''Re-binarize an existing segcsvd PVS output at a new threshold, without
    re-running the full segmentation pipeline.

    Uses the same sbtUnaryImageMath tool segcsvd's own segment_pvs entrypoint
    uses internally to binarize its output.

    Parameters:
    -----------
        subject (str): Subject ID, without the "sub-" prefix.
        session (str): Session ID, without the "ses-" prefix.
        out_dir (Path | str): Directory containing the existing
            {prefix}_seg_pvs.nii.gz to re-threshold.
        sif (Path | str): Path to the segcsvd apptainer image.
        seg_pvs_thr (float): Probability threshold to binarize at. Written
            as {prefix}_seg_pvs_thr_{seg_pvs_thr}.nii.gz.

    Returns:
    --------
        dict: {"subject", "session", "returncode"} summarizing the run.
    '''
    out_dir = Path(out_dir)
    prefix = f"sub-{subject}_ses-{session}"
    seg_pvs_fn = out_dir / f"{prefix}_seg_pvs.nii.gz"
    thr_fn = out_dir / f"{prefix}_seg_pvs_thr_{seg_pvs_thr}.nii.gz"

    result = subprocess.run(
        [
            "apptainer",
            "exec",
            "--bind",
            f"{out_dir}:/outdir",
            "--pwd",
            "/",
            str(sif),
            "sbtUnaryImageMath",
            f"/outdir/{seg_pvs_fn.name}",
            str(seg_pvs_thr),
            f"/outdir/{thr_fn.name}",
            "thr-bin",
        ]
    )

    return {
        "subject": subject,
        "session": session,
        "returncode": result.returncode,
    }


def segment_pvs_project(
    project,
    sif=SEGCSVD_SIF,
    subjects=None,
    sessions=None,
    skip_mask_and_bias=False,
    cleanup=True,
    seg_pvs_thr=0.35,
    n_threads=40,
    thr_only=False,
    nifti_dir="nifti",
):
    '''Run segcsvd PVS segmentation for every session in a project.

    Wrapper that finds T1w files under a project's sourcedata/nifti, matches
    each to its FreeSurfer derivatives, skips sessions that aren't ready or
    are already segmented, and calls segment_pvs_session for the rest.

    Parameters:
    -----------
        project (str): Project directory name under PROJECTS_ROOT, e.g. "GLIMPSE_OSA".
        sif (Path | str): Path to the segcsvd apptainer image. Default SEGCSVD_SIF.
        subjects (list[str] | None): Only process these subjects, e.g.
            ["sub-001", "sub-002"] or ["001", "002"] (the "sub-" prefix is
            optional). Default None (all subjects).
        sessions (list[str] | None): Only process these sessions, e.g.
            ["ses-01", "ses-02"] or ["01", "02"] (the "ses-" prefix is
            optional). Default None (all sessions).
        skip_mask_and_bias (bool): See segment_pvs_session. Default False.
        cleanup (bool): See segment_pvs_session. Default True.
        seg_pvs_thr (float): See segment_pvs_session. Default 0.35.
        n_threads (int | None): See segment_pvs_session. Default 32.
        thr_only (bool): Skip the full pipeline and just re-binarize each
            session's existing seg_pvs.nii.gz at seg_pvs_thr via
            rethreshold_pvs. Default False.
        nifti_dir (str): Name of the sourcedata subdirectory to find T1w
            files under, e.g. "nifti" or "nifti_uw" for sites with a
            separate sourcedata tree. Default "nifti".
    '''
    project_dir = Path(PROJECTS_ROOT) / project / "data"
    nifti_dir = project_dir / "sourcedata" / nifti_dir
    fs_deriv_root = project_dir / "derivatives" / "freesurfer"
    segcsvd_root = project_dir / "derivatives" / "segcsvd"

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
        out_dir = segcsvd_root / f"sub-{sub}" / f"ses-{ses}"
        prefix = f"sub-{sub}_ses-{ses}"

        if thr_only:
            if not (out_dir / f"{prefix}_seg_pvs.nii.gz").exists():
                print(f"SKIP {prefix}: no existing seg_pvs.nii.gz to re-threshold")
                continue

            if (out_dir / f"{prefix}_seg_pvs_thr_{seg_pvs_thr}.nii.gz").exists():
                print(f"SKIP {prefix}: already thresholded at {seg_pvs_thr}")
                continue

            print(f"Re-thresholding {prefix} at {seg_pvs_thr}")
            result = rethreshold_pvs(sub, ses, out_dir, sif, seg_pvs_thr)
        else:
            if not (fs_deriv_dir / "mri" / "synthseg.rca.mgz").exists() or not (
                fs_deriv_dir / "mri" / "rawavg.mgz"
            ).exists():
                print(f"SKIP {prefix}: missing FreeSurfer synthseg/rawavg outputs")
                continue

            if (out_dir / f"{prefix}_seg_pvs.nii.gz").exists():
                print(f"SKIP {prefix}: already segmented")
                continue

            print(f"Running PVS segmentation for {prefix}")
            result = segment_pvs_session(
                sub,
                ses,
                t1w_file,
                fs_deriv_dir,
                out_dir,
                sif,
                skip_mask_and_bias=skip_mask_and_bias,
                cleanup=cleanup,
                seg_pvs_thr=seg_pvs_thr,
                n_threads=n_threads,
            )

        if result["returncode"] == 0:
            print(f"DONE {prefix}")
        else:
            print(f"FAILED {prefix}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run segcsvd PVS segmentation over a BIDS project's sessions."
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
        default=SEGCSVD_SIF,
        help=f"Path to the segcsvd apptainer image (default: {SEGCSVD_SIF})",
    )
    parser.add_argument(
        "--skip-mask-and-bias",
        action="store_true",
        help="Pass skip_mask_and_bias=true to segment_pvs",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Pass cleanup=false to segment_pvs (default: cleanup=true)",
    )
    parser.add_argument(
        "--seg-pvs-thr",
        type=float,
        default=0.35,
        help="PVS segmentation probability threshold (default: 0.35)",
    )
    parser.add_argument(
        "--n-threads",
        type=int,
        default=32,
        help=(
            "Limit CPU threads used inside the container by setting "
            "OMP_NUM_THREADS and ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS "
            "(default: 32)"
        ),
    )
    parser.add_argument(
        "--thr-only",
        action="store_true",
        help=(
            "Skip the full segmentation pipeline and just re-binarize each "
            "session's existing seg_pvs.nii.gz at --seg-pvs-thr, writing "
            "..._seg_pvs_thr_{seg_pvs_thr}.nii.gz"
        ),
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

    segment_pvs_project(
        args.project,
        sif=args.sif,
        subjects=args.subjects,
        sessions=args.sessions,
        skip_mask_and_bias=args.skip_mask_and_bias,
        cleanup=not args.no_cleanup,
        seg_pvs_thr=args.seg_pvs_thr,
        n_threads=args.n_threads,
        thr_only=args.thr_only,
        nifti_dir=args.nifti_dir,
    )
