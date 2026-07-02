#!/usr/local/anaconda3/bin/python3

import sys
from pathlib import Path

PROJECT = Path("/mnt/cina//data")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from update_philips_BIDs import update_philips_bids

if __name__ == "__main__":
    update_philips_bids(PROJECT)
