#!/usr/bin/env bash
set -euo pipefail

# ---- Edit these paths ----
SIF="/mnt/cina/lib/heudiconv_latest.sif"
PROJECT="/mnt/cina/AC/data"
REPO_DIR="/mnt/cina/github/GLIMPSE/AC"
DICOM_ROOT="${PROJECT}/sourcedata/dicoms_fl"
OUT_ROOT="${PROJECT}/sourcedata/nifti_fl"
HEURISTIC="${REPO_DIR}/FL_AC_heuristic.py"

# Use apptainer by default.
RUNTIME="apptainer"

# Optional: pass one or more subject IDs (e.g. "101" or "101 102") to
# restrict the run; with no arguments, all subjects under DICOM_ROOT are run.
SUBJECT_FILTER=("$@")

mkdir -p "${OUT_ROOT}"

for subj_dir in "${DICOM_ROOT}"/sub-*; do
    if [[ ! -d "${subj_dir}" ]]; then
        continue
    fi

    folder_name="$(basename "${subj_dir}")"

    # FL dicoms are already in sub-XXX/ses-YYY BIDS layout, so the
    # subject/session IDs are read directly from the folder names 
    if [[ ! "${folder_name}" =~ ^sub-([0-9]+)$ ]]; then
        echo "WARNING: Folder name does not match expected pattern: ${folder_name}; skipping."
        continue
    fi
    bids_subject="${BASH_REMATCH[1]}"

    if [[ ${#SUBJECT_FILTER[@]} -gt 0 ]]; then
        skip=true
        for wanted in "${SUBJECT_FILTER[@]}"; do
            if [[ "${bids_subject}" == "${wanted}" ]]; then
                skip=false
                break
            fi
        done
        if [[ "${skip}" == true ]]; then
            continue
        fi
    fi

    # Some sessions have extra dicom exports split into additional folders,
    # e.g.:
    #   ses-102, ses-102_csf_flow, ses-102_ivim, ses-102_ivim_new, ses-102_t1
    # Group folders by their base session number so everything belonging to
    # one session is fed to heudiconv in a single call (keeps run-XX
    # numbering consistent across the whole session).
    declare -A session_dirs=()

    for ses_dir in "${subj_dir}"/ses-*; do
        if [[ ! -d "${ses_dir}" ]]; then
            continue
        fi

        ses_folder_name="$(basename "${ses_dir}")"

        if [[ "${ses_folder_name}" =~ ^ses-([0-9]+) ]]; then
            base_session="${BASH_REMATCH[1]}"
            session_dirs["${base_session}"]+="${ses_dir} "
        else
            echo "WARNING: Session folder name does not match expected pattern: ${ses_folder_name}; skipping."
        fi
    done

    for bids_session in "${!session_dirs[@]}"; do
        # shellcheck disable=SC2206
        dicom_dirs=(${session_dirs[${bids_session}]})

        echo "============================================================"
        echo "BIDS subject: sub-${bids_subject}"
        echo "BIDS session: ses-${bids_session}"
        echo "DICOM paths:  ${dicom_dirs[*]}"
        echo "Output path:  ${OUT_ROOT}"
        echo "============================================================"

        "${RUNTIME}" exec \
            --cleanenv \
            --bind "${PROJECT}:${PROJECT}" \
            --bind "${REPO_DIR}:${REPO_DIR}" \
            "${SIF}" \
            heudiconv \
                --files "${dicom_dirs[@]}" \
                -o "${OUT_ROOT}" \
                -f "${HEURISTIC}" \
                -s "${bids_subject}" \
                -ss "${bids_session}" \
                -c dcm2niix \
                -g custom \
                -b \
                --minmeta \
                --overwrite

    done

    unset session_dirs
done
