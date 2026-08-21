import sys
from pathlib import Path

PROJECT = Path("/mnt/cina/AC/data")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from update_siemens_BIDS import update_siemens_bids

if __name__ == "__main__":
    # AC has two nifti trees under one project: sourcedata/nifti (Siemens,
    # this script) and sourcedata/nifti_uw (Philips, see
    # run_update_philips_bids_AC.py). "nifti" is the default nifti_subdir.
    update_siemens_bids(PROJECT)
