#!/usr/local/anaconda3/bin/python3

import subprocess 
import os.path as op
import os
import json 
from glob import glob 

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




	


