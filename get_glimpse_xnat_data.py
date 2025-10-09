# DONT USE
# 1. Connect to the XNAT server (get from download script)
# 2. Loop through all subjects and their sessions
# 3. For each session: go through all scasn and assign them to specific types
# 4. Trim - remove last two nums
# 5. If a session has a version: adjust the subject ID to include v num
# 6. Store all the scan info in a dict for subject and session
# 7. Save MRIScanLog.csv

import csv
import xnat
import getpass
import os
import re
import sys


XNAT_HOST = 'https://xnatpro.ibic.washington.edu'
PROJECT = 'GLIMPSE-OSA'


SCAN_TYPES = ['MPRAGE', 'T2', 'CSF_QF', 'IVIM_14b0_APA', 'IVIM_b0_APP', 'MEASL_650', 'MEASL_950', 'MEASL_M0', 'parrec']

def extract_parrec_subject(session_label):
    print(f"Get parrec: {session_label}")
    if '_v' in session_label:
        base_id = session_label.split('_v')[0]
        version = session_label.split('_v')[1]
        print(f"Version: {version}")
        if version == '1':
            return base_id
        else:
            return f"{base_id}_{int(version)}"
    else:
        return session_label

def fetch_xnat_data(xnat_username, xnat_password):
    data = []
   
    print("Connecting to XNAT...")
    with xnat.connect(XNAT_HOST, user=xnat_username, password=xnat_password) as connection:
        print("Connected.")
        project = connection.projects[PROJECT]
       
        for subject in project.subjects.values():
            for session in subject.experiments.values():
                print(f"Processing session: {session.label}")
                scan_info = {scan_type: 'NA' for scan_type in SCAN_TYPES}
                scan_info['subject'] = subject.label
                scan_info['session'] = session.label

                for scan in session.scans.values():
                    scan_type = scan.type
                    scan_id = scan.id

                    for key in SCAN_TYPES:
                        if key in scan_type:
                            scan_info[key] = (extract_parrec_subject(session.label) if key == 'parrec' else scan_id[0])
                            print(f"Scan: {scan_type}, ID: {scan_id}")
                data.append(scan_info)

    print(f"Sort {len(data)}")
    data.sort(key=lambda x: (x['subject'], x['session']))
    return data

def write_to_csv(data, filename='MRIScanLog_AUTODONTUSE.csv'):
    headers = ['subject', 'session'] + SCAN_TYPES
    abs_path = os.path.abspath(filename)
   
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)

    print(f"\nSaved: {abs_path}")

def main(xnat_username,xnat_password):
    scan_data = fetch_xnat_data(xnat_username, xnat_password)
    print(f"found {len(scan_data)} entries.")
    write_to_csv(scan_data)

if __name__ == "__main__":
    main(sys.argv[1],sys.argv[2])
