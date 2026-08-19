#!/usr/local/anaconda3/bin/python3
"""Download GLIMPSE-OSA session data from XNAT.

Project-specific config lives here; the actual download logic is shared
with the other projects' downloadxnat.py scripts -- see
../downloadxnat_common.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from downloadxnat_common import run

XNATHOST = 'https://xnatpro.ibic.washington.edu'
PROJECT = 'GLIMPSE-OSA'
PROJECT_PATH = '/mnt/cina/GLIMPSE_OSA'
PHYSIO_RESOURCE = 'PARREC'
SUBJECT_SESSION_DELIM = '_'
PHYSIO_CSV_COLUMN = 10


def main():
    run(
        xnathost=XNATHOST,
        project=PROJECT,
        project_path=PROJECT_PATH,
        physio_resource=PHYSIO_RESOURCE,
        subject_session_delim=SUBJECT_SESSION_DELIM,
        physio_csv_column=PHYSIO_CSV_COLUMN,
        description='Download GLIMPSE-OSA session data from XNAT.',
    )


if __name__ == '__main__':
    main()
