# GLIMPSE
Processing Pipeline for GLIMPSE projects. Steps are:

1. download dicoms from xnat

2. convert dicoms to BIDS niftis using heudiconv image 

3. Edit BIDS .json sidecars for Philips data. Philips dicoms do not include     slice timing, phase encode polarity and this info must be included for fmriprep. The fmap and func images must also be linked via the .json meta data.

4. Freesurfer recon-all with version 8. this version is faster, has a more accurate brain mask and provides csf masks. Output is saved in derivatives/freesufer/sub-*_ses-*. Freesurfer output is not BIDS complient but this structure is easily passed to fmriprep

5. fmriprep

## CSF T1 Mapping 

1. Estimate the T1-time for each of the IRSE scans: `allsubs_t1_times`. 
    - This runs `estimate_t1_times` for each subject's sessions. 
    - If the necessary metadata json file is not present, `make_mixed_meta` will extract the information from the Nifiti files.

2. Register the IRSE images to the T1w image: `allsubs_reg_SE`. 
    - This runs `register_SE_T1_greedy`, which uses a container to register the SE images to the reference T1 image. 

3. Register the T1 Maps to the registered IRSE image: `allsubs_reg_T1maps`
    - This runs `register_T1maps_greedy` for each subject's sessions.
    - For reference session: applies the transform calculated in the previous step to the T1 map.  
    - For all other sessions: registers the session's SE image to the reference image and then applies that transform to the T1 map. 

4. Create CSF mask using the SE image ... (in progress)
