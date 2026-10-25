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

def plot_group_r1_maps(subjects, project, session:str='01'):

    out_dir = op.join(project, 'derivatives', 'csf_seg')
    plot_dir = op.join(out_dir, 'group', 'figures')

    os.makedirs(plot_dir, exist_ok=True)

    if len(subjects) <= 8: 
        fig, axes = plt.subplots(2, 4, figsize=(16, 9), layout='constrained')
        fig.patch.set_facecolor('black')
        axes = axes.flatten()
        for idx, subject in enumerate(subjects): 
            ax = axes[idx]

            sub_dir = op.join(out_dir, f'sub-{subject}', f'ses-{session}')
            r1map_basename = f'sub-{subject}_ses-{session}_acq-mixed_R1map_postproc.nii.gz'

            r1_fn = op.join(sub_dir, r1map_basename)
            r1_im = nib.load(r1_fn)
            cropped_r1 = image.crop_img(r1_im)
            display = plotting.plot_img(img=cropped_r1, vmin=0.2, vmax=0.25,
                                                cut_coords=[-10], threshold=0.2,  
                                                cmap="jet", display_mode="x",
                                                figure=fig, axes=ax, colorbar=False,
                                                black_bg=True, annotate=False)
            display.title(f'sub-{subject}', color='white', bgcolor='black', size=16)

    norm = mcolors.Normalize(vmin=0.2, vmax=0.25)

    mappable = cm.ScalarMappable(norm, cm.jet)
    cbar = fig.colorbar(mappable, ax=axes, location='right', orientation='vertical', 
                        aspect=40, pad=-0.07, shrink=0.7)
    cbar.ax.tick_params(labelcolor='white', color='white', labelsize=16)
    fig.suptitle('R1 Maps (1/s)', color='white', fontsize=24)

    first_sub, *_, last_sub = sorted(subjects)
    fig_fn = op.join(plot_dir, f'group_r1_maps_sub{first_sub}_to_sub{last_sub}.svg') 

    plt.savefig(fig_fn, dpi=300)

    print(f'Saved figure at {fig_fn}')

def plot_subject_r1_map(subject, project, session:str='01'): 

    out_dir = op.join(project, 'derivatives', 'csf_seg')
    sub_dir = op.join(out_dir, f'sub-{subject}', f'ses-{session}')
    plot_dir = op.join(sub_dir, 'figures')

    os.makedirs(plot_dir, exist_ok=True)

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('black')
    ax.set_facecolor('black')
    sub_dir = op.join(out_dir, f'sub-{subject}', f'ses-{session}')
    r1map_basename = f'sub-{subject}_ses-{session}_acq-mixed_R1map_postproc.nii.gz'

    r1_fn = op.join(sub_dir, r1map_basename)
    r1_im = nib.load(r1_fn)
    cropped_r1 = image.crop_img(r1_im)

    display = plotting.plot_img(img=cropped_r1, vmin=0.2, vmax=0.25,
                                cut_coords=[-10], threshold=0.2,  
                                cmap="jet", display_mode="x",
                                figure=fig,colorbar=False,
                                black_bg=True, annotate=False)

    norm = mcolors.Normalize(vmin=0.2, vmax=0.25)

    mappable = cm.ScalarMappable(norm, cm.jet)
    cbar = fig.colorbar(mappable, ax=ax, location='right', orientation='vertical', 
                        aspect=40, pad=-0.07, shrink=0.7)
    cbar.ax.tick_params(labelcolor='white', color='white', labelsize=16)
    fig.suptitle(f'Sub-{subject} R1 Map (1/s)', color='white', fontsize=24)

    fig_fn = op.join(plot_dir, f'sub-{subject}_ses-{session}_desc-r1_map.svg') 

    plt.savefig(fig_fn, dpi=300)

    print(f'Saved figure at {fig_fn}')

