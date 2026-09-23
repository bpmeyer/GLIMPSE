#!/bin/bash
set -euo pipefail

# Run fMRIPrep with Apptainer/Singularity .sif for a BIDS project directory.
#
# Usage: fmriprep_apptainer.sh PROJECT_DIR [PARTICIPANT_LABEL...] [--ses SESSION_LABEL...] [--nthreads N] [--omp-nthreads N] [--mem-mb N] [--bids-filter-file FILE]
#
# PROJECT_DIR is expected to contain sourcedata/nifti and derivatives/freesurfer,
# matching the layout used by recon_all_parallel.py. If no PARTICIPANT_LABEL is
# given, fMRIPrep is run over all participants found in the BIDS directory. If
# no --ses is given, fMRIPrep is run over all of each participant's sessions.
# If --bids-filter-file is given, that host-side JSON file is bind-mounted in
# and passed to fMRIPrep's --bids-filter-file.

FS_LICENSE="/usr/local/freesurfer/8.0.0/license.txt"
FMRIPREP_SIF="/mnt/cina/lib/fmriprep-latest.sif"

NTHREADS=32
OMP_NTHREADS=8
MEM_MB=160000
PARTICIPANTS=()
SESSIONS=()
BIDS_FILTER_FILE=""

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 PROJECT_DIR [PARTICIPANT_LABEL...] [--ses SESSION_LABEL...] [--nthreads N] [--omp-nthreads N] [--mem-mb N] [--bids-filter-file FILE]"
    exit 1
fi

PROJECT_DIR="$1"
shift

while [[ $# -gt 0 ]]; do
    case "$1" in
        --nthreads)
            NTHREADS="$2"
            shift 2
            ;;
        --omp-nthreads)
            OMP_NTHREADS="$2"
            shift 2
            ;;
        --mem-mb)
            MEM_MB="$2"
            shift 2
            ;;
        --bids-filter-file)
            BIDS_FILTER_FILE="$2"
            shift 2
            ;;
        --ses|--session-label)
            shift
            while [[ $# -gt 0 && "$1" != --* ]]; do
                SESSIONS+=("$1")
                shift
            done
            ;;
        *)
            PARTICIPANTS+=("$1")
            shift
            ;;
    esac
done

BIDS_DIR="${PROJECT_DIR}/sourcedata/nifti"
OUT_DIR="${PROJECT_DIR}/derivatives/fmriprep"
WORK_DIR="${PROJECT_DIR}/work/fmriprep_fl"
FS_DIR="${PROJECT_DIR}/derivatives/freesurfer"

mkdir -p "$OUT_DIR" "$WORK_DIR"

PARTICIPANT_ARGS=()
if [[ ${#PARTICIPANTS[@]} -gt 0 ]]; then
    PARTICIPANT_ARGS=(--participant-label "${PARTICIPANTS[@]}")
fi

SESSION_ARGS=()
if [[ ${#SESSIONS[@]} -gt 0 ]]; then
    SESSION_ARGS=(--session-label "${SESSIONS[@]}")
fi

BIND_ARGS=()
BIDS_FILTER_ARGS=()
if [[ -n "$BIDS_FILTER_FILE" ]]; then
    BIND_ARGS=(-B "$BIDS_FILTER_FILE":/bids_filter.json:ro)
    BIDS_FILTER_ARGS=(--bids-filter-file /bids_filter.json)
fi

apptainer run --cleanenv \
  -B "$BIDS_DIR":/data:ro \
  -B "$OUT_DIR":/out \
  -B "$WORK_DIR":/work \
  -B "$FS_DIR":/fs_dir \
  -B "$FS_LICENSE":/opt/freesurfer/license.txt \
  "${BIND_ARGS[@]}" \
  "$FMRIPREP_SIF" \
  /data /out participant \
  "${PARTICIPANT_ARGS[@]}" \
  "${SESSION_ARGS[@]}" \
  "${BIDS_FILTER_ARGS[@]}" \
  --fs-subjects-dir /fs_dir \
  --fs-license-file /opt/freesurfer/license.txt \
  --work-dir /work \
  --cifti-output \
  --output-spaces MNI152NLin2009cAsym:res-2 anat \
  --nthreads "$NTHREADS" \
  --omp-nthreads "$OMP_NTHREADS" \
  --mem-mb "$MEM_MB" \
  --skip-bids-validation \
  --fallback-total-readout-time estimated 
