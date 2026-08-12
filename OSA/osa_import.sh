#!/bin/bash

BASE_DICOM="/mnt/cina/GLIMPSE_OSA/tmp/data/sourcedata/dicom"
SPLIT_DICOM="/mnt/cina/GLIMPSE_OSA/tmp/data/sourcedata/dicom_split"
OUT="/mnt/cina/GLIMPSE_OSA/tmp/data/sourcedata/nifti"
HEURISTICS="/mnt/home/rka8/GLIMPSE/OSA"
CONFIG="/mnt/cina/GLIMPSE_OSA/tmp/data/config"
SPLITTER="/mnt/home/rka8/GLIMPSE/OSA/split_multiframe_qflow.py"
SIF="/mnt/cina/lib/heudiconv_latest.sif"

for SUB_DIR in "${BASE_DICOM}"/GLOtwo*; do

    [ -d "$SUB_DIR" ] || continue

    SUB=$(basename "$SUB_DIR")

    for v in v1 v2 v3 v4; do

        echo ""
        echo "======================================================"
        echo "Processing ${SUB} ${v}"
        echo "======================================================"

        # --------------------------------------------------
        # Find the enhanced QFlow DICOM
        # --------------------------------------------------

        QFLOW=$(find "${BASE_DICOM}/${SUB}/${v}/401-CSF_QF_retrospectivetrigger" \
            -type f -name "*.dcm" | head -n 1)

        if [ -z "$QFLOW" ]; then
            echo "WARNING: No QFlow DICOM found for ${SUB} ${v}"
            echo "Skipping..."
            continue
        fi

        echo "QFlow DICOM found:"
        echo "$QFLOW"

        # --------------------------------------------------
        # Split QFlow
        # --------------------------------------------------

        mkdir -p "${SPLIT_DICOM}/${SUB}/${v}"

        echo ""
        echo "Splitting QFlow..."

        python3 "$SPLITTER" \
            "$QFLOW" \
            "${SPLIT_DICOM}/${SUB}/${v}"

        if [ $? -ne 0 ]; then
            echo "ERROR: QFlow splitting failed for ${SUB} ${v}"
            exit 1
        fi

        # --------------------------------------------------
        # Run heudiconv using BOTH:
        #
        # 1. Normal DICOM directory
        # 2. Split QFlow directory
        # --------------------------------------------------

        echo ""
        echo "Running heudiconv on normal DICOMs + split QFlow..."

        singularity exec --cleanenv \
            -B "${BASE_DICOM}/${SUB}:/DICOMS" \
            -B "${SPLIT_DICOM}/${SUB}:/SPLIT" \
            -B "${OUT}:/OUT" \
            -B "${HEURISTICS}:/HEURISTICS" \
            -B "${CONFIG}:/CONFIG" \
            "$SIF" heudiconv \
            --files "/DICOMS/${v}" "/SPLIT/${v}" \
            -o /OUT \
            -f /HEURISTICS/OSA_heuristic.py \
            -s "${SUB}" \
            -ss "${v}" \
            -c dcm2niix \
            -g custom \
            -b \
            --minmeta \
            --dcmconfig /CONFIG/dcmconfig.json \
            --overwrite

        if [ $? -ne 0 ]; then
            echo "ERROR: heudiconv failed for ${SUB} ${v}"
            exit 1
        fi

        echo ""
        echo "Finished ${SUB} ${v}"

    done
done

echo ""
echo "======================================================"
echo "ALL PARTICIPANTS AND VISITS COMPLETED"
echo "======================================================"

echo "Deleting temporary split DICOM directory..."
rm -rf "${SPLIT_DICOM}"
echo ""
echo "======================================================"
echo "Renaming NIfTI folders to BIDS format"
echo "======================================================"

for SUB_DIR in "${OUT}"/GLOtwo*; do

    [ -d "$SUB_DIR" ] || continue

    OLD_SUB=$(basename "$SUB_DIR")

    # Extract participant number
    NUM=$(echo "$OLD_SUB" | sed 's/GLOtwo//')
    NUM=$(printf "%03d" "$((10#$NUM))")

    NEW_SUB="sub-${NUM}"

    echo "Renaming ${OLD_SUB} -> ${NEW_SUB}"

    # Rename participant folder
    mv "$SUB_DIR" "${OUT}/${NEW_SUB}"

    # Rename visit folders
    for VISIT_DIR in "${OUT}/${NEW_SUB}"/v*; do

        [ -d "$VISIT_DIR" ] || continue

        OLD_VISIT=$(basename "$VISIT_DIR")

        # Extract visit number
        VNUM=$(echo "$OLD_VISIT" | sed 's/v//')
        VNUM=$(printf "%02d" "$((10#$VNUM))")

        NEW_VISIT="ses-${VNUM}"

        echo "    Renaming ${OLD_VISIT} -> ${NEW_VISIT}"

        mv "$VISIT_DIR" "${OUT}/${NEW_SUB}/${NEW_VISIT}"

    done

done

echo ""
echo "NIfTI folder renaming complete."
echo "Done."
echo "Done."