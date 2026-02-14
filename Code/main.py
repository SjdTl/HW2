from Code.operating_point import read_operating_point, write_operating_point, save_schematic, annotate_voltages, annotate_currents
from Code.transient import write_transient, read_transient, virtual_ground_settling
from Code.ac import write_ac_closed, read_ac_closed, write_ac_open, read_ac_open, closed_loop_from_open
from Code.onoise import read_onoise, write_onoise
from Code.utils import compileLatex
import os 
import shutil
import re
import numpy as np
from skopt import gp_minimize
from skopt.space import Real
from PyLTSpice import SimRunner
from PyLTSpice import SpiceEditor
from PyLTSpice import LTSpiceLogReader
import matplotlib.pyplot as plt
import scienceplots
from skopt.callbacks import CheckpointSaver
from skopt import load
plt.style.use(['science','ieee', 'no-latex'])


dir_path = os.path.dirname(os.path.realpath(__file__))

filename="closed_loop"

def write_table(filename, parameters):
    template_file = os.path.join(dir_path, "Figures", rf"{filename}_template.tex")
    goal_file = os.path.join(dir_path, "Figures", rf"{filename}.tex")
    shutil.copy(template_file, goal_file)

    with open(goal_file, 'r+') as f:
        file_data = f.read()
        for name, data in parameters.items():
            file_data = re.sub(rf"__{name}__", rf"{data:.3f}", file_data)
        f.seek(0)
        f.write(file_data)
        f.truncate()

def write_final_values(filename, Sa, R34, Rmp, Ibmain, Cin, Sa_b):
    filepath = os.path.join(dir_path, "Figures", filename)

    with open(filepath, 'w') as f:
        f.write(rf"""
\begin{{equation}}
    \begin{{cases}} 
        S_a = {Sa} \\ 
        R_{{34}} = {R34} \\ 
        R_{{mp}} = {Rmp} \\ 
        I_{{bmain}} = {Ibmain*1e6} \mu A \\ 
        C_{{in}} = {Cin*1e12} p F \\ 
        S_{{ab}} = {Sa_b}
    \end{{cases}}
\end{{equation}}
""")

def evaluate_all(filename, Sa=3.5, R34=3, Rmp=5, Ibmain=200e-6, Cin=5e-12, Sa_b=1, simulate=False):
    parameters = {}
    parameters["Cin"]=Cin *1e12
    parameters["Cfb"]=Cin/8 * 1e12
    parameters["Ccm"]=Cin/8 * 1e12
    parameters["Cload"]=Cin * 1e12

    # OPERATING POINT
    print("-----------------------")
    print("Operating point")
    print("-----------------------")
    if simulate: write_operating_point(filename, Sa=Sa, R34=R34, Rmp=Rmp, Ibmain=Ibmain, Cin=Cin, Sa_b=Sa_b)
    read_operating_point(filename)
    annotate_voltages(filename, "op_amp")
    annotate_currents(filename, "op_amp")

    # TRANSIENT
    print("-----------------------")
    print("Transient")
    print("-----------------------")
    if simulate: write_transient(filename, Sa=Sa, R34=R34, Rmp=Rmp, Ibmain=Ibmain, Cin=Cin, Sa_b=Sa_b)
    vground_parameters = virtual_ground_settling(filename)
    parameters = vground_parameters | parameters
    I = read_transient(filename, T_settle = parameters["T_settle"])
    parameters["I"] = I
    P = I * 1.8
    parameters["P"] = P


    # AC closed
    print("-----------------------")
    print("AC closed")
    print("-----------------------")
    if simulate: write_ac_closed(filename, Sa=Sa, R34=R34, Rmp=Rmp, Ibmain=Ibmain, Cin=Cin, Sa_b=Sa_b)
    BW_cl, tau_cl = read_ac_closed(filename)
    parameters["BW_cl"] = BW_cl * 1e-6
    parameters["tau_cl"] = tau_cl

    print("-----------------------")
    print("AC open")
    print("-----------------------")
    if simulate: write_ac_open(filename, Sa=Sa, R34=R34, Rmp=Rmp, Ibmain=Ibmain, Cin=Cin, Sa_b=Sa_b, load="unloaded")
    _ = read_ac_open(filename, load="unloaded")
    if simulate: write_ac_open(filename, Sa=Sa, R34=R34, Rmp=Rmp, Ibmain=Ibmain, Cin=Cin, Sa_b=Sa_b, load="loaded")
    BW_ol = read_ac_open(filename, load="loaded")
    closed_loop_from_open(filename)
    parameters["BW_ol"] = BW_ol * 1e-6

    # NOISE
    print("-----------------------")
    print("Noise")
    print("-----------------------")
    if simulate: write_onoise(filename, Sa=Sa, R34=R34, Rmp=Rmp, Ibmain=Ibmain, Cin=Cin, Sa_b=Sa_b)
    SNR, int_noise = read_onoise(filename)
    parameters["SNR"] = SNR
    parameters["V_int"] = int_noise
    FOM_lin = 2 * np.pi * P * 1e-6 * parameters["tau_cl_tran"] * 1e-6 / (10**(SNR/20))**2
    FOM_dB = -10 * np.log10(FOM_lin)
    parameters["FOM_lin"] = FOM_lin * 1e18
    parameters["FOM_dB"] = FOM_dB

    return parameters

