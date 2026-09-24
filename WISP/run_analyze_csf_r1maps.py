#!/usr/local/anaconda3/bin/python3

import sys
from pathlib import Path
import os.path as op
PROJECT = Path("/mnt/cina/GLIMPSE_WISP/data")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyze_csf_r1maps import *

if __name__ == "__main__":

    ### Gathering list of subjects 
    nifti_dir = op.join(PROJECT, 'sourcedata', 'nifti')
    #subs = sorted([op.basename(s).split('-')[1] for s in glob(op.join(nifti_dir, 'sub-*'))])
    subs = [f'00{i}' for i in range(1, 9)]

    #lot_group_r1_maps(subs, PROJECT)
    plot_subject_csfseg(subject='004', project=PROJECT)
    # # Gather List of Subjects
    # for subject in subs:
    #     plot_subject_r1_map(subject, project)