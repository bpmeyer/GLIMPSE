#!/usr/bin/env bash
set -euo pipefail

# ---- Edit these paths ----
SIF="/mnt/cina/lib/heudiconv_latest.sif"
PROJECT="/mnt/cina/AC"
DICOM_ROOT="${PROJECT}/sourcedata/dicoms_uw"
OUT_ROOT="${PROJECT}/sourcedata/nifti_uw"
HEURISTIC="${PROJECT}/AC_heuristic.py"

# Use apptainer by default.
RUNTIME="apptainer"

mkdir -p "${OUT_ROOT}"

for subj_dir in "${DICOM_ROOT}"/*; do
    if [[ ! -d "${subj_dir}" ]]; then
        continue
    fi

    folder_name="$(basename "${subj_dir}")"

    # Expected examples:
    #   0ACSF02E
    #   0ACSF02M
    #   1ACSF02E
    #   1ACSF02M
    #   0ACSF001E
    #   0ACSF001M
    #
    # Regex groups:
    #   1 = visit number, 0 or 1
    #   2 = digits between ACSF and E/M/end
    #   3 =  final E or M
    if [[ "${folder_name}" =~ ^([01])ACSF0*([0-9]+)([EM])?$ ]]; then
        visit="${BASH_REMATCH[1]}"
        raw_digits="${BASH_REMATCH[2]}"
        suffix="${BASH_REMATCH[3]}"

        # Subject rule:
        #   02  -> 902
        #   001 -> 901
        #
        # Convert digits to decimal integer, then pad to 2 digits.
        digits_as_number="$((10#${raw_digits}))"
        bids_subject="9$(printf "%02d" "${digits_as_number}")"

        # Session rule.
        if [[ "${visit}" == "0" && "${suffix}" == "E" ]]; then
            bids_session="101"
        elif [[ "${visit}" == "0" && "${suffix}" == "M" ]]; then
            bids_session="102"
        elif [[ "${visit}" == "1" && "${suffix}" == "E" ]]; then
            bids_session="201"
        elif [[ "${visit}" == "1" && "${suffix}" == "M" ]]; then
            bids_session="202"
        else
            echo "WARNING: Could not determine session for ${folder_name}; skipping."
            continue
        fi

        echo "============================================================"
        echo "Input folder: ${folder_name}"
        echo "BIDS subject: sub-${bids_subject}"
        echo "BIDS session: ses-${bids_session}"
        echo "DICOM path:   ${subj_dir}"
        echo "Output path:  ${OUT_ROOT}"
        echo "============================================================"

        "${RUNTIME}" exec \
            --cleanenv \
            --bind "${PROJECT}:${PROJECT}" \
            "${SIF}" \
            heudiconv \
                --files "${subj_dir}" \
                -o "${OUT_ROOT}" \
                -f "${HEURISTIC}" \
                -s "${bids_subject}" \
                -ss "${bids_session}" \
                -c dcm2niix \
                -g custom \
                -b \
                --minmeta \

    else
        echo "WARNING: Folder name does not match expected pattern: ${folder_name}; skipping."
    fi
done