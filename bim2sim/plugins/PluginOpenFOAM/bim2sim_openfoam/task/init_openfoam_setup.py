import math
import pathlib
import shutil
from datetime import datetime

import pandas as pd

from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.utils import \
    PostprocessingUtils
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.openfoam_case import \
    OpenFOAMCase
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.utils.openfoam_utils import \
    OpenFOAMUtils
from bim2sim.tasks.base import ITask
from butterfly import fvSolution, fvSchemes, controlDict, \
    decomposeParDict, foamfile, turbulenceProperties, g


class InitializeOpenFOAMSetup(ITask):
    """This ITask initializes the OpenFOAM Setup.
    """

    reads = ()
    touches = ('openfoam_case',)

    single_use = False

    def __init__(self, playground):
        super().__init__(playground)

    def run(self):
        openfoam_case = OpenFOAMCase(playground=self.playground)
        self.create_directory(openfoam_case)
        # setup system
        self.create_fvSolution(openfoam_case)
        self.create_fvSchemes(openfoam_case)
        self.create_controlDict(openfoam_case,
                                self.playground.sim_settings.total_iterations)
        self.create_decomposeParDict(openfoam_case)
        # setup constant
        self.create_g(openfoam_case)
        self.create_radiationProperties(openfoam_case)
        self.create_thermophysicalProperties(openfoam_case)
        self.create_turbulenceProperties(openfoam_case)
        self.create_jobscripts(openfoam_case, self.playground.sim_settings)
        self.read_ep_results(openfoam_case,
                             date=self.playground.sim_settings.simulation_date,
                             time=self.playground.sim_settings.simulation_time)
        return openfoam_case,

    def create_directory(self, openfoam_case):
        openfoam_case.default_templates_dir = (
                pathlib.Path(__file__).parent.parent / 'assets' / 'templates')
        openfoam_case.openfoam_dir = self.paths.export / 'OpenFOAM'
        openfoam_case.openfoam_dir.mkdir(exist_ok=True)
        openfoam_case.openfoam_systems_dir = (openfoam_case.openfoam_dir /
                                              'system')
        openfoam_case.openfoam_constant_dir = (openfoam_case.openfoam_dir /
                                               'constant')
        openfoam_case.openfoam_0_dir = openfoam_case.openfoam_dir / '0'
        openfoam_case.openfoam_systems_dir.mkdir(exist_ok=True)
        openfoam_case.openfoam_constant_dir.mkdir(exist_ok=True)
        openfoam_case.openfoam_0_dir.mkdir(exist_ok=True)
        openfoam_case.openfoam_triSurface_dir = (
                openfoam_case.openfoam_constant_dir / 'triSurface')
        openfoam_case.openfoam_triSurface_dir.mkdir(exist_ok=True)

    @staticmethod
    def create_fvSolution(openfoam_case):
        openfoam_case.fvSolution = fvSolution.FvSolution()
        if openfoam_case.transient_simulation:
            # todo: for Final values, fix $U, $... that are currently not
            # recognized (and not imported). Options: (1) add an extended
            # version of fvSolution that does not contain any $... assignments,
            # or (2) modify the foamFile parser (?) to handle $... assignments
            # self.fvSolution = self.fvSolution.from_file(
            #     self.default_templates_dir / 'system' / 'transient'
            #     / 'fvSolution')
            # implemented hotfix: copy file to temp dir.
            shutil.copy2(openfoam_case.default_templates_dir / 'system' /
                         'transient' / 'fvSolution',
                         openfoam_case.openfoam_systems_dir)
            # todo: currently, fvSolution cannot be accessed using butterfly
            openfoam_case.fvSolution = None
        else:
            openfoam_case.fvSolution = openfoam_case.fvSolution.from_file(
                openfoam_case.default_templates_dir / 'system' / 'steadyState'
                / 'fvSolution')
            openfoam_case.fvSolution.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_fvSchemes(openfoam_case):
        openfoam_case.fvSchemes = fvSchemes.FvSchemes()
        if openfoam_case.transient_simulation:
            openfoam_case.fvSchemes = openfoam_case.fvSchemes.from_file(
                openfoam_case.default_templates_dir /
                'system' / 'transient' /
                'fvSchemes')
        else:
            openfoam_case.fvSchemes = openfoam_case.fvSchemes.from_file(
                openfoam_case.default_templates_dir /
                'system' /
                'steadyState' /
                'fvSchemes')
        openfoam_case.fvSchemes.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_controlDict(openfoam_case, total_iterations):
        openfoam_case.controlDict = controlDict.ControlDict()
        if openfoam_case.transient_simulation:
            openfoam_case.controlDict = openfoam_case.controlDict.from_file(
                openfoam_case.default_templates_dir / 'system' / 'transient' /
                'controlDict')
        else:
            openfoam_case.controlDict = openfoam_case.controlDict.from_file(
                openfoam_case.default_templates_dir / 'system' / 'steadyState' /
                'controlDict')
        openfoam_case.controlDict.save(openfoam_case.openfoam_dir)
        openfoam_case.controlDict.endTime = total_iterations

    @staticmethod
    def create_decomposeParDict(openfoam_case):
        openfoam_case.decomposeParDict = decomposeParDict.DecomposeParDict()
        if openfoam_case.transient_simulation:
            openfoam_case.decomposeParDict = (
                openfoam_case.decomposeParDict.from_file(
                    openfoam_case.default_templates_dir / 'system' /
                    'transient' / 'decomposeParDict'))
        else:
            openfoam_case.decomposeParDict = (
                openfoam_case.decomposeParDict.from_file(
                    openfoam_case.default_templates_dir / 'system' /
                    'steadyState' / 'decomposeParDict'))
        prev_procs = openfoam_case.decomposeParDict.get_value_by_parameter(
            'numberOfSubdomains')
        if prev_procs != openfoam_case.n_procs:
            hc1 = openfoam_case.decomposeParDict.get_value_by_parameter(
                'hierarchicalCoeffs')
            distrib = OpenFOAMUtils.split_into_three_factors(
                openfoam_case.n_procs)
            openfoam_case.decomposeParDict.set_value_by_parameter(
                'numberOfSubdomains', str(openfoam_case.n_procs))
            distrib = '(' + str(distrib[0]) + ' ' + str(distrib[1]) + ' ' + \
                      str(distrib[2]) + ')'
            hc1['n'] = distrib
            openfoam_case.decomposeParDict.set_value_by_parameter(
                'hierarchicalCoeffs', hc1)
        openfoam_case.decomposeParDict.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_g(openfoam_case):
        openfoam_case.g = g.G()
        openfoam_case.g = openfoam_case.g.from_file(
            openfoam_case.default_templates_dir / 'constant' / 'g')
        openfoam_case.g.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_radiationProperties(openfoam_case):
        # todo: create radiationProperties module?
        if openfoam_case.radiation_model == 'fvDOM':
            thispath = (openfoam_case.default_templates_dir / 'constant' /
                        'radiation' / 'fvDOM' /
                        'radiationProperties')
        else:  # P1 or preconditioned fvDOM or "noRadiation"
            thispath = (openfoam_case.default_templates_dir / 'constant' /
                        'radiation' / 'P1' /
                        'radiationProperties')
        posixpath = thispath.as_posix()

        openfoam_case.radiationProperties = foamfile.FoamFile.from_file(
            posixpath)
        if openfoam_case.radiation_model == 'none':
            openfoam_case.radiationProperties.set_value_by_parameter(
                'radiationModel', 'none')
            openfoam_case.radiationProperties.set_value_by_parameter(
                'radiation', 'off')
        openfoam_case.radiationProperties.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_thermophysicalProperties(openfoam_case):
        # todo: create thermophysicalProperties module?
        thispath = (openfoam_case.default_templates_dir / 'constant' /
                    'thermophysicalProperties')
        posixpath = thispath.as_posix()

        openfoam_case.thermophysicalProperties = foamfile.FoamFile.from_file(
            posixpath)
        openfoam_case.thermophysicalProperties.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_turbulenceProperties(openfoam_case):
        openfoam_case.turbulenceProperties = (
            turbulenceProperties.TurbulenceProperties())
        openfoam_case.turbulenceProperties = (
            openfoam_case.turbulenceProperties.from_file(
                openfoam_case.default_templates_dir / 'constant' /
                'turbulenceProperties'))
        openfoam_case.turbulenceProperties.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_jobscripts(openfoam_case, simsettings):
        openfoam_case.openfoam_scripts_dir = openfoam_case.openfoam_dir
        openfoam_case.openfoam_scripts_dir.mkdir(exist_ok=True)
        open(openfoam_case.openfoam_dir / 'paraview.foam', 'x')
        script_files = ['fullRun.sh', 'runMeshing.sh', 'runSimulation.sh']
        comp_acct = "" if not simsettings.cluster_compute_account else (
            "#SBATCH --account=" + simsettings.cluster_compute_account)
        of_version = "module load OpenFOAM/v2206"
        if simsettings.set_openfoam_version != "Standard":
            if simsettings.set_openfoam_version == "Modified":
                foam_path = "/work/rwth1588/openfoam-correctedSolar/etc/bashrc"
            elif simsettings.set_openfoam_version == "Custom":
                foam_path = "path/to/your/custom/openfoam/installation"
            else:
                foam_path = simsettings.set_openfoam_version
            of_version = f"source {foam_path}"

        replacements = {"JOBNAME": simsettings.cluster_jobname,
                        "STIME": simsettings.cluster_max_runtime_simulation,
                        "MTIME": simsettings.cluster_max_runtime_meshing,
                        "SET_COMP_ACCOUNT": comp_acct,
                        "LOAD_OPENFOAM_VERSION": of_version,
                        "NNODES": str(math.ceil(
                            openfoam_case.n_procs/simsettings.cluster_cpu_per_node)),
                        "NPROCS": str(openfoam_case.n_procs)}

        open(openfoam_case.openfoam_dir / 'paraview.foam', 'x')
        for script_file in script_files:
            src = openfoam_case.default_templates_dir / 'scripts' / script_file
            with open(src, 'r') as file:
                content = file.read()
            for key, value in replacements.items():
                content = content.replace(key, value)
            dst = openfoam_case.openfoam_scripts_dir / script_file
            with open(dst, 'w') as file:
                file.write(content)

    def read_ep_results(self, openfoam_case, year=1900, date='12/21', time=11):
        try:
            full_results_df = pd.read_csv(
                self.paths.export / 'EnergyPlus' / 'SimResults' /
                self.playground.project.name
                / 'eplusout.csv')
            full_results_df['Date/Time'] = full_results_df['Date/Time'].apply(
                PostprocessingUtils._string_to_datetime)
            full_results_df = full_results_df.set_index('Date/Time')
            target_date = datetime.strptime(f"{year}-{date} {time:02}", "%Y-%m/%d %H")
            if target_date in full_results_df.index:
                openfoam_case.timestep_df = full_results_df.loc[
                    f"{year}-{date} {time:02}:00:00"]
            else:
                self.logger.warning(f"The requested date: {year}-{date} {time:02} "
                                    f"is not available in the eplusout.csv file. "
                                    f"Calculating the closest available timestep "
                                    f"for the selected hour of the day.")
                target_day = pd.to_datetime(target_date).dayofyear
                dates = full_results_df.index
                filtered_dates = dates[dates.hour == time]
                delta = (filtered_dates.dayofyear - target_day) % 366
                min_delta = delta.min()
                new_date = filtered_dates[delta == min_delta]
                openfoam_case.timestep_df = full_results_df.loc[
                    new_date].squeeze(axis=0)
                self.logger.warning(f"The new date is set to {new_date}. This is "
                                    f"the timestep for the OpenFOAM simulation.")
        except FileNotFoundError:
            self.logger.warning("No sim_results found. Boundary conditions "
                                "cannot be generated. ")
