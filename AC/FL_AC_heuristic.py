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
    "CSF_QF_retrospectivetrigger"
    }

def grouping(files, dcmfilter, seqinfo):
    groups = collections.OrderedDict()
    wrappers = {}

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
    data = create_key('run-{item:02d}')
    t1w = create_key('{bids_subject_session_dir}/anat/{bids_subject_session_prefix}_run-{item:02d}_T1w')
    flair = create_key('{bids_subject_session_dir}/anat/{bids_subject_session_prefix}_run-{item:02d}_FLAIR')
    # func_rest = create_key('{bids_subject_session_dir}/func/{bids_subject_session_prefix}_task-rest_run-{item:02d}_bold')
    # fmap_ap = create_key('{bids_subject_session_dir}/fmap/{bids_subject_session_prefix}_acq-func_dir-AP_run-{item:02d}_epi')
    # fmap_pa = create_key('{bids_subject_session_dir}/fmap/{bids_subject_session_prefix}_acq-func_dir-PA_run-{item:02d}_epi')
    
    
    info: dict[tuple[str, tuple[str, ...], None], list] = {
        t1w: [],
        flair: [],
        # func_rest: [],
        # fmap_ap: [],
        # fmap_pa: [],
    }
    
    for s in seqinfo:      
        # these are one-to-one matching
        if 'mprage' in s.series_description:
            info[t1w] = [s.series_id]
        if 'FLAIR' in s.series_description:
            info[flair] = [s.series_id]
        # if ('fMRI_MB4_3mm' in s.series_description) and (s.series_files >= 100):
        #     info[func_rest] = [s.series_id]
        # if 'fMRI_SEAPA' in s.series_description:
        #     info[fmap_ap] = [s.series_id]
        # if 'fMRI_SEAPP' in s.series_description:
        #     info[fmap_pa] = [s.series_id]

    return info
