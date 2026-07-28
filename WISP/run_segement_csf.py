#!/usr/local/anaconda3/bin/python3

import sys
from pathlib import Path

PROJECT = Path("/mnt/cina/GLIMPSE_WISP/data")
greedy_fn = '/mnt/home/jdromero/Packages/greedy.sif'

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from segment_csf import allsubs_t1_times, allsubs_reg_SE, allsubs_reg_T1maps

if __name__ == "__main__":
    # allsubs_t1_times(PROJECT)
    # allsubs_reg_SE(PROJECT, greedy_fn = greedy_fn)
    allsubs_reg_T1maps(project=PROJECT, greedy_fn=greedy_fn)

