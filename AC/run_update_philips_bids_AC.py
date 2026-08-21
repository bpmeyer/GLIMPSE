import sys
from pathlib import Path

PROJECT = Path("/mnt/cina/AC/data")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from update_philips_BIDs import update_philips_bids

if __name__ == "__main__":
    # AC has two nifti trees under one project: sourcedata/nifti (Siemens,
    # see run_update_siemens_bids_AC.py) and sourcedata/nifti_uw (Philips).
    update_philips_bids(PROJECT, nifti_subdir="nifti_uw")
