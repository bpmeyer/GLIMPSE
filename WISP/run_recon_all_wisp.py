#!/usr/local/anaconda3/bin/python3

import sys
from pathlib import Path

PROJECT = Path("/mnt/cina/GLIMPSE_WISP/data")
N_CPUS = 16
USE_T2 = True

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from recon_all_parallel import recon_all_parallel

if __name__ == "__main__":
    recon_all_parallel(PROJECT, n_cpus=N_CPUS, use_t2=USE_T2)
