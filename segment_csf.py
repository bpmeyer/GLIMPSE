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

def estimate_t1_times(subject: str, session: str, project: str):

    '''Function to estimate the T1 Times using gmri2fem
    
    Parameters:
    -----------
        subject (str): Subject ID Number
        session (str): Session Number 
        project (str): The path to the project's root directory.
    
    Returns: 
    --------
        out_fname (nifti): The raw estimated mixed T1 Map. 
        post_fname (nifti): The postprocessed mixed T1 Map.

    '''

    mixed_dir = op.join(project, 'sourcedata', 'nifti', f'sub-{subject}', f'ses-{session}', 'mixed')
    out_dir = op.join(project, 'derivatives', 'csf_seg', f'sub-{subject}', f'ses-{session}')
    os.makedirs(out_dir, exist_ok=True)

    se_fname = op.join(mixed_dir, f'sub-{subject}_ses-{session}_acq-mixed_SE-modulus.nii.gz')
    ir_fname = op.join(mixed_dir, f'sub-{subject}_ses-{session}_acq-mixed_IR-corrected-real.nii.gz')
    meta_fname = op.join(mixed_dir, f'sub-{subject}_ses-{session}_acq-mixed_meta.json')
    out_fname = op.join(out_dir, f'sub-{subject}_ses-{session}_acq-mixed_T1map_raw.nii.gz')
    post_fname = op.join(out_dir, f'sub-{subject}_ses-{session}_acq-mixed_T1map_postproc.nii.gz')

    shell_cmd = [f'--SE', f'{se_fname}', 
                 f'--IR', f'{ir_fname}', 
                 f'--meta', f'{meta_fname}', 
                 f'--output', f'{out_fname}', 
                 f'--postprocessed', f'{post_fname}'] 

    if not op.isfile(meta_fname): 
        make_mixed_meta(subject, session, meta_fname, project)

    return subprocess.run(['gmri2fem', 'mri', 'mixed-t1map'] + shell_cmd)

def make_mixed_meta(subject:str, session: str, meta_fname:str, project:str): 

    '''Function to extract meta data from the SE-modulus and IR-corrected-real nifti sidecar files.
    
    Parameters:
    -----------
        subject (str): Subject ID Number
        session (str): Session Number 
        meta_fname (Path | str): The path to the meta data file (should be json). 
        project (str): The path to the project's root directory.
    
    Returns: 
    --------
        meta_fname (json): File that contains required metadata for gmri2fem mri mixed-T1map.

    '''

    dcm_path = op.join(project, 'sourcedata', 'dicom', )
    mixed_dir = op.join(project, 'sourcedata', 'nifti', f'sub-{subject}', f'ses-{session}', 'mixed')

    meta = {}
    subvolumes = ['SE-modulus', 'IR-corrected-real']
    for subvol in subvolumes: 
        sidecar_fn = op.join(mixed_dir, f'sub-{subject}_ses-{session}_acq-mixed_{subvol}.json')

        # Open the file and parse the JSON data
        with open(sidecar_fn, "r") as f:
            sidecar_data = json.load(f)
        
        if 'SE' in subvol:
            meta["TR_SE"] = sidecar_data['RepetitionTime']
            meta["TE"] = sidecar_data['EchoTime']
            meta["ETL"] = sidecar_data['EchoTrainLength']

        elif 'IR' in subvol: 
            meta["TR_IR"] = sidecar_data['RepetitionTime']
            meta["TI"] = sidecar_data['InversionTime']

    print(f'Saving Metadata to {meta_fname}')
    with open(meta_fname, "w") as f:
        json.dump(meta, f)

    return 

def allsubs_t1_times(project):

    nifti_dir = op.join(project, 'sourcedata', 'nifti')
    subs = sorted([op.basename(s).split('-')[1] for s in glob(op.join(nifti_dir, 'sub-*'))])

    scans = {}
    for sub in subs: 
        scans[sub] = [op.basename(s).split('-')[1] for s in glob(op.join(nifti_dir, f'sub-{sub}', 'ses-*'))]
    
    for sub, sessions in scans.items(): 
        print(f'Processing Subject {sub}')
        for ses in sessions: 
            print(f'\tProcessing Session {ses}')
            estimate_t1_times(sub, ses, project)

def allsubs_reg_SE(project, greedy_fn): 

    nifti_dir = op.join(project, 'sourcedata', 'nifti')
    subs = sorted([op.basename(s).split('-')[1] for s in glob(op.join(nifti_dir, 'sub-*'))])

    for sub in subs: 
        register_SE_T1_greedy(sub, project, greedy_fn)

def allsubs_reg_T1maps(project, greedy_fn): 

    nifti_dir = op.join(project, 'sourcedata', 'nifti')
    subs = sorted([op.basename(s).split('-')[1] for s in glob(op.join(nifti_dir, 'sub-*'))])

    for sub in subs: 
        register_T1maps_greedy(sub, project, greedy_fn)

