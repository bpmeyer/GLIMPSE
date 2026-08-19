"""Shared XNAT download logic used by each project's downloadxnat.py
(OSA/downloadxnat.py, WISP/downloadxnat.py, ...).

Project-specific config (XNAT host, project name, on-disk paths, physio
resource key, subject/session label delimiter, physio CSV column) stays in
each project's own script; this module only holds the parts that are
identical across projects. A project script imports run() and calls it with
its own config -- see OSA/downloadxnat.py for the pattern.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import os
import shutil
import tempfile
from zipfile import ZipFile

import xnat


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


#download the full experiment, then keep only the DICOM resource files,
#flattened to target_dir/<scan>/*.dcm
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
#xnat_session_label are the XNAT subject/experiment labels (e.g. "GLW-001-V2"),
#distinct from the BIDS-style subject/session directory names.
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


#download physio session data from xnat. physio_resource is the project's
#XNAT resource key holding physio zips (e.g. 'PARREC' for OSA, 'physio' for WISP)
def download_physio(connection, project, physio_resource, zipfile_name, zipfile_path):
    print('Downloading physio_zip ' + zipfile_name + ' from project ' + project)
    xnat_project = connection.projects[project]
    try:
        xnat_physio = xnat_project.resources[physio_resource]
    except:
        print('physio files xnat error')
        return False
    try:
        xnat_physio_session = xnat_physio.files[zipfile_name]
    except:
        print('Session physio missing')
        return False
    try:
        xnat_physio_session.download(zipfile_path)
    except:
        print('xnat physio download error')
        return False

    return True


#download the DICOMs for one scan-log row into dicomdir/<subject>/<session>,
#skipping if that directory already exists
def process_dicom_row(connection, project, xnat_subject_label, xnat_session_label, subject, session, dicomdir):
    sesspath = os.path.join(dicomdir, subject, session)
    if os.path.isdir(sesspath):
        print(f'DICOMs already downloaded: {sesspath}, skipping.')
        return

    print(sesspath)
    success = download_session(connection, project, xnat_subject_label, xnat_session_label, sesspath)
    if not success:
        shutil.rmtree(sesspath, ignore_errors=True)
        print('Xnat error, skipping DICOM download.')


#download and extract the physiology zip for one scan-log row into
#physiodir/<subject>/<session>, skipping if that directory already exists
#or if the row has no physiology file listed
def process_physio_row(connection, project, physio_resource, physio_basename, subject, session, physiodir):
    if physio_basename in ('', 'NA'):
        print('No physiology file listed, skipping.')
        return

    physiosubjpath = os.path.join(physiodir, subject)
    physiosesspath = os.path.join(physiosubjpath, session)
    if os.path.isdir(physiosesspath):
        print(f'Physiology already downloaded: {physiosesspath}, skipping.')
        return

    os.makedirs(physiosubjpath, exist_ok=True)
    zipfile_name = f'{physio_basename}.zip'
    zipfile_path = os.path.join(physiosubjpath, zipfile_name)
    print(zipfile_name)

    success = download_physio(connection, project, physio_resource, zipfile_name, zipfile_path)
    if success and os.path.isfile(zipfile_path):
        os.makedirs(physiosesspath, exist_ok=True)
        extract_zip_flattened(zipfile_path, physiosesspath)
        os.remove(zipfile_path)
    else:
        if os.path.isfile(zipfile_path):
            os.remove(zipfile_path)
        print('Physio xnat error, skipping.')


#shared CLI entrypoint -- each project's downloadxnat.py calls this from
#main() with its own config (host, project name, paths, csv layout).
def run(*, xnathost, project, project_path, physio_resource, subject_session_delim, physio_csv_column, description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('-f', type=str, required=False, help='scanlogcsv',
                         default=os.path.join(project_path, 'MRIScanLog.csv'))
    parser.add_argument('--dicom', action='store_true',
                         help='download DICOMs (default: both, if neither --dicom nor --physio is given)')
    parser.add_argument('--physio', action='store_true',
                         help='download physiology zips (default: both, if neither --dicom nor --physio is given)')
    args = parser.parse_args()
    scanlogcsv = args.f

    # default to downloading both when neither flag is given
    download_dicom = args.dicom or not (args.dicom or args.physio)
    download_physio = args.physio or not (args.dicom or args.physio)

    xnatusername = input("Enter your xnat username: ")
    xnatpassword = getpass.getpass("Enter your xnat password: ")

    print("*****Download from CSV file")
    #open the csv file for each row is a dataset (session/experiment)
    with open(scanlogcsv, newline='') as csvfile:
        print('Reading csv file: ' + scanlogcsv)
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        next(reader, None)  # skip the headers, !!!it would be better here to use the dictionary to match up the keys with the header names.

        datadir = os.path.join(project_path, 'data', 'sourcedata')
        dicomdir = os.path.join(datadir, 'dicom')
        physiodir = os.path.join(datadir, 'physio')
        if download_dicom:
            os.makedirs(dicomdir, exist_ok=True)
        if download_physio:
            os.makedirs(physiodir, exist_ok=True)

        print('Opening xnat connection')
        with xnat.connect(xnathost, user=xnatusername, password=xnatpassword) as connection:

            for row in reader:
                print(', '.join(row))
                #on xnat, the subject and session labels are both the combined
                #form (e.g. "GLW-001-V2"); split that into the subject/session
                #directory names we actually want, e.g. "GLW-001" and "V2"
                xnat_subject_label = row[0].strip()
                xnat_session_label = row[1].strip()

                subject, session = xnat_subject_label.rsplit(subject_session_delim, 1)
                physio_basename = row[physio_csv_column].strip()

                if download_dicom:
                    process_dicom_row(connection, project, xnat_subject_label, xnat_session_label, subject, session, dicomdir)

                if download_physio:
                    process_physio_row(connection, project, physio_resource, physio_basename, subject, session, physiodir)
