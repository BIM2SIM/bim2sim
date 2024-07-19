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
        # procs = round(procs / 4) * 2
        steady_iterations = self.playground.sim_settings.steady_iterations
        if self.playground.sim_settings.simulation_type == 'combined':
            openfoam_case.controlDict.update_values(
                'startTime', 0)
            openfoam_case.controlDict.update_values(
                'endTime', steady_iterations)
            openfoam_case.controlDict.save(of_path)
        # Execution
        cwd = os.getcwd()
        os.chdir(of_path)
        os.system('pwd')
        os.system('decomposePar -force')
        logger.info(
            'Writing buoyantSimpleFoam output to file \'logSimulation\'.')
        os.system('mpiexec --oversubscribe -np ' + str(procs) + ' buoyantSimpleFoam '
                                                '-parallel > logSimulation')
        if self.playground.sim_settings.simulation_type == 'combined':
            # update control dict for transient simulations
            openfoam_case.controlDict = openfoam_case.controlDict.from_file(
                openfoam_case.default_templates_dir /
                'system' / 'transient' /
                'controlDict')
            openfoam_case.controlDict.update_values(
                'startTime', steady_iterations)
            openfoam_case.controlDict.update_values('endTime',
                                                    steady_iterations + 10)
            openfoam_case.controlDict.save(of_path)
            # update fvSchemes for transient simulation
            openfoam_case.fvSchemes = openfoam_case.fvSchemes.from_file(
                openfoam_case.default_templates_dir /
                'system' / 'transient' /
                'fvSchemes')
            openfoam_case.fvSchemes.save(of_path)
            # update fvSolution for transient simulation
            openfoam_case.fvSolution = openfoam_case.fvSolution.from_file(
                openfoam_case.default_templates_dir /
                'system' / 'transient' /
                'fvSolution')
            openfoam_case.fvSolution.save(of_path)

            logger.info(
                'Writing buoyantPimpleFoam output to file '
                '\'logSimulationPimple\'.')
            os.system('mpiexec --oversubscribe -np ' + str(
                procs) + ' buoyantPimpleFoam '
                         '-parallel > logSimulationPimple')
        os.system('reconstructPar -latestTime')
        os.chdir(cwd)
        
