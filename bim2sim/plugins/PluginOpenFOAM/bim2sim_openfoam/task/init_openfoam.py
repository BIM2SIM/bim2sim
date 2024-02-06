import logging
from pathlib import Path

from bim2sim.tasks.base import ITask
from butterfly import butterfly
from butterfly.butterfly import fvSolution, case, fvSchemes, controlDict, \
    decomposeParDict, g, foamfile, turbulenceProperties


# todo: clone butterfly, fix imports in foamfile (and others?), update to
#  Python3(.10): change d.iteritems() to iter(d.items()). Load all default
#  files (or create from scratch?)


class InitializeOpenFOAMProject(ITask):
    """This ITask initializes the OpenFOAM Project.
    """

    reads = ('elements', 'idf')
    touches = ()

    def run(self, elements, idf):
        """
        This ITask runs the OpenFOAM initialization.

        Args:
            elements:
            idf:

        Returns:

        """
        # self.this_case = case.Case()
        self.create_directory()
        self.create_fvSolution()
        self.create_fvSchemes()
        self.create_controlDict()
        self.create_decomposeParDict()
        self.create_g()
        self.create_radiationProperties()
        self.create_thermophysicalProperties()
        self.create_turbulenceProperties()
        print('setup done!')
        # self.create_case()

    def create_directory(self):
        self.default_templates_dir =\
            Path(r'C:\Users\richter\Documents\CFD-Data\PluginTests\input')
        self.openfoam_dir = self.paths.export / 'OpenFOAM'
        self.openfoam_dir.mkdir(exist_ok=True)
        self.openfoam_systems_dir = self.openfoam_dir / 'system'
        self.openfoam_constant_dir = self.openfoam_dir / 'constant'
        self.openfoam_0_dir = self.openfoam_dir / '0'
        self.openfoam_systems_dir.mkdir(exist_ok=True)
        self.openfoam_constant_dir.mkdir(exist_ok=True)
        self.openfoam_0_dir.mkdir(exist_ok=True)

    def create_fvSolution(self):
        self.fvSolution = fvSolution.FvSolution()
        self.fvSolution = self.fvSolution.from_file(self.default_templates_dir / 'system' /
                                  'fvSolution')
        self.fvSolution.save(self.openfoam_dir)

    def create_fvSchemes(self):
        self.fvSchemes = fvSchemes.FvSchemes()
        self.fvSchemes = self.fvSchemes.from_file(self.default_templates_dir / 'system' /
                                  'fvSchemes')
        self.fvSchemes.save(self.openfoam_dir)

    def create_controlDict(self):
        self.controlDict = controlDict.ControlDict()
        self.controlDict = self.controlDict.from_file(self.default_templates_dir / 'system' /
                                  'controlDict')
        self.controlDict.save(self.openfoam_dir)

    def create_decomposeParDict(self):
        self.decomposeParDict = decomposeParDict.DecomposeParDict()
        self.decomposeParDict = self.decomposeParDict.from_file(
            self.default_templates_dir / 'system' /
                                  'decomposeParDict')
        self.decomposeParDict.save(self.openfoam_dir)

    def create_g(self):
        self.g = g.G()
        self.g = self.g.from_file(
            self.default_templates_dir / 'constant' / 'g')
        self.g.save(self.openfoam_dir)

    def create_radiationProperties(self):
        #todo: create radiationProperties module?
        thispath = self.default_templates_dir / 'constant' / 'radiationProperties'
        posixpath = thispath.as_posix()

        self.radiationProperties = foamfile.FoamFile.from_file(posixpath)
        self.radiationProperties.save(self.openfoam_dir)

    def create_thermophysicalProperties(self):
        #todo: create thermophysicalProperties module?
        thispath = (self.default_templates_dir / 'constant' /
                    'thermophysicalProperties')
        posixpath = thispath.as_posix()

        self.thermophysicalProperties = foamfile.FoamFile.from_file(posixpath)
        self.thermophysicalProperties.save(self.openfoam_dir)

    def create_turbulenceProperties(self):
        self.turbulenceProperties = turbulenceProperties.TurbulenceProperties()
        self.turbulenceProperties = self.turbulenceProperties.from_file(
            self.default_templates_dir / 'constant' / 'turbulenceProperties')
        self.turbulenceProperties.save(self.openfoam_dir)

    def create_case(self):
        case1 = case.Case.from_folder(
            r'C:\Users\richter\Documents\CFD-Data\PluginTests\input')
        case1.fvSolution.save(
            project_folder=r'C:\Users\richter\Documents\CFD-Data'
                           r'\PluginTests\output')
        case1.decomposeParDict.set_value_by_parameter('numberOfSubdomains', '8')
        hc1 = case1.decomposeParDict.get_value_by_parameter(
            'hierarchicalCoeffs')
        hc1['n'] = '(2 2 2)'
        case1.decomposeParDict.set_value_by_parameter('hierarchicalCoeffs',
                                                      hc1)
        case1.decomposeParDict.save(
            project_folder=r'C:\Users\richter\Documents\CFD-Data'
                           r'\PluginTests\output')
        # fvso1 = fvSolution.FvSolution.from_file(
        #     r'C:\Users\richter\Documents\CFD-Data\PluginTests\input\system'
        #     r'\fvSolution')
        # fvso2 = butterfly.fvSolution.FvSolution()
