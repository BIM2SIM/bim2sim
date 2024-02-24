import logging
import pathlib
import shutil
import tempfile
from collections import OrderedDict
from pathlib import Path

import pandas as pd
import stl
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex, \
    BRepBuilderAPI_Transform
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from OCC.Core.StlAPI import StlAPI_Writer
from OCC.Core.StlAPI import StlAPI_Reader
from OCC.Core.TopoDS import TopoDS_Compound, TopoDS_Builder, TopoDS_Shape
from OCC.Core.gp import gp_Pnt, gp_XYZ, gp_Trsf
from stl import mesh

from bim2sim.elements.mapping.units import ureg
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.utils import \
    PostprocessingUtils
from bim2sim.tasks.base import ITask
from bim2sim.utilities.pyocc_tools import PyOCCTools
from butterfly import butterfly
from butterfly.butterfly import fvSolution, case, fvSchemes, controlDict, \
    decomposeParDict, g, foamfile, turbulenceProperties, blockMeshDict, \
    snappyHexMeshDict, alphat, aoa, g_radiation, idefault, k, nut, omega, p, \
    p_rgh, qr, U, T, boundaryRadiationProperties


# todo: clone butterfly, fix imports in foamfile (and others?), update to
#  Python3(.10): change d.iteritems() to iter(d.items()). Load all default
#  files (or create from scratch?)

def create_stl_from_shape_single_solid_name(triangulated_shape,
                                            stl_file_path_name, solid_name):
    stl_writer = StlAPI_Writer()
    stl_writer.SetASCIIMode(True)
    stl_writer.Write(triangulated_shape, stl_file_path_name)
    sb_mesh = mesh.Mesh.from_file(stl_file_path_name)
    with (open(stl_file_path_name,
               'wb+') as output_file):
        sb_mesh.save(solid_name,
                     output_file,
                     mode=stl.Mode.ASCII)
    output_file.close()


