#!/usr/local/anaconda3/bin/python3

import os 
# Set the Thread Count
os.environ["ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS"] = "16"  
import os.path as op
import json 
from glob import glob 
import ants
from pathlib import Path
import nibabel as nib
import subprocess
import numpy as np
import simple_mri as sm
from pprint import pprint

from gmri2fem.csf_segmentation import create_csf_seg, create_precsf_seg, PRECSF_EXCLUDED_SEGMENTS
from gmri2fem.masking import create_csf_mask
from gmri2fem.segmentation_refinement import extrapolate_segmentation_to_mask
from gmri2fem import segment_tools as segtools
from gmri2fem.segment_tools import find_description_label, find_label_description


def register_aseg(subject:str, project:str, reference_ses: str ='01'): 

    fs_dir = op.join(project, 'derivatives', 'freesurfer', 
                     f'sub-{subject}_ses-{reference_ses}', 'mri')
    anat_dir = op.join(project, 'sourcedata', 'nifti', 
                     f'sub-{subject}', f'ses-{reference_ses}', 'anat')

    aseg_fn = op.join(fs_dir, 'aparc+aseg.mgz')
    aseg_nat_fn = op.join(fs_dir, 'aparc+aseg_native.mgz') 
    t1_fn = op.join(anat_dir, f'sub-{subject}_ses-{reference_ses}_T1w.nii.gz')
    
    aseg_im = ants.image_read(aseg_fn)
    t1_im = ants.image_read(t1_fn)

    xfm = ants.registration(fixed = t1_im, moving = aseg_im, 
                            type_of_transform='Rigid')

    aseg_reg_im = ants.apply_transforms(fixed = t1_im, moving=aseg_im, 
                                       transformlist = xfm['fwdtransforms'], 
                                       interpolator='nearestNeighbor')

    ants.image_write(aseg_reg_im, aseg_nat_fn)

def create_csf_segmentation(subject, project, reference_ses:str ='01'): 

    os.environ['FREESURFER_HOME'] = '/usr/local/freesurfer/stable8'

    fs_dir = op.join(project, 'derivatives', 'freesurfer', 
                     f'sub-{subject}_ses-{reference_ses}', 'mri')
    mixed_dir = op.join(project, 'derivatives', 'csf_seg', 
                        f'sub-{subject}', f'ses-{reference_ses}')
    out_dir = op.join(mixed_dir, 'segmentations')
    os.makedirs(out_dir, exist_ok=True)

    aseg_fn = op.join(fs_dir, 'aparc+aseg.mgz') 
    sereg_fn = op.join(mixed_dir, f'sub-{subject}_ses-{reference_ses}_acq-mixed_SE-modulus_registered.nii.gz') 

    sereg_im = sm.load_mri(sereg_fn, dtype=np.float32)
    aseg_im = sm.load_mri(aseg_fn, dtype=np.int16)

    # lut_table = segtools.read_lut(op.join(os.environ['FREESURFER_HOME'], "FreeSurferColorLUT.txt"))

    # labs = sorted([find_description_label(lab, lut_table) for lab in PRECSF_EXCLUDED_SEGMENTS])
    # print(labs)

    # csf_seg_im = create_csf_seg(aseg_im, sereg_im)

    ### Pre-CSF Segmentation - All Descs in PRECSF_EXCLUDED_LABELS set to 0
    precsf_seg_dat = create_precsf_seg(aseg_im.data)
    precsf_seg_im = sm.SimpleMRI(precsf_seg_dat, aseg_im.affine)
    sm.save_mri(precsf_seg_im,
                op.join(out_dir, f'sub-{subject}_seg-precsf_seg.nii.gz'),
                dtype=aseg_im.data.dtype)
    
    ### Create CSF Mask 
    csf_mask_data = create_csf_mask(sereg_im.data)
    csf_mask_im = sm.SimpleMRI(csf_mask_data, sereg_im.affine)
    sm.save_mri(csf_mask_im, 
                op.join(out_dir, f'sub-{subject}_seg-csf_mask.nii.gz'), 
                dtype=np.int16)

    ### Extrapolate 
    csf_seg_im = extrapolate_segmentation_to_mask(precsf_seg_im, csf_mask_im)
    sm.save_mri(csf_seg_im, 
                op.join(out_dir, f'sub-{subject}_seg-csf_seg.nii.gz'), 
                dtype=np.uint8)

def gather_groups():

    def _desc_to_cortex_labels(description_list):

        """Map a cortical region-description to it's corresponding FreeSurfer name
        for both left and right hemisphere."""

        return (
            [f'ctx-lh-{d.lower().replace(" ", "")}' for d in description_list]
            + [f'ctx-rh-{d.lower().replace(" ", "")}' for d in description_list]
        )

    ventricles = ["3rd-Ventricle", "4th-Ventricle",
                  "Left-Lateral-Ventricle", "Right-Lateral-Ventricle",
                  "Left-Inf-Lat-Vent", "Right-Inf-Lat-Vent"]
    infratentorial = ["Brain-Stem",
                    "Left-Cerebellum-Cortex", "Right-Cerebellum-Cortex"]
    basal = [*_desc_to_cortex_labels(["medial orbitofrontal", "fusiform", "frontal pole"]),
            "Optic-Chiasm", 
            "Left-VentralDC", "Right-VentralDC",
            "Left-Hippocampus", "Right-Hippocampus"]
    medial = _desc_to_cortex_labels(["Posterior cingulate", "Rostral anterior cingulate", "Caudal anterior cingulate",
                               "Superiorfrontal", "Precuneus", "Isthmus cingulate",
                               "Paracentral", "Cuneus", "Lingual", "Pericalcarine", 
                               "Entorhinal", "Parahippocampal"])
    insula = _desc_to_cortex_labels(["Insula"])
    
    return {"ventricles": ventricles,
            "infratentorial": infratentorial,
            "basal": basal,
            "medial": medial,
            "insula": insula
            }

