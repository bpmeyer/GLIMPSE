#!/usr/local/anaconda3/bin/python3

import sys
from pathlib import Path
import os.path as op
import os 

os.environ["ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS"] = "16"  
PROJECT = Path("/mnt/cina/GLIMPSE_WISP/data")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

sleep_meta_fn = '/mnt/home/jdromero/Documents/data/wisp_sleep_data.csv'
vol_df_fn = op.join('/mnt/home/jdromero/Documents', 'wisp_group_csf_vol_estimate.csv')

from analyze_csf_volumes import *

if __name__ == "__main__":

    ### Gathering list of subjects 
    nifti_dir = op.join(PROJECT, 'sourcedata', 'nifti')
    subs = sorted([op.basename(s).split('-')[1] for s in glob(op.join(nifti_dir, 'sub-*'))])
    subs = [s for s in subs if int(s) <= 18 and s not in ['013', '017', '023']]

    #calc_csf_vol(subs, project=PROJECT)
    #plot_wm_thresholds(sleep_meta_fn, vol_df_fn, project=PROJECT)
    # plot_csf_vol_by_visit(subs, project=PROJECT, sleep_meta=sleep_meta_fn)
    calc_avg_t1_time(subs, project=PROJECT)
    plot_csf_t1_by_visit(subs, project=PROJECT, sleep_meta=sleep_meta_fn)
    #plot_t1map_distributions(sleep_meta_fn, project=PROJECT)
    # plot_csf_vols_over_t1_image(subs, project=PROJECT, sleep_meta_fn = sleep_meta_fn)
    plot_csf_t1map_over_t1_image(subs, project=PROJECT, sleep_meta_fn = sleep_meta_fn)