class InitializeOpenFOAMProject(ITask):
    """This ITask initializes the OpenFOAM Project.
    """

    reads = ('elements', 'idf')
    touches = ()

    def __init__(self, playground):
        super().__init__(playground)
        self.topoSetDict = None
        self.heater = None
        self.refinementSurfaces = None
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
        self.default_surface_names = ['Back', 'Bottom', 'Front', 'Top', 'Left',
                                      'Right']
        self.inlet_names = None
        self.outlet_names = None
        self.radiator_names = None
        self.porous_media_names = None
        self.inlet_outlet_boxes_names = None

    def run(self, elements, idf):
        """
        This ITask runs the OpenFOAM initialization.

        Args:
            elements:
            idf:

        Returns:

        """
        self.transient_simulation = False  # todo: set as simsetting
        # self.this_case = case.Case()
        self.stl_bounds = []
        self.init_zone(elements, idf)
        self.create_directory()
        # setup system
        self.create_fvSolution()
        self.create_fvSchemes()
        self.create_controlDict()
        self.create_decomposeParDict()
        # setup constant
        self.create_g()
        self.create_radiationProperties()
        self.create_thermophysicalProperties()
        self.create_turbulenceProperties()
        self.create_boundaryRadiationProperties()
        # setup geometry for constant
        self.create_triSurface()
        # create blockMesh based on surface geometry
        self.create_blockMesh()
        # create snappyHexMesh based on surface types
        self.create_snappyHexMesh()
        # read BPS results from PluginEnergyPlus
        add_floor_heating = False  # todo: set as simsetting
        self.read_ep_results(add_floor_heating=add_floor_heating)
        # initialize boundary conditions based on surface types and BPS results
        self.init_boundary_conditions()

        if not add_floor_heating:
            # if no IFC is available for HVAC, create .stl for heating, otherwise
            # use IfcProduct shape for further modifications
            self.init_heater(elements)
            self.update_snappyHexMesh_heating()
            self.update_boundary_conditions_heating()
            self.update_boundary_radiation_properties_heating()
            self.add_fvOptions_for_heating()
            self.add_topoSetDict_for_heating()

        # if no IFC is available for HVAC, create .stl for airterminals, 
        # otherwise use IfcProduct shape for further modifications
        self.init_airterminals(elements)
        self.update_blockMeshDict_air()
        self.update_snappyHexMesh_air()
        self.update_boundary_conditions_air()
        self.update_boundary_radiation_properties_air()

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
        self.default_templates_dir = (
                pathlib.Path(__file__).parent.parent / 'data' / 'templates')
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
        if self.transient_simulation:
            # todo: for Final values, fix $U, $... that are currently not
            # recognized (and not imported),
            # todo: implement hotfix: copy file to temp dir. 
            self.fvSolution = self.fvSolution.from_file(
                self.default_templates_dir / 'system' / 'transient'
                / 'fvSolution')
        else:
            self.fvSolution = self.fvSolution.from_file(
                self.default_templates_dir / 'system' / 'steadyState'
                / 'fvSolution')
        self.fvSolution.save(self.openfoam_dir)

    def create_fvSchemes(self):
        self.fvSchemes = fvSchemes.FvSchemes()
        if self.transient_simulation:
            self.fvSchemes = self.fvSchemes.from_file(self.default_templates_dir /
                                                      'system' / 'transient' /
                                                      'fvSchemes')
        else:
            self.fvSchemes = self.fvSchemes.from_file(self.default_templates_dir /
                                                      'system' /
                                                      'steadyState' /
                                                      'fvSchemes')
        self.fvSchemes.save(self.openfoam_dir)

    def create_controlDict(self):
        self.controlDict = controlDict.ControlDict()
        if self.transient_simulation:
            self.controlDict = self.controlDict.from_file(
                self.default_templates_dir / 'system' / 'transient' /
                'controlDict')
        else:
            self.controlDict = self.controlDict.from_file(
                self.default_templates_dir / 'system' / 'steadyState' /
                'controlDict')
        self.controlDict.save(self.openfoam_dir)

    def create_decomposeParDict(self):
        self.decomposeParDict = decomposeParDict.DecomposeParDict()
        if self.transient_simulation:
            self.decomposeParDict = self.decomposeParDict.from_file(
                self.default_templates_dir / 'system' / 'transient' /
                'decomposeParDict')
        else:
            self.decomposeParDict = self.decomposeParDict.from_file(
                self.default_templates_dir / 'system' / 'steadyState' /
                'decomposeParDict')
        self.decomposeParDict.save(self.openfoam_dir)

    def create_g(self):
        self.g = g.G()
        self.g = self.g.from_file(
            self.default_templates_dir / 'constant' / 'g')
        self.g.save(self.openfoam_dir)

    def create_radiationProperties(self):
        # todo: create radiationProperties module?
        thispath = (self.default_templates_dir / 'constant' /
                    'radiationProperties')
        posixpath = thispath.as_posix()

        self.radiationProperties = foamfile.FoamFile.from_file(posixpath)
        self.radiationProperties.save(self.openfoam_dir)

    def create_thermophysicalProperties(self):
        # todo: create thermophysicalProperties module?
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

    def create_boundaryRadiationProperties(self):
        self.boundaryRadiationProperties = (
            boundaryRadiationProperties.BoundaryRadiationProperties())
        default_name_list = self.default_surface_names  # todo: add others here

        for obj in self.stl_bounds:
            self.boundaryRadiationProperties.values.update(
                {obj.solid_name:
                     {'type': 'lookup',
                      'emissivity': '0.90',
                      'absorptivity': '0.90',
                      'transmissivity': '0'
                      }})
        for name in default_name_list:
            self.boundaryRadiationProperties.values.update(
                {name:
                     {'type': 'lookup',
                      'emissivity': '0.90',
                      'absorptivity': '0.90',
                      'transmissivity': '0'
                      }})
        self.boundaryRadiationProperties.save(self.openfoam_dir)

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

    def create_blockMesh(self, resize_factor=0.1, mesh_size=0.08,
                         shape=None):
        if not shape:
            shape = self.current_zone.space_shape
        (min_pt, max_pt) = PyOCCTools.simple_bounding_box(shape)
        scaled_min_pt = []
        scaled_max_pt = []
        len_xyz = []
        for p1, p2 in zip(min_pt, max_pt):
            p1 -= resize_factor
            p2 += resize_factor
            len_xyz.append(p2 - p1)
            scaled_min_pt.append(p1)
            scaled_max_pt.append(p2)

        # calculate number of cells per xyz direction
        n_div_xyz = (round(len_xyz[0] / mesh_size),
                     round(len_xyz[1] / mesh_size),
                     round(len_xyz[2] / mesh_size))
        self.blockMeshDict = blockMeshDict.BlockMeshDict.from_min_max(
            scaled_min_pt, scaled_max_pt, n_div_xyz=n_div_xyz)
        self.blockMeshDict.save(self.openfoam_dir)

    def create_snappyHexMesh(self):
        stl_name = "space_" + self.current_zone.guid
        region_names = []
        regions = {}
        mesh_objects = mesh.Mesh.from_multi_file(self.openfoam_triSurface_dir /
                                                 str(stl_name + '.stl'),
                                                 mode=stl.Mode.ASCII)
        for obj in mesh_objects:
            region_names.append(str(obj.name, encoding='utf-8'))
        for name in region_names:
            regions.update({name: {'name': name}})
        self.snappyHexMeshDict = snappyHexMeshDict.SnappyHexMeshDict()
        self.snappyHexMeshDict.add_stl_geometry(str("space_" +
                                                    self.current_zone.guid),
                                                regions)

        # self.snappyHexMesh.values['geometry']['regions'].update(regions)
        location_in_mesh = str('(' +
                               str(self.current_zone.space_center.Coord()[
                                       0]) + ' ' +
                               str(self.current_zone.space_center.Coord()[
                                       1]) + ' ' +
                               str(self.current_zone.space_center.Coord()[
                                       2]) + ')'
                               )
        self.snappyHexMeshDict.values['castellatedMeshControls'][
            'locationInMesh'] = location_in_mesh
        self.set_refinementSurfaces(region_names)
        self.snappyHexMeshDict.values['castellatedMeshControls'][
            'refinementSurfaces'].update(self.refinementSurfaces)

        self.snappyHexMeshDict.save(self.openfoam_dir)

    def set_refinementSurfaces(self, region_names,
                               default_refinement_level=[1, 2]):
        stl_name = "space_" + self.current_zone.guid

        refinementSurface_regions = {}

        for obj in self.stl_bounds:
            refinementSurface_regions.update(
                {obj.solid_name:
                    {
                        'level': '({} {})'.format(
                            int(obj.refinement_level[0]),
                            int(obj.refinement_level[1])),
                        'patchInfo':
                            {'type': obj.patch_info_type}}})

        self.refinementSurfaces = {stl_name:
            {
                'level': '({} {})'.format(
                    int(default_refinement_level[0]),
                    int(default_refinement_level[
                            1])),
                'regions': refinementSurface_regions
            }}

    def init_boundary_conditions(self):
        self.create_alphat()
        self.create_AoA()
        self.create_G()
        self.create_IDefault()
        self.create_k()
        self.create_nut()
        self.create_omega()
        self.create_p()
        self.create_p_rgh()
        self.create_qr()
        self.create_T()
        self.create_U()

    def create_alphat(self):
        self.alphat = alphat.Alphat()
        self.alphat.values['boundaryField'] = {}
        self.alphat.values['dimensions'] = '[1 -1 -1 0 0 0 0]'
        default_name_list = self.default_surface_names  # todo: add others here
        for obj in self.stl_bounds:
            self.alphat.values['boundaryField'].update(
                {obj.solid_name:
                     {'type': 'compressible::alphatJayatillekeWallFunction',
                      'Prt': 0.85,
                      'value': 'uniform 0'}})
        for name in default_name_list:
            self.alphat.values['boundaryField'].update(
                {name:
                     {'type': 'compressible::alphatJayatillekeWallFunction',
                      'Prt': 0.85,
                      'value': 'uniform 0'}})
        self.alphat.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'compressible::alphatJayatillekeWallFunction',
                  'Prt': 0.85,
                  'value': 'uniform 0'
                  }
             })

        self.alphat.save(self.openfoam_dir)

    def create_AoA(self):
        self.aoa = aoa.AoA()
        self.aoa.values['boundaryField'] = {}
        default_name_list = self.default_surface_names  # todo: add others here

        for obj in self.stl_bounds:
            self.aoa.values['boundaryField'].update(
                {obj.solid_name:
                     {'type': 'zeroGradient'}})
        for name in default_name_list:
            self.aoa.values['boundaryField'].update(
                {name:
                     {'type': 'zeroGradient'}})
        self.aoa.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'zeroGradient'}
             }
        )
        self.aoa.save(self.openfoam_dir)

    def create_G(self):
        self.g_radiation = g_radiation.G_radiation()
        self.g_radiation.values['boundaryField'] = {}
        default_name_list = self.default_surface_names  # todo: add others here

        for obj in self.stl_bounds:
            self.g_radiation.values['boundaryField'].update(
                {obj.solid_name:
                     {'type': 'MarshakRadiation',
                      'T': 'T',
                      'value': 'uniform 0'}})
        for name in default_name_list:
            self.g_radiation.values['boundaryField'].update(
                {name:
                     {'type': 'MarshakRadiation',
                      'T': 'T',
                      'value': 'uniform 0'}})
        self.g_radiation.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'MarshakRadiation',
                  'T': 'T',
                  'value': 'uniform 0'}})
        self.g_radiation.save(self.openfoam_dir)

    def create_IDefault(self):
        self.idefault = idefault.IDefault()
        self.idefault.values['boundaryField'] = {}
        default_name_list = self.default_surface_names  # todo: add others here

        for obj in self.stl_bounds:
            self.idefault.values['boundaryField'].update(
                {obj.solid_name:
                     {'type': 'greyDiffusiveRadiation',
                      'T': 'T',
                      'value': 'uniform 0'}})
        for name in default_name_list:
            self.idefault.values['boundaryField'].update(
                {name:
                     {'type': 'greyDiffusiveRadiation',
                      'T': 'T',
                      'value': 'uniform 0'}})
        self.idefault.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'greyDiffusiveRadiation',
                  'T': 'T',
                  'value': 'uniform 0'}})
        self.idefault.save(self.openfoam_dir)

    def create_k(self):
        self.k = k.K()
        self.k.values['boundaryField'] = {}
        default_name_list = self.default_surface_names  # todo: add others here

        for obj in self.stl_bounds:
            self.k.values['boundaryField'].update(
                {obj.solid_name:
                     {'type': 'kqRWallFunction',
                      'value': 'uniform 0.1'}})
        for name in default_name_list:
            self.k.values['boundaryField'].update(
                {name:
                     {'type': 'kqRWallFunction',
                      'value': 'uniform 0.1'}})
        self.k.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'kqRWallFunction',
                  'value': 'uniform 0.1'}})
        self.k.save(self.openfoam_dir)

    def create_nut(self):
        self.nut = nut.Nut()
        self.nut.values['boundaryField'] = {}
        default_name_list = self.default_surface_names  # todo: add others here

        for obj in self.stl_bounds:
            self.nut.values['boundaryField'].update(
                {obj.solid_name:
                     {'type': 'nutkWallFunction',
                      'value': 'uniform 0'}})
        for name in default_name_list:
            self.nut.values['boundaryField'].update(
                {name:
                     {'type': 'nutkWallFunction',
                      'value': 'uniform 0'}})
        self.nut.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'nutkWallFunction',
                  'value': 'uniform 0'}})
        self.nut.save(self.openfoam_dir)

    def create_omega(self):
        self.omega = omega.Omega()
        self.omega.values['boundaryField'] = {}
        default_name_list = self.default_surface_names  # todo: add others here

        for obj in self.stl_bounds:
            self.omega.values['boundaryField'].update(
                {obj.solid_name:
                     {'type': 'omegaWallFunction',
                      'value': 'uniform 0.01'}})
        for name in default_name_list:
            self.omega.values['boundaryField'].update(
                {name:
                     {'type': 'omegaWallFunction',
                      'value': 'uniform 0.01'}})
        self.omega.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'omegaWallFunction',
                  'value': 'uniform 0.01'}})
        self.omega.save(self.openfoam_dir)

    def create_p(self):
        self.p = p.P()
        self.p.values['boundaryField'] = {}
        self.p.values['internalField'] = 'uniform 101325'
        self.p.values['dimensions'] = '[1 -1 -2 0 0 0 0]'
        default_name_list = self.default_surface_names  # todo: add others here

        for obj in self.stl_bounds:
            self.p.values['boundaryField'].update(
                {obj.solid_name:
                     {'type': 'calculated',
                      'value': 'uniform 101325'}})
        for name in default_name_list:
            self.p.values['boundaryField'].update(
                {name:
                     {'type': 'calculated',
                      'value': 'uniform 101325'}})
        self.p.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'calculated',
                  'value': 'uniform 101325'}})
        self.p.save(self.openfoam_dir)

    def create_p_rgh(self):
        self.p_rgh = p_rgh.P_rgh()
        self.p_rgh.values['boundaryField'] = {}
        self.p_rgh.values['internalField'] = 'uniform 101325'
        self.p_rgh.values['dimensions'] = '[1 -1 -2 0 0 0 0]'
        default_name_list = self.default_surface_names  # todo: add others here

        for obj in self.stl_bounds:
            self.p_rgh.values['boundaryField'].update(
                {obj.solid_name:
                     {'type': 'fixedFluxPressure',
                      'value': 'uniform 101325'}})
        for name in default_name_list:
            self.p_rgh.values['boundaryField'].update(
                {name:
                     {'type': 'fixedFluxPressure',
                      'value': 'uniform 101325'}})
        self.p_rgh.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'fixedFluxPressure',
                  'value': 'uniform 101325'}})
        self.p_rgh.save(self.openfoam_dir)

    def create_qr(self):
        self.qr = qr.Qr()
        self.qr.values['boundaryField'] = {}
        default_name_list = self.default_surface_names  # todo: add others here

        self.qr.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'calculated',
                  'value': 'uniform 0'}})
        self.qr.save(self.openfoam_dir)

    def create_T(self):
        self.T = T.T()
        self.T.values['boundaryField'] = {}
        self.T.values['internalField'] = 'uniform 293.15'
        default_name_list = self.default_surface_names  # todo: add others here

        for obj in self.stl_bounds:
            self.T.values['boundaryField'].update(
                {obj.solid_name:
                     {'type': 'externalWallHeatFluxTemperature',
                      'mode': 'flux',
                      'qr': 'qr',
                      'q': f'uniform {obj.surf_heat_cond}',
                      'qrRelaxation': 0.003,
                      'relaxation': 1.0,
                      'kappaMethod': 'fluidThermo',
                      'kappa': 'fluidThermo',
                      'value': f'uniform {obj.surf_temp + 273.15}'}})
        # for name in default_name_list:
        #     self.T.values['boundaryField'].update(
        #         {name:
        #              {'type': 'externalWallHeatFluxTemperature',
        #               'value': 'uniform 101325'}})

        self.T.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'zeroGradient'}})
        self.T.save(self.openfoam_dir)

        pass

    def create_U(self):
        self.U = U.U()
        self.U.values['boundaryField'] = {}
        default_name_list = self.default_surface_names  # todo: add others here

        self.U.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'fixedValue',
                  'value': 'uniform (0.000 0.000 0.000)'}})
        self.U.save(self.openfoam_dir)

    def read_ep_results(self, default_year=1900, default_date='12/21',
                        default_hour='11', add_floor_heating=False):
        full_results_df = pd.read_csv(
            self.paths.export / 'EnergyPlus' / 'SimResults' /
            self.playground.project.name
            / 'eplusout.csv')  # , index_col='Date/Time')
        # full_results_df.index.str.strip()
        full_results_df['Date/Time'] = full_results_df['Date/Time'].apply(
            PostprocessingUtils._string_to_datetime)
        full_results_df = full_results_df.set_index('Date/Time')
        timestep_df = full_results_df.loc[
            f"{default_year}-{default_date} {default_hour}:00:00"]
        self.current_zone.zone_heat_conduction = 0
        self.current_zone.air_temp = timestep_df[
                                         self.current_zone.guid.upper() +
                                         ':' + ('Zone Mean Air Temperature [C]('
                                                'Hourly)')] + 273.15
        for bound in self.stl_bounds:
            res_key = bound.guid.upper() + ':'
            bound.surf_temp = timestep_df[
                res_key + 'Surface Inside Face Temperature [C](Hourly)']
            if not any(s in bound.bound_element_type for s in ['Window']):
                bound.surf_heat_cond = timestep_df[
                    res_key + ('Surface Inside Face Conduction Heat Transfer '
                               'Rate per Area [W/m2](Hourly)')]
            else:
                bound.surf_heat_cond = (timestep_df[
                                            res_key + (
                                                'Surface Window Net Heat Transfer Rate [W](Hourly)')]
                                        / bound.bound_area)
            self.current_zone.zone_heat_conduction += (
                    bound.bound_area * bound.surf_heat_cond)
        if add_floor_heating:
            for bound in self.stl_bounds:
                # reduce calculated floor heating by floor heat losses
                # self.current_zone.floor_heating_qr = \
                #     (timestep_df[(f"{self.current_zone.guid.upper()} IDEAL LOADS AIR SYSTEM:Zone "
                #  f"Ideal Loads Zone Total Heating Rate [W](Hourly)")] /
                #      self.current_zone.net_area.m)
                if any(s in bound.bound_element_type for s in ['Floor',
                                                               'GroundFloor']):
                    self.current_zone.floor_heating_qr = abs(
                        self.current_zone.zone_heat_conduction / bound.bound_area
                        - bound.surf_heat_cond)
                    bound.surf_temp_org = bound.surf_heat_cond
                    bound.surf_heat_cond_org = bound.surf_heat_cond
                    bound.surf_temp = 30
                    bound.surf_heat_cond = self.current_zone.floor_heating_qr

    def init_heater(self, elements):
        # create Shape for heating in front of window unless space heater is
        # available in ifc.
        heater_window = None
        if 'SpaceHeater' in [name.__class__.__name__ for name in
                             list(elements.values())]:
            # todo: get product shape of space heater
            # identify space heater in current zone (maybe flag is already
            # set from preprocessing in bim2sim
            # get TopoDS_Shape for further preprocessing of the shape.
            pass
        else:
            openings = []
            for obj in self.stl_bounds:
                if obj.bound_element_type == 'Window':
                    openings.append(obj)
            if len(openings) == 1:
                heater_window = openings[0]
            elif len(openings) > 1:
                if self.current_zone.zone_heat_conduction < 2000:
                    heater_window = openings[0]
                else:
                    print('more than one heater required, not implemented. '
                          'Heater may be unreasonably large. ')
                    heater_window = openings[0]

            else:
                print('No window found for positioning of heater.')
                return
        heater_shape = self.get_boundaries_of_heater(heater_window)
        # heater_shape holds side surfaces of space heater.
        self.heater = Heater(heater_shape, self.openfoam_triSurface_dir,
                             abs(self.current_zone.zone_heat_conduction))

        pass

    def get_boundaries_of_heater(self, heater_window, heater_depth=0.08):
        move_reversed_flag = False
        # get upper limit
        window_min_max = PyOCCTools.simple_bounding_box(
            heater_window.bound.bound_shape)
        if isinstance(window_min_max[0], tuple):
            new_list = []
            for pnt in window_min_max:
                new_list.append(gp_Pnt(gp_XYZ(pnt[0], pnt[1], pnt[2])))
            window_min_max = new_list
        heater_upper_limit = window_min_max[0].Z() - 0.05
        heater_lower_limit = PyOCCTools.simple_bounding_box(
            heater_window.bound.parent_bound.bound_shape)[0][2] + 0.12
        heater_min_pre_X = window_min_max[0].X()
        heater_min_pre_Y = window_min_max[0].Y()
        heater_max_pre_X = window_min_max[1].X()
        heater_max_pre_Y = window_min_max[1].Y()
        heater_lower_center_pre_X = heater_window.bound.bound_center.X()
        heater_lower_center_pre_Y = heater_window.bound.bound_center.Y()
        heater_lower_center_Z = (heater_upper_limit -
                                 heater_lower_limit) / 2 + heater_lower_limit

        back_surface_pre = PyOCCTools.make_faces_from_pnts([
            gp_Pnt(heater_min_pre_X, heater_min_pre_Y, heater_lower_limit),
            gp_Pnt(heater_max_pre_X, heater_max_pre_Y, heater_lower_limit),
            gp_Pnt(heater_max_pre_X, heater_max_pre_Y, heater_upper_limit),
            gp_Pnt(heater_min_pre_X, heater_min_pre_Y, heater_upper_limit),
        ]
        )
        distance_pre_moving = (
            BRepExtrema_DistShapeShape(
                back_surface_pre, BRepBuilderAPI_MakeVertex(
                    self.current_zone.space_center).Shape(),
                Extrema_ExtFlag_MIN).Value())
        back_surface_moved = PyOCCTools.move_bound_in_direction_of_normal(
            back_surface_pre, move_dist=0.05)
        distance_post_moving = BRepExtrema_DistShapeShape(
            back_surface_moved, BRepBuilderAPI_MakeVertex(
                self.current_zone.space_center).Shape(),
            Extrema_ExtFlag_MIN).Value()
        if distance_post_moving < distance_pre_moving:
            back_surface = back_surface_moved

        else:
            move_reversed_flag = True
            back_surface = PyOCCTools.move_bound_in_direction_of_normal(
                back_surface_pre, move_dist=0.05, reverse=move_reversed_flag)

        front_surface = PyOCCTools.move_bound_in_direction_of_normal(
            back_surface, move_dist=heater_depth,
            reverse=move_reversed_flag)

        front_surface_min_max = PyOCCTools.simple_bounding_box(front_surface)
        back_surface_min_max = PyOCCTools.simple_bounding_box(back_surface)

        side_surface_left = PyOCCTools.make_faces_from_pnts([
            gp_Pnt(*back_surface_min_max[0]),
            gp_Pnt(*front_surface_min_max[0]),
            gp_Pnt(front_surface_min_max[0][0], front_surface_min_max[0][1],
                   front_surface_min_max[1][2]),
            gp_Pnt(back_surface_min_max[0][0], back_surface_min_max[0][1],
                   back_surface_min_max[1][2])]
        )
        side_surface_right = PyOCCTools.make_faces_from_pnts([

            gp_Pnt(back_surface_min_max[1][0], back_surface_min_max[1][1],
                   back_surface_min_max[0][2]),
            gp_Pnt(front_surface_min_max[1][0], front_surface_min_max[1][1],
                   front_surface_min_max[0][2]),
            gp_Pnt(*front_surface_min_max[1]),
            gp_Pnt(*back_surface_min_max[1])]
        )
        shape_list = [side_surface_left, side_surface_right,
                      front_surface, back_surface]
        heater_shape = TopoDS_Compound()
        builder = TopoDS_Builder()
        builder.MakeCompound(heater_shape)
        for shape in shape_list:
            builder.Add(heater_shape, shape)
        return heater_shape

    def update_snappyHexMesh_heating(self):
        self.snappyHexMeshDict.values['geometry'].update(
            {
                self.heater.stl_name + '.stl':
                    {
                        'type': 'triSurfaceMesh',
                        'name': self.heater.stl_name,
                        'regions':
                            {self.heater.solid_name:
                                {
                                    'name': self.heater.solid_name
                                }
                            }
                    },
                self.heater.porous_media_name:
                    {
                        'type': 'searchableBox',
                        'min': f"({self.heater.porous_media_min_max[0][0]} "
                               f"{self.heater.porous_media_min_max[0][1]} "
                               f"{self.heater.porous_media_min_max[0][2]})",
                        'max': f"({self.heater.porous_media_min_max[1][0]} "
                               f"{self.heater.porous_media_min_max[1][1]} "
                               f"{self.heater.porous_media_min_max[1][2]})",
                    },
                self.heater.solid_name + '_refinement_small':
                    {
                        'type': 'searchableBox',
                        'min': f"({self.heater.refinement_zone_small[0][0]} "
                               f"{self.heater.refinement_zone_small[0][1]} "
                               f"{self.heater.refinement_zone_small[0][2]})",
                        'max': f"({self.heater.refinement_zone_small[1][0]} "
                               f"{self.heater.refinement_zone_small[1][1]} "
                               f"{self.heater.refinement_zone_small[1][2]})",
                    },
                self.heater.solid_name + '_refinement_large':
                    {
                        'type': 'searchableBox',
                        'min': f"({self.heater.refinement_zone_large[0][0]} "
                               f"{self.heater.refinement_zone_large[0][1]} "
                               f"{self.heater.refinement_zone_large[0][2]})",
                        'max': f"({self.heater.refinement_zone_large[1][0]} "
                               f"{self.heater.refinement_zone_large[1][1]} "
                               f"{self.heater.refinement_zone_large[1][2]})",
                    }
            }
        )
        self.snappyHexMeshDict.values['castellatedMeshControls'][
            'refinementSurfaces'].update(
            {
                self.heater.stl_name:
                    {
                        'level': '(1 2)',
                        'regions':
                            {
                                self.heater.solid_name:
                                    {
                                        'level':
                                            f"({self.heater.refinement_level[0]} "
                                            f"{self.heater.refinement_level[1]})",
                                        'patchInfo':
                                            {
                                                'type': self.heater.patch_info_type
                                            }
                                    }
                            }
                    }
            },
        )
        self.snappyHexMeshDict.values['castellatedMeshControls'][
            'refinementRegions'].update(
            {
                self.heater.porous_media_name:
                    {
                        'mode': 'inside',
                        'levels': '((0 2))'
                    },
                self.heater.solid_name + '_refinement_small':
                    {
                        'mode': 'inside',
                        'levels': '((0 2))'
                    },
                self.heater.solid_name + '_refinement_large':
                    {
                        'mode': 'inside',
                        'levels': '((0 1))'
                    }

            }
        )
        self.snappyHexMeshDict.save(self.openfoam_dir)

        pass

    def update_boundary_conditions_heating(self):
        self.qr.values['boundaryField'].update({
            self.heater.porous_media_name:
                {
                    'type': 'fixedValue',
                    'value': f'uniform {self.heater.radiation_power}'
                }
        }
        )
        self.qr.save(self.openfoam_dir)

        self.T.values['boundaryField'].update(
            {self.heater.stl_name:
                 {'type': 'externalWallHeatFluxTemperature',
                  'mode': 'power',
                  'Q': '0',
                  'qr': 'qr',
                  'qrRelaxation': '0.003',
                  'relaxation': '1.0',
                  'kappaMethod': 'fluidThermo',
                  'kappa': 'fluidThermo',
                  'value': f'uniform {self.heater.surf_temp + 273.15}'}})
        self.T.save(self.openfoam_dir)

    def update_boundary_radiation_properties_heating(self):
        self.boundaryRadiationProperties.values.update(
            {self.heater.solid_name:
                 {'type': 'lookup',
                  'emissivity': '0.90',
                  'absorptivity': '0.90',
                  'transmissivity': '0'
                  }
             }

        )
        self.boundaryRadiationProperties.save(self.openfoam_dir)

    def add_fvOptions_for_heating(self):
        self.fvOptions = foamfile.FoamFile(
            name='fvOptions', cls='dictionary', location='system',
            default_values=OrderedDict()
        )
        self.fvOptions.values.update(
            {
                'porousMedia_ScalarSemiImplicitSource':
                    {
                        'type': 'scalarSemiImplicitSource',
                        'scalarSemiImplicitSourceCoeffs':
                            {
                                'mode': 'uniform',
                                'selectionMode': 'cellZone',
                                'volumeMode': 'absolute',
                                'cellZone':
                                    self.heater.porous_media_name,
                                'injectionRateSuSp':
                                    {
                                        'h':
                                            f"({self.heater.convective_power} 0)"
                                    }
                            }
                    }
            }
        )
        self.fvOptions.save(self.openfoam_dir)

    def add_topoSetDict_for_heating(self):
        self.topoSetDict = foamfile.FoamFile(
            name='topoSetDict', cls='dictionary', location='system',
            default_values=OrderedDict()
        )
        self.topoSetDict.values.update(
            {
                'actions (': {
                    'name': self.heater.porous_media_name,
                    'action': 'new',
                    'type': 'cellSet',
                    'source': 'surfaceToCell',
                    'sourceInfo':
                        {
                            'file': fr'"constant/triSurface/'
                                    fr'{self.heater.porous_media_name}.stl"',
                            'useSurfaceOrientation': 'true',
                            'outsidePoints': '((0 0 0))',
                            'includeCut': 'false',
                            'includeInside': 'true',
                            'includeOutside': 'false',
                            'nearDistance': '-1',
                            'curvature': '0',
                        }
                },
            }
        )
        self.topoSetDict.values.update({');': '//'})  # required to close the
        # round bracket. Replace by better option if you find any.

        self.topoSetDict.save(self.openfoam_dir)

    def init_airterminals(self, elements):
        air_terminal_surface = None
        if 'AirTerminal' in [name.__class__.__name__ for name in
                             list(elements.values())]:
            # todo: get product shape of air terminals
            # identify air terminals in current zone (maybe flag is already
            # set from preprocessing in bim2sim
            # get TopoDS_Shape for further preprocessing of the shape.
            pass
        else:
            ceiling_roof = []
            for obj in self.stl_bounds:
                if obj.bound_element_type in ['Ceiling', 'Roof']:
                    ceiling_roof.append(obj)
            if len(ceiling_roof) == 1:
                air_terminal_surface = ceiling_roof[0]
            elif len(ceiling_roof) > 1:
                print('multiple ceilings/roofs detected. Not implemented. '
                      'Merge shapes before proceeding to avoid errors. ')
                air_terminal_surface = ceiling_roof[0]
        # todo: add simsettings for outlet choice!
        self.inlet, self.outlet = self.create_airterminal_shapes(
            air_terminal_surface, set_inlet_diffusor_plate=True,
            set_outlet_diffusor=False,
            set_outlet_diffusor_plate=True, set_inlet_stl_shape=False)

    def create_airterminal_shapes(self, air_terminal_surface,
                                  set_outlet_diffusor=False,
                                  set_inlet_diffusor_plate=False,
                                  set_outlet_diffusor_plate=False,
                                  set_inlet_stl_shape=False):
        surf_min_max = PyOCCTools.simple_bounding_box(
            air_terminal_surface.bound.bound_shape)
        lx = surf_min_max[1][0] - surf_min_max[0][0]
        ly = surf_min_max[1][1] - surf_min_max[0][1]
        if ly > lx:
            div_wall_distance = ly / 4
            half_distance = lx / 2
            inlet_pos = [surf_min_max[0][0] + half_distance, surf_min_max[0][
                1] + div_wall_distance, surf_min_max[0][2] - 0.02]
            outlet_pos = [surf_min_max[0][0] + half_distance, surf_min_max[1][
                1] - div_wall_distance, surf_min_max[1][2] - 0.02]
        else:
            div_wall_distance = lx / 4
            half_distance = ly / 2
            inlet_pos = [surf_min_max[0][0] + div_wall_distance,
                         surf_min_max[0][
                             1] + half_distance, surf_min_max[0][2] - 0.02]
            outlet_pos = [surf_min_max[0][0] + div_wall_distance,
                          surf_min_max[1][
                              1] - half_distance, surf_min_max[1][2] - 0.02]

        # split multifile in single stl files, otherwise air terminal cannot
        # be read properly
        meshes = []
        for m in mesh.Mesh.from_multi_file(
                pathlib.Path(__file__).parent.parent / 'data' / 'geometry' /
                'AirTerminal.stl'):
            meshes.append(m)
            # print(str(m.name, encoding='utf-8'))
        temp_path = self.openfoam_triSurface_dir / 'Temp'
        temp_path.mkdir(exist_ok=True)
        for m in meshes:
            curr_name = temp_path.as_posix() + '/' + str(m.name,
                                                         encoding='utf-8') + '.stl'
            with open(curr_name, 'wb+') as output_file:
                m.save(str(m.name, encoding='utf-8'), output_file,
                       mode=stl.Mode.ASCII)
            output_file.close()
        # read individual files from temp directory.
        diffuser_shape = TopoDS_Shape()
        stl_reader = StlAPI_Reader()
        stl_reader.Read(diffuser_shape,
                        temp_path.as_posix() + '/' + "model_24.stl")
        source_shape = TopoDS_Shape()
        stl_reader = StlAPI_Reader()
        stl_reader.Read(source_shape,
                        temp_path.as_posix() + '/' + "inlet_1.stl")
        air_terminal_box = TopoDS_Shape()
        stl_reader = StlAPI_Reader()
        stl_reader.Read(air_terminal_box,
                        temp_path.as_posix() + '/' + "box_3.stl")

        air_terminal_compound = TopoDS_Compound()
        builder = TopoDS_Builder()
        builder.MakeCompound(air_terminal_compound)
        for shape in [diffuser_shape, source_shape, air_terminal_box]:
            builder.Add(air_terminal_compound, shape)

        compound_bbox = PyOCCTools.simple_bounding_box(air_terminal_compound)
        compound_center = PyOCCTools.get_center_of_shape(
            air_terminal_compound).Coord()
        compound_center_lower = gp_Pnt(compound_center[0], compound_center[1],
                                       compound_bbox[0][2])

        # new compounds
        trsf_inlet = gp_Trsf()
        trsf_inlet.SetTranslation(compound_center_lower, gp_Pnt(*inlet_pos))
        inlet_shape = BRepBuilderAPI_Transform(air_terminal_compound,
                                               trsf_inlet).Shape()
        inlet_diffuser_shape = BRepBuilderAPI_Transform(diffuser_shape,
                                                        trsf_inlet).Shape()
        inlet_source_shape = BRepBuilderAPI_Transform(source_shape,
                                                      trsf_inlet).Shape()
        inlet_box_shape = BRepBuilderAPI_Transform(air_terminal_box,
                                                   trsf_inlet).Shape()
        inlet_shapes = [inlet_diffuser_shape, inlet_source_shape,
                        inlet_box_shape]
        trsf_outlet = gp_Trsf()
        trsf_outlet.SetTranslation(compound_center_lower, gp_Pnt(*outlet_pos))
        outlet_shape = BRepBuilderAPI_Transform(air_terminal_compound,
                                                trsf_outlet).Shape()
        if set_outlet_diffusor:
            outlet_diffuser_shape = BRepBuilderAPI_Transform(diffuser_shape,
                                                            trsf_outlet).Shape()
        else:
            outlet_diffuser_shape = None
        outlet_source_shape = BRepBuilderAPI_Transform(source_shape,
                                                       trsf_outlet).Shape()
        outlet_box_shape = BRepBuilderAPI_Transform(air_terminal_box,
                                                    trsf_outlet).Shape()
        outlet_shapes = [outlet_diffuser_shape, outlet_source_shape,
                         outlet_box_shape]
        outlet_min_max = PyOCCTools.simple_bounding_box(outlet_shape)
        outlet_min_max_box = BRepPrimAPI_MakeBox(gp_Pnt(*outlet_min_max[0]),
                                                 gp_Pnt(
                                                     *outlet_min_max[1]))
        faces = PyOCCTools.get_faces_from_shape(outlet_min_max_box.Shape())
        shell = PyOCCTools.make_shell_from_faces(faces)
        outlet_solid = PyOCCTools.make_solid_from_shell(shell)
        inlet_min_max = PyOCCTools.simple_bounding_box(inlet_shape)
        inlet_min_max_box = BRepPrimAPI_MakeBox(gp_Pnt(*inlet_min_max[0]),
                                                gp_Pnt(
                                                    *inlet_min_max[1]))
        faces = PyOCCTools.get_faces_from_shape(inlet_min_max_box.Shape())
        shell = PyOCCTools.make_shell_from_faces(faces)
        inlet_solid = PyOCCTools.make_solid_from_shell(shell)
        cut_ceiling = PyOCCTools.triangulate_bound_shape(
            air_terminal_surface.bound.bound_shape, [inlet_solid, outlet_solid])
        inlet_shapes.extend([inlet_min_max_box.Shape(), inlet_min_max])
        outlet_shapes.extend([outlet_min_max_box.Shape(), outlet_min_max])

        air_terminal_surface.tri_geom = cut_ceiling
        # export stl geometry of surrounding surfaces again (including cut
        # ceiling)
        self.create_triSurface()
        # create instances of air terminal class and return them?
        inlet = AirTerminal('inlet', inlet_shapes,
                            self.openfoam_triSurface_dir,
                            self.current_zone.air_temp,
                            set_diffuser_plate=set_inlet_diffusor_plate,
                            stl_diffuser_shape=set_inlet_stl_shape)
        outlet = AirTerminal('outlet', outlet_shapes,
                             self.openfoam_triSurface_dir,
                             self.current_zone.air_temp,
                             set_diffuser_plate=set_outlet_diffusor_plate,
                             stl_diffuser_shape=False)
        # export moved inlet and outlet shapes

        return inlet, outlet

    def update_blockMeshDict_air(self):
        new_min_max = PyOCCTools.simple_bounding_box([
            self.current_zone.space_shape, self.inlet.box_min_max_shape,
            self.outlet.box_min_max_shape])
        new_blockmesh_box = BRepPrimAPI_MakeBox(
            gp_Pnt(*new_min_max[0]),
            gp_Pnt(*new_min_max[1])).Shape()

        self.create_blockMesh(shape=new_blockmesh_box)

        pass

    def update_snappyHexMesh_air(self):
        for name in [self.inlet.diffuser_name, self.inlet.source_sink_name,
                     self.inlet.box_name,  self.outlet.diffuser_name,
                     self.outlet.source_sink_name, self.outlet.box_name]:
            if not name:
                continue
            self.snappyHexMeshDict.values['geometry'].update(
                {
                    name + '.stl':
                        {
                            'type': 'triSurfaceMesh',
                            'name': name,
                            'regions':
                                {name:
                                    {
                                        'name': name
                                    }
                                }
                        }
                }
            )
        self.snappyHexMeshDict.values['geometry'].update({

            self.inlet.air_type + '_refinement_small':
                {
                    'type': 'searchableBox',
                    'min': f"({self.inlet.refinement_zone_small[0][0]} "
                           f"{self.inlet.refinement_zone_small[0][1]} "
                           f"{self.inlet.refinement_zone_small[0][2]})",
                    'max': f"({self.inlet.refinement_zone_small[1][0]} "
                           f"{self.inlet.refinement_zone_small[1][1]} "
                           f"{self.inlet.refinement_zone_small[1][2]})",
                },
            self.inlet.air_type + '_refinement_large':
                {
                    'type': 'searchableBox',
                    'min': f"({self.inlet.refinement_zone_large[0][0]} "
                           f"{self.inlet.refinement_zone_large[0][1]} "
                           f"{self.inlet.refinement_zone_large[0][2]})",
                    'max': f"({self.inlet.refinement_zone_large[1][0]} "
                           f"{self.inlet.refinement_zone_large[1][1]} "
                           f"{self.inlet.refinement_zone_large[1][2]})",
                },
            self.outlet.air_type + '_refinement_small':
                {
                    'type': 'searchableBox',
                    'min': f"({self.outlet.refinement_zone_small[0][0]} "
                           f"{self.outlet.refinement_zone_small[0][1]} "
                           f"{self.outlet.refinement_zone_small[0][2]})",
                    'max': f"({self.outlet.refinement_zone_small[1][0]} "
                           f"{self.outlet.refinement_zone_small[1][1]} "
                           f"{self.outlet.refinement_zone_small[1][2]})",
                },
            self.outlet.air_type + '_refinement_large':
                {
                    'type': 'searchableBox',
                    'min': f"({self.outlet.refinement_zone_large[0][0]} "
                           f"{self.outlet.refinement_zone_large[0][1]} "
                           f"{self.outlet.refinement_zone_large[0][2]})",
                    'max': f"({self.outlet.refinement_zone_large[1][0]} "
                           f"{self.outlet.refinement_zone_large[1][1]} "
                           f"{self.outlet.refinement_zone_large[1][2]})",
                }
        }
        )
        for name in [self.inlet.diffuser_name, self.outlet.diffuser_name]:
            if not name:
                continue
            self.snappyHexMeshDict.values['castellatedMeshControls'][
                'refinementSurfaces'].update(
                {name: {'level': f"({self.inlet.diffuser_refinement_level[0]}"
                                 f" {self.inlet.diffuser_refinement_level[1]})",
                        'regions':
                            {name:
                                 {'level':
                                      f"({self.inlet.diffuser_refinement_level[0]}"
                                      f" {self.inlet.diffuser_refinement_level[1]})",
                                  'patchInfo': {'type': 'wall'}}}}
                 },
            )
        for obj in [self.inlet, self.outlet]:
            self.snappyHexMeshDict.values['castellatedMeshControls'][
                'refinementSurfaces'].update(
                {obj.source_sink_name:
                     {'level': '(1 2)', 'regions':
                         {obj.source_sink_name: {'level': '(1 2)',
                                                 'patchInfo': {
                                                     'type': obj.air_type}}}}
                 },
            )
        for name in [self.inlet.box_name, self.outlet.box_name]:
            self.snappyHexMeshDict.values['castellatedMeshControls'][
                'refinementSurfaces'].update(
                {name: {'level': '(2 4)',
                        'regions': {name: {'level': '(2 4)',
                                           'patchInfo': {'type': 'wall'}}}}
                 },
            )
        for name in [self.inlet.air_type + '_refinement_small',
                     self.outlet.air_type + '_refinement_small']:
            self.snappyHexMeshDict.values['castellatedMeshControls'][
                'refinementRegions'].update(
                {name: {'mode': 'inside', 'levels': '((0 4))'}}
            )
        for name in [self.inlet.air_type + '_refinement_large',
                     self.outlet.air_type + '_refinement_large']:
            self.snappyHexMeshDict.values['castellatedMeshControls'][
                'refinementRegions'].update(
                {name: {'mode': 'inside', 'levels': '((0 3))'}}
            )
        self.snappyHexMeshDict.save(self.openfoam_dir)

    def update_boundary_conditions_air(self):
        # update alphat
        keep = None
        if self.alphat.values['boundaryField'].get('".*"'):
            keep = self.alphat.values['boundaryField'].get('".*"')
            self.alphat.values['boundaryField'].pop('".*"')
        self.alphat.values['boundaryField'].update({
            self.inlet.source_sink_name:
                {'type': 'calculated', 'value': 'uniform 0'
                 },
            self.outlet.source_sink_name:
                {'type': 'calculated', 'value': 'uniform 0'
                 },
        })
        if keep:
            self.alphat.values['boundaryField'].update({
                r'".*"': keep
            })
        self.alphat.save(self.openfoam_dir)
        # update AoA
        keep = None
        if self.aoa.values['boundaryField'].get('".*"'):
            keep = self.aoa.values['boundaryField'].get('".*"')
            self.aoa.values['boundaryField'].pop('".*"')
        self.aoa.values['boundaryField'].update({
            self.inlet.source_sink_name:
                {'type': 'fixedValue', 'value': 'uniform 0'
                 },
            self.outlet.source_sink_name:
                {'type': 'inletOutlet',
                 'inletValue': 'uniform 0',
                 'value': 'uniform 0'
                 },
        })
        if keep:
            self.aoa.values['boundaryField'].update({
                r'".*"': keep
            })
        self.aoa.save(self.openfoam_dir)
        # update k
        keep = None
        if self.k.values['boundaryField'].get('".*"'):
            keep = self.k.values['boundaryField'].get('".*"')
            self.k.values['boundaryField'].pop('".*"')
        self.k.values['boundaryField'].update({
            self.inlet.source_sink_name:
                {'type': 'turbulentIntensityKineticEnergyInlet',
                 'intensity': 0.02,
                 'value': 'uniform 1'
                 },
            self.outlet.source_sink_name:
                {'type': 'inletOutlet',
                 'inletValue': 'uniform 0.1',
                 'value': 'uniform 0.1'
                 },
        })
        if keep:
            self.k.values['boundaryField'].update({
                r'".*"': keep
            })
        self.k.save(self.openfoam_dir)
        # update nut
        keep = None
        if self.nut.values['boundaryField'].get('".*"'):
            keep = self.nut.values['boundaryField'].get('".*"')
            self.nut.values['boundaryField'].pop('".*"')
        self.nut.values['boundaryField'].update({
            self.inlet.source_sink_name:
                {'type': 'calculated', 'value': 'uniform 0'
                 },
            self.outlet.source_sink_name:
                {'type': 'calculated', 'value': 'uniform 0'
                 },
        })
        if keep:
            self.nut.values['boundaryField'].update({
                r'".*"': keep
            })
        self.nut.save(self.openfoam_dir)
        # update omega
        keep = None
        if self.omega.values['boundaryField'].get('".*"'):
            keep = self.omega.values['boundaryField'].get('".*"')
            self.omega.values['boundaryField'].pop('".*"')
        self.omega.values['boundaryField'].update({
            self.inlet.source_sink_name:
                {'type': 'turbulentMixingLengthFrequencyInlet',
                 'mixingLength': 0.1,
                 'k': 'k',
                 'value': 'uniform 0.01'
                 },
            self.outlet.source_sink_name:
                {'type': 'inletOutlet',
                 'inletValue': 'uniform 0.01',
                 'value': 'uniform 0.01'
                 },
        })
        if keep:
            self.omega.values['boundaryField'].update({
                r'".*"': keep
            })
        self.omega.save(self.openfoam_dir)
        # update p_rgh
        keep = None
        if self.p_rgh.values['boundaryField'].get('".*"'):
            keep = self.p_rgh.values['boundaryField'].get('".*"')
            self.p_rgh.values['boundaryField'].pop('".*"')
        self.p_rgh.values['boundaryField'].update({
            self.outlet.source_sink_name:
                {'type': 'fixedValue',
                 'value': 'uniform 101325'
                 },
        })
        if keep:
            self.p_rgh.values['boundaryField'].update({
                r'".*"': keep
            })
        self.p_rgh.save(self.openfoam_dir)
        # update T
        keep = None
        if self.T.values['boundaryField'].get('".*"'):
            keep = self.T.values['boundaryField'].get('".*"')
            self.T.values['boundaryField'].pop('".*"')
        self.T.values['boundaryField'].update(
            {self.inlet.source_sink_name:
                 {'type': 'fixedValue',
                  'value': f'uniform {self.inlet.air_temp}'},
             self.outlet.source_sink_name:
                 {'type': 'inletOutlet',
                  'inletValue': f'uniform {self.outlet.air_temp}',
                  'value': f'uniform {self.outlet.air_temp}'}})
        if keep:
            self.T.values['boundaryField'].update({
                r'".*"': keep
            })
        self.T.save(self.openfoam_dir)
        # update U
        keep = None
        if self.U.values['boundaryField'].get('".*"'):
            keep = self.U.values['boundaryField'].get('".*"')
            self.U.values['boundaryField'].pop('".*"')
        self.U.values['boundaryField'].update({
            self.inlet.source_sink_name:
                {'type': 'flowRateInletVelocity',
                 'flowRate': 'volumetricFlowRate',
                 'volumetricFlowRate': f'constant {self.inlet.volumetric_flow}',
                 'value': 'uniform (0.000 0.000 0.000)'
                 },
            self.outlet.source_sink_name:
                {'type': 'inletOutlet',
                 'inletValue': 'uniform (0.000 0.000 0.000)',
                 'value': 'uniform (0.000 0.000 0.000)'
                 },
        }
        )
        if keep:
            self.U.values['boundaryField'].update({
                r'".*"': keep
            })
        self.U.save(self.openfoam_dir)

    def update_boundary_radiation_properties_air(self):
        for name in [self.inlet.diffuser_name, self.inlet.source_sink_name,
                     self.inlet.box_name,  self.outlet.diffuser_name,
                     self.outlet.source_sink_name, self.outlet.box_name]:
            if not name:
                continue
            self.boundaryRadiationProperties.values.update(
                {name:
                     {'type': 'lookup',
                      'emissivity': '0.90',
                      'absorptivity': '0.90',
                      'transmissivity': '0'
                      }
                 }
            )
        self.boundaryRadiationProperties.save(self.openfoam_dir)


