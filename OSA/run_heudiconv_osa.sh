#!/usr/bin/env bash
set -euo pipefail

# ---- Edit these paths ----
SIF="/mnt/cina/lib/heudiconv_latest.sif"
PROJECT="/mnt/cina/GLIMPSE_OSA/data"
DICOM_ROOT="${PROJECT}/sourcedata/dicom"
OUT_ROOT="${PROJECT}/sourcedata/nifti"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEURISTIC="${SCRIPT_DIR}/OSA_heuristic.py"
SPLIT_SCRIPT="${SCRIPT_DIR}/split_enhanced_dicom.py"
MERGE_SCRIPT="${SCRIPT_DIR}/merge_trigger_delay_volumes.py"

# Force the container to use the cina server's dcm2niix (not the older
# version bundled in the .sif at /opt/dcm2niix-v1.0.20240202/bin/dcm2niix,
# which otherwise wins on PATH). Bind-mounting over that exact path makes
# this work regardless of PATH order, for anyone running on this server.
HOST_DCM2NIIX="/usr/bin/dcm2niix"
CONTAINER_DCM2NIIX="/opt/dcm2niix-v1.0.20240202/bin/dcm2niix"

# Use apptainer by default.
RUNTIME="apptainer"

mkdir -p "${OUT_ROOT}"

for subj_dir in "${DICOM_ROOT}"/*; do
    if [[ ! -d "${subj_dir}" ]]; then
        continue
    fi

    subj_folder="$(basename "${subj_dir}")"

    # Expected example: GLOtwo001
    # Drop the "GLOtwo" prefix -> bids subject 001
    if [[ ! "${subj_folder}" =~ ^GLOtwo-?([0-9]+)$ ]]; then
        echo "WARNING: Folder name does not match expected pattern: ${subj_folder}; skipping."
        continue
    fi
    # 10# forces base-10 interpretation so a folder like GLOtwo008 doesn't
    # make printf treat "008" as an (invalid) octal literal.
    bids_subject="$(printf "%03d" "$((10#${BASH_REMATCH[1]}))")"

    for ses_dir in "${subj_dir}"/*; do
        if [[ ! -d "${ses_dir}" ]]; then
            continue
        fi

        ses_folder="$(basename "${ses_dir}")"

        # Expected example: v1 -> ses-01
        if [[ ! "${ses_folder}" =~ ^[Vv]([0-9]+)$ ]]; then
            echo "WARNING: Could not determine session for ${subj_folder}/${ses_folder}; skipping."
            continue
        fi
        bids_session="$(printf "%02d" "$((10#${BASH_REMATCH[1]}))")"

        bids_ses_dir="${OUT_ROOT}/sub-${bids_subject}/ses-${bids_session}"
        if [[ -d "${bids_ses_dir}" ]]; then
            echo "Already converted: sub-${bids_subject}/ses-${bids_session}, skipping."
            continue
        fi

        echo "============================================================"
        echo "Input folder: ${subj_folder}/${ses_folder}"
        echo "BIDS subject: sub-${bids_subject}"
        echo "BIDS session: ses-${bids_session}"
        echo "DICOM path:   ${ses_dir}"
        echo "Output path:  ${OUT_ROOT}"
        echo "============================================================"

        # Enhanced (multi-frame) Philips DICOMs that mix several per-frame
        # image types (e.g. CSF_QF_retrospectivetrigger: M_FFE / M_PCA /
        # PHASE CONTRAST M in one file) get split into one homogeneous
        # multi-frame file per type before heudiconv runs, so its
        # SPLIT_BY_IMAGE_TYPE grouping in OSA_heuristic.py can tell them
        # apart. Idempotent: already-split series are skipped.
        python3 "${SPLIT_SCRIPT}" "${ses_dir}"

        "${RUNTIME}" exec \
            --cleanenv \
            --bind "${PROJECT}:${PROJECT}" \
            --bind "${SCRIPT_DIR}:${SCRIPT_DIR}" \
            --bind "${HOST_DCM2NIIX}:${CONTAINER_DCM2NIIX}" \
            "${SIF}" \
            heudiconv \
                --files "${ses_dir}" \
                -o "${OUT_ROOT}" \
                -f "${HEURISTIC}" \
                -s "${bids_subject}" \
                -ss "${bids_session}" \
                -c dcm2niix \
                -g custom \
                -b \
                --minmeta

        # dcm2niix can't merge this Philips Enhanced retrospective-trigger
        # data into 4D itself, so heudiconv writes one 3D volume per trigger
        # delay (..._flow1.nii.gz ... _flow15.nii.gz, non-chronologically
        # numbered). Merge those back into one 4D volume ordered by each
        # fragment's TriggerDelayTime, keeping the heudiconv-written BIDS
        # .json (with TriggerDelayTime rewritten as an array). Idempotent.
        python3 "${MERGE_SCRIPT}" "${bids_ses_dir}"

    done
done
