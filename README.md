# GLIMPSE
Processing Pipeline for GLIMPSE projects. Steps are:

1. download dicoms from xnat

2. convert dicoms to BIDS niftis using heudiconv image 

3. Edit BIDS .json sidecars for Philips data. Philips dicoms do not include     slice timing, phase encode polarity and this info must be included for fmriprep. The fmap and func images must also be linked via the .json meta data.




4. Freesurfer recon-all with version 8. this version is faster, has a more accurate brain mask and provides csf masks. Output is saved in derivatives/freesufer/sub-*_ses-*. Freesurfer output is not BIDS complient but this structure is easily passed to fmriprep

5. fmriprep