class StlBound:
    def __init__(self, bound, idf):
        self.bound = bound
        self.guid = bound.guid
        self.bound_element_type = bound.bound_element.__class__.__name__
        # hotfix for incorrectly assigned floors and roofs in bim2sim elements
        if self.bound_element_type in ['Floor', 'GroundFloor', 'Roof']:
            self.bound_element_type = idf.getobject('BUILDINGSURFACE:DETAILED',
                                                    self.guid.upper()).Surface_Type
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
        self.bound_area = PyOCCTools.get_shape_area(self.tri_geom)
        self.set_default_refinement_level()
        self.set_patch_info_type()

    def set_default_refinement_level(self):
        self.refinement_level = [1, 2]
        if self.bound_element_type in ['OuterWall', 'Window', 'Door',
                                       'Floor', 'Roof', 'GroundFloor',
                                       'OuterDoor', 'Ceiling']:
            self.refinement_level = [2, 3]
        elif self.bound_element_type in ['InnerWall', 'Wall', 'InnerDoor']:
            self.refinement_level = [2, 2]
        else:
            print(f"{self.bound_element_type} bound_element_type is unknown")

    def set_patch_info_type(self):
        # AirTerminal, SpaceHeater
        self.patch_info_type = 'wall'
        if self.bound_element_type == 'SpaceHeater':
            self.patch_info_type = 'wall'
        elif self.bound_element_type == 'AirTerminal':
            # todo: implement distinction for inlet (Zuluft) and outlet (
            #  Abluft), for the surface itself and the surrounding boxes.
            pass
        else:
            pass


