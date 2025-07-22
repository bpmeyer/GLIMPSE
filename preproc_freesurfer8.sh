#!/bin/bash

# DESCRIPTION:
#  runs freesurfer version 8 
#  recon-all v8 takes about 2-3 hours on a single CPU and uses 24GB memory
#  BPM 01/05/2025 - updated to version 8 4/30/2025
#  JS Updated to add T2 weighted image to refine pial surface 7/21/25

# ------------------------------------------------------------------------------

PROJECT_HOME=/mnt/cina/GLIMPSE_OSA
DCMNI=/usr/bin/dcm2niix
export ANTSPATH=/usr/local/ANTs-2.1.0-rc3/bin
export PATH=${ANTSPATH}:$PATH
export FREESURFER_HOME=/usr/local/freesurfer/stable8
source $FREESURFER_HOME/SetUpFreeSurfer.sh

session_list=`find /mnt/cina/GLIMPSE_OSA/data/ -mindepth 2 -maxdepth 2`

# ==================== freesurfer ====================
count=0

for ses in ${session_list[@]}; do

    # Skip if session already has wmparc.mgz
    if [ -f ${ses}/freesurfer8/mri/wmparc.mgz ]; then
        continue
    fi

    # Skip if no T1 found (session incomplete)
        if [ ! -f ${ses}/anat/t1w.nii ]; then
            echo "No T1 found for ${ses}, skipping..."
            continue
        fi

    # Choose recon-all command based on whether T2 exists
    # If T2 exists use to refine pial border
    if [ -f ${ses}/anat/t2w.nii ]; then
        recon-all -sd ${ses} \
         -i ${ses}/anat/t1w.nii \
          -T2 ${ses}/anat/t2w.nii \
          -T2pial \
          -subject freesurfer8 -all &
    else
        recon-all -sd ${ses} \
          -i ${ses}/anat/t1w.nii \
          -subject freesurfer8 -all &
    fi

    ((count++))
    if (( count % 10 == 0 )); then  # Wait after every 10 processes
        wait
    fi

done

wait  # Ensure all remaining jobs finish
echo "All recon-all jobs complete"