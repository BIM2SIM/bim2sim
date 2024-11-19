import os
from pathlib import Path
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

"""
A collection of post-processing python scripts for plotting different 
parameters from OpenFOAM simulations.
"""
from itertools import cycle


# Function to get the next unused color
def get_next_unused_color(ax):
    # Get current color cycle
    color_cycle = cycle(plt.rcParams['axes.prop_cycle'].by_key()['color'])

    # Get colors already used in the Axes
    used_colors = [line.get_color() for line in ax.get_lines()]

    # Find the next unused color
    for color in color_cycle:
        if color not in used_colors:
            return color

    # If all colors are used, return the first color in the cycle (fallback)
    return next(color_cycle)

def convergencePlot(of_directory: str):
    """
    Creates a plot of velocity (U) and temperature (T, directly proportional
    to h) residuals over the simulated iteration steps.
    """
    Ux_Init = []
    Ux_Final = []
    Uy_Init = []
    Uy_Final = []
    Uz_Init = []
    Uz_Final = []
    h_Init = []
    h_Final = []
    values = [Ux_Init, Ux_Final, Uy_Init, Uy_Final, Uz_Init, Uz_Final,
              h_Init, h_Final]
    # Collect directories from all simulation phases and sort them in
    # ascending time steps
    time_dirs = os.listdir(of_directory / 'postProcessing/solverInfo/')
    time_dirs.sort()
    time_dirs.sort(key=len)   # yes, these are both necessary
    for timestep in time_dirs:
        with open(of_directory / 'postProcessing/solverInfo/' /
                  timestep / 'solverInfo.dat', 'r') as f:
            lines = f.readlines()
            track_U = track_h = False
            indices = lines[1].split('\t')
            if 'U_solver' in lines[1]:
                track_U = True
                ind_u = indices.index('U_solver         ')
            if 'h_solver' in lines[1]:
                track_h = True
                ind_h = indices.index('h_solver         ')
            for line in lines[2:]:
                line = line.split('\t')
                if track_U and len(line) > 5:
                    [uxinit, uxfinal] = line[ind_u+1:ind_u+3]
                    [uyinit, uyfinal] = line[ind_u+4:ind_u+6]
                    [uzinit, uzfinal] = line[ind_u+7:ind_u+9]
                else:
                    uxinit = uxfinal = uyinit = uyfinal = uzinit = uzfinal = 0
                Ux_Init.append(float(uxinit))
                Ux_Final.append(float(uxfinal))
                Uy_Init.append(float(uyinit))
                Uy_Final.append(float(uyfinal))
                Uz_Init.append(float(uzinit))
                Uz_Final.append(float(uzfinal))
                if track_h and len(line) > 5:
                    [hinit, hfinal] = line[ind_h+1:ind_h+3]
                else:
                    hinit = hfinal = 0
                h_Init.append(float(hinit))
                h_Final.append(float(hfinal))

    legend = []
    if track_U:
        legend.extend(['Ux_Init', 'Ux_Final', 'Uy_Init', 'Uy_Final', 'Uz_Init',
                       'Uz_Final'])
    if track_h:
        legend.extend(['h_Init', 'h_Final'])
    for value in values:
        plt.plot(value)
    plt.ylabel('Residual')
    plt.xlabel('Iteration')
    plt.legend(legend)
    plt.yscale("log")
    plt.title('Residuals')
    plt.savefig(of_directory / 'Residuals.png')
    # plt.show()


