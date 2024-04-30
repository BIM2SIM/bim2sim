import os
import numpy as np
import matplotlib.pyplot as plt

"""
A collection of post-processing python scripts for plotting different 
parameters from OpenFOAM simulations.
"""


def convergencePlot(of_directory: str):
    """
    Creates a plot of velocity (U) and temperature (T, directly proportional
    to h) residuals over the simulated iteration steps.
    """
    Ux_Init = Ux_Final = []
    Uy_Init = Uy_Final = []
    Uz_Init = Uz_Final = []
    h_Init = h_Final = []
    values = [Ux_Init, Ux_Final, Uy_Init, Uy_Final, Uz_Init, Uz_Final,
              h_Init, h_Final]
    # Collect directories from all simulation phases and sort them in
    # ascending time steps
    time_dirs = os.listdir(of_directory + 'postProcessing/solverInfo/')
    time_dirs.sort()
    time_dirs.sort(key=len)   # yes, these are both necessary
    for timestep in time_dirs:
        with open(of_directory + 'postProcessing/solverInfo/' +
                  timestep + '/solverInfo.dat', 'r') as f:
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
    plt.savefig(of_directory + 'Residuals.png')
    plt.show()


def MinMaxPlot(of_directory: str):
    """
    Creates a plot of minimal and maximal values of the velocity's magnitude
    (U) and temperature (T) over the simulated iteration steps.
    """
    T_min = T_max = []
    U_mag_min = U_mag_max = []
    time_dirs = os.listdir(of_directory + 'postProcessing/MinMax/')
    time_dirs.sort()
    time_dirs.sort(key=len)  # yes, these are both necessary
    for timestep in time_dirs:
        with open(of_directory + 'postProcessing/MinMax/' +
                  timestep + '/fieldMinMax.dat', 'r') as f:
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

    plt.plot(T_min)
    plt.plot(T_max)
    plt.ylabel('T')
    plt.xlabel('Iteration')
    plt.legend(['T_min', 'T_max'])
    plt.title('Temperature min/max')
    plt.savefig(of_directory + 'minmaxT.png')
    plt.show()
    plt.close()

    plt.plot(U_mag_min)
    plt.plot(U_mag_max)
    plt.ylabel('|U|')
    plt.xlabel('Iteration')
    plt.legend(['|U|_min', '|U|_max'])
    plt.title('mag(U) min/max')
    plt.savefig(of_directory + 'minmax|U|.png')
    plt.show()
