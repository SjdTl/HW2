import pandas as pd
import os
import io
import re
import numpy as np
import subprocess
import shutil
import ltspice
import matplotlib.pyplot as plt
import scienceplots
import warnings
# plt.style.use(['science','ieee'])


from src.ltspice_to_svg import main as lt_to_svg

def optimize_svg(path):
    # Run the SVGO command if SVGO is installed
    if shutil.which("svgo") is not None:
        subprocess.run([shutil.which("svgo"), path])

def save_schematic(filename):
    filename = filename.split(".asc")[0]
    file_path = os.path.join(dir_path, rf"{filename}.asc")

    lt_to_svg([
    rf"{file_path}", 
    "--stroke-width", "3.0",
    "--ltspice-lib", "C:\\Users\\terlo\\OneDrive\\Documenten\\LTspiceXVII\\lib\\sym",
    "--font-family", "Times New Roman",
    ])

    optimize_svg(os.path.join(dir_path, rf"{filename}.svg"))

def compileLatex(dir_path, tex_name):
    if tex_name.split(".")[-1] == 'tex':
        raise ValueError("Do not provide the .tex extension of the file")
    
    print("COMPILING LATEX")
    if shutil.which("pdflatex") is not None:
        subprocess.run([
            "pdflatex",
            "--max-print-line=10000",
            "-synctex=1",
            "-shell-escape",
            "-interaction=nonstopmode",
            "-file-line-error",
            "-recorder",
            rf"{tex_name}.tex"
        ], cwd=dir_path)
        if shutil.which("gs") is not None:
            temp_out = f"{tex_name}_temp.pdf"
            subprocess.run([
                "gs",
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.7",
                "-dPDFSETTINGS=/prepress",
                "-dNOPAUSE",
                "-dQUIET",
                "-dBATCH",
                "-dColorImageFilter=/FlateEncode",
                "-dGrayImageFilter=/FlateEncode",
                "-dMonoImageFilter=/FlateEncode",
                "-dCompressFonts=true",
                "-dSubsetFonts=true",
                "-dRemoveFileName=true",
                f'-sOutputFile={temp_out}',
                f"{tex_name}.pdf"
            ], cwd = dir_path)

            path_temp = os.path.join(dir_path, temp_out)
            path_pdf = os.path.join(dir_path, f"{tex_name}.pdf")

            if os.path.getsize(path_temp) < os.path.getsize(path_pdf):
                print(f"Optimized pdf size by {os.path.getsize(path_pdf)/os.path.getsize(path_temp)}")
                os.replace(path_temp, path_pdf)
            else:
                os.remove(path_temp)
        else:
            warnings.warn("ghostscript not installed, can't compress pdf")
    else:
        warnings.warn("pdflatex not found in PATH, can't compile latex automatically")