def plot_subject_csfseg(subject, project, session:str='01'): 

    out_dir = op.join(project, 'derivatives', 'csf_seg')
    sub_dir = op.join(out_dir, f'sub-{subject}', f'ses-{session}')
    plot_dir = op.join(sub_dir, 'figures')

    os.makedirs(plot_dir, exist_ok=True)

    cvs_seg_fn = op.join(sub_dir, 'segmentations', f"sub-{subject}_seg-csf_sas-ventricle-cerebellum.nii.gz")
    cvs_im = nib.load(cvs_seg_fn)

    cvs_seg_lut_fn = op.join(sub_dir, 'segmentations', f'sub-{subject}_seg-csf_sas-ventricle-cerebellum-LUT.txt') 
    cvs_lut = segtools.read_lut(cvs_seg_lut_fn)
    cvs_lut = cvs_lut[cvs_lut['description'] != 'unknown']

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('black')
    ax.set_facecolor('black')
    colors = plt.colormaps['tab10'].colors[:3]
    cmap = mcolors.ListedColormap(colors)

    display = plotting.plot_roi(cvs_im, bg_img=None, cut_coords=[-10], 
                                display_mode='x', black_bg=True, 
                                figure=fig, colorbar=False,
                                cmap=cmap, annotate=False)

    handles = [mpatches.Patch(color=color) for color in cmap.colors]
    lab_dict = {'SAS': 'Cerebral SAS', 
                'cerebellum': 'Cerebellar SAS',
                'ventricles': 'Ventricles'}
    labels = [lab_dict[d] for d in cvs_lut['description']]
    
    fig.legend(handles, labels, loc='right', fontsize=16, 
               facecolor='black', labelcolor='white')
    fig.suptitle(f'Sub-{subject} CSF Segmentation', color='white', fontsize=24)

    plot_fn = op.join(plot_dir, f'sub-{subject}-ses{session}_desc-csv_segmentation.svg')
    plt.savefig(plot_fn, dpi=300)

    print(f'Saved figure at {plot_fn}')

def plot_group_csf_seg(subjects, project, session:str='01'):
        
    out_dir = op.join(project, 'derivatives', 'csf_seg')
    plot_dir = op.join(out_dir, 'group', 'figures')

    os.makedirs(plot_dir, exist_ok=True)

    if len(subjects) <= 8: 
        fig, axes = plt.subplots(2, 4, figsize=(16, 9), layout='constrained')
        fig.patch.set_facecolor('black')
        axes = axes.flatten()

        colors = plt.colormaps['tab10'].colors[:3]
        cmap = mcolors.ListedColormap(colors)

        for idx, subject in enumerate(subjects): 
            
            ax = axes[idx]
            ax.set_facecolor('black')

            sub_dir = op.join(out_dir, f'sub-{subject}', f'ses-{session}')
            cvs_seg_fn = op.join(sub_dir, 'segmentations', f"sub-{subject}_seg-csf_sas-ventricle-cerebellum.nii.gz")
            cvs_im = nib.load(cvs_seg_fn)

            cvs_seg_lut_fn = op.join(sub_dir, 'segmentations', f'sub-{subject}_seg-csf_sas-ventricle-cerebellum-LUT.txt') 
            cvs_lut = segtools.read_lut(cvs_seg_lut_fn)
            cvs_lut = cvs_lut[cvs_lut['description'] != 'unknown']

            display = plotting.plot_roi(cvs_im, bg_img=None, cut_coords=[-10], 
                                        display_mode='x', black_bg=True, 
                                        figure=fig, axes=ax, colorbar=False,
                                        cmap=cmap, annotate=False)
            display.title(f'sub-{subject}', color='white', bgcolor='black', size=16)
    
    handles = [mpatches.Patch(color=color) for color in cmap.colors]
    lab_dict = {'SAS': 'Cerebral SAS', 
                'cerebellum': 'Cerebellar SAS',
                'ventricles': 'Ventricles'}
    labels = [lab_dict[d] for d in cvs_lut['description']]
    
    fig.legend(handles, labels, loc='right', fontsize=16, 
               facecolor='black', labelcolor='white')

    fig.suptitle('CSF Segmentations', color='white', fontsize=24)

    first_sub, *_, last_sub = sorted(subjects)
    fig_fn = op.join(plot_dir, f'group_csf_segmentations_sub{first_sub}_to_sub{last_sub}.svg') 

    plt.savefig(fig_fn, dpi=300)

    print(f'Saved figure at {fig_fn}')

