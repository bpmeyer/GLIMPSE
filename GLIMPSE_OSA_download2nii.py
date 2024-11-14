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

# some defaults for this project
xnathost = 'https://xnatpro.ibic.washington.edu'
project = 'GLIMPSE-OSA'
dcm2niixPath = '/usr/bin/dcm2niix'

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
            if currscannum is None:
                print('No scan number for '+ key+', skipping')
                continue;
            regex_name = niftipath + '/*' + value_list[0]+'*_'+ currscannum+'0001*.nii*'
            files = sorted(glob.glob(regex_name))

            #build joint list of files and the TE stored in the description
            TElist = []
            for echo in files:
                nii_img = nib.load(echo)
                header = nii_img.header
                TE = header['descrip']
                #split the descrip info here with delimiters / = ;, and get the 2nd item ([1]) which is the TE
                teval = re.split(r'\+|=+|;',str(TE))
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
            if currscannum is None:
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
                    finally:
                        shutil.rmtree(niipath)
                    #delete converted nii files once copied/renamed




if __name__ == '__main__':
    main()
