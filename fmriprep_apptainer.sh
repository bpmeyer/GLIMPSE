#!/bin/bash
set -euo pipefail

# Run fMRIPrep with Apptainer/Singularity .sif for a BIDS project directory.
#
# Usage: fmriprep_apptainer.sh PROJECT_DIR [PARTICIPANT_LABEL...] [--nthreads N] [--omp-nthreads N] [--mem-mb N]
#
# PROJECT_DIR is expected to contain sourcedata/nifti and derivatives/freesurfer,
# matching the layout used by recon_all_parallel.py. If no PARTICIPANT_LABEL is
# given, fMRIPrep is run over all participants found in the BIDS directory.

FS_LICENSE="/usr/local/freesurfer/stable8/license.txt"
FMRIPREP_SIF="/mnt/cina/lib/fmriprep-latest.sif"

NTHREADS=32
OMP_NTHREADS=8
MEM_MB=160000
PARTICIPANTS=()

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 PROJECT_DIR [PARTICIPANT_LABEL...] [--nthreads N] [--omp-nthreads N] [--mem-mb N]"
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
        *)
            PARTICIPANTS+=("$1")
            shift
            ;;
    esac
done

BIDS_DIR="${PROJECT_DIR}/sourcedata/nifti"
OUT_DIR="${PROJECT_DIR}/derivatives/fmriprep"
WORK_DIR="${PROJECT_DIR}/work/fmriprep"
FS_DIR="${PROJECT_DIR}/derivatives/freesurfer"

mkdir -p "$OUT_DIR" "$WORK_DIR"

PARTICIPANT_ARGS=()
if [[ ${#PARTICIPANTS[@]} -gt 0 ]]; then
    PARTICIPANT_ARGS=(--participant-label "${PARTICIPANTS[@]}")
fi

apptainer run --cleanenv \
  -B "$BIDS_DIR":/data:ro \
  -B "$OUT_DIR":/out \
  -B "$WORK_DIR":/work \
  -B "$FS_DIR":/fs_dir \
  -B "$FS_LICENSE":/opt/freesurfer/license.txt \
  "$FMRIPREP_SIF" \
  /data /out participant \
  "${PARTICIPANT_ARGS[@]}" \
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
