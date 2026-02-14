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
from PyLTSpice import SimRunner
from PyLTSpice import SpiceEditor
from PyLTSpice import RawRead
from matplotlib.ticker import EngFormatter

dir_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

def read_onoise(filename):
    LTR = RawRead(os.path.join(dir_path, "Simulations", rf"{filename}_noise.raw"))
    f = LTR.get_axis()
    Vonoise = LTR.get_trace("V(onoise)")

    fig,ax = plt.subplots(figsize=(7,4))
    ax.set_xlabel("Frequency")

    ax.loglog(f, Vonoise, label="Total noise")

    formatter0=EngFormatter(unit='Hz')
    ax.xaxis.set_major_formatter(formatter0)
    noise_rms_uV = np.sqrt(np.abs((np.trapezoid(np.square(Vonoise),f)))) * 1e6
    SNR = np.abs(20*np.log10(0.8485/(noise_rms_uV*1e-6)))
    ax.annotate(rf"Total noise = {noise_rms_uV:.2f} $\mu V_{{rms}}$, $SNR={SNR:.2f}$", (np.min(f),np.min(Vonoise)))

    fig.savefig(os.path.join(dir_path, "Figures", rf"{filename}_noise.pdf"), transparent = True)
    plt.close()
    return SNR, noise_rms_uV


def write_onoise(filename, Rbn=4.8, Rbp=6.2, Sa=2.5, Rmp=5, R34=3, Ibmain=200e-6, Cin=1e-8, Sa_b=1):
    LTC = SimRunner(output_folder=os.path.join(dir_path, "Simulations"))
    LTC.create_netlist(os.path.join(dir_path, "Circuits", rf"{filename}.asc"))
    netlist = SpiceEditor(os.path.join(dir_path, "Circuits", rf"{filename}.net"))

    netlist.set_parameters(Rbn=Rbn, Rbp=Rbp, Sa=Sa, Rmp=Rmp, R34=R34, Ibmain=Ibmain, Cin=Cin, Sa_b=Sa_b)

    netlist.add_instructions(
    "; Simulation settings",
    ".noise V(Vo) Vi dec 100 10k 100G",
    )
    
    LTC.run(netlist, run_filename="closed_loop_noise")
    LTC.wait_completion(2)