def register_SE_T1_greedy(subject: str, project: str, greedy_fn:str, reference_ses: str ='01'):

    '''
    Function to register the first SE scan to the T1 space. 

    Parameters: 
    -----------
        subject (str): The Subject ID Number.
        reference_ses (str): The SE session to align other images with. Default: Visit 1
        greedy_fn (str): The path to the greedy sif file.
        project (Path | str): The path to the project directory.

    Returns: 
    --------
    '''

    mixed_dir = op.join(project, 'sourcedata', 'nifti', f'sub-{subject}', f'ses-{reference_ses}', 'mixed')
    anat_dir = op.join(project, 'sourcedata', 'nifti', f'sub-{subject}', f'ses-{reference_ses}', 'anat')
    out_dir = op.join(project, 'derivatives', 'csf_seg', f'sub-{subject}', f'ses-{reference_ses}')

    se0_basename = f'sub-{subject}_ses-{reference_ses}_acq-mixed_SE-modulus.nii.gz'
    sereg_basename = f'sub-{subject}_ses-{reference_ses}_acq-mixed_SE-modulus_registered.nii.gz' 
    xfm_basename = f'sub-{subject}_ses-{reference_ses}_acq-mixed.mat'
    t1_basename = f'sub-{subject}_ses-{reference_ses}_T1w.nii.gz'

    app_cmd = ['apptainer', 'exec', 
                '--bind', f'{mixed_dir}:{mixed_dir}', 
                '--bind', f'{anat_dir}:{anat_dir}', 
                '--bind', f'{out_dir}:{out_dir}', 
                greedy_fn]

    affine_cmd = ['greedy', '-d', '3', '-a', 
                '-i', f'{anat_dir}/{t1_basename}', f'{mixed_dir}/{se0_basename}', 
                '-o', f'{out_dir}/{xfm_basename}',
                '-ia-image-centers', 
                '-dof', '6', 
                '-m', 'NMI']

    subprocess.run(app_cmd + affine_cmd) 

    register_cmd = ['greedy', '-d', '3', 
                '-rf', f'{anat_dir}/{t1_basename}', 
                '-ri', 'NN', 
                '-rm', f'{mixed_dir}/{se0_basename}', f'{out_dir}/{sereg_basename}',
                '-r', f'{out_dir}/{xfm_basename}']

    subprocess.run(app_cmd + register_cmd)

    return 

def register_T1maps_greedy(subject: str, project: str, greedy_fn:str, reference_ses: str ='01'):

    '''
    Function to register the non-reference SE scans to the T1 space of the SE reference scan. 

    Parameters: 
    -----------
        subject (str): The Subject ID Number.
        reference_ses (str): The SE session to align other images with. Default: Visit 1
        greedy_fn (str): The path to the greedy sif file.
        project (Path | str): The path to the project directory.

    Returns: 
    --------
    '''
    nifti_dir = op.join(project, 'sourcedata', 'nifti')

    ref_mixed_dir = op.join(project, 'sourcedata', 'nifti', f'sub-{subject}', f'ses-{reference_ses}', 'mixed')
    ref_anat_dir = op.join(project, 'sourcedata', 'nifti', f'sub-{subject}', f'ses-{reference_ses}', 'anat')
    ref_out_dir = op.join(project, 'derivatives', 'csf_seg', f'sub-{subject}', f'ses-{reference_ses}')

    ref_sereg_basename = f'sub-{subject}_ses-{reference_ses}_acq-mixed_SE-modulus_registered.nii.gz' 
    ref_t1_basename = f'sub-{subject}_ses-{reference_ses}_T1w.nii.gz'
    
    sessions = sorted([op.basename(s).split('-')[1] for s in glob(op.join(nifti_dir, f'sub-{subject}', 'ses-*'))])


    for ses in sessions: 

        print(f'Registering Sub-{subject} SE Session {ses} to SE Reference')

        mixed_dir = op.join(project, 'sourcedata', 'nifti', f'sub-{subject}', f'ses-{ses}', 'mixed')
        anat_dir = op.join(project, 'sourcedata', 'nifti', f'sub-{subject}', f'ses-{ses}', 'anat')
        out_dir = op.join(project, 'derivatives', 'csf_seg', f'sub-{subject}', f'ses-{ses}')

        ses_se0_basename = f'sub-{subject}_ses-{ses}_acq-mixed_SE-modulus.nii.gz' 
        ses_xfm_basename = f'sub-{subject}_ses-{ses}_acq-mixed.mat'
        ses_t1_basename = f'sub-{subject}_ses-{ses}_T1w.nii.gz'
        ses_t1map_basename = f'sub-{subject}_ses-{ses}_acq-mixed_T1map_postproc.nii.gz'
        ses_t1map_reg_basename = f'sub-{subject}_ses-{ses}_acq-mixed_T1map_postproc_registered.nii.gz'

        if ses != reference_ses: 

            app_cmd = ['apptainer', 'exec', 
                '--bind', f'{mixed_dir}:{mixed_dir}', 
                '--bind', f'{ref_anat_dir}:{ref_anat_dir}', 
                '--bind', f'{out_dir}:{out_dir}', 
                '--bind', f'{ref_out_dir}:{ref_out_dir}',
                greedy_fn]

            affine_cmd = ['greedy', '-d', '3', '-a', 
                '-i', f'{ref_out_dir}/{ref_sereg_basename}', f'{mixed_dir}/{ses_se0_basename}', 
                '-o', f'{out_dir}/{ses_xfm_basename}',
                '-ia-image-centers', 
                '-dof', '6', 
                '-m', 'NCC', '5x5x5']
            
            subprocess.run(app_cmd + affine_cmd)
        
        else: 

            app_cmd = ['apptainer', 'exec', 
                '--bind', f'{mixed_dir}:{mixed_dir}', 
                '--bind', f'{ref_anat_dir}:{ref_anat_dir}', 
                '--bind', f'{out_dir}:{out_dir}', 
                greedy_fn]

        print(f'Aligning Sub-{subject} T1Map Session {ses} to T1 Reference')

        register_cmd = ['greedy', '-d', '3', 
            '-rf', f'{ref_anat_dir}/{ref_t1_basename}', 
            '-ri', 'NN', 
            '-rm', f'{out_dir}/{ses_t1map_basename}', f'{out_dir}/{ses_t1map_reg_basename}',
            '-r', f'{out_dir}/{ses_xfm_basename}']

        subprocess.run(app_cmd + register_cmd)

    return