def main(filename, Sa=3.5, R34=3, Rmp=5, Ibmain=200e-6, Cin=5e-12, Sa_b=1, simulate=True):
    print(rf"SIMULATION === {simulate}")
    parameters = evaluate_all(filename, Sa=Sa, R34=R34, Rmp=Rmp, Ibmain=Ibmain, Cin=Cin, Sa_b=Sa_b, simulate=simulate)
    write_final_values("input_values.tex", Sa, R34, Rmp, Ibmain, Cin, Sa_b=Sa_b)
    write_table("result_table", parameters)
    compileLatex(dir_path=os.path.dirname(dir_path), tex_name="HW2_Sjoerd_Terlouw")

    latex_path_old = os.path.join(os.path.dirname(dir_path), "HW2_Sjoerd_Terlouw.pdf")
    latex_path_new = os.path.join(os.path.dirname(dir_path), rf"Sa_{Sa}_R34_{R34}_Rmp_{Rmp}_Ibmain_{Ibmain*1e6}_Cin_{Cin*1e12}_Sab_{Sa_b}.pdf")
    shutil.copy(latex_path_old, latex_path_new)

def objective(params):
        Ibmain, R34, Rmp, Sa_b, Sa, Cin = params
        print(rf".param Ibmain = {Ibmain*1e6:.2f}u R34={R34:.2f} Rmp={Rmp:.2f} Sa_b={Sa_b:.2f} Sa={Sa:.2f} Cin={Cin*1e12:.3f}p")
        print(rf"main(filename, Cin={Cin*1e12:.3f}e-12, Ibmain={Ibmain*1e6:.2f}e-6, R34={R34:.2f}, Rmp={Rmp:.2f}, Sa_b = {Sa_b:.2f}, Sa={Sa:.2f})")
        
        import time
        temp_netlist = os.path.join(dir_path, "ML", f"temp_{int(time.time())}.net")

        import shutil
        shutil.copy2(os.path.join(dir_path, "Circuits", "ML.net"), temp_netlist)

        # 1. Load the template
        netlist = SpiceEditor(os.path.join(dir_path, "Circuits", temp_netlist))

        # 2. Set parameters
        netlist.set_parameters(Sa=Sa, Rmp=Rmp, R34=R34, Ibmain=Ibmain, Cin=Cin, Sa_b=Sa_b)

        # 3. Use a unique filename for the RUN
        LTC.run(netlist, run_filename='ML')
        LTC.wait_completion(timeout=5)

        log = LTSpiceLogReader(os.path.join(dir_path, "Simulations", rf"ML.log"))
        try:
            a0 = log.get_measure_value("a0")
            a1 = log.get_measure_value("a1")
            cur = log.get_measure_value("current")
            write_onoise(filename, Sa=Sa, R34=R34, Rmp=Rmp, Ibmain=Ibmain, Cin=Cin, Sa_b=Sa_b)
            SNR, _ = read_onoise(filename)

            fom = 0.1*np.abs((a1-57.3)*10000)**2 + 10*np.abs(cur) + 0.1*np.abs((SNR-83.65)*10000)**2

            print(a0, a1, cur, SNR)
        except:
            fom = 1e30
            print("SIMULATION FAILED")
            try:
                os.system("taskkill /f /im XVIIx64.exe /t")
            except:
                1==1

        with open(os.path.join(dir_path, "optimization_log.csv"),"a") as f:
            # Format: Time, Ibmain, R34, Rmp, Sa_b, Sa, FoM
            f.write(f"{time.ctime()}, {','.join(map(str, params))}, {fom}\n")
        return fom