def estimate_group_csf_region_R1s(subjects, project):

    r1_df_fn = op.join('/mnt/home/jdromero/Documents', 'wisp_group_meanR1s_by_region.csv')

    if op.isfile(r1_df_fn): 
         return pd.read_csv(r1_df_fn)
    else:
        r1_df = pd.DataFrame(columns=['Subject', 'Session', 'Region', 'MeanR1'])

        for subject in subjects: 
            sub_dir = op.join(project, 'derivatives', 'csf_seg', f'sub-{subject}')
            for ses_dir in glob(op.join(sub_dir, 'ses-*')):
                session = ses_dir.split('-')[-1]    

                r1map_basename = f'sub-{subject}_ses-{session}_acq-mixed_R1map_postproc.nii.gz'
                r1_fn = op.join(ses_dir, r1map_basename)
                r1_im = nib.load(r1_fn)

                ref_ses_dir = op.join(sub_dir, 'ses-01')
                cvs_seg_fn = op.join(ref_ses_dir, 'segmentations', f"sub-{subject}_seg-csf_sas-ventricle-cerebellum.nii.gz")
                cvs_im = nib.load(cvs_seg_fn)

                cvs_seg_lut_fn = op.join(ref_ses_dir, 'segmentations', f'sub-{subject}_seg-csf_sas-ventricle-cerebellum-LUT.txt') 
                cvs_lut = segtools.read_lut(cvs_seg_lut_fn)
                cvs_lut = cvs_lut[cvs_lut['description'] != 'unknown']

                for idx, row in cvs_lut.iterrows(): 

                    region_mask = (cvs_im.get_fdata() == row.label)
                    masked_r1 = np.where(region_mask, r1_im.get_fdata(), np.nan)

                    lower_bound = np.nanquantile(masked_r1, 0.3)
                    upper_bound = np.nanquantile(masked_r1, 0.7)

                    filtered_r1 = masked_r1[(masked_r1 >= lower_bound) & (masked_r1 <= upper_bound)]
                    
                    reg_dict = {'Subject': subject, 'Session': session, 'Region': row.description, 
                                'MeanR1': np.mean(filtered_r1)}
                    
                    reg_df = pd.DataFrame([reg_dict])

                    r1_df = pd.concat([r1_df, reg_df], ignore_index=True)
        
        r1_df.to_csv(r1_df_fn, index=False)

    return r1_df

def plot_r1map_segmentation_boxplot(subjects, project): 

    out_dir = op.join(project, 'derivatives', 'csf_seg')
    plot_dir = op.join(out_dir, 'group', 'figures')

    r1_df = estimate_group_csf_region_R1s(subjects, project)

    fig, ax = plt.subplots(figsize=(8, 8))

    colors = {reg: sns.color_palette('tab10')[i] 
              for reg, i in zip(['cerebellum', 'ventricles', 'SAS'], list(range(0, 3)))}

    sns.boxplot(data=r1_df, y = 'MeanR1', x = 'Region', hue='Region', legend=False, ax=ax, 
                order=['SAS', 'cerebellum', 'ventricles'],
                palette=colors)
    sns.stripplot(data = r1_df, y = 'MeanR1', x = 'Region', ax=ax,
                  order=['SAS', 'cerebellum', 'ventricles'], color='black', 
                  alpha=0.5, dodge=False, jitter=True, legend=False)

    new_x_ticks = ['Cerebral SAS', 'Cerebellar SAS', 'Ventricles']
    ax.set_xticks([lab.get_text() for lab in ax.get_xticklabels()], 
                  labels=new_x_ticks)
    ax.set_xlabel(None)
    ax.set_ylabel('R1 (1/s)', fontsize=18)
    ax.tick_params(axis='both', labelsize=16)
    fig.suptitle('Mean R1 Values by Region', fontsize=20)
    ax.set_yticks(np.arange(0, 0.3, 0.05))
    plt.tight_layout()
    
    first_sub, *_, last_sub = sorted(subjects)
    plot_fn = op.join(plot_dir, f'group_boxplot_meanr1_by_region_sub{first_sub}_to_sub{last_sub}.png') 
    plt.savefig(plot_fn, dpi=300)

    print(f'Saved figure at {plot_fn}')

