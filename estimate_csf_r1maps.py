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
from gmri2fem.csf_segmentation import create_csf_seg

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

    ### Directories
    mixed_dir = op.join(project, 'sourcedata', 'nifti', f'sub-{subject}', f'ses-{session}', 'mixed')
    out_dir = op.join(project, 'derivatives', 'csf_seg', f'sub-{subject}', f'ses-{session}')
    os.makedirs(out_dir, exist_ok=True)

    ### Gathering Filenames
    se_fname = op.join(mixed_dir, f'sub-{subject}_ses-{session}_acq-mixed_SE-modulus.nii.gz')
    ir_fname = op.join(mixed_dir, f'sub-{subject}_ses-{session}_acq-mixed_IR-corrected-real.nii.gz')
    meta_fname = op.join(mixed_dir, f'sub-{subject}_ses-{session}_acq-mixed_meta.json')
    out_fname = op.join(out_dir, f'sub-{subject}_ses-{session}_acq-mixed_T1map_raw.nii.gz')
    post_fname = op.join(out_dir, f'sub-{subject}_ses-{session}_acq-mixed_T1map_postproc.nii.gz')

    ### Setup Args for `mixed-t1map`
    shell_cmd = [f'--SE', f'{se_fname}', 
                 f'--IR', f'{ir_fname}', 
                 f'--meta', f'{meta_fname}', 
                 f'--output', f'{out_fname}', 
                 f'--postprocessed', f'{post_fname}'] 

    ### If the metadata file is not present, make it 
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
    ### Directories
    dcm_path = op.join(project, 'sourcedata', 'dicom', )
    mixed_dir = op.join(project, 'sourcedata', 'nifti', f'sub-{subject}', f'ses-{session}', 'mixed')

    ### Create Dict to store the metadata files from the niftis
    ## This is based on the documentation here: 
    ## https://github.com/jorgenriseth/gMRI2FEM/blob/f11a9961b3689250d7fd6cf41357dd7d99a53f68/src/gmri2fem/mixed_dicom.py#L71
    meta = {}
    subvolumes = ['SE-modulus', 'IR-corrected-real']
    for subvol in subvolumes: 
        sidecar_fn = op.join(mixed_dir, f'sub-{subject}_ses-{session}_acq-mixed_{subvol}.json')

        # Open the file and parse the JSON data
        with open(sidecar_fn, "r") as f:
            sidecar_data = json.load(f)
        
        if 'SE' in subvol:
            meta["TR_SE"] = sidecar_data['RepetitionTime'] * 1000
            meta["TE"] = sidecar_data['EchoTime'] * 1000 
            meta["ETL"] = sidecar_data['EchoTrainLength'] * 1000

        elif 'IR' in subvol: 
            meta["TR_IR"] = sidecar_data['RepetitionTime'] * 1000
            meta["TI"] = sidecar_data['InversionTime'] * 1000

    print(f'Saving Metadata to {meta_fname}')
    with open(meta_fname, "w") as f:
        json.dump(meta, f)

    return 

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
        sereg_basename (nifti) : Registered reference SE image.

    '''

    ### Directories 
    mixed_dir = op.join(project, 'sourcedata', 'nifti', f'sub-{subject}', f'ses-{reference_ses}', 'mixed')
    anat_dir = op.join(project, 'sourcedata', 'nifti', f'sub-{subject}', f'ses-{reference_ses}', 'anat')
    out_dir = op.join(project, 'derivatives', 'csf_seg', f'sub-{subject}', f'ses-{reference_ses}')

    ### Filenames 
    se0_basename = f'sub-{subject}_ses-{reference_ses}_acq-mixed_SE-modulus.nii.gz'
    sereg_basename = f'sub-{subject}_ses-{reference_ses}_acq-mixed_SE-modulus_registered.nii.gz' 
    xfm_basename = f'sub-{subject}_ses-{reference_ses}_acq-mixed.mat'
    t1_basename = f'sub-{subject}_ses-{reference_ses}_T1w.nii.gz'

    ### Setting up the greedy container 
    app_cmd = ['apptainer', 'exec', 
                '--bind', f'{mixed_dir}:{mixed_dir}', 
                '--bind', f'{anat_dir}:{anat_dir}', 
                '--bind', f'{out_dir}:{out_dir}', 
                greedy_fn]

    ### Greedy Affine Registration
    affine_cmd = ['greedy', '-d', '3', '-a', 
                '-i', f'{anat_dir}/{t1_basename}', f'{mixed_dir}/{se0_basename}', 
                '-o', f'{out_dir}/{xfm_basename}',
                '-ia-image-centers', 
                '-dof', '6', 
                '-m', 'NMI']

    subprocess.run(app_cmd + affine_cmd) 

    ### Applying the Registration 
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

    ### Directories 
    nifti_dir = op.join(project, 'sourcedata', 'nifti')
    ref_mixed_dir = op.join(nifti_dir, f'sub-{subject}', f'ses-{reference_ses}', 'mixed')
    ref_anat_dir = op.join(nifti_dir, f'sub-{subject}', f'ses-{reference_ses}', 'anat')
    ref_out_dir = op.join(project, 'derivatives', 'csf_seg', f'sub-{subject}', f'ses-{reference_ses}')

    ### Filenames
    ref_sereg_basename = f'sub-{subject}_ses-{reference_ses}_acq-mixed_SE-modulus_registered.nii.gz' 
    ref_t1_basename = f'sub-{subject}_ses-{reference_ses}_T1w.nii.gz'
    
    ### Gathering the list of Sessions for Subject
    sessions = sorted([op.basename(s).split('-')[1] for s in glob(op.join(nifti_dir, f'sub-{subject}', 'ses-*'))])

    ### Looping over Sessions
    for ses in sessions: 

        print(f'Registering Sub-{subject} SE Session {ses} to SE Reference')

        ### Session-Specific Directories 
        mixed_dir = op.join(project, 'sourcedata', 'nifti', f'sub-{subject}', f'ses-{ses}', 'mixed')
        anat_dir = op.join(project, 'sourcedata', 'nifti', f'sub-{subject}', f'ses-{ses}', 'anat')
        out_dir = op.join(project, 'derivatives', 'csf_seg', f'sub-{subject}', f'ses-{ses}')

        ### Session Specific Filenames
        ses_se0_basename = f'sub-{subject}_ses-{ses}_acq-mixed_SE-modulus.nii.gz' 
        ses_xfm_basename = f'sub-{subject}_ses-{ses}_acq-mixed.mat'
        ses_t1_basename = f'sub-{subject}_ses-{ses}_T1w.nii.gz'
        ses_t1map_basename = f'sub-{subject}_ses-{ses}_acq-mixed_T1map_postproc.nii.gz'
        ses_t1map_reg_basename = f'sub-{subject}_ses-{ses}_acq-mixed_T1map_postproc_registered.nii.gz'

        ### For the nonreference sessions, calculate the registration
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
        
        ### For the reference Session, just setup the container 
        else: 

            app_cmd = ['apptainer', 'exec', 
                '--bind', f'{mixed_dir}:{mixed_dir}', 
                '--bind', f'{ref_anat_dir}:{ref_anat_dir}', 
                '--bind', f'{out_dir}:{out_dir}', 
                greedy_fn]

        print(f'Aligning Sub-{subject} T1Map Session {ses} to T1 Reference')

        ### Apply the registration to the session to get it into the SE registered space for reference scan
        register_cmd = ['greedy', '-d', '3', 
            '-rf', f'{ref_anat_dir}/{ref_t1_basename}', 
            '-ri', 'NN', 
            '-rm', f'{out_dir}/{ses_t1map_basename}', f'{out_dir}/{ses_t1map_reg_basename}',
            '-r', f'{out_dir}/{ses_xfm_basename}']

        subprocess.run(app_cmd + register_cmd)

    return

def create_R1_map(subject:str, session:str, project: str):

    out_dir = op.join(project, 'derivatives', 'csf_seg', f'sub-{subject}', f'ses-{session}')
    t1map_basename = f'sub-{subject}_ses-{session}_acq-mixed_T1map_postproc_registered.nii.gz'
    r1map_basename = f'sub-{subject}_ses-{session}_acq-mixed_R1map_postproc.nii.gz'
    
    t1map_im = nib.load(op.join(out_dir, t1map_basename))
    t1map_data = t1map_im.get_fdata()
    r1map_data = np.divide(1000, t1map_data, where = (t1map_data != 0), out= np.zeros_like(t1map_data))

    nib.save(nib.Nifti1Image(r1map_data, t1map_im.affine), op.join(out_dir, r1map_basename))

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

def seg_csf(subject, project, reference_ses:str ='01'): 

    os.environ['FREESURFER_HOME'] = '/usr/local/freesurfer/stable8'

    fs_dir = op.join(project, 'derivatives', 'freesurfer', 
                     f'sub-{subject}_ses-{reference_ses}', 'mri')
    mixed_dir = op.join(project, 'derivatives', 'csf_seg', f'sub-{subject}', f'ses-{reference_ses}')

    aseg_fn = op.join(fs_dir, 'aparc+aseg.mgz') 
    sereg_fn = op.join(mixed_dir, f'sub-{subject}_ses-{reference_ses}_acq-mixed_SE-modulus_registered.nii.gz') 
    csf_seg_fn = op.join(mixed_dir, f'sub-{subject}_seg-csf_mask.nii.gz')

    sreg_im = sm.load_mri(sereg_fn, dtype=np.float32)
    aseg_im = sm.load_mri(aseg_fn, dtype=np.int16)

    csf_seg_im = create_csf_seg(aseg_im, sreg_im)

    sm.save_mri(csf_seg_im, csf_seg_fn, dtype=np.uint8)


