#!/usr/local/anaconda3/bin/python3

import sys
from pathlib import Path
import os.path as op
PROJECT = Path("/mnt/cina/GLIMPSE_WISP/data")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

sleep_meta_fn = '/mnt/home/jdromero/Documents/data/wisp_sleep_data.csv'

from analyze_csf_r1maps import *

if __name__ == "__main__":

    ### Gathering list of subjects 
    nifti_dir = op.join(PROJECT, 'sourcedata', 'nifti')
    #subs = sorted([op.basename(s).split('-')[1] for s in glob(op.join(nifti_dir, 'sub-*'))])
    subs = [f'00{i}' for i in range(1, 9)]

    # plot_group_r1_maps(subs, PROJECT)
    # plot_subject_csfseg(subject='004', project=PROJECT)
    # plot_group_csf_seg(subs, PROJECT)
    # plot_subject_r1_map(subject='004', project=PROJECT)
    # plot_r1map_segmentation_boxplot(subs, project=PROJECT)
    #plot_r1map_region_visit(subs, project=PROJECT, sleep_meta=sleep_meta_fn)
    calc_csf_vol(subs, project=PROJECT)
    # plot_csf_vol_by_visit(subs, project=PROJECT, sleep_meta=sleep_meta_fn)
    plot_wm_thresholds(subs, project=PROJECT)
    # # Gather List of Subjects
    # for subject in subs:
    #     plot_subject_r1_map(subject, project)