def plot_r1map_region_visit(subjects, project, sleep_meta): 

    sleep_df = pd.read_csv(sleep_meta)
    
    visit_order_dict = {0: 'Full', 1: 'Full Stim',
                        2: 'Restricted', 3: 'Restricted Stim'}

    out_dir = op.join(project, 'derivatives', 'csf_seg')
    plot_dir = op.join(out_dir, 'group', 'figures')

    r1_df = estimate_group_csf_region_R1s(subjects, project)

    r1_sleep_df = pd.merge(left = r1_df, right = sleep_df, 
                          left_on=['Subject', 'Session'], 
                          right_on=['ID', 'Visit'])

    r1_sleep_df.drop(columns=['ID', 'Visit'], inplace=True)

    fig, axes = plt.subplots(1, 2, figsize=(16, 9))

    colors = {reg: sns.color_palette('tab10')[i] 
              for reg, i in zip(['cerebellum', 'ventricles', 'SAS'], list(range(0, 3)))}

    # Left Axis
    sns.boxplot(data=r1_sleep_df, y = 'MeanR1', x = 'visit_order', hue='Region', 
                legend=True, ax=axes[0], palette='bright')
    sns.stripplot(data = r1_sleep_df, y = 'MeanR1', x = 'visit_order', hue='Region', 
                  ax=axes[0], palette='dark:black', 
                  alpha=0.5, dodge=True, jitter=True, legend=False)
    
    # Right Axis
    sns.boxplot(data=r1_sleep_df, y = 'MeanR1', x = 'visit_order', hue='visit_order', fill=False, 
                legend=False, ax=axes[1], palette='dark:black')
    sns.lineplot(data=r1_sleep_df, y = 'MeanR1', x = 'visit_order', hue='Region', units='Subject', 
                 estimator=None, marker='o', ax=axes[1], color='black', alpha = 0.5)
    
    for ax in axes:
        new_x_ticks = [visit_order_dict[int(lab.get_text())] for lab in ax.get_xticklabels()]
        ax.set_xticks([lab.get_text() for lab in ax.get_xticklabels()], 
                    labels = new_x_ticks)
        ax.set_yticks(np.arange(0, 0.3, 0.05))
        ax.set_xlabel(None)
        ax.set_ylabel('R1 (1/s)', fontsize=18)
        ax.tick_params(axis='both', labelsize=16)
    
    leg_dict = {'cerebellum':'Cerebellar SAS', 
                'SAS': 'Cerebral SAS', 
                'ventricles': 'Ventricles'}
    handles, labels = axes[0].get_legend_handles_labels()
    labels = [leg_dict[lab] for lab in labels]
    
    for ax in axes: ax.get_legend().remove()
    fig.legend(handles, labels, title='Region', loc='lower center', 
               fontsize=16, title_fontsize=16, ncol=3)

    fig.suptitle('Mean R1 Values by Region', fontsize=24)
    
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.15)
    first_sub, *_, last_sub = sorted(subjects)
    plot_fn = op.join(plot_dir, f'group_boxplot_meanr1_by_region_and_visit_sub{first_sub}_to_sub{last_sub}.png') 
    plt.savefig(plot_fn, dpi=300)

    print(f'Saved figure at {plot_fn}')

