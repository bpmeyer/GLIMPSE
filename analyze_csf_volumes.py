import numpy as np 
from nilearn import image, plotting
import nibabel as nib
import os
import os.path as op
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as cm
from matplotlib.ticker import MaxNLocator
from gmri2fem import segment_tools as segtools
import matplotlib.patches as mpatches
import pandas as pd 
from glob import glob
import seaborn as sns 
from scipy import ndimage
from skimage import measure 
import subprocess
from matplotlib.lines import Line2D
import matplotlib.patches as mpatches
from anat_masks import _resample_to_rawavg, run_with_freesurfer_env
from estimate_csf_r1maps import estimate_t1_times

def create_cranial_mask(sub:str, ses:str, cran_mask_fn, t1_fn, force=False): 

    if op.isfile(cran_mask_fn) and not force: 
        print(f'Sub-{sub} Ses-0{ses}:\tCranial mask alread exisits, skipping masking.')
        return

    cran_masked_t1_fn = op.join(op.dirname(cran_mask_fn), 
                                f'sub-{sub}_ses-0{ses}_desc-t1w_masked_cranium.nii.gz')

    ### Creating Cranial Mask
    cmd = ['mri_synthstrip', 
            '-i', t1_fn, 
            '-o', cran_masked_t1_fn, 
            '-m', cran_mask_fn,
            '-b', '3', 
            '-t', '16']
    
    run_with_freesurfer_env(cmd) 

def register_se_to_t1(sub:str, ses:str, se_fn:str, t1_fn:str, out_fn:str, force:bool = False):
    
    if op.isfile(out_fn) and not force: 
        print(f'Sub-{sub} Ses-0{ses}:\tRegistered SE-Modulus File Exists - Skipping.')
        return
    
    greedy_fn = '/mnt/home/jdromero/Packages/greedy.sif'
    xfm_basename = f'sub-{sub}_ses-0{ses}_acq-mixed_to_t1.mat'
    ### Setting up the greedy container 
    app_cmd = ['apptainer', 'exec', 
                '--bind', f'{op.dirname(se_fn)}:/mixed_dir', 
                '--bind', f'{op.dirname(t1_fn)}:/anat_dir', 
                '--bind', f'{op.dirname(out_fn)}:/out_dir', 
                greedy_fn]

    ### Greedy Affine Registration
    affine_cmd = ['greedy', '-d', '3', '-a', 
                '-i', f'/anat_dir/{op.basename(t1_fn)}', f'/mixed_dir/{op.basename(se_fn)}', 
                '-o', f'/out_dir/{xfm_basename}',
                '-ia-image-centers', 
                '-dof', '6', 
                '-m', 'NMI']

    subprocess.run(app_cmd + affine_cmd) 

    ### Applying the Registration 
    register_cmd = ['greedy', '-d', '3', 
                '-rf', f'/anat_dir/{op.basename(t1_fn)}', 
                '-ri', 'NN', 
                '-rm', f'/mixed_dir/{op.basename(se_fn)}', f'/out_dir/{op.basename(out_fn)}',
                '-r', f'/out_dir/{xfm_basename}']

    subprocess.run(app_cmd + register_cmd)

    print(f'Registered SE Image Saved at:\n\t{out_fn}')

def register_csf_t1_to_native(sub:str, ses:str, t1_fn:str, t1_map_fn:str, out_fn:str, force:bool = False): 
    
    if op.isfile(out_fn) and not force: 
        print(f'Sub-{sub} Ses-{ses}:\tRegistered T1 Map File Exists - Skipping.')
        return
    
    greedy_fn = '/mnt/home/jdromero/Packages/greedy.sif'
    xfm_basename = f'sub-{sub}_ses-{ses}_acq-mixed_to_t1.mat'

    app_cmd = ['apptainer', 'exec', 
                '--bind', f'{op.dirname(t1_map_fn)}:/mixed_dir', 
                '--bind', f'{op.dirname(t1_fn)}:/anat_dir', 
                '--bind', f'{op.dirname(out_fn)}:/out_dir', 
                greedy_fn]

    print(f'Aligning Sub-{sub} T1Map Session {ses} to T1 Reference')

    ### Apply the registration to the session to get it into the SE registered space for reference scan
    register_cmd = ['greedy', '-d', '3', 
        '-rf', f'/anat_dir/{op.basename(t1_fn)}', 
        '-ri', 'NN', 
        '-rm', f'/mixed_dir/{op.basename(t1_map_fn)}', f'/out_dir/{op.basename(out_fn)}',
        '-r', f'/out_dir/{xfm_basename}']

    subprocess.run(app_cmd + register_cmd)

    return

