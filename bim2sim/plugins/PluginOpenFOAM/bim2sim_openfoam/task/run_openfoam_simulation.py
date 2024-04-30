import logging
from bim2sim.tasks.base import ITask
import sys
import os
import pathlib

logger = logging.getLogger(__name__)


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
        elif not self.playground.sim_settings.run_meshing:
            logger.warning('Meshing must be done in advance. Simulation '
                           'aborted.')
        
        if not sys.platform == 'linux':
            logger.warning('Execution on non-Linux systems is not '
                           'recommended. Simulation aborted.')
            return

        of_path = openfoam_case.openfoam_dir
        logger.warning("Simulation in progress. This will take "
                       "a while.")
        # Use half of the available processes
        procs = os.cpu_count()
        procs = round(procs / 4) * 2

        # Execution
        cwd = os.getcwd()
        os.chdir(of_path)
        os.system('pwd')
        os.system('decomposePar -force')
        logger.info(
            'Writing buoyantSimpleFoam output to file \'logSimulation\'.')
        os.system('mpiexec -np ' + str(procs) + ' buoyantSimpleFoam '
                                                '-parallel > logSimulation')
        os.system('reconstructPar -latestTime')
        os.chdir(cwd)
        
