#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/bin/dcm2niix:$PATH"

# ---- Edit these paths ----
SIF="/mnt/cina/lib/heudiconv_latest.sif"
PROJECT="/mnt/cina/AC/data"
# Resolve the repo directory relative to this script's own location 
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DICOM_ROOT="${PROJECT}/sourcedata/dicoms_fl"
OUT_ROOT="${PROJECT}/sourcedata/nifti_fl"
HEURISTIC="${REPO_DIR}/FL_AC_heuristic.py"

# Use apptainer by default.
RUNTIME="apptainer"

# Newer dcm2niix than the one bundled in the SIF (v1.0.20240202); bind-mounted
# over the container's own binary path so heudiconv picks it up transparently.
DCM2NIIX_BIN="/mnt/home/briana90/.local/lib/python3.12/site-packages/dcm2niix/dcm2niix"
DCM2NIIX_CONTAINER_PATH="/opt/dcm2niix-v1.0.20240202/bin/dcm2niix"

# Optional: pass one or more subject IDs (e.g. "101" or "101 102") to
# restrict the run; with no arguments, all subjects under DICOM_ROOT are run.
SUBJECT_FILTER=("$@")

# Optional: set SESSION_FILTER to one or more session IDs (e.g. "101" or
# "101 102") to restrict the run to those sessions; unset/empty runs all
# sessions found for the selected subject(s).
SESSION_FILTER=(${SESSION_FILTER:-})

# Optional: set SPLIT_SESSIONS=1 to keep each additional dicom folder as
# its own separate output session (e.g. ses-102_ivim_new stays separate
# from ses-102) instead of grouping same-base-number folders together.
SPLIT_SESSIONS="${SPLIT_SESSIONS:-0}"

# heudiconv converter: "none" only extracts dicom info/heuristic mapping
# (dry run, no nifti files); "dcm2niix" performs the actual conversion.
CONVERTER="${CONVERTER:-none}"

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

        if [[ ! "${ses_folder_name}" =~ ^ses-([0-9]+) ]]; then
            echo "WARNING: Session folder name does not match expected pattern: ${ses_folder_name}; skipping."
            continue
        fi
        base_session="${BASH_REMATCH[1]}"

        if [[ ${#SESSION_FILTER[@]} -gt 0 ]]; then
            skip=true
            for wanted in "${SESSION_FILTER[@]}"; do
                if [[ "${base_session}" == "${wanted}" ]]; then
                    skip=false
                    break
                fi
            done
            if [[ "${skip}" == true ]]; then
                continue
            fi
        fi

        if [[ "${SPLIT_SESSIONS}" == "1" ]]; then
            # Keep this folder as its own separate output session instead
            # of merging it with other same-base-number folders.
            bids_session="${ses_folder_name#ses-}"
            dicom_dirs=("${ses_dir}")

            echo "============================================================"
            echo "BIDS subject: sub-${bids_subject}"
            echo "BIDS session: ses-${bids_session}"
            echo "DICOM paths:  ${dicom_dirs[*]}"
            echo "Output path:  ${OUT_ROOT}"
            echo "dcm2niix version: $(dcm2niix -v)"
            echo "============================================================"

            "${RUNTIME}" exec \
                --cleanenv \
                --bind "${PROJECT}:${PROJECT}" \
                --bind "${REPO_DIR}:${REPO_DIR}" \
                --bind "${DCM2NIIX_BIN}:${DCM2NIIX_CONTAINER_PATH}" \
                "${SIF}" \
                heudiconv \
                    --files "${dicom_dirs[@]}" \
                    -o "${OUT_ROOT}" \
                    -f "${HEURISTIC}" \
                    -s "${bids_subject}" \
                    -ss "${bids_session}" \
                    -c "${CONVERTER}" \
                    -g custom \
                    -b \
                    --minmeta \
                    --overwrite
        else
            session_dirs["${base_session}"]+="${ses_dir} "
        fi
    done

    if [[ "${SPLIT_SESSIONS}" != "1" ]]; then
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
                --bind "${DCM2NIIX_BIN}:${DCM2NIIX_CONTAINER_PATH}" \
                "${SIF}" \
                heudiconv \
                    --files "${dicom_dirs[@]}" \
                    -o "${OUT_ROOT}" \
                    -f "${HEURISTIC}" \
                    -s "${bids_subject}" \
                    -ss "${bids_session}" \
                    -c "${CONVERTER}" \
                    -g custom \
                    -b \
                    --minmeta \
                    --overwrite

        done
    fi

    unset session_dirs
done