def calc_mod_z(arr): 
    nonzero_arr = arr[arr != 0]
    med = np.median(nonzero_arr)
    mad = np.median(np.abs(nonzero_arr - med)) 
    if mad == 0: 
        return arr
    else: 
        return (0.6745 * (arr - med)) / mad
 
def calc_csf_vol(subjects, project): 

    vol_df_fn = op.join('/mnt/home/jdromero/Documents', 'wisp_group_csf_vol_estimate.csv')

    vol_df = pd.DataFrame(columns=['Subject', 'Session', 'Seg', 'Vol', 'Mean', 'SD'])

    for sub in subjects: 
        print(f'\nCalculating CSF Vols for Subject: {sub}')
        for ses in range(1, 5, 1): 
            print(f'\tSession 0{ses}')
            ### FS Segmentation Dir
            fs_dir = op.join(project, 'derivatives', 'freesurfer', f'sub-{sub}_ses-0{ses}', 'mri')
            aseg_fn = op.join(fs_dir, 'aparc+aseg.mgz')
    
            ### Native Directories
            src_dir = op.join(project, 'sourcedata', 'nifti', f'sub-{sub}', f'ses-0{ses}') 
            t1_fn = op.join(src_dir, 'anat', f'sub-{sub}_ses-0{ses}_T1w.nii.gz')
            se_fn = op.join(src_dir, 'mixed', f'sub-{sub}_ses-0{ses}_acq-mixed_SE-modulus.nii.gz')

            ### Output Directories 
            vol_dir = op.join(project, 'derivatives', 'csf_vol', f'sub-{sub}', f'ses-0{ses}') 
            os.makedirs(vol_dir, exist_ok=True)

            ### Calculating Volume of Freesurfer CSF Segmentation
            aseg_im = nib.load(aseg_fn)
            csf_labs = [4, 5, 14, 15, 24, 31, 43, 44, 63, 72, 85]
            csf_mask = np.isin(aseg_im.get_fdata(), csf_labs).astype(np.int16)
            csf_im = nib.Nifti1Image(csf_mask, aseg_im.affine, dtype=np.int16)
            nib.save(csf_im, op.join(vol_dir, f'sub-{sub}_ses-0{ses}_desc-full_csf_mask_from_fs.nii.gz'))
            csf_vol = nib.imagestats.mask_volume(csf_im) / 1000

            ### Adding calculated volume to the DF
            fs_dict = {'Subject': sub, 'Session': ses, 'Seg': 'Freesurfer', 'Vol': csf_vol}
            vol_df = pd.concat([vol_df, pd.DataFrame([fs_dict])], ignore_index=True)
            ### Calculating CSF Vol from IRSE
            ## Creating Native Space FS ASEG If needed
            native_aseg_fn = op.join(vol_dir, f'aparc+aseg_native.nii.gz')
            rawavg_fn = op.join(fs_dir, 'rawavg.mgz')
            _resample_to_rawavg(seg_fn = aseg_fn, 
                                rawavg_fn = rawavg_fn, 
                                out_fn = native_aseg_fn, 
                                prefix = f'sub-{sub}_ses-0{ses}')

            
            ## Creating Cranial Mask if Needed
            cran_mask_fn = op.join(vol_dir, f'sub-{sub}_ses-0{ses}_desc-cranial_mask.nii.gz')
            create_cranial_mask(sub, ses, cran_mask_fn, t1_fn)

            ## Registering the SE-Modulus image if needed 
            se_reg_fn = op.join(vol_dir, f'sub-{sub}_ses-0{ses}_acq-mixed_SE-modulus_registered.nii.gz')
            register_se_to_t1(sub, ses, se_fn, t1_fn, se_reg_fn)

            ## Apply Cranium Mask to SE Image 
            cran_mask_im = nib.load(cran_mask_fn)
            se_im = nib.load(se_reg_fn)
            se_dat = se_im.get_fdata() 
            se_cran = se_dat * cran_mask_im.get_fdata() 
            se_cran_im = nib.Nifti1Image(se_cran, se_im.affine)
            se_cran_fn = op.join(vol_dir, f'sub-{sub}_ses-0{ses}_acq-mixed_SE-modulus_registered_cranium_masked.nii.gz')
            nib.save(se_cran_im, se_cran_fn)

            ### Get Tissue Threshold from FS WM Mask
            ## Make WM Mask from FS
            nat_aseg_im = nib.load(native_aseg_fn)
            aseg_dat = nat_aseg_im.get_fdata()
            wm_mask = np.where((aseg_dat == 2) | (aseg_dat == 41), 1, 0)
            wm_mask_im = nib.Nifti1Image(wm_mask, nat_aseg_im.affine, dtype=np.int16)
            nib.save(wm_mask_im, op.join(vol_dir, f'sub-{sub}_ses-0{ses}_desc-WM_mask_from_fs.nii.gz'))
            
            ## Erode the WM Mask by 1 vox to get rid of partial volume effects
            erosion_mask = ndimage.binary_erosion(wm_mask, iterations=1)
            eroded_wm_mask = np.where(erosion_mask, 1, 0)
            eroded_wm_im = nib.Nifti1Image(eroded_wm_mask, nat_aseg_im.affine, dtype=np.int16) 
            nib.save(eroded_wm_im, op.join(vol_dir, f'sub-{sub}_ses-0{ses}_desc-eroded_WM_mask_from_fs.nii.gz'))
            
            ## Remove Voxels +1-4 SDs away from Mean of WM mask signal
            se_wm = se_cran * eroded_wm_mask
            mean = np.mean(se_wm, where=se_wm != 0)
            sd = np.std(se_wm[se_wm != 0])
            
            for thresh in range(1, 5): 
                cutoff = mean + sd * thresh

                se_thresh = np.where(se_cran > cutoff, se_cran, 0)
                se_thresh_im = nib.Nifti1Image(se_thresh, se_im.affine)
                thresh_fn = op.join(vol_dir, 
                                    f'sub-{sub}_ses-0{ses}_acq-mixed_SE-modulus_registered_cranium_masked_threshold{thresh}SD.nii.gz')
                nib.save(se_thresh_im, thresh_fn)

                ## Calculate the CSF Vol of the 1SD mask 
                se_csf_fn = op.join(vol_dir, 
                                    f'sub-{sub}_ses-0{ses}_acq-mixed_SE-modulus_registered_cranium_masked_threshold{thresh}SD.nii.gz')                    
                se_csf_im = nib.load(se_csf_fn)
                se_csf_mask = np.where(se_csf_im.get_fdata() != 0, 1, 0)
                se_csf_mask_im = nib.Nifti1Image(se_csf_mask, se_csf_im.affine, dtype=np.int16)
                se_csf_mask_im_fn = op.join(vol_dir, 
                                    f'sub-{sub}_ses-0{ses}_acq-mixed_SE-modulus_registered_csf_mask_{thresh}SD.nii.gz')                      
                nib.save(se_csf_mask_im, se_csf_mask_im_fn)
                se_csf_vol = nib.imagestats.mask_volume(se_csf_mask_im) / 1000
                irse_dict = {'Subject': sub, 'Session': ses, 'Seg': f'SE_{thresh}', 'Vol': se_csf_vol, 
                             'Mean': np.round(mean, 2), 'SD': round(sd, 2)}
                vol_df = pd.concat([vol_df, pd.DataFrame([irse_dict])], ignore_index=True)

    vol_df.to_csv(vol_df_fn, index=False)
    print(vol_df)

