#!/usr/bin/env bash
set -euo pipefail

PROJECT="/mnt/cina/GLIMPSE_WISP/data"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/../fmriprep_apptainer.sh" "${PROJECT}"
