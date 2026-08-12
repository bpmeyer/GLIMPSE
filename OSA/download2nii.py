#!/usr/local/anaconda3/bin/python3


import csv
import os
import re
import shutil
import tempfile
import xnat
import argparse
import getpass
from zipfile import ZipFile

# some defaults for this project
xnathost = 'https://xnatpro.ibic.washington.edu'
project = 'GLIMPSE-OSA'
dcm2niixPath = '/usr/bin'
PROJECT_PATH = "/mnt/cina/GLIMPSE_OSA/tmp"

# will prompt for password
xnatusername = input("Enter your xnat username: ")
xnatpassword = getpass.getpass("Enter your xnat password: ")

def get_suffix(filename):
    match = re.search(r"\.nii(\.gz)?$", filename)
    return match.group(0) if match else None


#extract a zip into target_dir, dropping a single top-level wrapper directory if present
def extract_zip_flattened(zipfile_path, target_dir):
    with tempfile.TemporaryDirectory() as temp_dir:
        with ZipFile(zipfile_path, 'r') as zipobject:
            zipobject.extractall(temp_dir)

        entries = os.listdir(temp_dir)
        if len(entries) == 1 and os.path.isdir(os.path.join(temp_dir, entries[0])):
            source_dir = os.path.join(temp_dir, entries[0])
        else:
            source_dir = temp_dir

        for name in os.listdir(source_dir):
            shutil.move(os.path.join(source_dir, name), os.path.join(target_dir, name))


#download the full experiment (like GLIMPSE_OSA_download2nii.py does), then keep
#only the DICOM resource files, flattened to target_dir/<scan>/*.dcm
def download_dicom_resources(xnat_experiment, target_dir):
    os.makedirs(target_dir, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        xnat_experiment.download_dir(temp_dir)

        scans_dir = os.path.join(temp_dir, xnat_experiment.label, 'scans')
        if not os.path.isdir(scans_dir):
            return

        for scan_name in sorted(os.listdir(scans_dir)):
            dicom_files_dir = os.path.join(scans_dir, scan_name, 'resources', 'DICOM', 'files')
            if os.path.isdir(dicom_files_dir):
                shutil.move(dicom_files_dir, os.path.join(target_dir, scan_name))


#download only the DICOM resources of a session from xnat. xnat_subject_label and
#xnat_session_label are the XNAT subject/experiment labels (e.g. both "GLW-001-V2"
#for this project), distinct from the BIDS-style subject/session directory names.
def download_session(connection, project, xnat_subject_label, xnat_session_label, target_dir):
    print('Downloading ' + xnat_session_label + ' from project ' + project)
    xnat_project = connection.projects[project]
    try:
        xnat_subject = xnat_project.subjects[xnat_subject_label]
    except:
        print('Subject xnat error')
        return False
    try:
        xnat_experiment = xnat_subject.experiments[xnat_session_label]
    except:
        print('Session xnat error')
        return False
    try:
        download_dicom_resources(xnat_experiment, target_dir)
    except Exception as e:
        print(f'xnat download error: {e}')
        return False
    return True

#download physio session data from xnat
def download_physio(connection, project, zipfile_name, zipfile_path):
    print('Downloading physio_zip ' + zipfile_name + ' from project '+ project)
    xnat_project = connection.projects[project]
    try:
        xnat_physio= xnat_project.resources['PARREC']
    except:
        print('physio files xnat error')
        return False
    try:
        xnat_physio_session= xnat_physio.files[zipfile_name]
    except:
        print('Session physio missing')
        return False
    try:
        xnat_physio_session.download(zipfile_path)
    except:
        print('xnat physio download error')
        return False

    return True

def main():
    #get input arguments
    parser = argparse.ArgumentParser(description='Prints all files from a certain scan.')
    parser.add_argument('-f', type=str, required=False, help='scanlogcsv',default=os.path.join('/mnt/cina/GLIMPSE_OSA','MRIScanLog.csv'))
    args = parser.parse_args()
    scanlogcsv = args.f

    print("*****Download from CSV file")
    #open the csv file for each row is a dataset (session/experiment)
    with open(scanlogcsv, newline='') as csvfile:
        print('Reading csv file: ' + scanlogcsv)
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        next(reader, None)  # skip the headers, !!!it would be better here to use the dictionary to match up the keys with the header names.


        print('Opening xnat connection')
        with xnat.connect(xnathost, user=xnatusername, password=xnatpassword) as connection:

            for row in reader:
                print(', '.join(row))
                #on xnat, the subject and session labels are both the combined
                #form e.g. "GLW-001-V2"; split that into the subject/session
                #directory names we actually want, e.g. "GLW-001" and "V2"
                xnat_subject_label = row[0].strip()
                xnat_session_label = row[1].strip()

                subject, session = xnat_subject_label.rsplit('_', 1)
                physio= row[10] #.zip file w physio data

                #download
                datadir = os.path.join(PROJECT_PATH,'data','sourcedata')
                dicomdir = os.path.join(datadir,'dicom')
                if not os.path.exists(dicomdir):
                    os.makedirs(dicomdir)
                subjpath = os.path.join(dicomdir,subject)
                sesspath = os.path.join(subjpath,session)
                print(sesspath)

                success = True
                if not os.path.isdir(sesspath):
                    success = download_session(connection, project, xnat_subject_label, xnat_session_label, sesspath)
                    if not success:
                        shutil.rmtree(sesspath, ignore_errors=True)
                if success == False:
                    print('Xnat error, skipping.')
                    continue

                #download physio zip
                physiodir = os.path.join(datadir,'physio')
                physiosubjpath = os.path.join(physiodir,subject)
                physiosesspath = os.path.join(physiosubjpath,session)

                zipfile_name = f"{row[10]}.zip"
                print(zipfile_name)
                zipfile_path = os.path.join(physiosubjpath,zipfile_name)
                success = True
                if not os.path.isdir(physiosesspath):
                    os.makedirs(physiosubjpath, exist_ok=True)
                    success = download_physio(connection, project, zipfile_name, zipfile_path)
                    if success:
                        os.makedirs(physiosesspath, exist_ok=True)
                        if os.path.isfile(zipfile_path):
                            extract_zip_flattened(zipfile_path, physiosesspath)
                            os.remove(zipfile_path)
                    elif os.path.isfile(zipfile_path):
                        os.remove(zipfile_path)
                if success == False:
                    print('zip xnat error, skipping.')
                    continue

                    
if __name__ == '__main__':
    main()