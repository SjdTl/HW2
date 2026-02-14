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

from src.ltspice_to_svg import main as lt_to_svg
plt.style.use(['science','ieee', 'no-latex'])


dir_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

def read_ac_closed(filename):
    LTR = RawRead(os.path.join(dir_path, "Simulations", rf"{filename}_ac.raw"))
    
    f = np.abs(LTR.get_axis())
    Vo = LTR.get_trace("V(Vo)")
    Vo_dB = 20*np.log10(np.abs(Vo))
    Vo_phase = np.unwrap(np.angle(Vo))

    fig,ax = plt.subplots(figsize=(7,4))
    ax.plot(f,Vo_dB, label="$V_o$ [dB]")
    axtwin = ax.twinx()
    axtwin.plot(f,Vo_phase, label="V_o [rad]", color="C1")
    plt.xscale('log')

    ax.set_xlabel("Frequency")
    ax.set_ylabel("Magnitude [dB]")
    axtwin.set_ylabel("Phase [rad]")

    formatter0=EngFormatter(unit='Hz')
    ax.xaxis.set_major_formatter(formatter0)


    # LABELS
    A_max = np.max(Vo_dB)
    A_3dB = A_max - 3
    f_3dB = f[np.argmin(np.abs(Vo_dB - A_3dB))]
    A_bot = np.min(Vo_dB)-5

    print(A_max)

    tau_cl=1/(2 * np.pi * f_3dB)*1e6

    ax.vlines(f_3dB, ymax=A_max, ymin = A_bot)
    ax.annotate(rf"$BW_{{cl}}={f_3dB*1e-6:.3f} MHz$", (f_3dB*0.8, A_bot), ha='right')
    ax.annotate(rf"$\tau={tau_cl:.3f} \mu s$", (f_3dB*1.2, A_bot), ha='left')

    ax.set_ylim(ymin=A_bot-4)
    plt.legend()
    plt.tight_layout()
    fig.savefig(os.path.join(dir_path, "Figures", rf"{filename}_ac.pdf"), transparent = True)

    return f_3dB, tau_cl


def write_ac_closed(filename, Rbn=4.8, Rbp=6.2, Sa=2.5, Rmp=5, R34=3, Ibmain=200e-6, Cin=1e-8, Sa_b=1):
    LTC = SimRunner(output_folder=os.path.join(dir_path, "Simulations"))
    LTC.create_netlist(os.path.join(dir_path, "Circuits", rf"{filename}.asc"))
    netlist = SpiceEditor(os.path.join(dir_path, "Circuits", rf"{filename}.net"))

    netlist.set_parameters(Rbn=Rbn, Rbp=Rbp, Sa=Sa, Rmp=Rmp, R34=R34, Ibmain=Ibmain, Cin=Cin, Sa_b=Sa_b)

    netlist.add_instructions(
    "; Simulation settings",
    ".ac dec 10 1 100G",
    )
    
    LTC.run(netlist, run_filename="closed_loop_ac")
    LTC.wait_completion(2)

def write_ac_open(filename, Rbn=4.8, Rbp=6.2, Sa=2.5, Rmp=5, R34=3, Ibmain=200e-6, Cin=1e-8, Sa_b=1, load="unloaded"):
    LTC = SimRunner(output_folder=os.path.join(dir_path, "Simulations"))
    LTC.create_netlist(os.path.join(dir_path, "Circuits", rf"{filename}_{load}.asc"))
    netlist = SpiceEditor(os.path.join(dir_path, "Circuits", rf"{filename}_{load}.net"))

    netlist.set_parameters(Rbn=Rbn, Rbp=Rbp, Sa=Sa, Rmp=Rmp, R34=R34, Ibmain=Ibmain, Cin=Cin, Sa_b=Sa_b)

    netlist.add_instructions(
    "; Simulation settings",
    ".ac dec 10 1 100G",
    )
    
    LTC.run(netlist, run_filename=rf"{filename}_{load}_ac")
    LTC.wait_completion(2)

