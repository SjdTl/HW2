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

from src.ltspice_to_svg import main as lt_to_svg

dir_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

t_offset = 1 # us

def read_transient(filename, T_settle = 10):
    LTR = RawRead(os.path.join(dir_path, "Simulations", rf"{filename}_tran.raw"))
    
    t = LTR.get_axis()  * 1e6
    Vop = LTR.get_trace('V(vop)')
    Von = LTR.get_trace('V(von)')
    Vip = LTR.get_trace('V(n006)')
    Vin = LTR.get_trace('V(n002)')
    Ivdd = LTR.get_trace('I(vdd)')

    fig, ax = plt.subplots(2,1, figsize=(7,7))
    ax[0].plot(t, Vip, label="$V_{ip}$")
    ax[0].plot(t, Vin, label="$V_{in}$")
    ax[1].plot(t, Vop, label="$V_{op}$")
    ax[1].plot(t, Von, label="$V_{on}$")
    
    for axx in ax:
        axx.set_xlabel("Time [$\mu$s]")
        axx.set_ylabel("Voltage [V]")
        axx.set_xlim(xmax=T_settle+5, xmin=0)

    plt.tight_layout()
    fig.savefig(os.path.join(dir_path, "Figures", rf"{filename}_tran.pdf"), transparent = True)

    return np.abs(Ivdd[-1] * 1e6)

def virtual_ground_settling(filename, Asettle=57):
    LTR = RawRead(os.path.join(dir_path, "Simulations", rf"{filename}_tran.raw"))
    t = LTR.get_axis() * 1e6
    Vm = LTR.get_trace('V(n001)').get_wave()
    Vp = LTR.get_trace('V(n005)').get_wave()
    Ivdd = LTR.get_trace('I(vdd)')

    accuracy = 20 * np.log10(1.2 / (np.abs(Vp-Vm) + 1e-9))

    fig, ax = plt.subplots(figsize=(7,4))
    ax.plot(t, accuracy)
    # ax.plot(t, np.abs(Virground-Virground[0]))
    ax.set_xlabel("Time [$\mu$s]")
    ax.set_ylabel("Accuracy [dB]")
    ax.set_ylim(ymax=accuracy[-1]*1.1)



    T_48dB = t[np.argmin(np.abs(accuracy - 48.69))] - t_offset
    T_40dB = t[np.argmin(np.abs(accuracy - 40))] - t_offset
    T_settle = t[np.argmin(np.abs(accuracy - Asettle))] - t_offset
    tau_cl_tran = T_48dB - T_40dB 

    parameters = {
        "T_48dB": T_48dB,
        "T_40dB": T_40dB,
        "T_settle": T_settle,
        "tau_cl_tran" : tau_cl_tran,
    }

    ax.set_xlim(xmax=T_settle+4, xmin=-0.1*(T_settle+4))
    fig.savefig(os.path.join(dir_path, "Figures", rf"{filename}_settling.pdf"), transparent=True)

    ax.hlines([48.69, 40, Asettle], xmin=t[0], xmax=T_settle*1.1+t_offset)


    ax.vlines(T_48dB+t_offset, ymax=48.69, ymin=np.min(accuracy))
    ax.vlines(T_40dB+t_offset, ymax=40, ymin=np.min(accuracy))
    ax.vlines(T_settle+t_offset, ymax=Asettle, ymin=np.min(accuracy))

    for i in [T_48dB, T_40dB, T_settle]:
        ax.annotate(rf"{i:.2f}$\mu s$", (i+t_offset, np.min(accuracy)-1), ha='center', va = "top")
    for i in [48.69, 40, Asettle]:
        ax.annotate(rf"{i:.2f}", (-0.25, i), ha='right', va='center')

    y_pos = np.min(accuracy)+5
    ax.annotate(
        '',                      
        xy=(T_40dB+t_offset, y_pos),      
        xytext=(T_48dB+t_offset, y_pos), 
        arrowprops=dict(arrowstyle="<->")
    )
    ax.annotate(
        rf'$\tau_{{cl}}$',
        ((T_40dB + T_48dB) / 2+t_offset, y_pos+1), 
        ha='center',
        va='bottom'
    )
    ax.annotate(
        rf'{tau_cl_tran:.3f}',
        ((T_40dB + T_48dB) / 2+t_offset, y_pos-1), 
        ha='center',
        va='top'
    )


    fig.savefig(os.path.join(dir_path, "Figures", rf"{filename}_settling_annotated.pdf"), transparent=True)

    return parameters
    

def write_transient(filename, Rbn=4.8, Rbp=6.2, Sa=2.5, Rmp=5, R34=3, Ibmain=200e-6, Cin=1e-8, Sa_b=1):
    LTC = SimRunner(output_folder=os.path.join(dir_path, "Simulations"))
    LTC.create_netlist(os.path.join(dir_path, "Circuits", rf"{filename}.asc"))
    netlist = SpiceEditor(os.path.join(dir_path, "Circuits", rf"{filename}.net"))

    netlist.set_parameters(Rbn=Rbn, Rbp=Rbp, Sa=Sa, Rmp=Rmp, R34=R34, Ibmain=Ibmain, Cin=Cin, Sa_b=Sa_b)

    netlist.add_instructions(
    "; Simulation settings",
    ".tran 0 100u 0 0.005u",
    ".save V(vop) V(n001) V(n005) V(von) V(n006) V(n002) I(vdd)",
    ".options plotwinsize=0",
    )

    
    LTC.run(netlist, run_filename="closed_loop_tran")
    LTC.wait_completion(2)