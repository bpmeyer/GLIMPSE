from __future__ import annotations

import logging
from typing import Any, Optional
lgr = logging.getLogger("heudiconv")
import collections
import pydicom as dcm
from heudiconv.utils import SeqInfo
from heudiconv.dicoms import create_seqinfo, validate_dicom
import nibabel.nicom.dicomwrappers as dw


def create_key(
    template: Optional[str],
    outtype: tuple[str, ...] = ("nii.gz",),
    annotation_classes: None = None,
) -> tuple[str, tuple[str, ...], None]:
    if template is None or not template:
        raise ValueError("Template must be a valid format string")
    return (template, outtype, annotation_classes)

# Edit this list when multiple image types are reconstructed.
SPLIT_BY_IMAGE_TYPE = {
    "csf_flow_fl2d_tra_"
    }

def grouping(files, dcmfilter, seqinfo):
    groups = collections.OrderedDict()
    wrappers = {}

    parsed = []
    key_formats = collections.defaultdict(set)

    for f in files:
        try:
            mwinfo = validate_dicom(f, dcmfilter)
        except Exception as exc:
            # Some vendor-generated derived series (e.g. flow analysis
            # screen captures) have malformed geometry tags (a single
            # value instead of the standard 6-value ImageOrientationPatient)
            # that crash nibabel's series signature check. Skip them rather
            # than aborting the whole conversion.
            lgr.warning("Skipping unparseable DICOM %s: %s", f, exc)
            continue
        if mwinfo is None:
            continue

        mw, series_id, study_uid = mwinfo
        ds = mw.dcm_data

        series_number = ds.get("SeriesNumber", "")
        protocol_name = ds.get("ProtocolName", "")
        series_desc = ds.get("SeriesDescription", "")
        image_type = tuple(ds.get("ImageType", ()))

        base_key = (
            series_number,
            protocol_name,
        )

        if series_desc in SPLIT_BY_IMAGE_TYPE:
            base_key = base_key + (image_type,)

        sop_class = ds.get("SOPClassUID", None)
        sop_name = sop_class.name if sop_class is not None else None
        is_enhanced = sop_name == "Enhanced MR Image Storage"

        key_formats[base_key].add(is_enhanced)
        parsed.append((base_key, is_enhanced, f, mw))

    # Some series are exported by the scanner twice: once as "Enhanced MR
    # Image Storage" (multi-frame) and once as "MR Image Storage" (classic,
    # per-slice) - see dcm2niix issues #236/#742. When both exist for the
    # same series, convert both, but keep them in separate groups (tagging
    # the key/series_id with the format) so they don't get merged into one
    # output; series that only ever exist in one format are untouched.
    format_suffix = {}
    for base_key, is_enhanced, f, mw in parsed:
        key = base_key
        if len(key_formats[base_key]) > 1:
            suffix = "enhanced" if is_enhanced else "classic"
            key = base_key + (suffix,)
            format_suffix[key] = suffix
        groups.setdefault(key, []).append(f)
        wrappers.setdefault(key, mw)

    seqinfos = collections.OrderedDict()

    for key, series_files in groups.items():
        mw = wrappers[key]
        ds = mw.dcm_data

        series_number = ds.get("SeriesNumber", "")
        protocol_name = ds.get("ProtocolName", "")
        series_desc = ds.get("SeriesDescription", "")

        series_id = f"{series_number}-{protocol_name}"

        if series_desc in SPLIT_BY_IMAGE_TYPE:
            image_type = tuple(ds.get("ImageType", ()))
            image_suffix = "_".join(str(x) for x in image_type)
            series_id = f"{series_id}-{image_suffix}"

        if key in format_suffix:
            series_id = f"{series_id}-{format_suffix[key]}"

        try:
            si = create_seqinfo(mw, series_files, series_id)
        except Exception as exc:
            # Some derived/secondary-capture series (e.g. flow analysis
            # screen captures) lack a proper image shape and crash
            # heudiconv's seqinfo builder. Skip them rather than aborting
            # the whole conversion.
            lgr.warning("Skipping series %s: failed to build seqinfo (%s)", series_id, exc)
            continue
        seqinfos[si] = series_files

    return collections.OrderedDict([("", seqinfos)])

def get_image_suffix(s):
    parts = s.series_id.split("-", 2)
    if len(parts) < 3:
        return ""
    return parts[2]