def ML(load_old=False):
    params = spice_to_dict(".param Cin=61p Ibmain=2000u R34=2 Rmp=4 Sa_b=4000 Sa=92.5")

    space = [
        Real(565.25e-6, 575e-6), # Ibmain
        Real(90, 100),                       # R34
        Real(0.5, 2),                       # Rmp
        Real(15, 19),  # Sa_b
        Real(0.8, 1.15),  # Sa
        Real(25e-12, 35e-12), # Cin
    ]

    checkpoint_callback = CheckpointSaver(os.path.join(dir_path, "result.pkl"), compress=4)

    if load_old:
        print("Found existing checkpoint")
        res_prev = load(os.path.join(dir_path, "result.pkl"))
        x0 = res_prev.x_iters
        y0 = res_prev.func_vals
        n_random = 40
    else:
        print("No checkpoint found")
        x0 = (572.25e-6, 95, 0.9, 17, 0.985, 32.18e-12)
        y0 = None
        n_random = 20

    # --- THE OPTIMIZER ---
    res = gp_minimize(
        objective, 
        space,
        x0=x0,
        y0=y0,
        n_calls=2000,
        n_random_starts=n_random,
        callback=[checkpoint_callback],
        verbose=True
    )

    Ibmain, R34, Rmp, Sa_b, Sa, Cin = res.x
    Ibmain, R34, Rmp, Sa_b, Sa, Cin = np.round((R34, Rmp, Sa_b, Sa, Ibmain*1e6, Cin*1e12),2)


    main(filename, Sa, R34, Rmp, Ibmain*1e-6, Cin*1e-12, Sa_b)

    from skopt.plots import plot_convergence
    import matplotlib.pyplot as plt

    plt.close()
    plot_convergence(res)
    plt.show()

def spice_to_dict(param_str):
    # Dictionary of Spice multipliers
    multipliers = {
        't': 1e12, 'g': 1e9, 'meg': 1e6, 'k': 1e3, 
        'm': 1e-3, 'u': 1e-6, 'n': 1e-9, 'p': 1e-12, 'f': 1e-15
    }
    
    # Extract key=value pairs using Regex
    # Matches patterns like Ibmain=28.05u
    matches = re.findall(r'(\w+)=([\d\.]+)([a-zA-Z]*)', param_str)
    
    results = {}
    for key, val, unit in matches:
        value = float(val)
        unit = unit.lower()
        
        # Apply multiplier if it exists
        if unit in multipliers:
            value *= multipliers[unit]
            
        results[key] = value
    print(results)
    return results

# params = spice_to_dict(".param Cin=29.5p Ibmain=572.25u Rmp=0.9 Sa=0.917 Sa_b=17 R34=95")
# write_operating_point(filename, Sa=params["Sa"], Rmp=params["Rmp"], R34=params["R34"], Ibmain=params["Ibmain"], Cin=params["Cin"], Sa_b=params["Sa_b"])
# read_operating_point(filename, save=True)