class Heater:
    def __init__(self, heater_shape, triSurface_path, total_heating_power,
                 increase_small_refinement=0.05, increase_large_refinement=0.1):
        self.tri_geom = PyOCCTools.triangulate_bound_shape(heater_shape)
        self.radiation_power = total_heating_power * 0.3
        self.convective_power = total_heating_power * 0.7
        self.bound_element_type = 'SpaceHeater'
        self.patch_info_type = 'wall'
        self.solid_name = 'heater'
        self.stl_name = 'Heater'
        self.surf_temp = 50.0
        self.porous_media_name = 'porous_media'
        self.stl_file_path_name = (triSurface_path.as_posix() + '/' +
                                   self.stl_name + '.stl')
        self.refinement_level = [2, 3]
        self.porous_media_file_path = (triSurface_path.as_posix() + '/' +
                                       self.porous_media_name + '.stl')
        self.porous_media_tri_geom, self.porous_media_min_max = (
            self.create_porous_media_tri_geom())
        # todo: change for oriented boxes?
        self.refinement_zone_small = []
        self.refinement_zone_small.append([c - increase_small_refinement for c
                                           in self.porous_media_min_max[0]])
        self.refinement_zone_small.append([c + increase_small_refinement for c
                                           in self.porous_media_min_max[1]])
        self.refinement_zone_large = []
        self.refinement_zone_large.append(
            [c - increase_large_refinement for c in
             self.porous_media_min_max[0]])
        self.refinement_zone_large.append(
            [c + increase_large_refinement for c in
             self.porous_media_min_max[1]])

        # create stl for Heater geometry
        create_stl_from_shape_single_solid_name(self.tri_geom,
                                                self.stl_file_path_name,
                                                self.solid_name)
        create_stl_from_shape_single_solid_name(self.porous_media_tri_geom,
                                                self.porous_media_file_path,
                                                self.porous_media_name)

    def create_porous_media_tri_geom(self):
        # add porous media
        porous_media_geom_min_max = PyOCCTools.simple_bounding_box(
            self.tri_geom)
        porous_media_geom = BRepPrimAPI_MakeBox(
            gp_Pnt(*porous_media_geom_min_max[0]),
            gp_Pnt(*porous_media_geom_min_max[1])).Shape()
        porous_face_list = PyOCCTools.get_faces_from_shape(porous_media_geom)
        porous_shape = TopoDS_Compound()
        builder = TopoDS_Builder()
        builder.MakeCompound(porous_shape)
        for shape in porous_face_list:
            builder.Add(porous_shape, shape)
        porous_media_geom = porous_shape

        porous_media_tri_geom = PyOCCTools.triangulate_bound_shape(
            porous_media_geom)

        return porous_media_tri_geom, porous_media_geom_min_max


