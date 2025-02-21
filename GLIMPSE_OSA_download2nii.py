#!/usr/bin/env python3
"""
==============

script to remane nifti files based on lines in a csv file with:
inputfilename, outputfilename


BPM, 11/14/24: first version

"""
import csv
import os  # system functions
import re
import shutil
import subprocess
import glob
import nibabel as nib
from pathlib import Path
import xnat
import argparse
import shutil
import certifi
import requests
import getpass
import json

# some defaults for this project
xnathost = 'https://xnatpro.ibic.washington.edu'
project = 'GLIMPSE-OSA'
dcm2niixPath = '/usr/bin'

# this greates path to dcm2niix if added and cloned from github and saved in bin folder
# thisfilepath = os.path.abspath(os.path.dirname(__file__))
# binpath = os.path.abspath(os.path.join(thisfilepath,'bin'))
# dcm2niixPath = binpath

# will prompt for password
xnatusername = input("Enter your xnat username: ")
xnatpassword = getpass.getpass("Enter your xnat password: ")

def niftiRename2Standard(scanlist,niftipath, outpath):

    #these correspond to {generic output name,  acqual sequence name (dicom), column in renaming csv file}
    scans = {'t1':['MPRAGE_0.8_CS_F',2],
    't2': ['3D_Brain_VIEW_T2_32chSHC_0.8_CS_F',3],
    'csf_qf':['CSF_QF_retrospectivetrigger',4],
    'ivim_apa':['DTI_IVIM_14b0_APA', 5],
    'ivim_app':['DTI_IVIM_b0_APP', 6],
    'measl_650':['MEASL_650',7],
    'measl_950':['MEASL_950',8],
    'measl_m0':['MEASL_M0_NEW',9]}
             
    print(', '.join(scanlist))

    #for each of the file types/scans we want to rename
    for key in scans:
        #these are multi-echo outputs, so treat them differently
        #since dcm2niix does not sort echoes properly, get the TE info from the
        #nifti header, and resort into key_echo1, key_echo2, etc
        if key in ['measl_m0']:
            value_list = scans[key]
            #get list of matching files using regular expression (glob)
            currscannum = scanlist[value_list[1]]
            if currscannum == 'NA':
                print('No scan number for '+ key+', skipping')
                continue;
            regex_name = niftipath + '/*' + value_list[0]+'*_'+ currscannum+'01*.nii*'
            files = sorted(glob.glob(regex_name))

            #build joint list of files and the TE stored in the description
            TElist = []
            for echo in files:
                nii_img = nib.load(echo)
                header = nii_img.header
                TE = header['descrip']
                #split the descrip info here with delimiters / = ;, and get the 2nd item ([1]) which is the TE
                teval = re.split(r"[;=\s]+",str(TE))
                #print(teval)
                #convert it to a float value so it can be sorted
                TElist.append(float(teval[1]))
                #print(TElist)

            #zip the matching lists into a single list, sort by the 2nd set, then output the sorted filenames
            filesTEs = zip(files, TElist)
            filesTEs = list(filesTEs)
            sortedbyTE = sorted(filesTEs, key = lambda x: x[1]) #this sorts by the TE float value
            sortedfiles, sortedTEs =  zip(*sortedbyTE)

            # now rename the ordered/sorted files to key_echo1, key_echo2, etc,
            # where key is still the generic filename
            echonum = 1
            for echo in sortedfiles:
                orig_file = echo
                origSuffix = Path(orig_file).suffixes
                #handle multiple suffixes (.nii.gz) if they exist, since this is just renaming/copying the file
                outdir = os.path.join(outpath,key)
                newname = os.path.join(outdir, key + '_echo'+str(echonum) + ''.join(origSuffix))

                echonum = echonum + 1
                if not os.path.isdir(outdir):
                    os.mkdir(outdir)

                print('mv ' + orig_file + ' ' + newname)
                shutil.copy(orig_file, newname)

        # single one-to-one file mapping (not multi-echo)
        else:
            value_list = scans[key]
            # use regular expression matching (glob)
            currscannum = scanlist[value_list[1]]
            if currscannum == 'NA':
                print('No scan number for '+ key+', skipping')
                continue;
            regex_name = niftipath + '/*' + value_list[0]+'*_'+ currscannum+'01*.nii*'
            files = sorted(glob.glob(regex_name))
            orig_file = files[0]

            origSuffix = Path(orig_file).suffixes
            #handle multiple suffixes (.nii.gz) if they exist, since this is just renaming/copying the file
            outdir = os.path.join(outpath,key)
            newname = os.path.join(outdir, key +  ''.join(origSuffix))
            #print(regex_name)
            if not os.path.isdir(outdir):
                os.mkdir(outdir)
                print('mv ' + orig_file + ' ' + newname)
                shutil.copy(orig_file, newname)
            else:
                print('no files for' + regex_name)


