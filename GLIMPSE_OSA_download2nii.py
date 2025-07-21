#!/usr/bin/env python3
"""
==============

script to remane nifti files based on lines in a csv file with:
inputfilename, outputfilename


BPM, 11/14/24: first version
2/25/25: BIDs update, parrec
7/21/25: Cleaned up by BPM

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
import certifi
import requests
import getpass
import json
import sys
from zipfile import ZipFile
sys.path.append('/mnt/cina/GLIMPSE_OSA/repo') 
import get_glimpse_xnat_data

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

def get_suffix(filename):
    match = re.search(r"\.nii(\.gz)?$", filename)
    return match.group(0) if match else None

def niftiRename2Standard(scanlist,niftipath, outpath):

    #these correspond to {generic output name,  actual sequence name (dicom), column in renaming csv file, output dir}
    scans = {'t1w':['MPRAGE_0.8_CS_F',2,'anat'],
    't2w': ['3D_Brain_VIEW_T2_32chSHC_0.8_CS_F',3,'anat'],
    'csf_qf':['CSF_QF_retrospectivetrigger',4,'qf'],
    'ivim_apa':['DTI_IVIM_14b0_APA', 5,'dwi'],
    'ivim_app':['DTI_IVIM_b0_APP', 6,'dwi'],
    'measl_650':['MEASL_650',7,'asl'],
    'measl_950':['MEASL_950',8,'asl'],
    'measl_m0':['MEASL_M0_NEW',9,'asl']}
             
    print(', '.join(scanlist))

    #for each of the file types/scans we want to rename
    for key in scans:
        #these are multi-echo outputs, so treat them differently
        #since dcm2niix does not sort echoes properly, get the TE info from the
        #nifti header, and resort into key_echo1, key_echo2, etc
        if key in ['csf_qf']:
            value_list = scans[key]
            #get list of matching files using regular expression (glob)
            currscannum = scanlist[value_list[1]]
            if currscannum == 'NA':
                print('No scan number for '+ key+', skipping')
                continue;
            regex_name = niftipath + '/*' + value_list[0]+'*_'+ currscannum+'01*.nii*'
            files = sorted(glob.glob(regex_name))

            for delay in files:
                origSuffix = get_suffix(delay)
                basename = delay.rsplit(".nii", 1)[0]
                json_name = f"{basename}.json"
                with open(json_name, 'r') as json_file:
                    data = json.load(json_file)
                trigger_time = data.get('TriggerDelayTime', "") if "ImageType" in data else ""
                image_type = "_ph" if "PHASE" in data.get("ImageType", "") else ""
                outdir = os.path.join(outpath,value_list[2])
                newname = os.path.join(outdir, key + '_t'+str(trigger_time) + image_type + ''.join(origSuffix))
                newjson = os.path.join(outdir, key + '_t'+str(trigger_time) + image_type + '.json')
                if not os.path.isdir(outdir):
                    os.mkdir(outdir)
                #print('mv ' + orig_file + ' ' + newname)
                shutil.copy(orig_file, newname)
                shutil.copy(json_name, newjson)

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
            if os.path.exists(orig_file):
                basename = orig_file.rsplit(".nii", 1)[0]
                json_name = f"{basename}.json"
                # rename and move bvec and bval for dwi 
                bvec_path = f"{basename}.bvec"
                bval_path = f"{basename}.bval"
                origSuffix = get_suffix(orig_file)
                #handle multiple suffixes (.nii.gz) if they exist, since this is just renaming/copying the file
                outdir = os.path.join(outpath,value_list[2])
                newname = os.path.join(outdir, key +  ''.join(origSuffix))
                newjson = os.path.join(outdir, key + '.json')
                newbvec = os.path.join(outdir, key + '.bvec')
                newbval = os.path.join(outdir, key + '.bval')
                if not os.path.isdir(outdir):
                    os.mkdir(outdir)
                #print('mv ' + orig_file + ' ' + newname)
                shutil.copy(orig_file, newname)
                shutil.copy(json_name, newjson)
                if os.path.exists(bvec_path):
                    shutil.copy(bvec_path, newbvec)
                if os.path.exists(bval_path):
                    shutil.copy(bval_path, newbval)
            else:
                print('no files for ' + regex_name)


def parrecRename2Standard(scanlist,zipfile_dir, outpath):

    #these correspond to {generic output name,  acqual sequence name (dicom), column in renaming csv file}
    scans = {'measl_650':['MEASL_650',7,'asl'],
    'measl_950':['MEASL_950',8,'asl'],
    'measl_m0':['MEASL_M0_NEW',9,'asl'],
    'psalog':['ScanPsaLog',10,'physio']}
             
    print(', '.join(scanlist))

    #for each of the file types/scans we want to rename
    for key in scans:
        if key in ['psalog']:
            value_list = scans[key]
            physiofile_name = zipfile_dir + '/*.log'
            physiofiles = sorted(glob.glob(physiofile_name))
            if physiofiles:
                for orig_log in physiofiles:
                    basename = os.path.basename(orig_log).split('.')[0]
                    physio_outdir = os.path.join(outpath,value_list[2])
                    physio_newname = os.path.join(physio_outdir,basename +'.log')
                    if not os.path.isdir(physio_outdir):
                        os.mkdir(physio_outdir)
                    shutil.copy(orig_log, physio_newname)
            else:
                print('no physio files')
        else:
            value_list = scans[key]
            # use regular expression matching (glob)
            currscannum = scanlist[value_list[1]]
            if currscannum == 'NA':
                print('No scan number for '+ key+', skipping')
                continue
            regex_name = zipfile_dir + '/*' + value_list[0]+'*_'+ currscannum+'*.PAR'
            parfiles = sorted(glob.glob(regex_name))
            if parfiles:
                for parorig_file in parfiles:
                    basename = parorig_file.rsplit(".PAR", 1)[0]
                    recorig_file = f"{basename}.REC"
                    outdir = os.path.join(outpath,value_list[2])
                    par_newname = os.path.join(outdir, key + '.PAR')
                    rec_newname = os.path.join(outdir, key + '.REC')
                    if not os.path.isdir(outdir):
                        os.mkdir(outdir)
                    shutil.copy(parorig_file, par_newname)
                    shutil.copy(recorig_file, rec_newname)
            else:
                print('no parrec files for' + key)


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

#download parrec session data from xnat
def download_parrec(connection, project, session, parrec, outputdir):
    print('Downloading PARREC ' + session + ' from project '+project)
    xnat_project = connection.projects[project]

    try:
        xnat_parrec= xnat_project.resources["PARREC"]
    except:
        print('parrec files xnat error')
        return False
    try:
        xnat_parrec_session = xnat_parrec.files[parrec]
    except:
        print('Session parrec missing')
        return False
    try:
        xnat_parrec_session.download(outputdir)
    except:
        print('xnat parrec download error')
        return False

    return True

def main():
    #get input arguments
    parser = argparse.ArgumentParser(description='Prints all files from a certain scan.')
    parser.add_argument('-f', type=str, required=False, help='scanlogcsv',default='MRIScanLog.csv')
    args = parser.parse_args()
    scanlogcsv = args.f

    print("*****1.Writing MRI Scan Log")
    get_glimpse_xnat_data.main(xnatusername, xnatpassword)
    print('done csv script')

    print("*****2.Download from CSV file")
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
                # Split by letters and underscores
                parts = re.split(r"[A-Za-z_v]+", subject)
                subject_num = parts[1].lstrip('0')
                if len(subject_num) == 1:
                    subject_num = '0' + subject_num
                subject_id = f"sub-{subject_num}"
                session_id = f"ses-{parts[2]}"

                parrec= row[10] #.zip file with parrec and physio data

                #these are setup as seperate steps, files can be
                #downloaded
                #converted to nifti
                #remaned appropriately
                # in successive steps and if one step fails can continue with others.
                #This is better for early testing for example, not to have to download
                # if the conversion/processing is not functional.
                datadir = 'data'
                if not os.path.exists(datadir):
                    os.mkdir(datadir)
                bidspath = os.path.join(datadir,subject_id,session_id)
                currssubpath = os.path.join(datadir,subject)
                currsesspath = os.path.join(currssubpath,session)
                print(currsesspath)

                success = True
                if not os.path.isdir(bidspath):
                    success = download_session(connection, project, subject, session, currssubpath)
                    os.makedirs(bidspath, exist_ok=True)
                    os.rename(currsesspath,bidspath)
                    shutil.rmtree(currssubpath)
                if success == False:
                    print('Xnat error, skipping.')
                    continue

                #download parrec zip
                zipfile_name = f"{row[10]}.zip"
                zipfile_path = os.path.join(bidspath,zipfile_name)
                zipfile_dir = os.path.join(bidspath,parrec)
                success = True
                try:
                    success = download_parrec(connection, project, session, zipfile_name, zipfile_path)
                    if os.path.isfile(zipfile_path):
                        with ZipFile(zipfile_path,'r') as zipobject:
                            zipobject.extractall(bidspath)
                        os.remove(zipfile_path)

                except Exception as e:
                    print(f"Error occurred: {e}")
                    success = False
                    continue

                dcmpath = os.path.join(bidspath,'scans')
                niipath = os.path.join(bidspath,'niftis')
                outpath = bidspath

                # if the dicom data is there, but nifti are not, convert with dcm2niix
                if (os.path.isdir(dcmpath) and not os.path.isdir(niipath)):
                    print('Converting ' + session + ' to nii')
                    os.mkdir(niipath)
                    dcmcmd = os.path.join(dcm2niixPath,'dcm2niix') + ' -o '+ niipath + ' -f %f_%p_%s_%e '+ dcmpath
                    process = subprocess.run(dcmcmd, stdout=subprocess.PIPE,shell=True)

                #delete dicom files once converted
                if os.path.isdir(dcmpath):
                    shutil.rmtree(dcmpath)

                #rename nifti files to BIDS-like formats.
                if os.path.isdir(niipath):
                    print('Renaming files ' + session)
                    try:
                        niftiRename2Standard(row, niipath, outpath)
                        parrecRename2Standard(row, zipfile_dir, outpath)
                    finally:#delete converted nii files once copied/renamed 
                        shutil.rmtree(niipath) 

                #delete converted zip files once copied/renamed      
                if os.path.isdir(zipfile_dir):
                    shutil.rmtree(zipfile_dir)
                    

if __name__ == '__main__':
    main()