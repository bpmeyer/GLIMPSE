#!/usr/local/anaconda3/bin/python3

import sys
from pathlib import Path

PROJECT = Path("/mnt/cina/GLIMPSE_WISP/data")
FREESURFER_HOME = Path('/usr/local/freesurfer/8.0.0')
greedy_fn = '/mnt/home/jdromero/Packages/greedy.sif'

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from estimate_csf_r1maps import *

if __name__ == "__main__":

    ### Gathering list of subjects 
    nifti_dir = op.join(PROJECT, 'sourcedata', 'nifti')
    subs = sorted([op.basename(s).split('-')[1] for s in glob(op.join(nifti_dir, 'sub-*'))])
    subs = [s for s in subs if int(s) <= 18]
    # Gather List of Subjects
    for subject in subs:
        
        print(f'Processiong Subject {subject}')
        # Sorted list of Sessions for Subject
        sessions = sorted([op.basename(s).split('-')[1] for s in glob(op.join(nifti_dir, f'sub-{subject}', 'ses-*'))]) 

        # Get the T1 maps for Subject
        for session in sessions: 
            print(f'Estimating T1 Times for sub-{subject}, ses-{session}')
            estimate_t1_times(subject, session, PROJECT)
        
        # for ses in sessions: 

        #     print(f'Registering SE Images to T1 for sub-{subject} ses-{ses}')
        #     register_SE_T1_greedy(subject, PROJECT, greedy_fn = greedy_fn, 
        #                           ses=ses, freesurfer_home=FREESURFER_HOME)

        # print(f'Registering T1 Maps to Registered SE Image')
        # register_T1maps_greedy(subject, PROJECT, greedy_fn = greedy_fn)

        # for session in sessions: 
        #     print(f'Calculating R1 map for sub-{subject}, ses-{session}')
        #     create_R1_map(subject, session, PROJECT)