#download a full session data from xnat
def download_session(connection, project, subject, session, outputdir):
    print('Downloading ' + session + ' from project '+project)
    xnat_project = connection.projects[project]
    try:
        xnat_subject = xnat_project.subjects[subject]
    except:
        print('Subject xnat error')
        return False
    try:
        xnat_experiment = xnat_subject.experiments[session]
    except:
        print('Session xnat error')
        return False
    try:
        xnat_experiment.download_dir(outputdir)
    except:
        print('xnat download error')
        return False

    return True

def clean_and_merge_csf_qf(niipath, outpath):
    csf_folder = os.path.join(os.path.dirname(niipath), 'csf_qf')
    os.makedirs(csf_folder, exist_ok=True)

    if not os.path.exists(niipath):
        print(f"Error: niipath '{niipath}' does not exist.")
        return

    os.makedirs(csf_folder, exist_ok=True)
    
    all_files = os.listdir(niipath)
    print(f"Files in niipath ({niipath}): {all_files}")

    # Find all NIfTI files starting with "scans_WIP_CSF" in the niipath
    nii_files = [f for f in all_files if f.startswith("scans_WIP_CSF") and (f.endswith(".nii.gz") or f.endswith(".json"))]
    
    if not nii_files:
        print("No matching NIfTI files found.")
        return

    for file in nii_files:
        src_path = os.path.join(niipath, file)
        dest_path = os.path.join(csf_folder, file)
        
        if os.path.exists(dest_path):
            base, ext = os.path.splitext(file)
            counter = 1
            new_dest_path = os.path.join(csf_folder, f"{base}_{counter}{ext}")
            while os.path.exists(new_dest_path):
                counter += 1
                new_dest_path = os.path.join(csf_folder, f"{base}_{counter}{ext}")
            shutil.move(src_path, new_dest_path)
            print(f"Renamed and moved {file} to {dest_path}")
        else:
            shutil.move(src_path, dest_path)
            print(f"Moved {file} to {dest_path}")

    # Rename NIfTI files based on phase and magnitude
    for file in os.listdir(csf_folder):
        if file.endswith('.nii.gz') or file.endswith('.json'):
            file_path = os.path.join(csf_folder, file)
            base, ext = os.path.splitext(file)
            base = base.replace('.nii', '')
            trigger_time = ""
            
            json_path = os.path.join(csf_folder, f"{base}.json")
            if os.path.exists(json_path):
                with open(json_path, 'r') as json_file:
                    data = json.load(json_file)
                    trigger_time = f"_t{data.get('TriggerDelayTime', '')}" if 'TriggerDelayTime' in data else ""
            
            if "ph" in base:
                new_name = f"csf_qf_ph{trigger_time}.nii.gz"
            else:
                new_name = f"csf_qf_mag{trigger_time}.nii.gz"

            new_path = os.path.join(csf_folder, new_name)
            os.rename(file_path, new_path)
            print(f"Renamed {file} to {new_name}")

