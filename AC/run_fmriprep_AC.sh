#!/usr/bin/env bash
set -euo pipefail

PROJECT="/mnt/cina/AC/data"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/../fmriprep_apptainer.sh" "${PROJECT}" \
    111 120 \
    --ses 101 102 201 202 \
    --bids-filter-file "${SCRIPT_DIR}/bids_filter_fmriprep.json"
    # 901 902 903 904 905 906 907 913 915 916 918 919 920 924