def calc_mod_z(arr): 
    nonzero_arr = arr[arr != 0]
    med = np.median(nonzero_arr)
    mad = np.median(np.abs(nonzero_arr - med)) 
    if mad == 0: 
        return arr
    else: 
        return (0.6745 * (arr - med)) / mad
 
def plot_csf_vol_by_visit(subs, project, sleep_meta): 

    vol_df_fn = op.join('/mnt/home/jdromero/Documents', 'wisp_group_csf_vol_estimate.csv')
    vol_df = pd.read_csv(vol_df_fn)

    sleep_df = pd.read_csv(sleep_meta)
    
    sleep_con_dict = {0: 'Full Sleep',
                      1: 'Restricted Sleep'}

    out_dir = op.join(project, 'derivatives', 'csf_seg')
    plot_dir = op.join(out_dir, 'group', 'figures')

    vol_sleep_df = pd.merge(left = vol_df, right = sleep_df, 
                          left_on=['Subject', 'Session'], 
                          right_on=['ID', 'Visit'])

    vol_sleep_df.drop(columns=['ID', 'Visit'], inplace=True)
    vol_sleep_df = vol_sleep_df[vol_sleep_df['Stim_Condition'] == 0]
    vol_sleep_df['Res_sleep'] = np.where(vol_sleep_df['Full_sleep'] == 1, 0, 1)
    fig, axes = plt.subplots(1, 2, figsize=(16, 9), sharey=True)
    for idx, (name, grp) in enumerate(vol_sleep_df.groupby(['Seg'])): 
        method = name[0]
        ax = axes[0] if method == 'Freesurfer' else axes[1]
        # Right Axis
        sns.boxplot(data=grp, y = 'Vol', x = 'Res_sleep', fill=False,
                    legend=False, ax=ax, color='black')
        sns.lineplot(data=grp, y= 'Vol', x = 'Res_sleep', hue='Subject', 
                    estimator=None, marker='o', ax=ax, palette='tab20')
        
        ax.set_xlabel('Sleep Condition')
        ax.tick_params(axis='y', labelleft=True)
        ax.set_ylabel('CSF Volume (mL)', visible=True)
        
        new_x_ticks = [sleep_con_dict[int(lab.get_text())] for lab in ax.get_xticklabels()]
        ax.set_xticks([lab.get_text() for lab in ax.get_xticklabels()], 
                    labels = new_x_ticks)

    axes[0].set_title('Freesurfer Parcellation')
    axes[1].set_title('SE Modulus Based Parcellation')

    handles, labels = axes[0].get_legend_handles_labels()

    for ax in axes: ax.get_legend().remove()
    fig.legend(handles, labels, loc='lower center', title='Subject', ncol=8)    

    fig.suptitle(f'CSF Volume Changes with Partial Sleep Deprivation')
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.125)
    
    plot_fn = op.join(plot_dir, 'csf_volume_changes_by_method_and_sleep_condition.png') 
    plt.savefig(plot_fn, dpi=300)
    print(plot_fn)
    