def restructure_folders():
    current_dir = os.getcwd()
    folders = [f for f in os.listdir(current_dir) if os.path.isdir(f) and f.startswith("GLOtwo")]

    if not folders:
        print("No matching folders found.")
        return

    # Extract subject ID from the first folder name (assumes consistent naming)
    subject_id = folders[0][6:9]  # Extracts '001' from 'GLOtwo001_v1'
    subject_folder = os.path.join(current_dir, f"sub-{subject_id}")

    # Create subject folder if it doesn't exist
    os.makedirs(subject_folder, exist_ok=True)

    for folder in folders:
        old_path = os.path.join(current_dir, folder)
        
        # Check if the folder contains a subfolder with the same name (GLOtwo001_v1/GLOtwo001_v2 structure)
        inner_folder = os.path.join(old_path, folder)
        if os.path.isdir(inner_folder):
            # Move contents from the inner folder to the parent folder (i.e., flatten it)
            for item in os.listdir(inner_folder):
                item_path = os.path.join(inner_folder, item)
                shutil.move(item_path, old_path)

            # Remove the now empty inner folder
            os.rmdir(inner_folder)

        # Determine the new folder name (Visit 1 or Visit 2)
        if "v1" in folder:
            new_name = "Visit 1"
        elif "v2" in folder:
            new_name = "Visit 2"
        else:
            continue  # Skip if the folder doesn't match expected format

        new_path = os.path.join(current_dir, new_name)

        # Rename the folder in place
        os.rename(old_path, new_path)

        # Move the renamed folder into the subject folder
        final_path = os.path.join(subject_folder, new_name)
        os.rename(new_path, final_path)

        anat_folder = os.path.join(final_path, "anat")
        os.makedirs(anat_folder, exist_ok=True)

        # Move the t1 and t2 folders inside 'anat'
        for subfolder in ['t1', 't2']:
            subfolder_path = os.path.join(final_path, subfolder)
            if os.path.isdir(subfolder_path):
                shutil.move(subfolder_path, anat_folder)

        measl_folders = [f for f in os.listdir(final_path) if os.path.isdir(os.path.join(final_path, f)) and 'measl' in f]
        if measl_folders:
            measl_folder_path = os.path.join(final_path, "measl")
            os.makedirs(measl_folder_path, exist_ok=True)

            for measl in measl_folders:
                measl_path = os.path.join(final_path, measl)
                shutil.move(measl_path, measl_folder_path)

        ivim_folders = [f for f in os.listdir(final_path) if os.path.isdir(os.path.join(final_path, f)) and 'ivim' in f]
        if ivim_folders:
            ivim_folder_path = os.path.join(final_path, "ivim")
            os.makedirs(ivim_folder_path, exist_ok=True)

            for ivim in ivim_folders:
                ivim_path = os.path.join(final_path, ivim)
                shutil.move(ivim_path, ivim_folder_path)

    print(f"Folders successfully reorganized under {subject_folder}.")

def main():
    #get input arguments
    parser = argparse.ArgumentParser(description='Prints all files from a certain scan.')
    parser.add_argument('-f', type=str, required=False, help='scanlogcsv',default='MRIScanLog.csv')
    args = parser.parse_args()
    scanlogcsv = args.f

    #open the csv file for each row is a dataset (session/experiment)
    with open(scanlogcsv, newline='') as csvfile:
        print('Reading csv file: ' + scanlogcsv)
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        next(reader, None)  # skip the headers, !!!it would be better here to use the dictionary to match up the keys with the header names.


        print('Opening xnat connection')
        with xnat.connect(xnathost, user=xnatusername, password=xnatpassword) as connection:

            for row in reader:
                print(', '.join(row))
                subject = row[0]
                session = row[1]


                #these are setup as seperate steps, files can be
                #downloaded
                #converted to nifti
                #remaned appropriately
                # in successive steps and if one step fails can continue with others.
                #This is better for early testing for example, not to have to download
                # if the conversion/processing is not functional.


                currsesspath = os.path.join(subject,session)
                print(currsesspath)
                success = True
                if not os.path.isdir(currsesspath):
                    success = download_session(connection, project, subject, session, subject)

                if success == False:
                    print('Xnat error, skipping.')
                    continue


                dcmpath = os.path.join(currsesspath,'scans')
                niipath = os.path.join(currsesspath,'niftis')
                outpath = currsesspath

                # is the dicom data is there, but nifti are not, convert with dcm2niix
                if (os.path.isdir(dcmpath) and not os.path.isdir(niipath)):
                    print('Converting ' + session + ' to nii')
                    os.mkdir(niipath)
                    dcmcmd = os.path.join(dcm2niixPath,'dcm2niix') + ' -o '+ niipath + ' -f %f_%p_%s_%e '+ dcmpath
                    print(dcmcmd)
                    process = subprocess.run(dcmcmd, stdout=subprocess.PIPE,shell=True)


                #delete dicom files once converted
                if os.path.isdir(dcmpath):
                    shutil.rmtree(dcmpath)

                #rename nifti files to BIDS-like formats.
                if os.path.isdir(niipath):
                    print('Renaming files ' + session)
                    try:
                        niftiRename2Standard(row, niipath, outpath)
                        clean_and_merge_csf_qf(niipath, outpath)
                    finally:
                        shutil.rmtree(niipath)
                    #delete converted nii files once copied/renamed
    restructure_folders()

                    


if __name__ == '__main__':
    main()
