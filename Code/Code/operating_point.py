import pandas as pd
import os
import io
import re
import numpy as np
import subprocess
import shutil
import ltspice
import matplotlib.pyplot as plt
from PyLTSpice import SimRunner, RawRead
from PyLTSpice import SpiceEditor
from .utils import optimize_svg

from src.ltspice_to_svg import main as lt_to_svg

dir_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

def read_operating_point(filename, save=True):
    """
    Parses the Semiconductor Device Operating Points section from LTSpice output 
    and returns a pandas DataFrame.
    """
    try:
        filename = filename.split(".log")[0]
        file_path = os.path.join(dir_path, "Simulations", rf"{filename}_op.log")
        fileout = os.path.join(dir_path, "Processing", filename)
    except:
        file_path=filename

    with open(file_path, "r") as file:
        content = file.read()

    start_tag = "Semiconductor Device Operating Points:"
    end_tag = "Date: "
    try:
        data_section = content.split(start_tag, 1)[1]
    except IndexError:
        raise ValueError("Could not find the start of the operating points data.")
    data_section = data_section.split(end_tag, 1)[0]
    
    lines = data_section.split('\n')
    filtered_lines = [
        line for line in lines 
        if line.strip() and not line.strip().startswith('---')
    ]
    cleaned_data = '\n'.join(
        re.sub(r'\s{2,}', ' ', line.strip()) for line in filtered_lines
    )
    split_data = cleaned_data.split("Name:")
    dfs = []
    for i in range(1, np.size(split_data)):
        df=pd.read_csv(
            io.StringIO(split_data[i]),
            sep='\s+',
            index_col=0,
        )
        dfs.append(df)
    op_df = pd.concat(dfs, axis=1)

    test_saturation = pd.DataFrame()
    test_saturation[r"$\vert V_{Th} \vert$"] =  op_df.loc["Vth:"].astype("float").abs()
    test_saturation[r"$\vert V_{GS} \vert$"] =  op_df.loc["Vgs:"].astype("float").abs()
    test_saturation[r"$\vert V_{DS}+V_{Th} \vert$"] = op_df.loc["Vds:"].astype("float").abs() + (op_df.loc["Vth:"]).astype("float").abs()
    test_saturation[r"$\vert V_{GT}-V_{Th} \vert$"] = op_df.loc["Vgs:"].astype("float").abs() - (op_df.loc["Vth:"]).astype("float").abs()
    test_saturation["Saturation?"] = np.logical_and((test_saturation[r"$\vert V_{Th} \vert$"] < test_saturation[r"$\vert V_{GS} \vert$"]), (test_saturation[r"$\vert V_{GS} \vert$"] < test_saturation[r"$\vert V_{DS}+V_{Th} \vert$"]))
    test_saturation.sort_index(axis=0, inplace=True)
    test_saturation = test_saturation.T

    tot_df = pd.concat([test_saturation, op_df])
    tot_df.loc["Id:"] = tot_df.loc["Id:"].astype("float") * 1e6
    if save==True:
        # Split the dataframe into two halves
        df1 = tot_df.sort_index(axis=1).iloc[:, :10]  
        df2 = tot_df.sort_index(axis=1).iloc[:, 10:] 


        df1.to_latex(rf"{fileout}_op1.tex", float_format="%.2f")
        df2.to_latex(rf"{fileout}_op2.tex", float_format="%.2f")
        tot_df.to_csv(rf"{fileout}.csv")
    return tot_df 

def write_operating_point(filename, Rbn=4.8, Rbp=6.2, Sa=2.5, Rmp=5, R34=3, Ibmain=200e-6, Cin=1e-8, Sa_b=1):
    LTC = SimRunner(output_folder=os.path.join(dir_path, "Simulations"))
    LTC.create_netlist(os.path.join(dir_path, "Circuits", rf"{filename}.asc"))


    netlist = SpiceEditor(os.path.join(dir_path, "Circuits", rf"{filename}.net"))

    netlist.add_instructions(
    "; Simulation settings",
    ".op",
    )

    netlist.set_parameters(Rbn=Rbn, Rbp=Rbp, Sa=Sa, Rmp=Rmp, R34=R34, Ibmain=Ibmain, Cin=Cin, Sa_b=Sa_b)
    LTC.run(netlist, run_filename="closed_loop_op")
    LTC.wait_completion(2)

def save_schematic(filename):
    filename = filename.split(".asc")[0]
    file_path = os.path.join(dir_path, "Circuits", rf"{filename}.asc")

    lt_to_svg([
    rf"{file_path}", 
    "--stroke-width", "3.0",
    "--ltspice-lib", "C:\\Users\\terlo\\OneDrive\\Documenten\\LTspiceXVII\\lib\\sym",
    "--font-family", "Times New Roman",
    ])

    optimize_svg(os.path.join(dir_path, "Circuits", rf"{filename}.svg"))

def annotate_voltages(filename, schematic_name):
    template_file = os.path.join(dir_path, "Figures", rf"{schematic_name}_voltage_template.svg")
    schematic_file = os.path.join(dir_path, "Figures", rf"{schematic_name}_voltage.svg")
    shutil.copy(template_file, schematic_file)

    LTR = RawRead(os.path.join(dir_path, "Simulations", rf"{filename}_op.raw"))

    gd = lambda s : np.float32(LTR.get_trace(rf"V({s})"))[0]
    
    voltages = {
        "Vbp": gd("x1:vbp"),
        "Vsp": gd("x1:vsp"),
        "Vcp": gd("x1:vcp"),
        "Vcn": gd("x1:vcn"),
        "Vsn": gd("x1:vsn"),
        "Vbn": gd("x1:vbn"),
        "Vdd": gd("n003"),
        "Vi\+": gd("n005"),
        "Vi-": gd("n001"),
        "Vo-": gd("vop"),
        "Vo\+": gd("von"),
        "Vgn2": gd("x1:vcn"),
        "Vsi": gd("x1:vsi"),
        "Vssi": gd("x1:vssi"),
        "Vbcm" : gd("x1:vbcm"),
        "Vpml" : gd("x1:vpml"),
        "Vpmr" : gd("x1:vpmr"),
        "Vpg" : gd("x1:vpg"),
        "Vnml" : gd("x1:vnml"),
        "Vnmr" : gd("x1:vnmr"),
    }

    with open(schematic_file, 'r+') as f:
        file_data = f.read()
        for name, voltage in voltages.items():
            file_data = re.sub(rf"{name}_V", rf"{voltage:.2f} V", file_data)
        f.seek(0)
        f.write(file_data)
        f.truncate()

def annotate_currents(filename, schematic_name):
    template_file = os.path.join(dir_path, "Figures", rf"{schematic_name}_current_template.svg")
    schematic_file = os.path.join(dir_path, "Figures", rf"{schematic_name}_current.svg")
    shutil.copy(template_file, schematic_file)

    df = read_operating_point(filename, save=False) 
    # print(df)
    gd = lambda s: np.abs(np.float32(df[rf"m:x1:{s}"].loc["Id:"]))

    currents = {
        "n3": gd("n3"),
        "n4": gd("n4"),
        "p3": gd("p3"),
        "p1": gd("p1"),
        "n2": gd("n2"),
        "n5": gd("n5"),
        "n7": gd("n7"),
    }

    with open(schematic_file, 'r+') as f:
        file_data = f.read()
        for name, current in currents.items():
            file_data = re.sub(rf"{name}_uA", rf"{current:.1f} uA", file_data)
        f.seek(0)
        f.write(file_data)
        f.truncate()