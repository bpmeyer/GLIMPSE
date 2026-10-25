#!/usr/bin/env python

import subprocess
import sys
from pathlib import Path

# Project name under /mnt/cina (update_philips_BIDs.py resolves it to
# /mnt/cina/GLIMPSE_WISP/data).
PROJECT = "GLIMPSE_WISP"
SIF = "/mnt/cina/lib/heudiconv_latest.sif"
REPO_DIR = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    # Run inside the heudiconv container, which provides heudiconv and nibabel.
    # Any extra arguments (e.g. --subjects 001 --sessions 01) are passed through.
    cmd = [
        "apptainer",
        "exec",
        "--cleanenv",
        "--bind",
        "/mnt/cina",
        "--bind",
        str(REPO_DIR),
        "--pwd",
        str(REPO_DIR),
        SIF,
        "python",
        "update_philips_BIDs.py",
        PROJECT,
        *sys.argv[1:],
    ]
    sys.exit(subprocess.run(cmd).returncode)
