#!/usr/local/anaconda3/bin/python3

import sys
from pathlib import Path
from pprint import pprint

PROJECT = Path("/mnt/cina/GLIMPSE_WISP/data")
FREESURFER_HOME = Path('/usr/local/freesurfer/8.0.0')
greedy_fn = '/mnt/home/jdromero/Packages/greedy.sif'

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from segment_csf import *

if __name__ == "__main__":

    ### Gathering list of subjects 
    nifti_dir = op.join(PROJECT, 'sourcedata', 'nifti')
    #subs = sorted([op.basename(s).split('-')[1] for s in glob(op.join(nifti_dir, 'sub-*'))])
    subs = [f'00{i}' for i in range(1, 9)]
    for sub in subs: 

        print(f'PROCESSING SUB-{sub}')
        print(f'Creating CSF Segmentation for: sub-{sub}')
        create_csf_segmentation(subject=sub, project=PROJECT)

        print(f'Creating Grouped Segentation for : sub-{sub}')
        create_grouped_segmentation(subject = sub, project=PROJECT, freesurfer_home=FREESURFER_HOME)
        
        print(f'Creating C-V-S Segmentation for: sub-{sub}')
        create_cvs_segmentation(subject = sub, project=PROJECT, freesurfer_home=FREESURFER_HOME)