def convergencePlot2(of_directory: str):
    """
    Creates a plot of velocity (U) and temperature (T, directly proportional
    to h) residuals over the simulated iteration steps and detects the
    stabilization point where residuals converge with minimal variations.
    """
    Ux_Init = []
    Ux_Final = []
    Uy_Init = []
    Uy_Final = []
    Uz_Init = []
    Uz_Final = []
    h_Init = []
    h_Final = []
    values = [Ux_Init, Ux_Final, Uy_Init, Uy_Final, Uz_Init, Uz_Final,
              h_Init, h_Final]

    # Collect directories from all simulation phases and sort them
    time_dirs = os.listdir(of_directory / 'postProcessing/solverInfo/')
    time_dirs.sort()
    time_dirs.sort(key=len)  # both sorts needed for correct order

    # Parse residual data
    for timestep in time_dirs:
        with open(of_directory / 'postProcessing/solverInfo/' /
                  timestep / 'solverInfo.dat', 'r') as f:
            lines = f.readlines()
            track_U = track_h = False
            indices = lines[1].split('\t')
            if 'U_solver' in lines[1]:
                track_U = True
                ind_u = indices.index('U_solver         ')
            if 'h_solver' in lines[1]:
                track_h = True
                ind_h = indices.index('h_solver         ')
            for line in lines[2:]:
                line = line.split('\t')
                if track_U and len(line) > 5:
                    [uxinit, uxfinal] = line[ind_u + 1:ind_u + 3]
                    [uyinit, uyfinal] = line[ind_u + 4:ind_u + 6]
                    [uzinit, uzfinal] = line[ind_u + 7:ind_u + 9]
                else:
                    uxinit = uxfinal = uyinit = uyfinal = uzinit = uzfinal = 0
                Ux_Init.append(float(uxinit))
                Ux_Final.append(float(uxfinal))
                Uy_Init.append(float(uyinit))
                Uy_Final.append(float(uyfinal))
                Uz_Init.append(float(uzinit))
                Uz_Final.append(float(uzfinal))
                if track_h and len(line) > 5:
                    [hinit, hfinal] = line[ind_h + 1:ind_h + 3]
                else:
                    hinit = hfinal = 0
                h_Init.append(float(hinit))
                h_Final.append(float(hfinal))

    # Helper functions
    def smooth_data(data, window_size=500):
        """Apply a moving average to smooth out small peaks in the data."""
        return pd.DataFrame(data).rolling(window=window_size,
                                          center=True).median().values

    def find_stabilization_iteration(smoothed_residuals, min_tolerance=1e-6,
                                     stop_tolerance=1e-8,
                                     consecutive=1000):
        """Find the first iteration where residuals stabilize within a given tolerance."""

        curr_abs = 1
        final_iter = None
        for start_iter in range(len(smoothed_residuals) - consecutive):
            if start_iter < 1500:
                continue
            window = smoothed_residuals[start_iter:start_iter + consecutive]
            this_abs = np.abs(np.diff(window, axis=0))
            this_abs = pd.DataFrame(this_abs).median().values
            if this_abs[0] > min_tolerance:
                continue
            if this_abs[0] < curr_abs and this_abs[0] > 0:
                curr_abs = this_abs[0]
                final_iter = start_iter
            if this_abs[0] < stop_tolerance:
                return final_iter
        return final_iter  # If stabilization is not found

    # Apply smoothing and find stabilization points for each residual
    stabilization_points = []
    smoothed_values = [smooth_data(value) for value in values]
    global_max = 0
    for smoothed_value in smoothed_values:
        stabilization_iteration = find_stabilization_iteration(smoothed_value)
        if stabilization_iteration and stabilization_iteration > global_max:
            global_max = stabilization_iteration
        stabilization_points.append(stabilization_iteration)

    # Prepare the legend
    legend = []
    if 'U_solver         ' in indices:  # Check if 'U_solver' is in the data
        legend.extend(['Ux_Init', 'Ux_Final', 'Uy_Init', 'Uy_Final', 'Uz_Init',
                       'Uz_Final'])
    if 'h_solver         ' in indices:  # Check if 'h_solver' is in the data
        legend.extend(['h_Init', 'h_Final'])

    # Check if the number of legend labels matches the number of values
    if len(legend) != len(values):
        print(
            f"Warning: The number of legend labels ({len(legend)}) doesn't match the number of values ({len(values)}).")
        print("Legend and values may not correspond correctly.")
        # Adjust the legend size or values accordingly to match

    # Plotting
    plt.figure(figsize=(10, 6))
    for idx, value in enumerate(values):
        plt.plot(value, label=legend[idx] if idx < len(
            legend) else f"Parameter {idx + 1}")
        if stabilization_points[idx] == global_max:
            plt.axvline(stabilization_points[idx], color='r', linestyle='--')
        if stabilization_points[idx] is not None:
            plt.plot(stabilization_points[idx], value[stabilization_points[
                idx]], 'ro')
            plt.text(stabilization_points[idx], value[stabilization_points[
                idx]], f'(it={stabilization_points[idx]:d},'
                       f' v={value[stabilization_points[idx]]:.2e})',
                     ha='right', va='bottom', color='red', fontsize=10)
    print('global max: ', global_max)

    plt.ylabel('Residual')
    plt.xlabel('Iteration')
    plt.legend(legend)
    plt.yscale("log")
    plt.title('Residuals with Stabilization Points')
    plt.savefig(of_directory / 'Residuals.png')
    plt.show()
    return global_max

