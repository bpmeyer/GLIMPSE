"""Generate anatomical-space tissue masks from FreeSurfer wmparc/aparc+aseg
output.

For each subject/session with FreeSurfer output, this:
  1. Resamples wmparc.mgz, aparc+aseg.mgz, and brainmask.mgz into native
     (rawavg) space with mri_label2vol.
  2. Runs mri_binarize against those resampled volumes to extract eight
     tissue masks (ventricles, cerebral WM, cortical GM, subcortical GM,
     CSF, brainstem, cerebellum, and basal ganglia) plus a brainmask.
     Every mask comes from the resampled wmparc except cerebral WM, which
     comes from aparc+aseg (see CEREBRAL_WM_LABELS), and the brainmask,
     which comes from brainmask.mgz. 
  3. The basal ganglia mask also gets a bounding-box blob (computed in
     FreeSurfer space) added in between the pallidum and putamen.
     A tenth mask, cerebral-wm-no-basal-ganglia, is then made by
     subtracting the (blob-expanded) basal ganglia mask from the cerebral
     WM mask.


Expects FreeSurfer output at `{project}/data/derivatives/freesurfer/sub-*_ses-*/mri/`

Writes output to `{project}/data/derivatives/masks/sub-*/ses-*/anat/`
Sessions without FreeSurfer wmparc/aparc+aseg/brainmask output are skipped.
Each step is skipped individually if its output already exists, unless --force is given.

With --resample-only, only step 1 (the wmparc/aparc+aseg/brainmask-in-rawavg
resamples) runs; mri_binarize is skipped entirely.

Usage:
    python anat_masks.py PROJECT [--subj 101 102] [--ses 101 102 201 202]
    python anat_masks.py PROJECT --resample-only
    python anat_masks.py PROJECT --force
    pixi run anat-masks PROJECT
"""

import argparse
import shlex
import subprocess
from pathlib import Path

import nibabel as nib
import numpy as np
from nibabel.orientations import aff2axcodes
from scipy.ndimage import binary_fill_holes

FREESURFER_HOME = "/usr/local/freesurfer/8.0.0"
PROJECTS_ROOT = "/mnt/cina"

# Ventricle labels (includes 4th ventricle) --
VENTRICLE_LABELS = [4, 5, 14, 15, 43, 44]

# Corpus callosum
CORPUS_CALLOSUM_LABELS = [251, 252, 253, 254, 255]

# Cerebral WM, from aparc+aseg's generic Left/Right-Cerebral-White-Matter
# labels (2, 41) rather than wmparc's per-gyrus subdivision (3000-3035 lh,
# 4000-4035 rh)  Plus WM-hypointensities (77).
CEREBRAL_WM_LABELS = [2, 41, 77]

# cortical GM
# (1000-1035 lh, 2000-2035 rh)
CORTICAL_GM_LABELS = list(range(1000, 1036)) + list(range(2000, 2036))

# CSF
CSF_LABELS = [24]

# Subcortical GM (thalamus, caudate, putamen, pallidum, hippocampus,
# amygdala, accumbens, substantia nigra, VentralDC) -- explicit list rather
# than mri_binarize's built-in --subcort-gm, which also includes cerebellum
# cortex (labels 8, 47).
SUBCORTICAL_GM_LABELS = [10, 11, 12, 13, 17, 18, 26, 27, 28, 49, 50, 51, 52, 53, 54, 58, 59, 60]

# Brainstem
BRAINSTEM_LABELS = [16]

# Cerebellum (white matter + cortex, both hemispheres)
CEREBELLUM_LABELS = [7, 8, 46, 47]

# Basal ganglia (thalamus, putamen, pallidum, accumbens)
THALAMUS_LABELS = [10, 49]
PUTAMEN_LABELS = [12, 51]
PALLIDUM_LABELS = [13, 52]
ACCUMBENS_LABELS = [26, 58]
BASAL_GANGLIA_LABELS = THALAMUS_LABELS + PUTAMEN_LABELS + PALLIDUM_LABELS + ACCUMBENS_LABELS