def calc_csf_vol(subjects, project): 

    vol_df_fn = op.join('/mnt/home/jdromero/Documents', 'wisp_group_csf_vol_estimate.csv')

    vol_df = pd.DataFrame(columns=['Subject', 'Session', 'Seg', 'Vol', 'Threshold'])

    for sub in subjects: 
        for ses in range(1, 5, 1): 

            fs_dir = op.join(project, 'derivatives', 'freesurfer', f'sub-{sub}_ses-0{ses}', 'mri')
            aseg_fn = op.join(fs_dir, 'aparc+aseg.mgz')
            t1_fn = op.join(fs_dir, 'T1_ras.nii.gz')

            mixed_dir = op.join(project, 'derivatives', 'csf_seg', f'sub-{sub}', f'ses-0{ses}')
            vol_dir = op.join(project, 'derivatives', 'csf_vol', f'sub-{sub}', f'ses-0{ses}') 
            os.makedirs(vol_dir, exist_ok=True)

            aseg_im = nib.load(aseg_fn)
            csf_labs = [4, 5, 14, 15, 24, 31, 43, 44, 63, 72, 85]
            csf_mask = np.isin(aseg_im.get_fdata(), csf_labs).astype(np.int16)
            csf_im = nib.Nifti1Image(csf_mask, aseg_im.affine, dtype=np.int16)
            nib.save(csf_im, op.join(vol_dir, f'sub-{sub}_ses-0{ses}_desc-full_csf_mask_from_fs.nii.gz'))
            csf_vol = nib.imagestats.mask_volume(csf_im) / 1000

            fs_dict = {'Subject': sub, 'Session': ses, 'Seg': 'Freesurfer', 'Vol': csf_vol}

            ### Calculating CSF Vol from IRSE

            cran_mask_fn = op.join(vol_dir, f'sub-{sub}_ses-0{ses}_desc-cranial_mask.nii.gz')
            cran_masked_t1_fn = op.join(vol_dir, f'sub-{sub}_ses-0{ses}_desc-t1w_masked_cranium.nii.gz')

            ### Creating Cranial Mask
            cmd = ['mri_synthstrip', 
                    '-i', t1_fn, 
                    '-o', cran_masked_t1_fn, 
                    '-m', cran_mask_fn,
                    '-b', '5', 
                    '-t', '16']

            if not op.isfile(cran_mask_fn): subprocess.run(cmd) 

            ### Apply the cranium mask to the SE modulus image
            cran_mask_im = nib.load(cran_mask_fn)
            se_fn = op.join(mixed_dir, f'sub-{sub}_ses-0{ses}_acq-mixed_SE-modulus_registered.nii.gz')
            se_im = nib.load(se_fn)

            se_dat = se_im.get_fdata() 
            se_cran = se_dat * cran_mask_im.get_fdata() 
            se_cran_im = nib.Nifti1Image(se_cran, se_im.affine)
            se_cran_fn = op.join(vol_dir, f'sub-{sub}_ses-0{ses}_acq-mixed_SE-modulus_registered_cranium_masked.nii.gz')
            nib.save(se_cran_im, se_cran_fn)

            ### Get a Tissue Threshold using the WM FS Mask  
            aseg_ras_fn = op.join(fs_dir, 'aparc+aseg_ras.nii.gz') 
            aseg_ras_im = nib.load(aseg_ras_fn)
            aseg_ras_dat = aseg_ras_im.get_fdata()
            wm_mask = np.where((aseg_ras_dat == 2) | (aseg_ras_dat == 41), 1, 0)
            wm_mask_im = nib.Nifti1Image(wm_mask, aseg_ras_im.affine, dtype=np.int16)
            nib.save(wm_mask_im, op.join(vol_dir, f'sub-{sub}_ses-0{ses}_desc-WM_mask_from_fs.nii.gz'))
            
            ### Erode the WM Mask by 2 voxels to get rid of partial volume effects
            erosion_mask = ndimage.binary_erosion(wm_mask, iterations=2)
            final_wm_mask = np.where(erosion_mask, 1, 0)

            # ### Take the 2 Largest Islands in the WM mask
            # lab_arr, nfeats = ndimage.label(errode_wm_mask)
            # sizes = ndimage.sum(errode_wm_mask, lab_arr, range(1, nfeats+1))
            # sorted_idxs = np.flip(np.argsort(sizes))
            # wm_labs = sorted_idxs[:2] + 1 
            # final_wm_mask = np.isin(lab_arr, wm_labs).astype(np.int16) 

            final_wm_im = nib.Nifti1Image(final_wm_mask, aseg_ras_im.affine, dtype=np.int16) 
            nib.save(final_wm_im, op.join(vol_dir, f'sub-{sub}_ses-0{ses}_desc-eroded_WM_mask_from_fs.nii.gz'))

            ### Apply the wm_mask to SE image 
            se_wm = final_wm_mask * se_cran

            ### Remove the high intensity voxels with a modified z-score
            se_wm_modz = calc_mod_z(se_wm)
            se_wm = np.where(se_wm_modz >= 3.5, 0, se_wm)

            se_wm_im = nib.Nifti1Image(se_wm, se_im.affine)
            nib.save(se_wm_im, op.join(vol_dir, f'sub-{sub}_ses-0{ses}_acq-mixed_SE-modulus_wm_only.nii.gz'))

            ### Use the Max signal in the wm mask to threshold the rest of the image
            se_mask = np.where(se_cran > np.max(se_wm), se_cran, 0)
            masked_se = nib.Nifti1Image(se_mask, se_im.affine)
            
            nib.save(masked_se, op.join(vol_dir, f'sub-{sub}_ses-0{ses}_acq-mixed_SE-modulus_wm_masked.nii.gz'))

            csf_mask = np.where(se_mask != 0 , 1, 0)
            csf_mask_im = nib.Nifti1Image(csf_mask, se_im.affine, dtype=np.int16) 
            nib.save(csf_mask_im, op.join(vol_dir, f'sub-{sub}_ses-0{ses}_acq-mixed_SE-modulus_csf_mask.nii.gz'))

            se_csf_vol = nib.imagestats.mask_volume(masked_se) / 1000

            irse_dict = {'Subject': sub, 'Session': ses, 'Seg': 'SE_Modulus', 'Vol': se_csf_vol, 'Threshold': np.max(se_wm)}

            ses_df = pd.DataFrame([fs_dict, irse_dict])

            vol_df = pd.concat([vol_df, ses_df], ignore_index=True)

    vol_df.to_csv(vol_df_fn, index=False)