def MinMaxPlot(of_directory: str):
    """
    Creates a plot of minimal and maximal values of the velocity's magnitude
    (U) and temperature (T) over the simulated iteration steps.
    """
    T_min = []
    T_max = []
    T_av = []
    U_mag_min = []
    U_mag_max = []
    time_dirs = os.listdir(of_directory / 'postProcessing/MinMax/')
    mean_dirs = os.listdir(of_directory / 'postProcessing/volFieldValue')
    time_dirs.sort()
    time_dirs.sort(key=len)  # yes, these are both necessary
    mean_dirs.sort()
    mean_dirs.sort(key=len)
    for timestep in time_dirs:
        with open(of_directory / 'postProcessing/MinMax' /
                  timestep / 'fieldMinMax.dat', 'r') as f:
            lines = f.readlines()
            for i in range(11, len(lines)):
                line = lines[i].split('\t')
                if len(line) > 5 and 'T' in line[1]:
                    tmin = line[2]
                    tmax = line[5]
                    T_min.append(float(tmin))
                    T_max.append(float(tmax))
                elif len(line) > 5 and 'mag(U)' in line[1]:
                    umin = line[2]
                    umax = line[5]
                    U_mag_min.append(float(umin))
                    U_mag_max.append(float(umax))
    for timestep in mean_dirs:
        with open(of_directory/ 'postProcessing/volFieldValue' /
                  timestep / 'volFieldValue.dat', 'r') as f2:
            lines = f2.readlines()
            for i in range(4, len(lines)):
                line = lines[i].split('\t')
                avT = line[1]
                T_av.append(float(avT))
    plt.plot(T_min, linewidth=0.1)
    plt.plot(T_max, linewidth=0.1)
    plt.plot(T_av, linewidth=0.1)
    plt.text(len(T_av), T_av[-1], f'T_mean_final: {T_av[-1]:.2f} K',
             ha='right', va='bottom', fontsize=12)
    plt.ylabel('T')
    plt.xlabel('Iteration')
    plt.legend(['T_min', 'T_max', 'T_av'])
    plt.title('Temperature min/max/average')
    plt.savefig(of_directory / 'minmaxavT.png')
    plt.show()
    plt.close()

    plt.plot(U_mag_min)
    plt.plot(U_mag_max)
    plt.ylabel('|U|')
    plt.xlabel('Iteration')
    plt.legend(['|U|_min', '|U|_max'])
    plt.title('mag(U) min/max')
    plt.savefig(of_directory / 'minmax_U_.png')
    plt.show()


def analyze_execution_times(of_directory, target_iterations=[1000, 'final']):
    """
    Extracts execution times from an OpenFOAM log file, prints times for specific iterations,
    and plots all execution times over the course of the iterations with target times annotated.

    Parameters:
    - of_directory (str or Path): Directory containing the OpenFOAM log file.
    - target_iterations (list): List of iteration numbers to print and annotate (e.g., [1000, 'final']).
    """
    # Initialize lists to store all iterations and their execution times
    all_iterations = []
    all_execution_times = []

    # Dictionary to store the target iteration times for printing
    target_times = {}
    last_time = None

    # Regular expressions to match lines
    iteration_re = re.compile(r"Time = (\d+)")
    execution_re = re.compile(r"ExecutionTime = ([\d.]+)")

    # Parse the log file
    with open(of_directory / 'log3.compress', 'r') as file:
        current_iteration = None
        iteration_done = True
        for line in file:
            # Match iteration number
            iteration_match = iteration_re.search(line)
            if iteration_match and iteration_done:
                current_iteration = int(iteration_match.group(1))
                iteration_done = False

            # Match execution time if we have an iteration
            execution_match = execution_re.search(line)
            if execution_match and current_iteration is not None:
                execution_time = float(execution_match.group(1))
                last_time = (current_iteration, execution_time)

                # Store all iterations and execution times for plotting
                all_iterations.append(current_iteration)
                all_execution_times.append(execution_time)

                # Store target times for specified iterations
                if current_iteration in target_iterations:
                    target_times[current_iteration] = execution_time
                iteration_done = True

    # Store the last recorded execution time if 'final' is specified in target_iterations
    if 'final' in target_iterations and last_time:
        target_times[last_time[0]] = last_time[1]  # Use the final iteration number as the key

    # Print the execution times for the specified target iterations
    print("Execution times for specified iterations:")
    for iteration, exec_time in target_times.items():
        print(f"Iteration {iteration}: {exec_time} seconds")

    # Plot all execution times over the iterations
    plt.figure(figsize=(10, 6))
    plt.plot(all_iterations, all_execution_times, 'b-', label="Execution Time")
    plt.xlabel("Iteration")
    plt.ylabel("Execution Time (s)")
    plt.title("Execution Time Over Iterations")
    plt.legend()
    plt.grid(True)

    # Annotate target times on the plot
    for iteration, exec_time in target_times.items():
        plt.text(iteration, exec_time, f'{exec_time:.2f}s',
                 ha='right', va='bottom', color='red', fontsize=10)

    # Save the plot
    plt.savefig(of_directory / 'iteration_time.png')

    # plt.show()
    plt.close()
    return plt