def run_with_freesurfer_env(cmd, **kwargs):
    '''Run a command with FREESURFER_HOME set and SetUpFreeSurfer.sh sourced.

    Parameters:
    -----------
        cmd (list[str]): Command and arguments to run, e.g. ["mri_binarize", ...].
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


def _resample_to_rawavg(seg_fn, rawavg_fn, out_fn, prefix, force=False):
    '''Resample a FreeSurfer conformed-space segmentation volume into
    native (rawavg) space with mri_label2vol, using the segmentation's own
    header for the registration (--regheader) rather than a computed
    registration.

    Skips re-running mri_label2vol if out_fn already exists, unless
    force=True.

    Parameters:
    -----------
        seg_fn (Path | str): Segmentation volume to resample (e.g.
            wmparc.mgz or aparc+aseg.mgz), in FreeSurfer conformed space.
        rawavg_fn (Path | str): rawavg.mgz to resample into the space of.
        out_fn (Path | str): Where to write the resampled volume.
        prefix (str): Filename prefix, e.g. "sub-001_ses-01" (for logging).
        force (bool): Re-run even if the output already exists. Default False.

    Returns:
    --------
        Path: out_fn.
    '''
    out_fn = Path(out_fn)

    if out_fn.exists() and not force:
        print(f"  {prefix}: {out_fn.name} already exists, skipping resample")
        return out_fn

    run_with_freesurfer_env(
        [
            "mri_label2vol",
            "--seg",
            str(seg_fn),
            "--temp",
            str(rawavg_fn),
            "--o",
            str(out_fn),
            "--regheader",
            str(seg_fn),
        ]
    )

    return out_fn


def resample_wmparc(fs_deriv_dir, out_dir, prefix, force=False):
    '''Resample wmparc.mgz into native (rawavg) space with mri_label2vol.

    Skips re-running mri_label2vol if the output already exists, unless
    force=True.

    Parameters:
    -----------
        fs_deriv_dir (Path | str): Subject/session's FreeSurfer derivatives
            dir (contains mri/wmparc.mgz and mri/rawavg.mgz).
        out_dir (Path | str): Directory to write the resampled volume to.
        prefix (str): Filename prefix, e.g. "sub-001_ses-01".
        force (bool): Re-run even if the output already exists. Default False.

    Returns:
    --------
        Path: The resampled wmparc-in-rawavg.nii.gz file.
    '''
    fs_deriv_dir = Path(fs_deriv_dir)
    out_dir = Path(out_dir)
    wmparc = fs_deriv_dir / "mri" / "wmparc.mgz"
    rawavg = fs_deriv_dir / "mri" / "rawavg.mgz"
    out_fn = out_dir / f"{prefix}_wmparc-in-rawavg.nii.gz"

    return _resample_to_rawavg(wmparc, rawavg, out_fn, prefix, force=force)


def resample_aparc_aseg(fs_deriv_dir, out_dir, prefix, force=False):
    '''Resample aparc+aseg.mgz into native (rawavg) space with mri_label2vol.

    Used for the cerebral WM mask
    Skips re-running mri_label2vol if the output already exists, unless
    force=True.

    Parameters:
    -----------
        fs_deriv_dir (Path | str): Subject/session's FreeSurfer derivatives
            dir (contains mri/aparc+aseg.mgz and mri/rawavg.mgz).
        out_dir (Path | str): Directory to write the resampled volume to.
        prefix (str): Filename prefix, e.g. "sub-001_ses-01".
        force (bool): Re-run even if the output already exists. Default False.

    Returns:
    --------
        Path: The resampled aparc-aseg-in-rawavg.nii.gz file.
    '''
    fs_deriv_dir = Path(fs_deriv_dir)
    out_dir = Path(out_dir)
    aparc_aseg = fs_deriv_dir / "mri" / "aparc+aseg.mgz"
    rawavg = fs_deriv_dir / "mri" / "rawavg.mgz"
    out_fn = out_dir / f"{prefix}_aparc-aseg-in-rawavg.nii.gz"

    return _resample_to_rawavg(aparc_aseg, rawavg, out_fn, prefix, force=force)


def resample_brainmask(fs_deriv_dir, out_dir, prefix, force=False):
    '''Resample brainmask.mgz into native (rawavg) space with mri_label2vol.

    Used for the brainmask output: FreeSurfer's brainmask.mgz

    Skips re-running mri_label2vol if the output already exists, unless
    force=True.

    Parameters:
    -----------
        fs_deriv_dir (Path | str): Subject/session's FreeSurfer derivatives
            dir (contains mri/brainmask.mgz and mri/rawavg.mgz).
        out_dir (Path | str): Directory to write the resampled volume to.
        prefix (str): Filename prefix, e.g. "sub-001_ses-01".
        force (bool): Re-run even if the output already exists. Default False.

    Returns:
    --------
        Path: The resampled brainmask-in-rawavg.nii.gz file.
    '''
    fs_deriv_dir = Path(fs_deriv_dir)
    out_dir = Path(out_dir)
    brainmask = fs_deriv_dir / "mri" / "brainmask.mgz"
    rawavg = fs_deriv_dir / "mri" / "rawavg.mgz"
    out_fn = out_dir / f"{prefix}_brainmask-in-rawavg.nii.gz"

    return _resample_to_rawavg(brainmask, rawavg, out_fn, prefix, force=force)


def make_pial_surface_mask(fs_deriv_dir, out_dir, prefix, force=False):
    '''Make a thin cortical (pial) surface shell mask in native (rawavg)
    space with mri_surf2vol.

    Surfaces are defined in FreeSurfer's conformed space (orig.mgz), which
    is generally not identity-registered to the native rawavg volume (they
    can differ in orientation/resolution) -- see
    https://surfer.nmr.mgh.harvard.edu/fswiki/FsAnat-to-NativeAnat. So this
    first builds a header-based registration between rawavg and orig with
    tkregister2 --regheader, then passes that to mri_surf2vol via --reg
    (rather than assuming --identity between the surface and rawavg).

    Resamples lh.pial and rh.pial separately (mri_surf2vol --mkmask marks
    only the voxels each surface's vertices fall in, not a filled volume),
    then ORs the two hemispheres together.

    Skips re-running if the output already exists, unless force=True.

    Parameters:
    -----------
        fs_deriv_dir (Path | str): Subject/session's FreeSurfer derivatives
            dir (contains surf/lh.pial, surf/rh.pial, mri/orig.mgz, and
            mri/rawavg.mgz).
        out_dir (Path | str): Directory to write the pial surface mask to.
        prefix (str): Filename prefix, e.g. "sub-001_ses-01".
        force (bool): Re-run even if the output already exists. Default False.

    Returns:
    --------
        Path: The pial surface mask file.
    '''
    fs_deriv_dir = Path(fs_deriv_dir)
    out_dir = Path(out_dir)
    rawavg = fs_deriv_dir / "mri" / "rawavg.mgz"
    orig = fs_deriv_dir / "mri" / "orig.mgz"
    out_fn = out_dir / f"{prefix}_pial_surface_mask.nii.gz"

    if out_fn.exists() and not force:
        print(f"  {prefix}: {out_fn.name} already exists, skipping")
        return out_fn

    reg_fn = out_dir / f"{prefix}_rawavg-to-orig_register.dat"
    run_with_freesurfer_env(
        [
            "tkregister2",
            "--mov",
            str(rawavg),
            "--targ",
            str(orig),
            "--reg",
            str(reg_fn),
            "--noedit",
            "--regheader",
        ]
    )

    hemi_data = []
    header = None
    for hemi in ("lh", "rh"):
        hemi_fn = out_dir / f"{prefix}_{hemi}_pial_surface_mask.nii.gz"
        run_with_freesurfer_env(
            [
                "mri_surf2vol",
                "--mkmask",
                "--hemi",
                hemi,
                "--surf",
                "pial",
                "--reg",
                str(reg_fn),
                "--subject",
                fs_deriv_dir.name,
                "--sd",
                str(fs_deriv_dir.parent),
                "--template",
                str(rawavg),
                "--o",
                str(hemi_fn),
            ]
        )
        hemi_img = nib.load(hemi_fn)
        hemi_data.append(hemi_img.get_fdata() > 0)
        header = hemi_img.header
        hemi_fn.unlink()

    reg_fn.unlink()

    out_data = (hemi_data[0] | hemi_data[1]).astype(np.uint8)
    nib.save(nib.Nifti1Image(out_data, None, header=header), out_fn)

    return out_fn


def fill_mask_holes(mask_fn):
    '''Fill enclosed holes in a binary mask file in place.

    The binarized brainmask (from FreeSurfer's brainmask.mgz) can have small
    interior holes -- binary_fill_holes closes any background region that
    isn't connected to the volume's edge.

    Parameters:
    -----------
        mask_fn (Path | str): Binary mask nifti file to fill and overwrite.
    '''
    mask_fn = Path(mask_fn)
    img = nib.load(mask_fn)
    data = binary_fill_holes(img.get_fdata() > 0).astype(np.uint8)

    header = img.header.copy()
    header.set_data_dtype(np.uint8)
    nib.save(nib.Nifti1Image(data, None, header=header), mask_fn)


def _axis_extent(mask, axis):
    '''Return the (min, max) voxel index of a boolean mask's extent along
    one axis, projecting out the other two axes first.
    '''
    other_axes = tuple(a for a in range(3) if a != axis)
    idxs = np.flatnonzero(mask.any(axis=other_axes))
    return int(idxs.min()), int(idxs.max())


def add_basal_ganglia_blob(fs_deriv_dir, out_dir, prefix, mask_fn):
    '''Add a bounding-box blob spanning the region between the pallidum and
    putamen to a basal ganglia mask, in place.

    The blob is an axis-aligned box bounded left-right and anterior-
    posterior by the putamen's own extent (both hemispheres), and
    superior-inferior from the pallidum's most inferior ("bottom") extent
    to the putamen's most superior ("top") extent. It's then restricted to
    the brainmask (nonzero wmparc labels), with CSF, cortical GM, ventricle,
    and corpus callosum voxels excluded, since the raw box can otherwise
    spill into those structures at its edges.

    Bounds are computed directly on wmparc.mgz in FreeSurfer's native
    conformed space, not the resampled rawavg volume -- conformed volumes
    have a fixed, axis-aligned orientation (e.g. LIA), so array axes map
    cleanly onto L/R, S/I, and A/P; an arbitrary rawavg volume isn't
    guaranteed to be axis-aligned that way. The resulting box is then
    resampled into native (rawavg) space with mri_label2vol --regheader
    (the same trick resample_wmparc uses, since the box shares wmparc.mgz's
    header) before being OR'd into mask_fn.

    Parameters:
    -----------
        fs_deriv_dir (Path | str): Subject/session's FreeSurfer derivatives
            dir (contains mri/wmparc.mgz and mri/rawavg.mgz).
        out_dir (Path | str): Directory to write intermediate blob volumes
            to (deleted once merged).
        prefix (str): Filename prefix, e.g. "sub-001_ses-01".
        mask_fn (Path | str): Basal ganglia binary mask nifti file (in
            rawavg space) to add the blob to and overwrite.
    '''
    fs_deriv_dir = Path(fs_deriv_dir)
    out_dir = Path(out_dir)
    mask_fn = Path(mask_fn)

    wmparc_img = nib.load(fs_deriv_dir / "mri" / "wmparc.mgz")
    wmparc_data = np.asarray(wmparc_img.dataobj)
    axcodes = aff2axcodes(wmparc_img.affine)

    axis_lr = next(i for i, c in enumerate(axcodes) if c in "LR")
    axis_si = next(i for i, c in enumerate(axcodes) if c in "SI")
    axis_ap = next(i for i, c in enumerate(axcodes) if c in "AP")

    putamen_mask = np.isin(wmparc_data, PUTAMEN_LABELS)
    lr_lo, lr_hi = _axis_extent(putamen_mask, axis_lr)
    ap_lo, ap_hi = _axis_extent(putamen_mask, axis_ap)
    put_si_lo, put_si_hi = _axis_extent(putamen_mask, axis_si)

    pallidum_mask = np.isin(wmparc_data, PALLIDUM_LABELS)
    pal_si_lo, pal_si_hi = _axis_extent(pallidum_mask, axis_si)

    # S-I bound: from the pallidum's most inferior ("bottom") extent to the
    # putamen's most superior ("top") extent -- which end of the axis is
    # inferior vs. superior depends on this volume's orientation.
    if axcodes[axis_si] == "S":
        si_lo, si_hi = pal_si_lo, put_si_hi
    else:
        si_lo, si_hi = put_si_lo, pal_si_hi

    box = np.zeros(wmparc_data.shape, dtype=np.uint8)
    slices = [slice(None)] * 3
    slices[axis_lr] = slice(lr_lo, lr_hi + 1)
    slices[axis_si] = slice(si_lo, si_hi + 1)
    slices[axis_ap] = slice(ap_lo, ap_hi + 1)
    box[tuple(slices)] = 1

    # Restrict the raw bounding box to the brainmask (nonzero wmparc labels),
    # excluding CSF, cortical GM, ventricles, and corpus callosum -- the box
    # can otherwise spill into ventricle/CSF spaces, insular/opercular
    # cortex, or the callosum at its edges.
    excluded_labels = (
        CSF_LABELS + CORTICAL_GM_LABELS + VENTRICLE_LABELS + CORPUS_CALLOSUM_LABELS
    )
    excluded = (wmparc_data == 0) | np.isin(wmparc_data, excluded_labels)
    box[excluded] = 0

    box_conformed_fn = out_dir / f"{prefix}_basal-ganglia-blob_conformed.nii.gz"
    box_rawavg_fn = out_dir / f"{prefix}_basal-ganglia-blob_rawavg.nii.gz"
    nib.save(
        nib.Nifti1Image(box, wmparc_img.affine, header=wmparc_img.header), box_conformed_fn
    )

    run_with_freesurfer_env(
        [
            "mri_label2vol",
            "--seg",
            str(box_conformed_fn),
            "--temp",
            str(fs_deriv_dir / "mri" / "rawavg.mgz"),
            "--o",
            str(box_rawavg_fn),
            "--regheader",
            str(box_conformed_fn),
        ]
    )

    mask_img = nib.load(mask_fn)
    mask_data = mask_img.get_fdata() > 0
    blob_data = nib.load(box_rawavg_fn).get_fdata() > 0
    out_data = (mask_data | blob_data).astype(np.uint8)

    header = mask_img.header.copy()
    header.set_data_dtype(np.uint8)
    nib.save(nib.Nifti1Image(out_data, None, header=header), mask_fn)

    box_conformed_fn.unlink()
    box_rawavg_fn.unlink()


def make_cerebral_wm_no_basal_ganglia_mask(out_dir, prefix, force=False):
    '''Make a cerebral WM mask with basal ganglia voxels excluded.

    Subtracts basal-ganglia_mask (including its bounding-box blob, see
    add_basal_ganglia_blob) from cerebral-wm_mask -- the blob can include
    some cerebral-WM-labeled voxels (e.g. internal capsule) between the
    pallidum and putamen, so this keeps that overlap out of the WM mask.

    Skips re-running if the output already exists, unless force=True.

    Parameters:
    -----------
        out_dir (Path | str): Directory holding cerebral-wm_mask.nii.gz and
            basal-ganglia_mask.nii.gz, and to write the output to.
        prefix (str): Filename prefix, e.g. "sub-001_ses-01".
        force (bool): Re-run even if the output already exists. Default False.

    Returns:
    --------
        Path: The cerebral-wm-no-basal-ganglia_mask.nii.gz file.
    '''
    out_dir = Path(out_dir)
    out_fn = out_dir / f"{prefix}_cerebral-wm-no-basal-ganglia_mask.nii.gz"

    if out_fn.exists() and not force:
        print(f"  {prefix}: {out_fn.name} already exists, skipping")
        return out_fn

    cerebral_wm_img = nib.load(out_dir / f"{prefix}_cerebral-wm_mask.nii.gz")
    cerebral_wm_data = cerebral_wm_img.get_fdata() > 0
    basal_ganglia_data = (
        nib.load(out_dir / f"{prefix}_basal-ganglia_mask.nii.gz").get_fdata() > 0
    )

    out_data = (cerebral_wm_data & ~basal_ganglia_data).astype(np.uint8)

    header = cerebral_wm_img.header.copy()
    header.set_data_dtype(np.uint8)
    nib.save(nib.Nifti1Image(out_data, None, header=header), out_fn)

    return out_fn


def make_anat_masks(subject, session, fs_deriv_dir, out_dir, force=False):
    '''Generate the ten anatomical-space tissue masks plus the pial surface
    mask for a subject/session.

    Skips re-running the resample step or any individual mask whose output
    already exists, unless force=True.

    Parameters:
    -----------
        subject (str): Subject ID, without the "sub-" prefix.
        session (str): Session ID, without the "ses-" prefix.
        fs_deriv_dir (Path | str): Subject/session's FreeSurfer derivatives
            dir (contains mri/wmparc.mgz, mri/aparc+aseg.mgz,
            mri/brainmask.mgz, and mri/rawavg.mgz).
        out_dir (Path | str): Directory to write the resampled volumes and
            mask outputs to.
        force (bool): Re-run every step even if its output already exists.
            Default False.

    Returns:
    --------
        dict: {"subject", "session", "returncode"} summarizing the run
            (returncode is the first nonzero mri_binarize exit code, or 0).
    '''
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    prefix = f"sub-{subject}_ses-{session}"
    wmparc_native_fn = resample_wmparc(fs_deriv_dir, out_dir, prefix, force=force)
    aparc_aseg_native_fn = resample_aparc_aseg(fs_deriv_dir, out_dir, prefix, force=force)
    brainmask_native_fn = resample_brainmask(fs_deriv_dir, out_dir, prefix, force=force)

    mask_specs = [
        ("ventricles_mask", wmparc_native_fn, ["--match"] + [str(v) for v in VENTRICLE_LABELS]),
        (
            "cerebral-wm_mask",
            aparc_aseg_native_fn,
            ["--match"] + [str(v) for v in CEREBRAL_WM_LABELS],
        ),
        (
            "cortical-gm_mask",
            wmparc_native_fn,
            ["--match"] + [str(v) for v in CORTICAL_GM_LABELS],
        ),
        (
            "subcortical-gm_mask",
            wmparc_native_fn,
            ["--match"] + [str(v) for v in SUBCORTICAL_GM_LABELS],
        ),
        ("csf_mask", wmparc_native_fn, ["--match"] + [str(v) for v in CSF_LABELS]),
        ("brainstem_mask", wmparc_native_fn, ["--match"] + [str(v) for v in BRAINSTEM_LABELS]),
        ("cerebellum_mask", wmparc_native_fn, ["--match"] + [str(v) for v in CEREBELLUM_LABELS]),
        (
            "basal-ganglia_mask",
            wmparc_native_fn,
            ["--match"] + [str(v) for v in BASAL_GANGLIA_LABELS],
        ),
        ("brainmask", brainmask_native_fn, ["--min", "1"]),
    ]

    returncode = 0
    for suffix, input_fn, match_args in mask_specs:
        mask_fn = out_dir / f"{prefix}_{suffix}.nii.gz"
        if mask_fn.exists() and not force:
            print(f"  {prefix}: {mask_fn.name} already exists, skipping")
            continue

        result = run_with_freesurfer_env(
            [
                "mri_binarize",
                "--i",
                str(input_fn),
                *match_args,
                "--o",
                str(mask_fn),
            ]
        )
        if result.returncode != 0:
            if returncode == 0:
                returncode = result.returncode
        elif suffix == "brainmask":
            fill_mask_holes(mask_fn)
        elif suffix == "basal-ganglia_mask":
            add_basal_ganglia_blob(fs_deriv_dir, out_dir, prefix, mask_fn)

    cerebral_wm_fn = out_dir / f"{prefix}_cerebral-wm_mask.nii.gz"
    basal_ganglia_fn = out_dir / f"{prefix}_basal-ganglia_mask.nii.gz"
    if cerebral_wm_fn.exists() and basal_ganglia_fn.exists():
        make_cerebral_wm_no_basal_ganglia_mask(out_dir, prefix, force=force)

    make_pial_surface_mask(fs_deriv_dir, out_dir, prefix, force=force)

    return {
        "subject": subject,
        "session": session,
        "returncode": returncode,
    }


def anat_masks_project(
    project, subjects=None, sessions=None, resample_only=False, force=False
):
    '''Generate anatomical-space tissue masks for every session in a project.

    Wrapper that finds FreeSurfer derivatives for a project, skips sessions
    that aren't ready or already have all mask outputs, and calls
    make_anat_masks for the rest.

    Parameters:
    -----------
        project (str): Project directory name under PROJECTS_ROOT, e.g. "GLIMPSE_OSA".
        subjects (list[str] | None): Only process these subjects, e.g.
            ["sub-001", "sub-002"] or ["001", "002"] (the "sub-" prefix is
            optional). Default None (all subjects).
        sessions (list[str] | None): Only process these sessions, e.g.
            ["ses-01", "ses-02"] or ["01", "02"] (the "ses-" prefix is
            optional). Default None (all sessions).
        resample_only (bool): Only run the wmparc/aparc+aseg/brainmask-
            in-rawavg resample steps, skipping mri_binarize entirely.
            Default False.
        force (bool): Re-run every step even if its output already exists.
            Default False.
    '''
    project_dir = Path(PROJECTS_ROOT) / project / "data"
    fs_deriv_root = project_dir / "derivatives" / "freesurfer"
    masks_root = project_dir / "derivatives" / "masks"

    if subjects:
        subj_patterns = [s if s.startswith("sub-") else f"sub-{s}" for s in subjects]
    else:
        subj_patterns = ["sub-*"]
    if sessions:
        ses_patterns = [s if s.startswith("ses-") else f"ses-{s}" for s in sessions]
    else:
        ses_patterns = ["ses-*"]

    fs_deriv_dirs = sorted(
        d
        for subj in subj_patterns
        for ses in ses_patterns
        for d in fs_deriv_root.glob(f"{subj}_{ses}")
        if d.is_dir()
    )
    print(f"Found {len(fs_deriv_dirs)} FreeSurfer subject/session directories")

    mask_names = [
        "ventricles_mask",
        "cerebral_wm_mask",
        "cortical_gm_mask",
        "subcortical_gm_mask",
        "csf_mask",
        "brainstem_mask",
        "cerebellum_mask",
        "basal-ganglia_mask",
        "cerebral-wm-no-basal-ganglia_mask",
        "brainmask",
        "pial_surface_mask",
    ]

    for fs_deriv_dir in fs_deriv_dirs:
        sub, ses = fs_deriv_dir.name.split("_", 1)
        sub = sub.split("-", 1)[1]
        ses = ses.split("-", 1)[1]
        prefix = f"sub-{sub}_ses-{ses}"
        out_dir = masks_root / f"sub-{sub}" / f"ses-{ses}" / "anat"

        if (
            not (fs_deriv_dir / "mri" / "wmparc.mgz").exists()
            or not (fs_deriv_dir / "mri" / "aparc+aseg.mgz").exists()
            or not (fs_deriv_dir / "mri" / "brainmask.mgz").exists()
            or not (fs_deriv_dir / "mri" / "rawavg.mgz").exists()
            or not (fs_deriv_dir / "surf" / "lh.pial").exists()
            or not (fs_deriv_dir / "surf" / "rh.pial").exists()
        ):
            print(
                f"SKIP {prefix}: missing FreeSurfer wmparc/aparc+aseg/brainmask/rawavg/pial outputs"
            )
            continue

        if resample_only:
            resampled_fn = out_dir / f"{prefix}_wmparc-in-rawavg.nii.gz"
            aparc_aseg_resampled_fn = out_dir / f"{prefix}_aparc-aseg-in-rawavg.nii.gz"
            brainmask_resampled_fn = out_dir / f"{prefix}_brainmask-in-rawavg.nii.gz"
            if (
                resampled_fn.exists()
                and aparc_aseg_resampled_fn.exists()
                and brainmask_resampled_fn.exists()
                and not force
            ):
                print(f"SKIP {prefix}: {resampled_fn.name} already exists")
                continue

            out_dir.mkdir(parents=True, exist_ok=True)
            print(f"Resampling wmparc, aparc+aseg, and brainmask for {prefix}")
            resample_wmparc(fs_deriv_dir, out_dir, prefix, force=force)
            resample_aparc_aseg(fs_deriv_dir, out_dir, prefix, force=force)
            resample_brainmask(fs_deriv_dir, out_dir, prefix, force=force)
            print(f"DONE {prefix}")
            continue

        if not force and all(
            (out_dir / f"{prefix}_{name}.nii.gz").exists() for name in mask_names
        ):
            print(f"SKIP {prefix}: masks already exist")
            continue

        print(f"Making anatomical masks for {prefix}")
        result = make_anat_masks(sub, ses, fs_deriv_dir, out_dir, force=force)

        if result["returncode"] == 0:
            print(f"DONE {prefix}")
        else:
            print(f"FAILED {prefix}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate anatomical-space tissue masks from FreeSurfer wmparc/aparc+aseg output."
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
        "--resample-only",
        action="store_true",
        help="Only run the wmparc/aparc+aseg/brainmask-in-rawavg resample steps, skipping mri_binarize entirely",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run every step even if its output already exists (default: skip steps whose output already exists)",
    )
    args = parser.parse_args()

    anat_masks_project(
        args.project,
        subjects=args.subjects,
        sessions=args.sessions,
        resample_only=args.resample_only,
        force=args.force,
    )
