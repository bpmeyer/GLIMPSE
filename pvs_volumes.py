"""Tabulate PVS volume per subject/session, split into cerebral white
matter vs. basal ganglia.

For each subject/session, combines:
  - segment_pvs.py's thresholded PVS mask (default 0.25 threshold) from
    `{project}/data/derivatives/segcsvd/sub-*/ses-*/`.
  - anat_masks.py's cerebral-wm-no-basal-ganglia_mask and basal-ganglia_mask
    (the latter includes its pallidum/putamen bounding-box blob -- see
    anat_masks.py's add_basal_ganglia_blob) from
    `{project}/data/derivatives/masks/sub-*/ses-*/anat/`.

All are in the subject's native T1w/rawavg space, so voxel counts translate
directly to volume via each session's voxel size. Sessions missing any
input, or where the masks don't share a voxel grid, are skipped.

Writes one project-wide CSV to `{project}/data/derivatives/pvs_volumes.csv`,
with columns subject, session, visit, total_vol, cerewm_vol, bg_vol,
ventricle_vol, csf_vol:
  - visit: "v1" for ses-101/102, "v2" for ses-201/202.
  - total_vol: total PVS volume (mm^3).
  - cerewm_vol: PVS volume inside cerebral-wm-no-basal-ganglia_mask (mm^3).
  - bg_vol: PVS volume inside basal-ganglia_mask (mm^3).
  - ventricle_vol: total ventricle volume (mm^3), from anat_masks.py's
    ventricles_mask (not PVS-related; a proxy for atrophy/ventricular
    enlargement).
  - csf_vol: total CSF volume (mm^3), from anat_masks.py's csf_mask
    (not PVS-related; a proxy for atrophy).

The CSV is fully rebuilt each run from whatever subjects/sessions are found
(respecting --subj/--ses filters), not incrementally updated.

Usage:
    python pvs_volumes.py PROJECT [--subj 101 102] [--ses 101 102 201 202]
    python pvs_volumes.py PROJECT --thr 0.35
    pixi run pvs-volumes PROJECT
"""

import argparse
from pathlib import Path

import nibabel as nib
import numpy as np
import pandas as pd

PROJECTS_ROOT = "/mnt/cina"

VISIT_LABELS = {"101": "v1", "102": "v1", "201": "v2", "202": "v2"}


def compute_pvs_volumes(subject, session, pvs_fn, cerewm_fn, bg_fn, ventricles_fn, csf_fn):
    '''Compute total, cerebral-WM, basal-ganglia PVS volume, ventricle
    volume, and CSF volume (mm^3) for a subject/session.

    Parameters:
    -----------
        subject (str): Subject ID, without the "sub-" prefix.
        session (str): Session ID, without the "ses-" prefix.
        pvs_fn (Path | str): segment_pvs.py's thresholded PVS mask.
        cerewm_fn (Path | str): anat_masks.py's
            cerebral-wm-no-basal-ganglia_mask.
        bg_fn (Path | str): anat_masks.py's basal-ganglia_mask.
        ventricles_fn (Path | str): anat_masks.py's ventricles mask.
        csf_fn (Path | str): anat_masks.py's csf mask.

    Returns:
    --------
        dict | None: {"subject", "session", "total_vol", "cerewm_vol",
            "bg_vol", "ventricle_vol", "csf_vol"}, or None if the masks
            don't share a voxel grid.
    '''
    pvs_img = nib.load(pvs_fn)
    cerewm_img = nib.load(cerewm_fn)
    bg_img = nib.load(bg_fn)
    ventricles_img = nib.load(ventricles_fn)
    csf_img = nib.load(csf_fn)

    if (
        pvs_img.shape != cerewm_img.shape
        or pvs_img.shape != bg_img.shape
        or pvs_img.shape != ventricles_img.shape
        or pvs_img.shape != csf_img.shape
    ):
        print(
            f"  sub-{subject}_ses-{session}: PVS mask shape {pvs_img.shape} != "
            f"cerebral WM mask shape {cerewm_img.shape}, basal ganglia mask shape "
            f"{bg_img.shape}, ventricles mask shape {ventricles_img.shape}, or CSF "
            f"mask shape {csf_img.shape}, skipping"
        )
        return None

    pvs_data = pvs_img.get_fdata() > 0
    cerewm_data = cerewm_img.get_fdata() > 0
    bg_data = bg_img.get_fdata() > 0
    ventricles_data = ventricles_img.get_fdata() > 0
    csf_data = csf_img.get_fdata() > 0

    voxel_vol_mm3 = np.prod(pvs_img.header.get_zooms()[:3])
    total_vol = pvs_data.sum() * voxel_vol_mm3
    cerewm_vol = (pvs_data & cerewm_data).sum() * voxel_vol_mm3
    bg_vol = (pvs_data & bg_data).sum() * voxel_vol_mm3
    ventricle_vol = ventricles_data.sum() * voxel_vol_mm3
    csf_vol = csf_data.sum() * voxel_vol_mm3

    return {
        "subject": subject,
        "session": session,
        "cerewm_vol": cerewm_vol,
        "bg_vol": bg_vol,
        "ventricle_vol": ventricle_vol,
        "csf_vol": csf_vol,
    }