def add_simulation_times(fig, of_directory, name='', number=0):
    all_iterations = []
    all_execution_times = []

    # Regular expressions to match lines
    iteration_re = re.compile(r"Time = (\d+)")
    execution_re = re.compile(r"ExecutionTime = ([\d.]+)")

    # Parse the log file
    with open(of_directory / 'log3.compress', 'r') as file:
        current_iteration = None
        iteration_done = True
        for line in file:
            # Match iteration number
            iteration_match = iteration_re.search(line)
            if iteration_match and iteration_done:
                current_iteration = int(iteration_match.group(1))
                iteration_done = False

            # Match execution time if we have an iteration
            execution_match = execution_re.search(line)
            if execution_match and current_iteration is not None:
                execution_time = float(execution_match.group(1))
                last_time = (current_iteration, execution_time)

                # Store all iterations and execution times for plotting
                all_iterations.append(current_iteration)
                all_execution_times.append(execution_time)

                # Store target times for specified iterations
                iteration_done = True

    # Store the last recorded execution time if 'final' is specified in target_iterations

    # Plot all execution times over the iterations
    if not fig:
        fig, ax = plt.subplots(figsize=(9, 6))
        ax.set_xlabel("Iteration")
        ax.set_ylabel("Execution Time (s)")
        ax.set_title("Execution Time Over Iterations")
        ax.grid(True)
    else:
        ax = fig.axes[0]
    this_color = get_next_unused_color(ax)
    ax.plot(all_iterations, all_execution_times, color=this_color,
            label=f"Execution Time {name}")
    # line = ax.lines[0]  # Access the first plotted line
    # line.set_label(f"Execution Time {name}")
    ax.legend(loc='upper right')

    # Annotate target times on the plot
    ax.text(all_iterations[-1], all_execution_times[-1], f'{all_execution_times[-1]:.2f}s',
             ha='right', va='bottom', fontsize=18, color=this_color)
    for item in ([ax.title, ax.xaxis.label, ax.yaxis.label] +
                 ax.get_xticklabels() + ax.get_yticklabels() + ax.get_legend().get_texts()):
        item.set_fontsize(14)
    # Save the plot
    fig.savefig(of_directory / f'iteration_time_V{number}.png')

    fig.show()
    return fig

if __name__ == '__main__':
    # this_path = Path(r'C:\Users\richter\sciebo\03-Paperdrafts\00-Promotion\05'
    #                  r'-SIM-Data\02-CFD\diss_fv_100\OpenFOAM')
    # global_conv_iter = convergencePlot2(this_path)
    # MinMaxPlot(this_path)
    # if global_conv_iter:
    #     analyze_execution_times(this_path, target_iterations=[global_conv_iter, 'final'])
    # else:
    #     analyze_execution_times(this_path, target_iterations=[1000, 'final'])
    #
    directory = Path(r'C:\Users\richter\Documents\CFD-Data\PluginTests')
    # Iterate through directories that start with 'diss_'

    fig_temp = None
    counter=0
    for diss_dir in directory.glob('diss_[!noR]*'):
        # Check if "OpenFOAM" subdirectory exists within the current directory
        openfoam_dir = diss_dir / 'OpenFOAM'
        if openfoam_dir.is_dir():
            print(openfoam_dir)
            try:
                global_conv_iter = convergencePlot2(openfoam_dir)
                MinMaxPlot(openfoam_dir)
                if global_conv_iter:
                    analyze_execution_times(openfoam_dir,
                                            target_iterations=[global_conv_iter,
                                                               'final'])
                else:
                    analyze_execution_times(openfoam_dir,
                                            target_iterations=[1000, 'final'])
                fig_temp = add_simulation_times(fig_temp, openfoam_dir,
                                                name=diss_dir.name.replace(
                                                    'diss_', ''),
                                            number=counter)
                plt.close('all')
                counter+=1
            except:
                print(f"failed plot for {diss_dir}")
