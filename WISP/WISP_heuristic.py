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
    "CSF_QF_retrospectivetrigger",
    "hT2W_IRSE",
    }

def grouping(files, dcmfilter, seqinfo):
    groups = collections.OrderedDict()
    wrappers = {}

    for f in files:
        mwinfo = validate_dicom(f, dcmfilter)
        if mwinfo is None:
            continue

        mw, series_id, study_uid = mwinfo
        ds = mw.dcm_data

        series_number = ds.get("SeriesNumber", "")
        protocol_name = ds.get("ProtocolName", "")
        series_desc = ds.get("SeriesDescription", "")
        image_type = tuple(ds.get("ImageType", ()))

        key = (
            series_number,
            protocol_name,
        )

        if series_desc in SPLIT_BY_IMAGE_TYPE:
            key = key + (image_type,)

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

        si = create_seqinfo(mw, series_files, series_id)
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
    
    t1w = create_key('{bids_subject_session_dir}/anat/{bids_subject_session_prefix}_T1w')
    t2w = create_key('{bids_subject_session_dir}/anat/{bids_subject_session_prefix}_T2w')
    func_rest = create_key('{bids_subject_session_dir}/func/{bids_subject_session_prefix}_task-rest_bold')
    fmap_ap = create_key('{bids_subject_session_dir}/fmap/{bids_subject_session_prefix}_acq-func_dir-AP_epi')
    fmap_pa = create_key('{bids_subject_session_dir}/fmap/{bids_subject_session_prefix}_acq-func_dir-PA_epi')
    dwi_ap = create_key('{bids_subject_session_dir}/dwi/{bids_subject_session_prefix}_dir-AP_dwi')
    dwi_fmap_pa = create_key('{bids_subject_session_dir}/fmap/{bids_subject_session_prefix}_acq-dwi_dir-PA_epi')

    csf_qf_ph = create_key('{bids_subject_session_dir}/flow/{bids_subject_session_prefix}_acq-CSF_part-phase_flow')
    csf_qf_mag = create_key('{bids_subject_session_dir}/flow/{bids_subject_session_prefix}_acq-CSF_part-mag_flow')

    ir_cr = create_key('sub-{subject}/{session}/mixed/{bids_subject_session_prefix}_acq-mixed_IR-corrected-real')
    se_m = create_key('sub-{subject}/{session}/mixed/{bids_subject_session_prefix}_acq-mixed_SE-modulus')
    
    info: dict[tuple[str, tuple[str, ...], None], list] = {
        t1w: [],
        t2w: [],
        func_rest: [],
        fmap_ap: [],
        fmap_pa: [],
        dwi_ap: [],
        dwi_fmap_pa: [],
        csf_qf_ph: [],
        csf_qf_mag: [],
        ir_cr: [],
        se_m: [],
    }
    
    for s in seqinfo:      
        # these are one-to-one matching
        if 'T1W_3D_TFE' in s.series_description:
            info[t1w] = [s.series_id]
        if 'T2W_3D_Brain' in s.series_description:
            info[t2w] = [s.series_id]
        if 'fFMRI_MB8_SENSE' in s.series_description:
            info[func_rest] = [s.series_id]
        if 'fMRI_SEAPA' in s.series_description:
            info[fmap_ap] = [s.series_id]
        if 'fMRI_SEAPP' in s.series_description:
            info[fmap_pa] = [s.series_id]
        if 'DTI_IVIM_14b0_APA' in s.series_description:
            info[dwi_ap] = [s.series_id]
        if 'DTI_IVIM_b0_APP' in s.series_description:
            info[dwi_fmap_pa] = [s.series_id]


        if 'hT2W_IRSE' in s.series_description:
            image_suffix = get_image_suffix(s)
            if "CR_IR" in image_suffix:
                info[ir_cr].append(s.series_id)
            elif "M_SE" in image_suffix:
                info[se_m].append(s.series_id)
            else:
                continue

        if 'CSF_QF' in s.series_description:
            image_suffix = get_image_suffix(s)
            if 'PHASE CONTRAST M' in image_suffix:
                info[csf_qf_ph].append(s.series_id)
            elif 'M_FFE' in image_suffix:
                info[csf_qf_mag].append(s.series_id)
            else:
                continue

    return info
