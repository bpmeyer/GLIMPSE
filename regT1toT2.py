import os
import multiprocessing
import shutil
from pathlib import Path
import ants

# Set project home and session list
Proj_home = "/mnt/cina/GLIMPSE_OSA/"
session_list = list(Path(Proj_home, "data").glob("*/"))
parallelize = min(multiprocessing.cpu_count() // 2, 10)

def run_registration(session):
    print(f"Processing: {session.name}")
    
    for ses in ["ses-1", "ses-2"]:
        anat_path = Path(session, ses, "anat")
        t1_path = anat_path / "t1w.nii"
        t2_path = anat_path / "t2w.nii"
        output_prefix = anat_path / "t1wreg2t2w"

        print(f"Checking: {ses}")
        if not t1_path.exists() or not t2_path.exists():
            print(f"Missing T1/T2: {anat_path}")
            continue
        if (output_prefix.with_suffix('.nii.gz')).exists():
            print(f"Output exists: {anat_path}")
            continue

        print(f"Running reg: {anat_path}")
        try:
            t1 = ants.image_read(str(t1_path))
            t2 = ants.image_read(str(t2_path))

            reg = ants.registration(fixed=t2, moving=t1, type_of_transform='DenseRigid')
            ants.image_write(reg['warpedmovout'], str(output_prefix) + '.nii.gz')

            transform_mat = reg['fwdtransforms'][0]
            transform_mat_name = str(output_prefix) + '0GenericAffine.mat'
            shutil.move(transform_mat, transform_mat_name)

            print(f"Registration done: {anat_path}")
        except Exception as e:
            print(f"Registration failed for {anat_path}: {e}")

if __name__ == "__main__":
    print("starting reg")
    with multiprocessing.Pool(parallelize) as pool:
        pool.map(run_registration, session_list)
    print("reg done")
