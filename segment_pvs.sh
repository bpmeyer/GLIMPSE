#!/bin/bash

# DESCRIPTION:
#  runs segcsvd_pvs from singularity container 
#  https://github.com/AICONSlab/segcsvd

# ------------------------------------------------------------------------------

PROJECT_HOME=/mnt/cina/GLIMPSE_OSA
DCMNI=/usr/bin/dcm2niix
export ANTSPATH=/usr/local/ANTs-2.1.0-rc3/bin
export PATH=${ANTSPATH}:$PATH
export FREESURFER_HOME=/usr/local/freesurfer/stable8
source $FREESURFER_HOME/SetUpFreeSurfer.sh

session_list=`find /mnt/cina/GLIMPSE_OSA/data/ -mindepth 2 -maxdepth 2`

for ses in ${session_list[@]}; do
	mkdir -p ${ses}/segcsvd
    mri_label2vol --seg ${ses}/freesurfer8/mri/synthseg.rca.mgz --temp ${ses}/freesurfer8/mri/rawavg.mgz \
    --o ${ses}/segcsvd/synthseg.nii.gz --regheader ${ses}/freesurfer8/mri/synthseg.rca.mgz
    fslmaths ${ses}/anat/t1w.nii -mul 0 ${ses}/segcsvd/empty_mask_T1space.nii.gz
    fslmaths ${ses}/anat/t1w.nii -mul 1 ${ses}/segcsvd/T1.nii.gz
    
    # set variables for pvs seg
    in_dir=${ses}/segcsvd
    out_dir=${in_dir}
    t1_fn=T1.nii.gz
    sif=${PROJECT_HOME}/repo/segcsvd_rc03.sif
    seg_wmh_fn=empty_mask_T1space.nii.gz
    synth_fn=synthseg.nii.gz
    out_fn=seg_pvs.nii.gz
    skip_mask_and_bias=false
    cleanup=true
    seg_pvs_thr=0.35

    #run pvs seg
    singularity run --bind ${in_dir}:/indir,${out_dir}:/outdir \
    --pwd / \
    ${sif} \
    segment_pvs \
    /indir/${t1_fn} \
    /indir/${synth_fn} \
    /indir/${seg_wmh_fn} \
    /outdir/${out_fn} \
    "1.0,1.4" 0 \
    ${skip_mask_and_bias} \
    ${cleanup} \
    ${seg_pvs_thr}
done