def plot_wm_thresholds(sleep_meta_fn, vol_df_fn, project):

    sleep_df = pd.read_csv(sleep_meta_fn)
    vol_df = pd.read_csv(vol_df_fn)
    vol_sleep_df = pd.merge(left = vol_df, right = sleep_df, 
                        left_on=['Subject', 'Session'], 
                        right_on=['ID', 'Visit']).drop(columns=['ID', 'Visit'])

    out_dir = op.join(project, 'derivatives', 'csf_vol')
    plot_dir = op.join(out_dir, 'group', 'figures')
    os.makedirs(plot_dir, exist_ok=True)
    vol_sleep_df = vol_sleep_df[(vol_sleep_df['Stim_Condition'] == 0) & 
                                (vol_sleep_df['Seg'] == 'SE_Modulus')]
    vol_sleep_df.reset_index(inplace=True)
    fig, axes = plt.subplots(4, 4, figsize=(16, 9), sharey=True, sharex=True)
    plot_fn = op.join(plot_dir, f'white_matter_se_signal_thresholds.png')
    for idx, ((sub, sleep), grp) in enumerate(vol_sleep_df.groupby(['Subject', 'Full_sleep'], as_index=False)): 

        col_idx = 0 if idx < 4 * 2 else 2
        col_idx = col_idx if sleep == 1 else col_idx + 1
        row_idx = (sub - 1) % 4

        ax = axes[row_idx, col_idx]
        sleep_title = 'Full' if sleep == 1 else 'Restricted'
        ax.set_title(f'Sub-0{sub}: {sleep_title}', fontsize=12)

        ses = grp['Session'].iloc[0]   
        print(sub, ses)
        vol_dir = op.join(project, 'derivatives', 'csf_vol', f'sub-00{sub}', f'ses-0{ses}') 
        full_se_fn = op.join(vol_dir, f'sub-00{sub}_ses-0{ses}_acq-mixed_SE-modulus_registered_cranium_masked.nii.gz')
        se_im = nib.load(full_se_fn)
        se_dat = se_im.get_fdata()
        se_dat_flat = se_dat.flatten()
        se_dat_flat = se_dat_flat[se_dat_flat != 0]
        ax.hist(x = se_dat_flat, bins=60, color='darkgrey', log=True)
        
        wm_mask_fn = op.join(vol_dir, f'sub-00{sub}_ses-0{ses}_desc-eroded_WM_mask_from_fs.nii.gz')
        wm_mask = nib.load(wm_mask_fn)
        se_wm = se_dat * wm_mask.get_fdata()
        se_wm_dat = se_wm.flatten()
        se_wm_flat = se_wm_dat[se_wm_dat != 0]
        ax.hist(x = se_wm_flat, bins=60, color='grey', log=True)

        mean = grp['Mean'].iloc[0] 
        sd = grp['SD'].iloc[0] 

        ax.axvline(x= mean, color='black')
        ax.axvline(x = mean + sd, color='red')
        ax.axvline(x = mean + (2 * sd), color='blue')

        ax.tick_params(labelbottom=True, labelleft=True)

    handles = [Line2D([0], [0], color='black', lw=1.5, linestyle='-'),
               Line2D([0], [0], color='red', lw=1.5, linestyle='-'), 
               Line2D([0], [0], color='blue', lw=1.5, linestyle='-'), 
               mpatches.Patch(color="darkgrey"),
               mpatches.Patch(color="grey")]

    labels = ['WM Sig. Mean', 'WM Sig. Mean + 1SD', 'WM Sig. Mean + 2SD', 
              'Cranial Sig.', 'WM Sig.']

    fig.legend(handles, labels, loc='upper right', ncols=2, fontsize=12)    

    fig.supxlabel('Signal (Millions)', fontsize=16)
    fig.supylabel('Voxels (Log10 Scale)', fontsize=16)
    fig.suptitle('Upper Cutoffs for CSF Signal\nin Cranium and White Matter', fontsize=18)

    plt.tight_layout()
    plt.subplots_adjust(left=0.065, top=0.87)
    plt.savefig(plot_fn, dpi=300)
    print(plot_fn)

