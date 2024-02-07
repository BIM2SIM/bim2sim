import logging
import shutil
import tempfile
from pathlib import Path

import stl
from OCC.Core.StlAPI import StlAPI_Writer
from stl import mesh

from bim2sim.elements.mapping.units import ureg
from bim2sim.tasks.base import ITask
from bim2sim.utilities.pyocc_tools import PyOCCTools
from butterfly import butterfly
from butterfly.butterfly import fvSolution, case, fvSchemes, controlDict, \
    decomposeParDict, g, foamfile, turbulenceProperties, blockMeshDict


# todo: clone butterfly, fix imports in foamfile (and others?), update to
#  Python3(.10): change d.iteritems() to iter(d.items()). Load all default
#  files (or create from scratch?)


class InitializeOpenFOAMProject(ITask):
    """This ITask initializes the OpenFOAM Project.
    """

    reads = ('elements', 'idf')
    touches = ()

    def __init__(self, playground):
        super().__init__(playground)
        self.turbulenceProperties = None
        self.radiationProperties = None
        self.thermophysicalProperties = None
        self.decomposeParDict = None
        self.controlDict = None
        self.fvSchemes = None
        self.fvSolution = None
        self.openfoam_0_dir = None
        self.openfoam_constant_dir = None
        self.openfoam_triSurface_dir = None
        self.openfoam_systems_dir = None
        self.openfoam_dir = None
        self.default_templates_dir = None
        self.stl_bounds = None
        self.current_bounds = None
        self.current_zone = None

    def run(self, elements, idf):
        """
        This ITask runs the OpenFOAM initialization.

        Args:
            elements:
            idf:

        Returns:

        """
        # self.this_case = case.Case()
        self.stl_bounds = []
        self.init_zone(elements, idf)
        self.create_directory()
        self.create_fvSolution()
        self.create_fvSchemes()
        self.create_controlDict()
        self.create_decomposeParDict()
        self.create_g()
        self.create_radiationProperties()
        self.create_thermophysicalProperties()
        self.create_turbulenceProperties()
        self.create_triSurface()
        self.create_blockMesh()
        # self.create_case()

    def init_zone(self, elements, idf, space_guid='2RSCzLOBz4FAK$_wE8VckM'):
        # guid '2RSCzLOBz4FAK$_wE8VckM' Single office has no 2B bounds
        # guid '3$f2p7VyLB7eox67SA_zKE' Traffic area has 2B bounds
        # this_zone = elements['3$f2p7VyLB7eox67SA_zKE']

        self.current_zone = elements[space_guid]
        self.current_bounds = self.current_zone.space_boundaries
        if hasattr(self.current_zone, 'space_boundaries_2B'):
            self.current_bounds += self.current_zone.space_boundaries_2B
        for bound in self.current_bounds:
            self.stl_bounds.append(StlBound(bound, idf))

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
        self.openfoam_triSurface_dir = self.openfoam_constant_dir / 'triSurface'
        self.openfoam_triSurface_dir.mkdir(exist_ok=True)

    def create_fvSolution(self):
        self.fvSolution = fvSolution.FvSolution()
        self.fvSolution = self.fvSolution.from_file(
            self.default_templates_dir / 'system' / 'fvSolution')
        self.fvSolution.save(self.openfoam_dir)

    def create_fvSchemes(self):
        self.fvSchemes = fvSchemes.FvSchemes()
        self.fvSchemes = self.fvSchemes.from_file(self.default_templates_dir /
                                                  'system' / 'fvSchemes')
        self.fvSchemes.save(self.openfoam_dir)

    def create_controlDict(self):
        self.controlDict = controlDict.ControlDict()
        self.controlDict = self.controlDict.from_file(
            self.default_templates_dir / 'system' / 'controlDict')
        self.controlDict.save(self.openfoam_dir)

    def create_decomposeParDict(self):
        self.decomposeParDict = decomposeParDict.DecomposeParDict()
        self.decomposeParDict = self.decomposeParDict.from_file(
            self.default_templates_dir / 'system' / 'decomposeParDict')
        self.decomposeParDict.save(self.openfoam_dir)

    def create_g(self):
        self.g = g.G()
        self.g = self.g.from_file(
            self.default_templates_dir / 'constant' / 'g')
        self.g.save(self.openfoam_dir)

    def create_radiationProperties(self):
        #todo: create radiationProperties module?
        thispath = (self.default_templates_dir / 'constant' /
                    'radiationProperties')
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

    def create_triSurface(self):
        temp_stl_path = Path(
            tempfile.TemporaryDirectory(
                prefix='bim2sim_temp_stl_files_').name)
        temp_stl_path.mkdir(exist_ok=True)
        with (open(self.openfoam_triSurface_dir /
                  str("space_" + self.current_zone.guid + ".stl"),
                  'wb+') as output_file):
            for stl_bound in self.stl_bounds:
                stl_path_name = temp_stl_path.as_posix() + '/' + \
                    stl_bound.solid_name + '.stl'
                stl_writer = StlAPI_Writer()
                stl_writer.SetASCIIMode(True)
                stl_writer.Write(stl_bound.tri_geom, stl_path_name)
                sb_mesh = mesh.Mesh.from_file(stl_path_name)
                sb_mesh.save(stl_bound.solid_name, output_file,
                             mode=stl.Mode.ASCII)
        output_file.close()
        if temp_stl_path.exists() and temp_stl_path.is_dir():
            shutil.rmtree(temp_stl_path)

    def create_blockMesh(self, resize_factor=0.1, mesh_size=0.08):
        (min_pt, max_pt) = PyOCCTools.simple_bounding_box(
            self.current_zone.space_shape)
        scaled_min_pt = []
        scaled_max_pt = []
        len_xyz = []
        for p1, p2 in zip(min_pt, max_pt):
            p1 -= resize_factor
            p2 += resize_factor
            len_xyz.append(p2-p1)
            scaled_min_pt.append(p1)
            scaled_max_pt.append(p2)

        # calculate number of cells per xyz direction
        n_div_xyz = (round(len_xyz[0]/mesh_size),
                     round(len_xyz[1]/mesh_size),
                     round(len_xyz[2]/mesh_size))
        self.blockMeshDict = blockMeshDict.BlockMeshDict.from_min_max(
            scaled_min_pt, scaled_max_pt, n_div_xyz=n_div_xyz)

        pass



class StlBound:
    def __init__(self, bound, idf):
        self.bound = bound
        self.guid = bound.guid
        self.bound_element_type = bound.bound_element.__class__.__name__
        self.solid_name = self.bound_element_type + '_' + bound.guid.replace(
            '$', '___')
        if not hasattr(bound, 'cfd_face'):
            bound.cfd_face = bound.bound_shape
        opening_shapes = []
        if bound.opening_bounds:
            opening_shapes = [s.bound_shape for s in bound.opening_bounds]
        self.tri_geom = PyOCCTools.triangulate_bound_shape(bound.cfd_face,
                                                           opening_shapes)
        self.temperature = 293.15
        self.heat_flux = 0
        self.bound_area = bound.bound_area.to(ureg.meter**2).m


    def read_ep_results(self):
        pass



