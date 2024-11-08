import pathlib
import shutil

from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.openfoam_case import \
    OpenFOAMCase
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.utils.openfoam_utils import \
    OpenFOAMUtils
from bim2sim.tasks.base import ITask
from butterfly.butterfly import fvSolution, fvSchemes, controlDict, \
    decomposeParDict, foamfile, turbulenceProperties, g


class InitializeOpenFOAMSetup(ITask):
    """This ITask initializes the OpenFOAM Setup.
    """

    reads = ()
    touches = ('openfoam_case',)

    def __init__(self, playground):
        super().__init__(playground)

    def run(self):
        openfoam_case = OpenFOAMCase(playground=self.playground)
        self.create_directory(openfoam_case)
        # setup system
        self.create_fvSolution(openfoam_case)
        self.create_fvSchemes(openfoam_case)
        self.create_controlDict(openfoam_case)
        self.create_decomposeParDict(openfoam_case)
        # setup constant
        self.create_g(openfoam_case)
        self.create_radiationProperties(openfoam_case)
        self.create_thermophysicalProperties(openfoam_case)
        self.create_turbulenceProperties(openfoam_case)

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
    def create_controlDict(openfoam_case):
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
        else:  # P1 or preconditioned fvDOM
            thispath = (openfoam_case.default_templates_dir / 'constant' /
                        'radiation' / 'P1' /
                        'radiationProperties')
        posixpath = thispath.as_posix()

        openfoam_case.radiationProperties = foamfile.FoamFile.from_file(
            posixpath)
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
