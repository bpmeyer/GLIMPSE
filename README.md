# GLIMPSE
Processing Pipeline for GLIMPSE projects.

## Getting started

Clone the repo:

```
git clone git@github.com:bpmeyer/GLIMPSE.git
cd GLIMPSE
```

Dependencies are managed with [pixi](https://pixi.sh). Install pixi (see
their [install docs](https://pixi.sh/latest/installation/)), then from the
repo root:

```
pixi install
```

This creates a `.pixi` environment with the Python dependencies each
project's scripts need (pydicom, nibabel, xnat, etc.), pinned in
`pixi.toml`/`pixi.lock`.

Run any command inside that environment with `pixi run <command>`, or drop
into a shell with `pixi shell`. Run `pixi task list` to see the full, current
list. The common ones:

**OSA pipeline**

| Task | What it does |
| --- | --- |
| `pixi run heudiconv-osa` | Convert GLIMPSE-OSA DICOMs to BIDS niftis |

**Shared** (work on any registered/BIDS project directory under `/mnt/cina`)

| Task | What it does |
| --- | --- |
| `pixi run download-xnat` | Download a project's session data from XNAT |
| `pixi run recon-all-parallel` | Run FreeSurfer recon-all in parallel across subjects |
| `pixi run freesurfer-qa` | Open a subject's FreeSurfer output in freeview for QA |
| `pixi run segment-pvs` | Run segcsvd PVS segmentation over every session |

Details and flags for each task:

<details>
<summary><code>pixi run heudiconv-osa</code></summary>

Convert GLIMPSE-OSA DICOMs to BIDS niftis. See `OSA/run_heudiconv_osa.sh`.
</details>

<details>
<summary><code>pixi run download-xnat</code></summary>

Download a project's session data from XNAT, from the scan-log CSV listed
for each session (`MRIScanLog.csv` in the project directory by default).

```
pixi run download-xnat PROJECT [-f SCANLOGCSV] [--dicom] [--physio]
```

- `PROJECT` — one of the registered projects: `GLIMPSE_OSA`, `GLIMPSE_WISP`.
  New projects are added via `PROJECT_CONFIGS` in `downloadxnat.py`.
- `--dicom` / `--physio` — limit to just one (default: both).
- `-f` — path to the scan-log CSV, if not the project's default `MRIScanLog.csv`.

Example: `pixi run download-xnat GLIMPSE_OSA --dicom`
</details>

<details>
<summary><code>pixi run recon-all-parallel</code></summary>

Run FreeSurfer recon-all in parallel across subjects, for any BIDS project
directory.

```
pixi run recon-all-parallel PROJECT [--n-cpus N] [--use-t2] [--sessions SES [SES ...]]
```

- `PROJECT` — project directory name under `/mnt/cina`, e.g. `GLIMPSE_OSA`.
- `--n-cpus` — default 8, capped at 8. FreeSurfer uses ~24GB of memory per
  job.
- `--use-t2` — use the matching T2w image to refine the pial surface, if available.
- `--sessions` — only run for these sessions, e.g. `--sessions ses-01 ses-02`.

Example: `pixi run recon-all-parallel GLIMPSE_OSA --use-t2`
</details>

<details>
<summary><code>pixi run freesurfer-qa</code></summary>

Open a subject/session's FreeSurfer output (T1, brainmask, aparc+aseg,
white/pial surfaces) in freeview, then prompt for a pass/fail QA result and
log it to `derivatives/freesurfer/qa_log.csv`. A comment is required on fail.

```
pixi run freesurfer-qa PROJECT --subject SUBJECT_ID
```

- `PROJECT` — project directory name under `/mnt/cina`, e.g. `GLIMPSE_OSA`.
- `--subject` — required. Subject/session id to QA, e.g. `sub-001_ses-01`.

Example: `pixi run freesurfer-qa GLIMPSE_OSA --subject sub-001_ses-01`
</details>

<details>
<summary><code>pixi run segment-pvs</code></summary>

Run [segcsvd](https://github.com/AICONSlab/segcsvd) PVS segmentation over
every session in a project that already has FreeSurfer synthseg output.
Sessions missing that output, or already segmented, are skipped.

```
pixi run segment-pvs PROJECT [--sessions SES [SES ...]] [--sif SIF] [--skip-mask-and-bias] [--no-cleanup] [--seg-pvs-thr THR] [--n-threads N]
```

- `PROJECT` — project directory name under `/mnt/cina`, e.g. `GLIMPSE_OSA`.
- `--seg-pvs-thr` — probability threshold used to binarize the output. Default 0.35.
- `--n-threads` — default 32. Caps CPU threads used inside the container
  (`OMP_NUM_THREADS`/`ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS`), since the
  shared machine has no working cgroup-based resource limiting.
- `--sif` — path to the segcsvd apptainer image, if not using the shared default.
- `--skip-mask-and-bias` / `--no-cleanup` — passed straight through to segcsvd.

Example: `pixi run segment-pvs GLIMPSE_OSA --sessions ses-01`
</details>

## Pipeline

Steps are:

1. download dicoms from xnat

2. convert dicoms to BIDS niftis using heudiconv image 

3. Edit BIDS .json sidecars for Philips data. Philips dicoms do not include     slice timing, phase encode polarity and this info must be included for fmriprep. The fmap and func images must also be linked via the .json meta data.

4. Freesurfer recon-all with version 8. this version is faster, has a more accurate brain mask and provides csf masks. Output is saved in derivatives/freesufer/sub-*_ses-*. Freesurfer output is not BIDS complient but this structure is easily passed to fmriprep

5. Freesurfer QA

6. fmriprep

7. PVS segmentation: segcsvd_pvs (https://github.com/AICONSlab/segcsvd)

## CSF T1 Mapping 

1. Estimate the T1-time for each of the IRSE scans: `allsubs_t1_times`. 
    - This runs `estimate_t1_times` for each subject's sessions. 
    - If the necessary metadata json file is not present, `make_mixed_meta` will extract the information from the Nifiti files.

2. Register the IRSE images to the T1w image: `allsubs_reg_SE`. 
    - This runs `register_SE_T1_greedy`, which uses a container to register the SE images to the reference T1 image. 

3. Register the T1 Maps to the registered IRSE image: `allsubs_reg_T1maps`
    - This runs `register_T1maps_greedy` for each subject's sessions.
    - For reference session: applies the transform calculated in the previous step to the T1 map.  
    - For all other sessions: registers the session's SE image to the reference image and then applies that transform to the T1 map. 

4. Create CSF mask using the SE image ... (in progress)
