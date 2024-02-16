import logging
import shutil
import tempfile
from collections import OrderedDict
from pathlib import Path

import pandas as pd
import stl
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from OCC.Core.StlAPI import StlAPI_Writer
from OCC.Core.TopoDS import TopoDS_Compound, TopoDS_Builder
from OCC.Core.gp import gp_Pnt, gp_XYZ
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
        add_floor_heating = False
        self.read_ep_results(add_floor_heating=add_floor_heating)
        # initialize boundary conditions based on surface types and BPS results
        self.init_boundary_conditions()

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
        self.create_triSurface_air()
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
        self.default_templates_dir = \
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

    def create_blockMesh(self, resize_factor=0.1, mesh_size=0.08):
        (min_pt, max_pt) = PyOCCTools.simple_bounding_box(
            self.current_zone.space_shape)
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

        pass

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
                self.heater.solid_name+'_refinement_small':
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
                                'mode':            'uniform',
                                'selectionMode':   'cellZone',
                                'volumeMode':      'absolute',
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
        self.topoSetDict.values.update({');': '//'}) # required to close the
        # round bracket. Replace by better option if you find any.

        self.topoSetDict.save(self.openfoam_dir)



    def create_triSurface_air(self):
        pass

    def update_snappyHexMesh_air(self):
        pass

    def update_boundary_conditions_air(self):
        pass

    def update_boundary_radiation_properties_air(self):
        pass



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
        self.bound_area = bound.bound_area.to(ureg.meter ** 2).m
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
        self.radiation_power = total_heating_power*0.3
        self.convective_power = total_heating_power*0.7
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
        self.refinement_zone_small.append([c-increase_small_refinement for c
                                           in self.porous_media_min_max[0]])
        self.refinement_zone_small.append([c+increase_small_refinement for c
                                           in self.porous_media_min_max[1]])
        self.refinement_zone_large = []
        self.refinement_zone_large.append([c-increase_large_refinement for c in
                                         self.porous_media_min_max[0]])
        self.refinement_zone_large.append([c+increase_large_refinement for c in
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
