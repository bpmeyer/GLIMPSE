from __future__ import annotations

import logging
from pathlib import Path
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
    "CSF_QF_retrospectivetrigger"
    }

def get_series_image_type(ds):
    """Type label for a file within a SPLIT_BY_IMAGE_TYPE series.

    Classic (single-frame) Philips exports carry the magnitude/phase
    distinction in the top-level Complex Image Component (0008,9208) tag,
    while top-level ImageType stays a generic ('ORIGINAL', 'PRIMARY',
    'FLOW_ENCODED', 'MIXED') for every file. Enhanced multi-frame files
    that have been pre-split by split_enhanced_dicom.py instead carry the
    distinction directly in top-level ImageType (e.g. M_FFE, M_PCA,
    PHASE CONTRAST M), with no Complex Image Component tag at top level.
    Combining both covers either export style.
    """
    parts = []
    complex_component = ds.get(0x00089208)
    if complex_component is not None:
        parts.append(str(complex_component.value))
    parts.extend(str(x) for x in ds.get("ImageType", ()))
    return tuple(parts)

def grouping(files, dcmfilter, seqinfo):
    groups = collections.OrderedDict()
    wrappers = {}

    for f in files:
        # Skip original enhanced DICOMs backed up by split_enhanced_dicom.py;
        # only the per-type files it wrote alongside them should be used.
        if "orig" in Path(f).parts:
            continue

        mwinfo = validate_dicom(f, dcmfilter)
        if mwinfo is None:
            continue

        mw, series_id, study_uid = mwinfo
        ds = mw.dcm_data

        series_number = ds.get("SeriesNumber", "")
        protocol_name = ds.get("ProtocolName", "")
        series_desc = ds.get("SeriesDescription", "")

        key = (
            series_number,
            protocol_name,
        )

        if series_desc in SPLIT_BY_IMAGE_TYPE:
            key = key + (get_series_image_type(ds),)

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
            image_suffix = "_".join(get_series_image_type(ds))
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

    t1w = create_key('{bids_subject_session_dir}/anat/{bids_subject_session_prefix}_run-{item:02d}_T1w')
    t2w = create_key('{bids_subject_session_dir}/anat/{bids_subject_session_prefix}_run-{item:02d}_T2w')
    dwi_ap = create_key('{bids_subject_session_dir}/dwi/{bids_subject_session_prefix}_dir-AP_run-{item:02d}_dwi')
    dwi_fmap_pa = create_key('{bids_subject_session_dir}/fmap/{bids_subject_session_prefix}_acq-dwi_dir-PA_run-{item:02d}_epi')

    pcasl_650 = create_key('{bids_subject_session_dir}/perf/{bids_subject_session_prefix}_pld-650_run-{item:02d}_asl')
    pcasl_950 = create_key('{bids_subject_session_dir}/perf/{bids_subject_session_prefix}_pld-950_run-{item:02d}_asl')
    pcasl_m0 = create_key('{bids_subject_session_dir}/perf/{bids_subject_session_prefix}_run-{item:02d}_m0scan') 

    csf_qf_ph = create_key('{bids_subject_session_dir}/flow/{bids_subject_session_prefix}_acq-CSF_part-phase_run-{item:02d}_flow')
    csf_qf_mag = create_key('{bids_subject_session_dir}/flow/{bids_subject_session_prefix}_acq-CSF_part-mag_run-{item:02d}_flow')

    
    info: dict[tuple[str, tuple[str, ...], None], list] = {
        t1w: [],
        t2w: [],
        dwi_ap: [],
        dwi_fmap_pa: [],
        pcasl_650: [],
        pcasl_950: [],
        pcasl_m0: [],
        csf_qf_ph: [],
        csf_qf_mag: [],
    }
    
    for s in seqinfo:      
        # these are one-to-one matching
        if 'MPRAGE' in s.series_description:
            info[t1w] = [s.series_id]
        if '3D_Brain_VIEW_T2' in s.series_description:
            info[t2w] = [s.series_id]
        if 'DTI_IVIM_14b0_APA' in s.series_description:
            info[dwi_ap] = [s.series_id]
        if 'DTI_IVIM_b0_APP' in s.series_description:
            info[dwi_fmap_pa] = [s.series_id]
        if  s.series_description == 'MEASL_M0_NEW':
            info[pcasl_m0].append(s.series_id)
        if s.series_description == 'MEASL_950':
            info[pcasl_950].append(s.series_id) 
        if s.series_description == 'MEASL_650':
            info[pcasl_650].append(s.series_id) 


        if 'CSF_QF' in s.series_description:
            image_suffix = get_image_suffix(s)
            # Enhanced (pre-split) files: 'PHASE CONTRAST M' / 'M_FFE' in ImageType.
            # Classic per-file exports: suffix starts with Complex Image
            # Component 'PHASE' / 'MAGNITUDE' instead.
            if 'PHASE CONTRAST M' in image_suffix or image_suffix.startswith('PHASE'):
                info[csf_qf_ph].append(s.series_id)
            elif 'M_FFE' in image_suffix or image_suffix.startswith('MAGNITUDE'):
                info[csf_qf_mag].append(s.series_id)
            else:
                continue

    return info