class AirTerminal:
    def __init__(self, air_type, inlet_shapes, triSurface_path, air_temp,
                 volumetric_flow=90,
                 increase_small_refinement=0.10,
                 increase_large_refinement=0.20, set_diffuser_plate=True,
                 stl_diffuser_shape=False):
        self.air_type = air_type
        self.diffuser_name = air_type + '_diffuser'
        self.source_sink_name = air_type + '_source_sink'
        self.box_name = air_type + '_box'
        (diffuser_shape, source_sink_shape, box_shape, self.box_min_max_shape,
         self.box_min_max) = inlet_shapes
        if diffuser_shape and stl_diffuser_shape:
            self.tri_geom_diffuser = PyOCCTools.triangulate_bound_shape(
                diffuser_shape)
            self.diffuser_refinement_level = [8, 11]
        elif set_diffuser_plate:
            x1 = self.box_min_max[0][0] - 0.05
            x2 = self.box_min_max[1][0] + 0.05
            y1 = self.box_min_max[0][1] - 0.05
            y2 = self.box_min_max[1][1] + 0.05
            z = self.box_min_max[0][2] - 0.02
            self.tri_geom_diffuser = PyOCCTools.triangulate_bound_shape(
                PyOCCTools.make_faces_from_pnts([
                    gp_Pnt(x1, y1, z),
                    gp_Pnt(x2, y1, z),
                    gp_Pnt(x2, y2, z),
                    gp_Pnt(x1, y2, z)]
                ))
            self.diffuser_refinement_level = [4, 7]
        else:
            self.tri_geom_diffuser = None
            self.diffuser_name = None
        self.tri_geom_source_sink = PyOCCTools.triangulate_bound_shape(
            source_sink_shape)
        self.tri_geom_box = PyOCCTools.triangulate_bound_shape(box_shape)
        self.volumetric_flow = volumetric_flow / 3600  # convert to m3/s

        self.air_temp = air_temp
        # write trinangulated shapes to stl
        if self.tri_geom_diffuser:
            create_stl_from_shape_single_solid_name(self.tri_geom_diffuser,
                                                    triSurface_path.as_posix() + '/'
                                                    + self.diffuser_name +
                                                    '.stl', self.diffuser_name)
        create_stl_from_shape_single_solid_name(self.tri_geom_source_sink,
                                                triSurface_path.as_posix() + '/'
                                                + self.source_sink_name +
                                                '.stl', self.source_sink_name)
        create_stl_from_shape_single_solid_name(self.tri_geom_box,
                                                triSurface_path.as_posix() + '/'
                                                + self.box_name + '.stl',
                                                self.box_name)

        # todo: change for oriented boxes?
        self.refinement_zone_small = []
        self.refinement_zone_small.append([c - increase_small_refinement for c
                                           in self.box_min_max[0]])
        self.refinement_zone_small.append([c + increase_small_refinement for c
                                           in self.box_min_max[1]])
        self.refinement_zone_large = []
        self.refinement_zone_large.append(
            [c - increase_large_refinement for c in
             self.box_min_max[0]])
        self.refinement_zone_large.append(
            [c + increase_large_refinement for c in
             self.box_min_max[1]])