def plot_csf_vol_by_visit(subs, project, sleep_meta): 

    vol_df_fn = op.join('/mnt/home/jdromero/Documents', 'wisp_group_csf_vol_estimate.csv')
    vol_df = pd.read_csv(vol_df_fn)

    sleep_df = pd.read_csv(sleep_meta)
    
    sleep_con_dict = {0: 'Full Sleep',
                      1: 'Restricted Sleep'}

    out_dir = op.join(project, 'derivatives', 'csf_vol')
    plot_dir = op.join(out_dir, 'group', 'figures')

    vol_sleep_df = pd.merge(left = vol_df, right = sleep_df, 
                          left_on=['Subject', 'Session'], 
                          right_on=['ID', 'Visit'])

    vol_sleep_df.drop(columns=['ID', 'Visit'], inplace=True)
    vol_sleep_df = vol_sleep_df[vol_sleep_df['Stim_Condition'] == 0]
    vol_sleep_df['Res_sleep'] = np.where(vol_sleep_df['Full_sleep'] == 1, 0, 1)

    fig, axes = plt.subplots(1, 2, figsize=(16, 9))
    for idx, (name, grp) in enumerate(vol_sleep_df.groupby(['Seg'])): 
        method = name[0]
        if method not in ['Freesurfer', 'SE_2']: continue

         
        ax = axes[0] if method == 'Freesurfer' else axes[1]

        # Right Axis
        sns.boxplot(data=grp, y = 'Vol', x = 'Res_sleep', fill=False,
                    legend=False, ax=ax, color='black')
        sns.lineplot(data=grp, y= 'Vol', x = 'Res_sleep', hue='Subject', 
                    estimator=None, marker='o', ax=ax, palette='tab20', legend=True)
        
        ax.set_xlabel('Sleep Condition')
        ax.tick_params(axis='y', labelleft=True)
        ax.set_ylabel('CSF Volume (mL)', visible=True)
        
        new_x_ticks = [sleep_con_dict[int(lab.get_text())] for lab in ax.get_xticklabels()]
        ax.set_xticks([lab.get_text() for lab in ax.get_xticklabels()], 
                    labels = new_x_ticks)

    axes[0].set_title('Freesurfer Parcellation')
    axes[1].set_title('SE Modulus Based Parcellation')

    handles, labels = axes[0].get_legend_handles_labels()

    for ax in axes: 
        ax.get_legend().remove()
    fig.legend(handles, labels, loc='lower center', title='Subject', ncol=8)    

    fig.suptitle(f'CSF Volume Changes with Partial Sleep Deprivation')
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.125)
    
    plot_fn = op.join(plot_dir, 'csf_volume_changes_by_method_and_sleep_condition.png') 
    plt.savefig(plot_fn, dpi=300)
    print(plot_fn)