def pvs_volumes_project(project, subjects=None, sessions=None, thr=0.25):
    '''Tabulate PVS volumes for every session in a project and write the
    project-wide CSV.

    Wrapper that finds segment_pvs.py and anat_masks.py output for a
    project, skips sessions that aren't ready, and writes one CSV row per
    remaining session.

    Parameters:
    -----------
        project (str): Project directory name under PROJECTS_ROOT, e.g. "GLIMPSE_OSA".
        subjects (list[str] | None): Only process these subjects, e.g.
            ["sub-001", "sub-002"] or ["001", "002"] (the "sub-" prefix is
            optional). Default None (all subjects).
        sessions (list[str] | None): Only process these sessions, e.g.
            ["ses-01", "ses-02"] or ["01", "02"] (the "ses-" prefix is
            optional). Default None (all sessions).
        thr (float): Which segment_pvs.py threshold's mask to use, e.g. 0.25
            for `..._seg_pvs_thr_0.25.nii.gz`. Default 0.25.
    '''
    project_dir = Path(PROJECTS_ROOT) / project / "data"
    segcsvd_root = project_dir / "derivatives" / "segcsvd"
    masks_root = project_dir / "derivatives" / "masks"
    out_csv = project_dir / "derivatives" / "pvs_volumes.csv"

    if subjects:
        subj_patterns = [s if s.startswith("sub-") else f"sub-{s}" for s in subjects]
    else:
        subj_patterns = ["sub-*"]
    if sessions:
        ses_patterns = [s if s.startswith("ses-") else f"ses-{s}" for s in sessions]
    else:
        ses_patterns = ["ses-*"]

    session_dirs = sorted(
        d
        for subj in subj_patterns
        for ses in ses_patterns
        for d in segcsvd_root.glob(f"{subj}/{ses}")
        if d.is_dir()
    )
    print(f"Found {len(session_dirs)} segcsvd subject/session directories")

    rows = []
    for session_dir in session_dirs:
        sub = session_dir.parts[-2].split("-", 1)[1]
        ses = session_dir.parts[-1].split("-", 1)[1]
        prefix = f"sub-{sub}_ses-{ses}"

        pvs_fn = session_dir / f"{prefix}_seg_pvs_thr_{thr}.nii.gz"
        anat_dir = masks_root / f"sub-{sub}" / f"ses-{ses}" / "anat"
        cerewm_fn = anat_dir / f"{prefix}_cerebral-wm-no-basal-ganglia_mask.nii.gz"
        bg_fn = anat_dir / f"{prefix}_basal-ganglia_mask.nii.gz"
        ventricles_fn = anat_dir / f"{prefix}_ventricles_mask.nii.gz"
        csf_fn = anat_dir / f"{prefix}_csf_mask.nii.gz"

        if not pvs_fn.exists():
            print(f"SKIP {prefix}: missing {pvs_fn.name} (run segment_pvs.py --thr-only --seg-pvs-thr {thr} first)")
            continue
        if not cerewm_fn.exists():
            print(f"SKIP {prefix}: missing {cerewm_fn.name} (run anat_masks.py first)")
            continue
        if not bg_fn.exists():
            print(f"SKIP {prefix}: missing {bg_fn.name} (run anat_masks.py first)")
            continue
        if not ventricles_fn.exists():
            print(f"SKIP {prefix}: missing {ventricles_fn.name} (run anat_masks.py first)")
            continue
        if not csf_fn.exists():
            print(f"SKIP {prefix}: missing {csf_fn.name} (run anat_masks.py first)")
            continue

        row = compute_pvs_volumes(sub, ses, pvs_fn, cerewm_fn, bg_fn, ventricles_fn, csf_fn)
        if row is not None:
            if ses not in VISIT_LABELS:
                print(f"  {prefix}: unrecognized session {ses!r}, leaving visit blank")
            row["visit"] = VISIT_LABELS.get(ses, "")
            rows.append(row)
            print(f"DONE {prefix}")

    df = pd.DataFrame(
        rows,
        columns=["subject", "session", "visit", "total_vol", "cerewm_vol", "bg_vol", "ventricle_vol", "csf_vol"],
    )
    df = df.sort_values(["subject", "session"]).reset_index(drop=True)
    df.to_csv(out_csv, index=False)
    print(f"Wrote {len(df)} rows to {out_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tabulate PVS volume per subject/session, split into cerebral WM vs. basal ganglia."
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
        "--thr",
        type=float,
        default=0.25,
        help="Which segment_pvs.py threshold's mask to use, e.g. 0.25 for ..._seg_pvs_thr_0.25.nii.gz (default: 0.25)",
    )
    args = parser.parse_args()

    pvs_volumes_project(
        args.project,
        subjects=args.subjects,
        sessions=args.sessions,
        thr=args.thr,
    )
