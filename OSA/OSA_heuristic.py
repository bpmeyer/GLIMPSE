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
        cic = ds.get("ComplexImageComponent", "")

        key = (
            series_number,
            protocol_name,
        )

        if series_desc in SPLIT_BY_IMAGE_TYPE:
            key = key + (cic,)

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
            cic = ds.get("ComplexImageComponent", "")
            series_id = f"{series_id}-{cic}"

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
    
    asl_650 = create_key('{bids_subject_session_dir}/perf/{bids_subject_session_prefix}_acq-650_asl')
    asl_950 = create_key('{bids_subject_session_dir}/perf/{bids_subject_session_prefix}_acq-950_asl')
    m0 = create_key('{bids_subject_session_dir}/perf/{bids_subject_session_prefix}_M0scan')
    pcasl1 = create_key('{bids_subject_session_dir}/perf/{bids_subject_session_prefix}_acq-pcasl1_asl')
    pcasl2 = create_key('{bids_subject_session_dir}/perf/{bids_subject_session_prefix}_acq-pcasl2_asl')
    pcasl3 = create_key('{bids_subject_session_dir}/perf/{bids_subject_session_prefix}_acq-pcasl3_asl')
    
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

        asl_650: [],
        asl_950: [],
        m0: [],
        pcasl1: [],
        pcasl2: [],
        pcasl3: [],
    }
    
    for s in seqinfo:      
        # these are one-to-one matching
        if 'MPRAGE' in s.series_description:
            info[t1w] = [s.series_id]
        if '3D_Brain_VIEW_T2' in s.series_description:
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

        if 'CSF_QF' in s.series_description:
            image_suffix = get_image_suffix(s).upper()
            if image_suffix == 'PHASE':
                info[csf_qf_ph].append(s.series_id)
            elif image_suffix == 'MAGNITUDE':
                info[csf_qf_mag].append(s.series_id)
            else:
                continue
        
        if 'MEASL_650' in s.series_description:
            info[asl_650] = [s.series_id]

        if 'MEASL_950' in s.series_description:
            info[asl_950] = [s.series_id]

        if 'MEASL_M0' in s.series_description:
            info[m0] = [s.series_id]

        if '3D_pCASL_6mm_H4_900BS' in s.series_description:
            if s.series_id.startswith('703-'):
                info[pcasl1] = [s.series_id]
            elif s.series_id.startswith('803-'):
                info[pcasl2] = [s.series_id]
            elif s.series_id.startswith('902-'):
                info[pcasl3] = [s.series_id]

    return info