def plot_wm_thresholds(subjects, project):

    out_dir = op.join(project, 'derivatives', 'csf_seg')
    plot_dir = op.join(out_dir, 'group', 'figures')

    for idx, batch in enumerate([subjects[i: i + 4] for i in range(0, len(subjects), 4)]): 
        
        fig, axes = plt.subplots(4, 4, figsize=(16, 9))
        plot_fn = op.join(plot_dir, f'white_matter_se_signal_thresholds_group{idx}.png')
        for sub_idx, sub in enumerate(batch): 
            for ses_idx, ses in enumerate(list(range(1, 5))): 
                ax = axes[sub_idx, ses_idx]
                if ses == 1: ax.set_ylabel(f'Sub-{sub}', fontsize=16)
                if sub_idx == 0: ax.set_title(f'Ses-0{ses}', fontsize=16)

                mixed_dir = op.join(project, 'derivatives', 'csf_seg', f'sub-{sub}', f'ses-0{ses}')
                vol_dir = op.join(project, 'derivatives', 'csf_vol', f'sub-{sub}', f'ses-0{ses}') 
                se_fn = op.join(vol_dir, f'sub-{sub}_ses-0{ses}_acq-mixed_SE-modulus_registered_cranium_masked.nii.gz')
                se_im = nib.load(se_fn)
                se_dat = se_im.get_fdata()
                se_dat_flat = se_dat.flatten()
                se_dat_flat = se_dat_flat[se_dat_flat != 0]

                wm_mask_fn = op.join(vol_dir, f'sub-{sub}_ses-0{ses}_desc-eroded_WM_mask_from_fs.nii.gz')
                wm_mask = nib.load(wm_mask_fn)

                se_wm = se_dat * wm_mask.get_fdata()
                se_wm_flat = se_wm.flatten()
                se_wm_flat = se_wm[se_wm != 0]

                ax.hist(x = se_dat_flat, bins=60, color='blue', log=True, alpha=0.5)
                ax.hist(x = se_wm_flat, bins=60, color='red', log=True, alpha=0.5)
        
        plt.tight_layout()
        plt.savefig(plot_fn, dpi=300)
        print(plot_fn)

    # for batch in [subjects[i : 1 + 4] for i in range(0, len(subjects), 4)]: 
    #     print(batch)
    


    





            



    




    
            







