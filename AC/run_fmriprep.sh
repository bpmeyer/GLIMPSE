#!/bin/bash

# Run fMRIPrep with Apptainer/Singularity .sif

BIDS_DIR="/mnt/cina/AC/sourcedata/nifti"
OUT_DIR="/mnt/cina/AC/derivatives/fmriprep"
WORK_DIR="/mnt/cina/AC/work/fmriprep"
FS_LICENSE="/usr/local/freesurfer/stable8/license.txt"
FMRIPREP_SIF="/mnt/cina/lib/fmriprep-latest.sif"

participant="902"
FS_DIR="/mnt/cina/AC/derivatives/freesurfer/sub-902"

mkdir -p "$OUT_DIR" "$WORK_DIR"

apptainer run --cleanenv \
  -B "$BIDS_DIR":/data:ro \
  -B "$OUT_DIR":/out \
  -B "$WORK_DIR":/work \
  -B "$FS_DIR":/fs_dir \
  -B "$FS_LICENSE":/opt/freesurfer/license.txt \
  "$FMRIPREP_SIF" \
  /data /out participant \
  --participant-label "$participant" \
  --fs-subjects-dir /fs_dir \
  --fs-license-file /opt/freesurfer/license.txt \
  --work-dir /work \
  --output-spaces MNI152NLin2009cAsym:res-2 \
  --nthreads 32 \
  --omp-nthreads 8 \
  --mem-mb 160000 \
  --skip-bids-validation \
  --fallback-total-readout-time estimated \
  --stop-on-first-crash