# LTC = SimRunner(output_folder=os.path.join(dir_path, "Simulations"))
# LTC.create_netlist(os.path.join(dir_path, "Circuits", rf"ML.asc"))
# ML(load_old=False)




# REQUIREMENTS+NOSAT+173.5
# .param Cin=60p Ibmain=200u R34=2 Rmp=4 Sa_b=1200 Sa=253
# main(filename, Cin=60e-12, Ibmain=200e-6, R34=2, Rmp=4, Sa_b = 1200, Sa=253)

# REQUIREMENTS+NOSAT+173.6
# main(filename, Cin=58.05e-12, Ibmain=193.93e-6, R34=1.86, Rmp=4.32, Sa_b=1258.3, Sa=257.25)

# REQUIREMENTS + SAT + 170.3
# .param Cin=58.7p Ibmain=226u R34=1.99 Rmp=4.16 Sa_b=20 Sa=7
# main(filename, Cin=58.7e-12, Ibmain=226e-6, R34=1.99, Rmp=4.16, Sa_b=20, Sa=7)

# REQUIREMENTS+SAT+
# params = spice_to_dict(".param Cin=61p Ibmain=2000u R34=2 Rmp=4 Sa_b=4000 Sa=92.5")
# main(filename, Sa=params["Sa"], Rmp=params["Rmp"], R34=params["R34"], Ibmain=params["Ibmain"], Cin=params["Cin"], Sa_b=params["Sa_b"])

# REQUIREMENTS+ALMOSTSAT+175.18
# params = spice_to_dict(".param Cin=37p Ibmain=226u R34=100 Rmp=0.5 Sa_b=20 Sa=2.97")
# main(filename, Sa=params["Sa"], Rmp=params["Rmp"], R34=params["R34"], Ibmain=params["Ibmain"], Cin=params["Cin"], Sa_b=params["Sa_b"])

# REQUIREMENTS+ALMOSTSAT+175.4
# params = spice_to_dict(".param Cin=32.5p Rmp=0.67 Sa=1.21 Sa_b=20.20 R34=89.14 Ibmain=572.25u")
# main(filename, Sa=params["Sa"], Rmp=params["Rmp"], R34=params["R34"], Ibmain=params["Ibmain"], Cin=params["Cin"], Sa_b=params["Sa_b"])

# REQUIREMENTS+ALMOSTSAT+175.2
# params = spice_to_dict(".param Cin=33.61p Ibmain=572.25u Rmp=0.67 Sa=1.466 Sa_b=25.11 R34=89.14")
# main(filename, Sa=params["Sa"], Rmp=params["Rmp"], R34=params["R34"], Ibmain=params["Ibmain"], Cin=params["Cin"], Sa_b=params["Sa_b"])

# REQUIREMENTS+ALMOSTSAT+175.34
# params = spice_to_dict(".param Cin=32.18p Ibmain=572.25u Rmp=0.9 Sa=0.985 Sa_b=17 R34=95")
# main(filename, Sa=params["Sa"], Rmp=params["Rmp"], R34=params["R34"], Ibmain=params["Ibmain"], Cin=params["Cin"], Sa_b=params["Sa_b"])

# REQUIREMENTS+ALMOSTSAT+175.333
params = spice_to_dict(".param Cin=32.36p Ibmain=572.1u Rmp=0.907 Sa=0.986 Sa_b=16.907 R34=95")
main(filename, Sa=params["Sa"], Rmp=params["Rmp"], R34=params["R34"], Ibmain=params["Ibmain"], Cin=params["Cin"], Sa_b=params["Sa_b"])

# .param Cin=48.4p*(1-0.32*{x}**0.43) Rmp=0.67 Sa=13 Sa_b=20.20 R34=89.14*{x} Ibmain=572.25u*{x}