def create_grouped_segmentation(subject, project, freesurfer_home:str, reference_ses:str = '01'):

    # read csf segmentation file
    mixed_dir = op.join(project, 'derivatives', 'csf_seg', f'sub-{subject}', f'ses-{reference_ses}')
    out_dir = op.join(mixed_dir, 'segmentations')

    csf_seg_fn = op.join(out_dir, f'sub-{subject}_seg-csf_seg.nii.gz')
    csf_seg_mri = sm.load_mri(csf_seg_fn, dtype=np.uint8)

    grouped_seg_fn = op.join(out_dir, f"sub-{subject}_seg-csf_grouped.nii.gz")
    grouped_lut_fn = op.join(out_dir, f"sub-{subject}_seg-csf_grouped_LUT.txt") 

    # {group: [desc from LUT]}
    groups = gather_groups()

    # Read LUT into pd.dataframe
    lut_table = segtools.read_lut(op.join(freesurfer_home, 'FreeSurferColorLUT.txt'))

    # Gather all labels from 
    labels = np.unique(csf_seg_mri.data[csf_seg_mri.data > 0])

    ### Relabel labels in csf_seg that are not in groups as 'lateral'
    ## Get master list of group descriptions
    grouped_descriptions = sum(groups.values(), start=[])
    ## Get master list of group labels
    grouped_labels = [find_description_label(x, lut_table) for x in grouped_descriptions]
    ## Add labels in csf_seg to groups under 'lateral' key
    groups["lateral"] = [find_label_description(x, lut_table) for x in labels[~np.isin(labels, grouped_labels)] ]
    
    # Get dict of numeric labels: {group : [numeric label from LUT]}
    relabeling = {group: [segtools.find_description_label(x, lut_table) 
                            for x in group_descriptions]
                                for group, group_descriptions in groups.items()}
    
    grouped_seg = segtools.collapse(csf_seg_mri.data, relabeling)
    grouped_seg_mri = sm.SimpleMRI(grouped_seg, csf_seg_mri.affine)
    sm.save_mri(grouped_seg_mri, grouped_seg_fn, np.int16)

    # Also create a lookup-table for identifying regions
    grouped_lut = segtools.canonical_lut(relabeling, "jet", permute_colors=None)

    segtools.write_lut(grouped_lut_fn, grouped_lut)

def create_cvs_segmentation(subject, project, freesurfer_home:str, reference_ses:str = '01'):

    # read csf segmentation file
    mixed_dir = op.join(project, 'derivatives', 'csf_seg', f'sub-{subject}', f'ses-{reference_ses}')
    out_dir = op.join(mixed_dir, 'segmentations')
    csf_seg_fn = op.join(out_dir, f'sub-{subject}_seg-csf_seg.nii.gz')
    csf_seg_mri = sm.load_mri(csf_seg_fn, dtype=np.uint8)

    cvs_seg_fn = op.join(out_dir, f"sub-{subject}_seg-csf_sas-ventricle-cerebellum.nii.gz")
    cvs_seg_lut_fn = op.join(out_dir, f'sub-{subject}_seg-csf_sas-ventricle-cerebellum-LUT.txt') 

    lut_table = segtools.read_lut(op.join(freesurfer_home, 'FreeSurferColorLUT.txt'))

    # Cerebellum Descriptions
    cerebellum = ["Left-Cerebellum-Cortex", "Right-Cerebellum-Cortex"]
    ventricles = gather_groups()['ventricles']

    # Gathering Labels in csf_mask
    labels = np.unique(csf_seg_mri.data[csf_seg_mri.data > 0])

    # Creating C/V/S dict with relevent labels {group: [numeric label]}
    relabeling = {"cerebellum": [find_description_label(x, lut_table) for x in cerebellum],
                  "ventricles": [find_description_label(x, lut_table) for x in ventricles]}
    ### SAS is all labels that are not cerebellum or ventricular 
    relabeling["SAS"]= list(labels[~np.isin(labels, relabeling["cerebellum"] + relabeling["ventricles"])])

    # Making Dict of the groups {group: [description from LUT]} 
    groups = {desc: [find_label_description(x, lut_table) for x in group_labels]
        for desc, group_labels in relabeling.items()}  
    
    # Create LUT for segmentation 
    cvs_lut = segtools.canonical_lut(relabeling, "viridis", permute_colors=None)

    # Create segmentation for cerebellum, ventricular and SAS CSF
    newseg = segtools.collapse(csf_seg_mri.data, relabeling)
    newseg_mri = sm.SimpleMRI(newseg, csf_seg_mri.affine)
    
    # Save the segementation and the LUT
    sm.save_mri(newseg_mri, cvs_seg_fn, np.int16)
    segtools.write_lut(cvs_seg_lut_fn, cvs_lut)

