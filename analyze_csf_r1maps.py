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

# def plot_subject_r1_map(subject, project):

#     out_dir = op.join(project, 'derivatives', 'csf_seg', f'sub-{subject}', f'ses-{session}')
#     plot_dir = op.join(out_dir, 'figures')
#     os.makdirs(plot_dir, exist_ok=True)
#     r1map_basename = f'sub-{subject}_ses-{session}_acq-mixed_R1map_postproc.nii.gz'
    
#     r1_fn = op.join(out_dir, r1map_basename)
#     r1_im = nib.load(r1_fn)

    # display = plotting.plot_img(img = r1_im, vmin=0.2, vmax=0.25, 
    #                            cmap="RdBu_r", display_mode="x")

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
    labels = [d.title() if d != 'SAS' else d for d in cvs_lut['description'].tolist()]
    
    fig.legend(handles, labels, loc='right', fontsize=16, 
               facecolor='black', labelcolor='white')

    plot_fn = op.join(plot_dir, f'sub-{subject}-ses{session}_desc-csv_segmentation.svg')
    plt.savefig(plot_fn, dpi=300)
    
        