def infotodict(
    seqinfo: list[SeqInfo],
) -> dict[tuple[str, tuple[str, ...], None], list]:

    # The "data" key creates sequential numbers which can be used for naming sequences.
    t1w = create_key('{bids_subject_session_dir}/anat/{bids_subject_session_prefix}_run-{item:02d}_T1w')
    t2w = create_key('{bids_subject_session_dir}/anat/{bids_subject_session_prefix}_run-{item:02d}_T2w')
    swi_mag= create_key('{bids_subject_session_dir}/swi/{bids_subject_session_prefix}_part-mag_run-{item:02d}_GRE')
    swi_ph= create_key('{bids_subject_session_dir}/swi/{bids_subject_session_prefix}_part-phase_run-{item:02d}_GRE')
    swi = create_key('{bids_subject_session_dir}/swi/{bids_subject_session_prefix}_run-{item:02d}_swi') 
    swi_mIP = create_key('{bids_subject_session_dir}/swi/{bids_subject_session_prefix}_run-{item:02d}_minIP') 
    flair = create_key('{bids_subject_session_dir}/anat/{bids_subject_session_prefix}_run-{item:02d}_FLAIR')
    func_rest = create_key('{bids_subject_session_dir}/func/{bids_subject_session_prefix}_task-rest_dir_PA_run-{item:02d}_bold')
    fmap_ap = create_key('{bids_subject_session_dir}/fmap/{bids_subject_session_prefix}_acq-func_dir-AP_run-{item:02d}_epi')
    pcasl = create_key('{bids_subject_session_dir}/perf/{bids_subject_session_prefix}_task-pcasl_run-{item:02d}_asl')
    dwi = create_key('{bids_subject_session_dir}/dwi/{bids_subject_session_prefix}_dir_AP_run-{item:02d}_dwi')
    dwi_fmap_pa = create_key('{bids_subject_session_dir}/fmap/{bids_subject_session_prefix}_acq-dwi_dir-PA_run-{item:02d}_epi')
    csf_qf_ph = create_key('{bids_subject_session_dir}/flow/{bids_subject_session_prefix}_acq-CSF_part-phase_run-{item:02d}_flow')
    csf_qf_mag = create_key('{bids_subject_session_dir}/flow/{bids_subject_session_prefix}_acq-CSF_part-mag_run-{item:02d}_flow')

    info: dict[tuple[str, tuple[str, ...], None], list] = {
        t1w: [],
        t2w: [],
        swi_mag: [],
        swi_ph: [],
        swi: [],
        swi_mIP: [],
        flair: [],
        func_rest: [],
        fmap_ap: [],
        pcasl: [],
        dwi: [],
        dwi_fmap_pa: [],
        csf_qf_ph: [],
        csf_qf_mag: [],
        }
    
    for s in seqinfo:      
        # these are one-to-one matching
        if ('mprage' in s.series_description) and (s.is_derived == False):
            info[t1w].append(s.series_id)
        if 't2_tse_tra' in s.series_description:
            info[t2w].append(s.series_id)
        if 'FLAIR' in s.series_description:
            info[flair].append(s.series_id)
        if ('ep2d_bold_moco_p2_s2 USE BIO  PA  P' in s.series_description) and (s.is_derived == False):
             info[func_rest].append(s.series_id)
        if ('ep2d_bold_moco_p2_s2 USE BIO AP' in s.series_description) and (s.is_derived == False):
             info[fmap_ap].append(s.series_id)
        if ('pcasl_3d_multiTI' in s.series_description) and (s.is_derived == False):
             info[pcasl].append(s.series_id)
        if ('ep2d_diff_mddw' in s.series_description) and (s.is_derived == False):
            if s.series_files in {1,30,31}:
                info[dwi_fmap_pa].append(s.series_id)
            elif s.series_files > 31:
                info[dwi].append(s.series_id)
            else:
                continue

        if 'csf_flow_fl2d_tra' in s.series_description:
            if 'P' == s.image_type[2]:
                info[csf_qf_ph].append(s.series_id)
            elif 'M' == s.image_type[2]:
                info[csf_qf_mag].append(s.series_id)
            else:
                continue

        if 't2_swi_tra_p3' in s.series_description:
            if 'Pha' in s.series_description:
                info[swi_ph].append(s.series_id)
            elif 'Mag' in s.series_description:
                info[swi_mag].append(s.series_id)
            elif 'SWI_mIP' in s.series_description:
                info[swi_mIP].append(s.series_id)
            elif 'SWI' in s.series_description:
                info[swi].append(s.series_id)

    return info
