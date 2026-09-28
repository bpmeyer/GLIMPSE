import numpy as np 
from nilearn import image, plotting
import nibabel as nib
import os
import os.path as op
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as cm
from gmri2fem import segment_tools as segtools
import matplotlib.patches as mpatches
import pandas as pd 
from glob import glob
import seaborn as sns 

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
    plot_fn = op.join(plot_dir, f'group_boxplot_meanr1_by_region_sub{first_sub}_to_sub{last_sub}.svg') 
    plt.savefig(plot_fn, dpi=300)

    print(f'Saved figure at {plot_fn}')

    



            



    




    
            