def calc_avg_t1_time(subs, project):
    
    t1_df_fn = op.join('/mnt/home/jdromero/Documents', 'wisp_group_t1_avgs.csv')
    t1_df = pd.DataFrame(columns=['Subject', 'Session', 'MeanT1'])

    for sub in subs: 
        for ses in range(1, 5): 

            mixed_dir = op.join(project, 'derivatives', 'csf_seg', f'sub-{sub}', f'ses-0{ses}') 
            csf_t1_fn = op.join(mixed_dir, f'sub-{sub}_ses-0{ses}_acq-mixed_T1map_postproc.nii.gz')
            
            vol_dir = op.join(project, 'derivatives', 'csf_vol', f'sub-{sub}', f'ses-0{ses}') 

            src_dir = op.join(project, 'sourcedata', 'nifti', f'sub-{sub}', f'ses-0{ses}') 
            t1_fn = op.join(src_dir, 'anat', f'sub-{sub}_ses-0{ses}_T1w.nii.gz')
            
            reg_t1_map_fn = op.join(vol_dir, f'sub-{sub}_ses-0{ses}_acq-mixed_T1map_postproc_native.nii.gz')

            if not op.isfile(csf_t1_fn): 
                estimate_t1_times(sub, ses, project)
            
            ### Register the T1 Map to Native 
            register_csf_t1_to_native(sub=sub, ses=f'0{ses}', t1_fn=t1_fn, 
                                      t1_map_fn=csf_t1_fn, out_fn=reg_t1_map_fn)

            ### Load the registered T1 map
            t1_map_im = nib.load(reg_t1_map_fn)
            
            ### Apply Cranial Mask to the T1 Map
            cran_mask_fn = op.join(vol_dir, f'sub-{sub}_ses-0{ses}_desc-cranial_mask.nii.gz')
            create_cranial_mask(sub, ses, cran_mask_fn, t1_fn)

            cran_mask = nib.load(cran_mask_fn)
            masked_t1_map = t1_map_im.get_fdata() * cran_mask.get_fdata()
            masked_t1_map_im = nib.Nifti1Image(masked_t1_map, t1_map_im.affine, dtype=np.int16)
            nib.save(masked_t1_map_im, 
                     op.join(vol_dir, f'sub-{sub}_ses-0{ses}_acq-mixed_T1map_postproc_native_masked.nii.gz'))
            MeanT1 = np.mean(masked_t1_map, where = masked_t1_map != 0)

            ses_dict = {'Subject': sub, 'Session': ses, 'MeanT1': np.round(MeanT1, 2)}

            t1_df = pd.concat([t1_df, pd.DataFrame([ses_dict])], ignore_index=True)

    t1_df.to_csv(t1_df_fn, index=False)