def closed_loop_from_open(filename, load="loaded"):
    LTR = RawRead(os.path.join(dir_path, "Simulations", rf"{filename}_{load}_ac.raw"))
    
    f = np.abs(LTR.get_axis())
    Vo = LTR.get_trace("V(Vo)").get_wave()
    Vip = LTR.get_trace("V(Vinp)").get_wave()
    
    A_CL = (Vip) / (1 + Vip) * (Vo/Vip-1)
    # A_CL = 1/(1+Vip)
    A_dB = 20*np.log10(np.abs(A_CL))
    A_phase = np.unwrap(np.angle(A_CL))

    fig,ax = plt.subplots(figsize=(7,4))
    ax.plot(f,A_dB, label="$V_o$ [dB]")
    axtwin = ax.twinx()
    axtwin.plot(f,A_phase, label="V_o [rad]", color="C1")
    plt.xscale('log')

    ax.set_xlabel("Frequency")
    ax.set_ylabel("Magnitude [dB]")
    axtwin.set_ylabel("Phase [rad]")

    formatter0=EngFormatter(unit='Hz')
    ax.xaxis.set_major_formatter(formatter0)


    # LABELS
    A_max = np.max(A_dB)
    A_3dB = A_max - 3
    f_3dB = f[np.argmin(np.abs(A_dB - A_3dB))]
    A_bot = np.min(A_dB)-5

    print(A_max)

    tau_cl=1/(2 * np.pi * f_3dB)*1e6

    ax.vlines(f_3dB, ymax=A_max, ymin = A_bot)
    ax.annotate(rf"$BW_{{cl}}={f_3dB*1e-6:.3f} MHz$", (f_3dB*0.8, A_bot), ha='right')
    ax.annotate(rf"$\tau={tau_cl:.3f} \mu s$", (f_3dB*1.2, A_bot), ha='left')

    ax.set_ylim(ymin=A_bot-4)
    plt.legend()
    plt.tight_layout()
    fig.savefig(os.path.join(dir_path, "Figures", rf"{filename}_ac_closed_from_open.pdf"), transparent = True)


def read_ac_open(filename, load="unloaded"):
    LTR = RawRead(os.path.join(dir_path, "Simulations", rf"{filename}_{load}_ac.raw"))
    
    f = np.abs(LTR.get_axis())
    Vo = LTR.get_trace("V(Vo)")
    Vo_dB = 20*np.log10(np.abs(Vo))
    Vo_phase = np.unwrap(np.angle(Vo))
    Vip = LTR.get_trace("V(Vinp)")
    Vip_dB = 20*np.log10(np.abs(Vip))
    Vip_phase = np.unwrap(np.angle(Vip))

    fig,ax = plt.subplots(figsize=(7,4))
    ax.plot(f,Vo_dB, "-", label="A [dB]", color="C0")
    ax.plot(f, Vip_dB, "-", label=r"A$\beta$ [dB]", color="C1")
    axtwin = ax.twinx()
    axtwin.plot(f,Vo_phase, "--", label="A [rad]", color="C0")
    axtwin.plot(f,Vip_phase, "--", label=r"A$\beta$ [rad]", color="C1")
    plt.xscale('log')

    ax.set_xlabel("Frequency")
    ax.set_ylabel("Magnitude [dB]")
    axtwin.set_ylabel("Phase [rad]")

    formatter0=EngFormatter(unit='Hz')
    ax.xaxis.set_major_formatter(formatter0)


    # LABELS
    zero_index = np.argmin(np.abs(Vip_dB))
    BW_ol = f[zero_index]
    PM = Vip_phase[zero_index]+np.pi

    fully_real_index = np.argmin(np.abs(Vip_phase+np.pi/2))
    GM = -Vip_dB[fully_real_index]
    f_GM = f[fully_real_index]


    tau_cl=1/(2 * np.pi * BW_ol)*1e6

    # BW
    A_bot = np.min(Vip_dB)-5
    ax.vlines(BW_ol, ymax=0, ymin = A_bot)
    ax.annotate(rf"$BW_{{cl}}={BW_ol*1e-6:.3f} MHz$", (BW_ol*0.8, A_bot), ha='right')
    ax.annotate(rf"$\tau={tau_cl:.3f} \mu s$", (BW_ol*1.2, A_bot), ha='left')

    # Margins 
    axtwin.annotate(
        '',                      
        xy=(BW_ol, -np.pi + PM),      
        xytext=(BW_ol, -np.pi), 
        arrowprops=dict(arrowstyle="<->")
    )
    axtwin.annotate(
        rf'PM={PM:.2f}',
        xy = (BW_ol*0.9, -np.pi + 0.5 * PM),
        ha='right',
        va='center'
    )
    
    ax.annotate(
        '',                      
        xy=(f_GM, 0),      
        xytext=(f_GM, -GM), 
        arrowprops=dict(arrowstyle="<->")
    )
    ax.annotate(
        rf'GM={GM:.2f}',
        xy = (f_GM*1.1, -0.5 * GM),
        ha='left',
        va='center'
    )

    ax.set_ylim(ymin=A_bot-4)
    ax.grid()
    plt.legend()
    plt.tight_layout()
    fig.savefig(os.path.join(dir_path, "Figures", rf"{filename}_{load}_ac.pdf"), transparent = True)

    return BW_ol

closed_loop_from_open("closed_loop")
read_ac_closed("closed_loop")