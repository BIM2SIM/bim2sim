from bim2sim.tasks.base import ITask
import sys
import os
import pathlib


class RunOpenFOAMSimulation(ITask):
    """This ITask runs the openfoam simulation on linux systems.
    """

    reads = ('openfoam_case', )
    touches = ()

    def __init__(self, playground):
        super().__init__(playground)

    def run(self, openfoam_case):
        if not self.playground.sim_settings.run_cfd_simulation:
            return 
        
        if not sys.platform == 'linux':
            print('Execution on non-Linux systems is not recommended.')
            return

        of_path = openfoam_case.openfoam_dir
        run = input(
            "Warning: Meshing must be done in advance. \n This will take "
            "a while. Proceed anyways? [Y/n] \n")
        if run == 'Y':
            # Use half of the available processes
            procs = os.cpu_count()
            procs = round(procs / 4) * 2

            # Execution
            cwd = os.getcwd()
            os.chdir(of_path)
            os.system('pwd')
            os.system('decomposePar -force')
            print(
                'Writing buoyantSimpleFoam output to file \'logSimulation\'.')
            os.system('mpiexec -np ' + str(procs) + ' buoyantSimpleFoam '
                                                    '-parallel > logSimulation')
            os.system('reconstructPar -latestTime')
            os.chdir(cwd)
        