def plot_csf_t1_by_visit(subs, project, sleep_meta): 

    t1_df_fn = op.join('/mnt/home/jdromero/Documents', 'wisp_group_t1_avgs.csv')
    t1_df = pd.read_csv(t1_df_fn)

    sleep_df = pd.read_csv(sleep_meta)
    
    sleep_con_dict = {0: 'Full Sleep',
                      1: 'Restricted Sleep'}

    out_dir = op.join(project, 'derivatives', 'csf_vol')
    plot_dir = op.join(out_dir, 'group', 'figures')

    t1_sleep_df = pd.merge(left = t1_df, right = sleep_df, 
                          left_on=['Subject', 'Session'], 
                          right_on=['ID', 'Visit'])

    t1_sleep_df.drop(columns=['ID', 'Visit'], inplace=True)
    t1_sleep_df = t1_sleep_df[t1_sleep_df['Stim_Condition'] == 0]
    t1_sleep_df['Res_sleep'] = np.where(t1_sleep_df['Full_sleep'] == 1, 0, 1)

    fig, ax = plt.subplots(1, 1, figsize=(8, 9))
    sns.boxplot(data=t1_sleep_df, y = 'MeanT1', x = 'Res_sleep', fill=False,
                legend=False, ax=ax, color='black')
    sns.lineplot(data=t1_sleep_df, y= 'MeanT1', x = 'Res_sleep', hue='Subject', 
                estimator=None, marker='o', ax=ax, palette='tab20', legend=True)
    ax.set_xlabel('Sleep Condition')
    new_x_ticks = [sleep_con_dict[int(lab.get_text())] for lab in ax.get_xticklabels()]
    ax.set_xticks([lab.get_text() for lab in ax.get_xticklabels()], 
                labels = new_x_ticks)
    
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', title='Subject', ncol=8)
    ax.get_legend().remove()
    ax.set_ylabel('T1 (ms)', visible=True)

    fig.suptitle(f'CSF T1 Changes with Partial Sleep Deprivation')
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.125)
    
    plot_fn = op.join(plot_dir, 'csf_t1_changes_by_method_and_sleep_condition.png') 
    plt.savefig(plot_fn, dpi=300)
    print(plot_fn)

def plot_t1map_distributions(sleep_meta_fn:str, project:str):

    sleep_df = pd.read_csv(sleep_meta_fn)
    
    out_dir = op.join(project, 'derivatives', 'csf_vol')
    plot_dir = op.join(out_dir, 'group', 'figures')
    os.makedirs(plot_dir, exist_ok=True)

    sleep_df = sleep_df[(sleep_df['Stim_Condition'] == 0)]
    sleep_df.reset_index(inplace=True)

    fig, axes = plt.subplots(4, 2, figsize=(16, 9), sharey=True, sharex=True)
    plot_fn = op.join(plot_dir, f'csf_t1_time_distributions_by_condition.png')
    for idx, (name, grp) in enumerate(sleep_df.groupby(['ID'], as_index=False)): 
        sub = name[0]
        if sub > 8: continue
        col_idx = 0 if idx < 4 else 1
        row_idx = (sub - 1) % 4

        ax = axes[row_idx, col_idx]
        ax.set_title(f'Sub-0{sub}', fontsize=12) 

        for name, sgrp in grp.groupby(['Full_sleep'], as_index=False):
            sleep = name[0]
            ses = sgrp['Visit'].iloc[0]   
            color = 'blue' if sleep == 1 else 'red'

            vol_dir = op.join(project, 'derivatives', 'csf_vol', f'sub-00{sub}', f'ses-0{ses}') 
            t1_map_fn = op.join(vol_dir, f'sub-00{sub}_ses-0{ses}_acq-mixed_T1map_postproc_native_masked.nii.gz')

            t1_map_im = nib.load(t1_map_fn)
            t1_map = t1_map_im.get_fdata()
            t1_map = t1_map[t1_map != 0]
            ax.hist(x = t1_map, bins=60, color=color, log=True, alpha=0.5)
            ax.tick_params(labelbottom=True, labelleft=True)


    handles = [mpatches.Patch(color="blue"),
               mpatches.Patch(color="red")]

    labels = ['Full', 'Restricted']
            
    fig.legend(handles, labels, loc='upper right', title='Sleep Condition', ncols=2, fontsize=12)    

    fig.supxlabel('T1 (ms)', fontsize=16)
    fig.supylabel('Voxels (Log10 Scale)', fontsize=16)
    fig.suptitle('Distribution of T1 times by Sleep Condition', fontsize=18)

    plt.tight_layout()
    plt.subplots_adjust(left=0.065)
    plt.savefig(plot_fn, dpi=300)
    print(plot_fn) 
            


