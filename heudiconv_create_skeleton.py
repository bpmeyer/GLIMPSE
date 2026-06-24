#!/usr/bin/env python3
"""Run heudiconv in a SIF container to create a conversion skeleton."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


SIF_CONTAINER = Path("/mnt/cina/lib/heudiconv_latest.sif")


def find_sif_container(sif_container: str | Path | None = None) -> Path:
    """Return the requested SIF container, or the project default."""

    path = Path(sif_container).expanduser().resolve() if sif_container else SIF_CONTAINER
    if not path.is_file():
        raise FileNotFoundError(f"SIF container not found: {path}")
    return path


def run_heudiconv_create_skeleton(
    subject: str,
    sif_container: str | Path | None = None,
    dicom_dir: str | None = None,
    output_dir: str | Path = "nifti",
    heuristic: str = "convertall",
    converter: str = "none",
    runtime: str | None = None,
    workdir: str | Path = ".",
) -> subprocess.CompletedProcess[str]:
    """Run heudiconv with the default GLIMPSE skeleton command layout.

    Expected project layout:
        dicoms/{subject}/{session}/scans/**/*.dcm
        nifti/
    """

    workdir = Path(workdir).resolve()
    sif_container = find_sif_container(sif_container)
    output_dir = Path(output_dir)
    dicom_dir = f"dicoms/{subject}/"

    (workdir / output_dir).mkdir(parents=True, exist_ok=True)

    runtime = runtime or shutil.which("apptainer") or shutil.which("singularity")
    if runtime is None:
        raise RuntimeError("Could not find apptainer or singularity on PATH.")

    command = [
        runtime,
        "exec",
        "--cleanenv",
        "--bind",
        f"{workdir}:/work",
        str(sif_container),
        "heudiconv",
        "--files",
        f"/work/dicom_dir",
        "-o",
        str(output_dir),
        "-f",
        heuristic,
        "-s",
        subject,
        "-c",
        converter,
    ]

    print("Running:", " ".join(command))
    return subprocess.run(command, check=True, text=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a heudiconv skeleton with a SIF container."
    )
    parser.add_argument("subject", help="Subject ID, e.g. 219.")
    parser.add_argument(
        "--sif-container",
        default=None,
        help="Optional path to a .sif container. Defaults to /mnt/cina/lib/heudiconv_lastest.sif.",
    )
    parser.add_argument(
        "--dicom-dir",
        default="dicoms", help="DICOM dir relative to the working directory.")
    parser.add_argument("-o", "--output-dir", default="nifti", help="Output directory.")
    parser.add_argument("-f", "--heuristic", default="convertall", help="Heuristic.")
    parser.add_argument("-c", "--converter", default="none", help="Converter.")
    parser.add_argument(
        "--runtime",
        choices=("apptainer", "singularity"),
        default=None,
        help="Container runtime. Defaults to apptainer, then singularity.",
    )
    parser.add_argument(
        "--workdir",
        default=".",
        help="Directory to bind as /work inside the container.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_heudiconv_create_skeleton(
        subject=args.subject,
        sif_container=args.sif_container,
        dicom_dir=args.dicom_dir,
        output_dir=args.output_dir,
        heuristic=args.heuristic,
        converter=args.converter,
        runtime=args.runtime,
        workdir=args.workdir,
    )
