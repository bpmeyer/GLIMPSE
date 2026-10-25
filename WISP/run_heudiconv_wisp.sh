#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/bin/dcm2niix:$PATH"

# ---- Edit these paths ----
SIF="/mnt/cina/lib/heudiconv_latest.sif"
PROJECT="/mnt/cina/GLIMPSE_WISP/data"
DICOM_ROOT="${PROJECT}/sourcedata/dicom"
OUT_ROOT="${PROJECT}/sourcedata/nifti"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "${SCRIPT_DIR}")"
HEURISTIC="${SCRIPT_DIR}/WISP_heuristic.py"

# Use apptainer by default.
RUNTIME="apptainer"

mkdir -p "${OUT_ROOT}"

# Version of the dcm2niix bundled in the SIF, which is what heudiconv converts with.
DCM2NIIX_VERSION="$("${RUNTIME}" exec --cleanenv "${SIF}" dcm2niix -v 2>&1 | tail -n 1 || true)"

for subj_dir in "${DICOM_ROOT}"/*; do
    if [[ ! -d "${subj_dir}" ]]; then
        continue
    fi

    subj_folder="$(basename "${subj_dir}")"

    # Expected example: GLW-001
    # Drop the "GLW" prefix -> bids subject 001
    if [[ ! "${subj_folder}" =~ ^GLW-?([0-9]+)$ ]]; then
        echo "WARNING: Folder name does not match expected pattern: ${subj_folder}; skipping."
        continue
    fi
    bids_subject="${BASH_REMATCH[1]}"

    for ses_dir in "${subj_dir}"/*; do
        if [[ ! -d "${ses_dir}" ]]; then
            continue
        fi

        ses_folder="$(basename "${ses_dir}")"

        # Expected example: V1 -> ses-01
        if [[ ! "${ses_folder}" =~ ^V([0-9]+)$ ]]; then
            echo "WARNING: Could not determine session for ${subj_folder}/${ses_folder}; skipping."
            continue
        fi
        bids_session="$(printf "%02d" "${BASH_REMATCH[1]}")"

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
        echo "dcm2niix version: ${DCM2NIIX_VERSION}"
        echo "============================================================"

        "${RUNTIME}" exec \
            --cleanenv \
            --bind "${PROJECT}:${PROJECT}" \
            --bind "${SCRIPT_DIR}:${SCRIPT_DIR}" \
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

        # Fix up the Philips JSON sidecars (slice timing, phase encoding,
        # B0 field metadata, readout time) for this session
        "${RUNTIME}" exec \
            --cleanenv \
            --bind "${PROJECT}:${PROJECT}" \
            --bind "${REPO_DIR}:${REPO_DIR}" \
            --pwd "${REPO_DIR}" \
            "${SIF}" \
            python update_philips_BIDs.py "$(basename "$(dirname "${PROJECT}")")" \
                --subjects "${bids_subject}" \
                --sessions "${bids_session}"

    done
done
