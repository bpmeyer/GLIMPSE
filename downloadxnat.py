#!/usr/bin/env python3
"""
Download GLIMPSE session data from XNAT without renaming files.

"""
import argparse
import csv
import getpass
import os
from zipfile import ZipFile
import xnat

# some defaults for this project
xnathost = 'https://xnatpro.ibic.washington.edu'

# will prompt for password
project = input("Enter xnat project: ")
xnatusername = input("Enter your xnat username: ")
xnatpassword = getpass.getpass("Enter your xnat password: ")

def download_session(connection, project_name, subject, session, outputdir):
    """Download a full session directory from XNAT."""
    print('Downloading ' + session + ' from project ' + project_name)
    xnat_project = connection.projects[project_name]
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


def download_physio(connection, project_name, session, physio_zip, outputdir):
    """Download a physiology zip file from the project-level PARREC resource."""
    print('Downloading physiology data ' + session + ' from project ' + project_name)
    xnat_project = connection.projects[project_name]

    try:
        xnat_physio = xnat_project.resources['PARREC']
    except:
        print('physiology files xnat error')
        return False
    try:
        xnat_physio_session = xnat_physio.files[physio_zip]
    except:
        print('Session physiology zip missing')
        return False
    try:
        xnat_physio_session.download(outputdir)
    except:
        print('xnat physiology download error')
        return False

    return True


def download_xnat_from_csv(
    scanlogcsv='MRIScanLog.csv',
    datadir='data',
    host=xnathost,
    project_name=project,
    username=None,
    password=None,
    extract_physio=True,
):
    """
    Download sessions listed in a scan-log CSV without renaming anything.

    The CSV is expected to use the same columns as MRIScanLog.csv:
    subject in column 0, session in column 1, and physiology zip basename in column 10.
    """
    if username is None:
        username = input('Enter your xnat username: ')
    if password is None:
        password = getpass.getpass('Enter your xnat password: ')

    print('*****Download from CSV file')
    os.makedirs(datadir, exist_ok=True)

    with open(scanlogcsv, newline='') as csvfile:
        print('Reading csv file: ' + scanlogcsv)
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        next(reader, None)  # skip the headers

        print('Opening xnat connection')
        with xnat.connect(host, user=username, password=password) as connection:
            for row in reader:
                print(', '.join(row))
                subject = row[0]
                session = row[1]
                physio = row[10]

                subject_path = os.path.join(datadir, subject)
                session_path = os.path.join(subject_path, session)
                print(session_path)

                if not os.path.isdir(session_path):
                    success = download_session(
                        connection,
                        project_name,
                        subject,
                        session,
                        subject_path,
                    )
                    if success is False:
                        print('Xnat error, skipping.')
                        continue

                if physio in ['', 'NA']:
                    print('No physiology zip listed, skipping physiology download.')
                    continue

                zipfile_name = f'{physio}.zip'
                zipfile_path = os.path.join(session_path, zipfile_name)
                success = download_physio(
                    connection,
                    project_name,
                    session,
                    zipfile_name,
                    zipfile_path,
                )
                if success is False:
                    print('Physiology download error, skipping physiology extraction.')
                    continue

                if extract_physio and os.path.isfile(zipfile_path):
                    with ZipFile(zipfile_path, 'r') as zipobject:
                        zipobject.extractall(session_path)


def main():
    parser = argparse.ArgumentParser(
        description='Download GLIMPSE-OSA XNAT sessions without renaming files.'
    )
    parser.add_argument(
        '-f',
        type=str,
        required=False,
        help='scanlogcsv',
        default='MRIScanLog.csv',
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        required=False,
        help='directory where XNAT data will be downloaded',
        default='data',
    )
    args = parser.parse_args()

    download_xnat_from_csv(scanlogcsv=args.f, datadir=args.data_dir)


if __name__ == '__main__':
    main()
