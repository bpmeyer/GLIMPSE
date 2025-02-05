# GLIMPSE
Processing Pipeline for GLIMPSE projects

GLIMPSE_OSA_download2nii.py
1. Reads cvs file. Default is MRIScanLog.csv or use -f flag to specify different name
2. Download all dcm and a .zip file from xnat. You will be prompted for your xnat user name and password
3. convert dcms to nii
4. rename nii and move to appropriate folders
