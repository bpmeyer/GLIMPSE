#!/usr/local/anaconda3/bin/python3

import sys
from pathlib import Path

PROJECT = Path("/mnt/cina/GLIMPSE_WISP/data")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from segment_csf import allsubs_t1_times

if __name__ == "__main__":
    allsubs_t1_times(PROJECT)
