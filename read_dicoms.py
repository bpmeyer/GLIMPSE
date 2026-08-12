# quick script to read dicoms and print out the header of the 
# first file that has a certain string in the ImageType field
# can edit for any other field, or to print out all files that match the criteria

from pathlib import Path
import pydicom

folder_path = Path("/mnt/cina/GLIMPSE_WISP/data/sourcedata/dicom/GLW-001/V1/1001-hT2W_IRSE")
target = "CR_IR"

for file_path in sorted(folder_path.glob("*.dcm")):
    try:
        ds = pydicom.dcmread(file_path, stop_before_pixels=True)
    except Exception as e:
        print(f"Error reading {file_path.name}: {e}")
        continue

    if any(target in str(v) for v in getattr(ds, "ImageType", [])):
        print(f"--- {file_path.name} ---")
        print(ds)
        break
else:
    print(f"No file with {target} in ImageType found.")

