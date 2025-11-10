import logging
import shutil

from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.utils.openfoam_utils import \
    OpenFOAMUtils
from bim2sim.tasks.base import ITask
import sys
import os
import pathlib

from butterfly import foamfile

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
        radiation_precondition_time = self.playground.sim_settings.radiation_precondition_time
        if (self.playground.sim_settings.simulation_type == 'combined' or
                self.playground.sim_settings.radiation_model == 'preconditioned_fvDOM'):
            new_end_time = 0
            if self.playground.sim_settings.simulation_type == 'combined':
                new_end_time = steady_iterations
            elif self.playground.sim_settings.radiation_model == 'preconditioned_fvDOM':
                new_end_time = radiation_precondition_time
            openfoam_case.controlDict.update_values({'startTime': 0})
            openfoam_case.controlDict.update_values({
                'endTime': new_end_time})
            write_interval = float(openfoam_case.controlDict.values['writeInterval'])
            if write_interval > (new_end_time/2):
                openfoam_case.controlDict.update_values({'writeInterval':
                                                        new_end_time / 2})
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
        if self.playground.sim_settings.radiation_model == 'preconditioned_fvDOM':
            os.system('reconstructPar -latestTime')
            # add IDefault for transient simulation
            shutil.copy2(openfoam_case.openfoam_0_dir / 'IDefault',
                         openfoam_case.openfoam_dir / str(new_end_time) / 'IDefault')

            openfoam_case.controlDict.update_values({
                'startFrom': 'latestTime'})
            openfoam_case.controlDict.update_values({
                    'startTime': new_end_time})
            openfoam_case.controlDict.update_values({'endTime':
                                                         new_end_time + 5000})
            openfoam_case.controlDict.save(of_path)
            eq = openfoam_case.fvSolution.relaxationFactors.values['equations']
            new_eq = OpenFOAMUtils.duplicate_table_for_restart(eq, new_end_time)
            openfoam_case.fvSolution.relaxationFactors.values['equations'] = \
                (new_eq)
            openfoam_case.fvSolution.save(of_path)

            thispath = (openfoam_case.default_templates_dir / 'constant' /
                        'radiation' / 'fvDOM' /
                        'radiationProperties')
            posixpath = thispath.as_posix()
            openfoam_case.radiationProperties = foamfile.FoamFile.from_file(posixpath)
            openfoam_case.radiationProperties.save(openfoam_case.openfoam_dir)
            os.system('decomposePar -fields')
            logger.info(
                'Writing buoyantSimpleFoam output to file \'logSimulationfvDOM\'.')
            os.system('mpiexec --oversubscribe -np ' + str(procs) + ' buoyantSimpleFoam '
                                                                    '-parallel > logSimulationfvDOM')
        if self.playground.sim_settings.simulation_type == 'combined':
            # update control dict for transient simulations
            openfoam_case.controlDict = openfoam_case.controlDict.from_file(
                openfoam_case.default_templates_dir /
                'system' / 'transient' /
                'controlDict')
            openfoam_case.controlDict.update_values({
                'startFrom': 'latestTime'})
            openfoam_case.controlDict.update_values({
                'startTime': steady_iterations})
            openfoam_case.controlDict.update_values({'endTime':
                                                    steady_iterations + 10})
            # get comfort settings from previous control_dict if applicable:
            if self.playground.sim_settings.add_comfort:
                openfoam_case.controlDict.values['functions'].update(openfoam_case.comfortDict)

            openfoam_case.controlDict.save(of_path)
            # update fvSchemes for transient simulation
            openfoam_case.fvSchemes = openfoam_case.fvSchemes.from_file(
                openfoam_case.default_templates_dir /
                'system' / 'transient' /
                'fvSchemes')
            openfoam_case.fvSchemes.save(of_path)
            # update fvSolution for transient simulation
            shutil.copy2(openfoam_case.default_templates_dir / 'system' /
                         'transient' / 'fvSolution',
                         openfoam_case.openfoam_systems_dir)
            # todo: currently, fvSolution cannot be accessed using butterfly
            openfoam_case.fvSolution = None
            logger.info(
                'Writing buoyantPimpleFoam output to file '
                '\'logSimulationPimple\'.')
            os.system('mpiexec --oversubscribe -np ' + str(
                procs) + ' buoyantPimpleFoam '
                         '-parallel > logSimulationPimple')
        os.system('reconstructPar -latestTime')
        os.chdir(cwd)
        
