import math
import pathlib
import random
import shutil
import tempfile
import logging
from pathlib import Path

import numpy as np
import stl
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Common
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex, \
    BRepBuilderAPI_Transform, BRepBuilderAPI_MakeEdge
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.BRepLib import BRepLib_FuseEdges
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from OCC.Core.StlAPI import StlAPI_Writer, StlAPI_Reader
from OCC.Core.TopAbs import TopAbs_SOLID
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopOpeBRep import TopOpeBRep_ShapeIntersector
from OCC.Core.TopoDS import TopoDS_Compound, TopoDS_Builder, TopoDS_Shape
from OCC.Core.gp import gp_Pnt, gp_XYZ, gp_Trsf, gp_Ax1, gp_Dir, gp_Vec
from stl import mesh

from bim2sim.elements.mapping.units import ureg
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.utils.utils_visualization import \
    VisualizationUtils
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.airterminal import \
    AirTerminal
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.furniture import \
    Furniture, Table
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.heater import \
    Heater
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.people import \
    People
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.stlbound import \
    StlBound
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.utils.openfoam_utils \
    import OpenFOAMUtils
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.pyocc_tools import PyOCCTools

logger = logging.getLogger(__name__)


class CreateOpenFOAMGeometry(ITask):
    """This ITask initializes the OpenFOAM Geometry.
    """

    reads = ('openfoam_case', 'elements', 'idf')
    touches = ('openfoam_case', 'openfoam_elements')

    def __init__(self, playground):
        super().__init__(playground)

    def run(self, openfoam_case, elements, idf):
        openfoam_elements = dict()
        self.init_zone(openfoam_case,
                       elements, idf, openfoam_elements,
                       space_guid=self.playground.sim_settings.select_space_guid)
        # todo: add geometry for heater and air terminals
        self.init_heater(openfoam_case, elements, openfoam_elements)
        self.init_airterminals(openfoam_case, elements, openfoam_elements,
                               self.playground.sim_settings.inlet_type,
                               self.playground.sim_settings.outlet_type)
        self.get_base_surface(openfoam_case, openfoam_elements)
        self.init_furniture(openfoam_case, elements, openfoam_elements)
        self.init_people(openfoam_case, elements, openfoam_elements)
        # setup geometry for constant
        self.export_stlbound_triSurface(openfoam_case, openfoam_elements)
        self.export_heater_triSurface(openfoam_elements)
        self.export_airterminal_triSurface(openfoam_elements)
        self.export_furniture_triSurface(openfoam_elements)
        self.export_people_triSurface(openfoam_elements)
        if self.playground.sim_settings.adjust_refinements:
            self.adjust_refinements(openfoam_case, openfoam_elements)

        return openfoam_case, openfoam_elements

    def get_base_surface(self, openfoam_case, openfoam_elements):
        furniture_surface = None
        stl_bounds = filter_elements(openfoam_elements, 'StlBound')
        floor = []
        for bound in stl_bounds:
            if 'floor' in bound.bound_element_type.lower():
                # and bound.bound.top_bottom == 'BOTTOM':
                floor.append(bound)
        if len(floor) == 1:
            furniture_surface = floor[0].tri_geom
        elif len(floor) > 1:
            logger.warning('more than 1 floor surface detected, using largest '
                           'floor surface.')
            fla = 0
            for fl in floor:
                if fl.bound_area > fla:
                    furniture_surface = fl
                    fla = fl.bound_area
            logger.warning(f'Multiple floor surfaces ({len(floor)} detected, '
                           f'largest surface has area = {fla}m2. Merge '
                           f'floor surfaces to prevent errors.')
            fused_floor = PyOCCTools.fuse_shapes([f.tri_geom for f in floor])
            furniture_surface = fused_floor
            logger.warning(f'Merged floor surfaces have a total floor area of '
                        f'{PyOCCTools.get_shape_area(fused_floor)}m2.')
        else:
            raise NotImplementedError('NO FLOOR SURFACE FOUND FOR FURNITURE '
                                      'POSITION.')
        openfoam_case.furniture_surface = furniture_surface

    @staticmethod
    def init_zone(openfoam_case, elements, idf, openfoam_elements,
                  space_guid='2RSCzLOBz4FAK$_wE8VckM'):
        # guid '2RSCzLOBz4FAK$_wE8VckM' Single office has no 2B bounds
        # guid '3$f2p7VyLB7eox67SA_zKE' Traffic area has 2B bounds

        openfoam_case.current_zone = elements[space_guid]
        openfoam_case.floor_area = openfoam_case.current_zone.net_area.m
        openfoam_case.current_bounds = openfoam_case.current_zone.space_boundaries
        if hasattr(openfoam_case.current_zone, 'space_boundaries_2B'):  # todo
            # remove 2b
            openfoam_case.current_bounds += openfoam_case.current_zone.space_boundaries_2B
        for bound in openfoam_case.current_bounds:
            new_stl_bound = StlBound(bound, idf, openfoam_case.radiation_model)
            openfoam_elements[new_stl_bound.solid_name] = new_stl_bound
            # openfoam_case.stl_bounds.append(new_stl_bound)

    def init_heater(self, openfoam_case, elements, openfoam_elements):
        # create Shape for heating in front of window unless space heater is
        # available in ifc.
        if ((self.playground.sim_settings.add_floorheating) and
                (self.playground.sim_settings.add_heating)):
            # floor heating is added in set_boundary_conditions.py if applicable
            return
        elif not self.playground.sim_settings.add_heating:
            return

        heater_window = None
        bim2sim_heaters = filter_elements(elements, 'SpaceHeater')
        heater_shapes = []
        if not hasattr(openfoam_case.current_zone, 'heaters'):
            openfoam_case.current_zone.heaters = []
        if bim2sim_heaters:
            # todo: get product shape of space heater
            # identify space heater in current zone (maybe flag is already
            # set from preprocessing in bim2sim
            # get TopoDS_Shape for further preprocessing of the shape.
            for space_heater in bim2sim_heaters:
                if PyOCCTools.obj2_in_obj1(
                        obj1=openfoam_case.current_zone.space_shape,
                        obj2=space_heater.shape):
                    openfoam_case.current_zone.heaters.append(space_heater)
        if openfoam_case.current_zone.heaters:
            for b2s_heater in openfoam_case.current_zone.heaters:
                # visualization to check if heaters are inside of current
                # space boundaries
                # VisualizationUtils.display_occ_shapes(
                #     [bim2sim_heaters[0].shape,
                #      bim2sim_heaters[1].shape,
                #      *[b.bound_shape for b in
                #        list(openfoam_case.current_bounds)[:-8]]])
                heater_bbox_shape = PyOCCTools.simple_bounding_box(
                    b2s_heater.shape)
                front_surface_min_max = (heater_bbox_shape[0],
                                         (heater_bbox_shape[1][0],
                                          heater_bbox_shape[0][1],
                                          heater_bbox_shape[1][2]))
                front_surface = PyOCCTools.make_faces_from_pnts([
                    gp_Pnt(*front_surface_min_max[0]),
                    gp_Pnt(front_surface_min_max[1][0],
                           front_surface_min_max[0][1],
                           front_surface_min_max[0][2]),
                    gp_Pnt(*front_surface_min_max[1]),
                    gp_Pnt(front_surface_min_max[0][0],
                           front_surface_min_max[0][1],
                           front_surface_min_max[1][2])])
                back_surface_min_max = ((heater_bbox_shape[0][0],
                                         heater_bbox_shape[1][1],
                                         heater_bbox_shape[0][2]),
                                        heater_bbox_shape[1])
                back_surface = PyOCCTools.make_faces_from_pnts([
                    gp_Pnt(*back_surface_min_max[0]),
                    gp_Pnt(back_surface_min_max[1][0],
                           back_surface_min_max[0][1],
                           back_surface_min_max[0][2]),
                    gp_Pnt(*back_surface_min_max[1]),
                    gp_Pnt(back_surface_min_max[0][0],
                           back_surface_min_max[0][1],
                           back_surface_min_max[1][2])])

                side_surface_left = PyOCCTools.make_faces_from_pnts([
                    gp_Pnt(*back_surface_min_max[0]),
                    gp_Pnt(*front_surface_min_max[0]),
                    gp_Pnt(front_surface_min_max[0][0],
                           front_surface_min_max[0][1],
                           front_surface_min_max[1][2]),
                    gp_Pnt(back_surface_min_max[0][0],
                           back_surface_min_max[0][1],
                           back_surface_min_max[1][2])]
                )
                side_surface_right = PyOCCTools.make_faces_from_pnts([

                    gp_Pnt(back_surface_min_max[1][0],
                           back_surface_min_max[1][1],
                           back_surface_min_max[0][2]),
                    gp_Pnt(front_surface_min_max[1][0],
                           front_surface_min_max[1][1],
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
                heater_shapes.append(heater_shape)
        else:
            openings = []
            stl_bounds = filter_elements(openfoam_elements, 'StlBound')
            for obj in stl_bounds:
                if obj.bound_element_type == 'Window':
                    openings.append(obj)
            if len(openings) == 1:
                heater_window = openings[0]
            elif len(openings) > 1:
                if openfoam_case.current_zone.net_area.m < 35:
                    heater_window = openings[0]
                else:
                    logger.warning('more than one heater required, '
                                   'not implemented. '
                                   'Heater may be unreasonably large. ')
                    heater_window = openings[0]

            else:
                logger.warning('No window found for positioning of heater.')
                return
            heater_shape = self.get_boundaries_of_heater(openfoam_case,
                                                         heater_window)
            heater_shapes.append(heater_shape)

        # heater_shape holds side surfaces of space heater.
        for i, shape in enumerate(heater_shapes):
            heater = Heater(f'heater{i}', shape,
                            openfoam_case.openfoam_triSurface_dir,
                            openfoam_case.radiation_model)
            # abs(openfoam_case.current_zone.zone_heat_conduction))
            openfoam_elements[heater.solid_name] = heater

    @staticmethod
    def get_boundaries_of_heater(openfoam_case, heater_window,
                                 heater_depth=0.08):
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
                    openfoam_case.current_zone.space_center).Shape(),
                Extrema_ExtFlag_MIN).Value())
        back_surface_moved = PyOCCTools.move_bound_in_direction_of_normal(
            back_surface_pre, move_dist=0.05)
        distance_post_moving = BRepExtrema_DistShapeShape(
            back_surface_moved, BRepBuilderAPI_MakeVertex(
                openfoam_case.current_zone.space_center).Shape(),
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

    def init_airterminals(self, openfoam_case, elements, openfoam_elements,
                          inlet_type, outlet_type):
        if not self.playground.sim_settings.add_airterminals:
            return
        inlets = []
        outlets = []

        air_terminal_surface = None
        stl_bounds = filter_elements(openfoam_elements, 'StlBound')
        ceiling_roof = []
        for bound in stl_bounds:
            if (bound.bound_element_type in ['Ceiling', 'Roof']):
                # or (
                # bound.bound_element_type in ['Floor', 'InnerFloor']
                # and bound.bound.top_bottom == 'TOP')):
                ceiling_roof.append(bound)
        if len(ceiling_roof) == 1:
            air_terminal_surface = ceiling_roof[0]
        elif len(ceiling_roof) > 1:
            logger.warning('multiple ceilings/roofs detected. Not implemented. '
                           'Merge shapes before proceeding to avoid errors. ')
            air_terminal_surface = ceiling_roof[0]
        bim2sim_airterminals = filter_elements(elements, 'AirTerminal')
        openfoam_case.current_zone.airterminals = []
        if bim2sim_airterminals:
            if not hasattr(openfoam_case.current_zone, 'airterminals'):
                openfoam_case.current_zone.airterminals = []
            for airterminal in bim2sim_airterminals:
                if PyOCCTools.obj2_in_obj1(
                        obj1=openfoam_case.current_zone.space_shape,
                        obj2=airterminal.shape):
                    openfoam_case.current_zone.airterminals.append(airterminal)
        if openfoam_case.current_zone.airterminals:
            air_terminals = openfoam_case.current_zone.airterminals
            # if 'AirTerminal' in [name.__class__.__name__ for name in
            #                      list(elements.values())]:
            #     air_terminals = [a for a in list(elements.values()) if
            #              (a.__class__.__name__ == 'AirTerminal')]
            # todo: get product shape of air terminals
            # identify air terminals in current zone (maybe flag is already
            # set from preprocessing in bim2sim
            # get TopoDS_Shape for further preprocessing of the shape.
            meshes = []
            if inlet_type == 'Original':
                at0 = air_terminals[0]
                # at0_fcs = PyOCCTools.get_faces_from_shape(at0.shape)
                # d = {PyOCCTools.get_center_of_face(f).Coord(): f for f in
                #      at0_fcs}
                # sd = {k: v for k, v in sorted(d.items(), key=lambda x: x[0][2])}
                # low_fc = list(sd.items())[0][1]
                air_terminal_box, shapes, removed = (
                    PyOCCTools.remove_sides_of_bounding_box(
                        at0.shape, cut_top=False, cut_bottom=True,
                        cut_left=False, cut_right=False, cut_back=False,
                        cut_front=False))
                inlet_base_shape = removed[0]
                if 'schlitz' in at0.name.lower():
                    base_min_max = PyOCCTools.get_minimal_bounding_box(
                        inlet_base_shape)
                    x_dist = abs(base_min_max[0][0] - base_min_max[1][0])
                    y_dist = abs(base_min_max[0][1] - base_min_max[1][1])
                    cut_each_side_percent = 0.45
                    if x_dist < y_dist:
                        source_shape = PyOCCTools.make_faces_from_pnts([
                            gp_Pnt(base_min_max[0][0] +
                                   cut_each_side_percent * x_dist,
                                   base_min_max[0][1] + 0.01,
                                   base_min_max[0][2]),
                            gp_Pnt(base_min_max[1][0] -
                                   cut_each_side_percent * x_dist,
                                   base_min_max[0][1] + 0.01,
                                   base_min_max[0][2]),
                            gp_Pnt(base_min_max[1][
                                       0] - cut_each_side_percent * x_dist,
                                   base_min_max[1][1] - 0.01,
                                   base_min_max[1][2]),
                            gp_Pnt(base_min_max[0][0] +
                                   cut_each_side_percent * x_dist,
                                   base_min_max[1][1] - 0.01, base_min_max[1][
                                       2])])
                    else:
                        source_shape = PyOCCTools.make_faces_from_pnts([
                            gp_Pnt(base_min_max[0][0] + 0.01,
                                   base_min_max[0][1] + cut_each_side_percent * y_dist,
                                   base_min_max[0][2]),
                            gp_Pnt(base_min_max[1][0] - 0.01,
                                   base_min_max[0][1] + cut_each_side_percent * y_dist,
                                   base_min_max[0][2]),
                            gp_Pnt(base_min_max[1][0] - 0.01,
                                   base_min_max[1][1] - cut_each_side_percent * y_dist,
                                   base_min_max[1][2]),
                            gp_Pnt(base_min_max[0][0] + 0.01,
                                   base_min_max[1][1] - cut_each_side_percent * y_dist,
                                   base_min_max[1][2])])
                else:
                    source_shape = PyOCCTools.scale_shape(inlet_base_shape, 0.2,
                                                          predefined_center=PyOCCTools.get_center_of_face(
                                                              inlet_base_shape))
                diffuser_shape = PyOCCTools.triangulate_bound_shape(
                    inlet_base_shape, [source_shape])
                if self.playground.sim_settings.outflow_direction == 'side':
                    blend_shape_pnts = PyOCCTools.get_points_of_face(
                        inlet_base_shape)
                    blend_shape_coords = [p.Coord() for p in blend_shape_pnts]
                    new_blend_shape_pnts = [gp_Pnt(x, y, z - 0.01)
                                            for x, y, z in blend_shape_coords]
                    additional_face = PyOCCTools.make_faces_from_pnts(
                        new_blend_shape_pnts)
                    compound = TopoDS_Compound()
                    builder = TopoDS_Builder()
                    builder.MakeCompound(compound)
                    for shp in [diffuser_shape, additional_face]:
                        builder.Add(compound, shp)
                    diffuser_shape = PyOCCTools.triangulate_bound_shape(
                        compound)
                elif (self.playground.sim_settings.outflow_direction ==
                      'angle45down'):
                    base_min_max = PyOCCTools.get_minimal_bounding_box(
                        source_shape)
                    x_dist = abs(base_min_max[0][0] - base_min_max[1][0])
                    y_dist = abs(base_min_max[0][1] - base_min_max[1][1])
                    if y_dist > x_dist:
                        center_line_x1 = gp_Pnt(base_min_max[0][0] + x_dist/2,
                                                base_min_max[0][1],
                                                base_min_max[0][2])
                        center_line_x2 = gp_Pnt(base_min_max[1][0] + x_dist/2,
                                                base_min_max[1][1],
                                                base_min_max[1][2])
                        # todo: add lowered points (decreased z-coord) for
                        #  new tilted face.

            elif inlet_type == 'SimpleStlDiffusor':
                for m in mesh.Mesh.from_multi_file(
                        Path(
                            __file__).parent.parent / 'assets' / 'geometry' /
                        'air' / 'drallauslass_ersatzmodell.stl'):
                    meshes.append(m)
            else:
                for m in mesh.Mesh.from_multi_file(
                        Path(
                            __file__).parent.parent / 'assets' / 'geometry' /
                        'air' / 'AirTerminal.stl'):
                    meshes.append(m)
                    # print(str(m.name, encoding='utf-8'))
            temp_path = openfoam_case.openfoam_triSurface_dir / 'Temp'
            temp_path.mkdir(exist_ok=True)
            for m in meshes:
                curr_name = temp_path.as_posix() + '/' + str(m.name,
                                                             encoding='utf-8') + '.stl'
                with open(curr_name, 'wb+') as output_file:
                    m.save(str(m.name, encoding='utf-8'), output_file,
                           mode=stl.Mode.ASCII)
                output_file.close()
            # read individual files from temp directory.
            if inlet_type == 'Original':
                pass
            elif inlet_type == 'SimpleStlDiffusor':
                diffuser_shape = TopoDS_Shape()
                stl_reader = StlAPI_Reader()
                stl_reader.Read(diffuser_shape,
                                temp_path.as_posix() + '/' + "origin-w_drallauslass.stl")
                source_shape = TopoDS_Shape()
                stl_reader = StlAPI_Reader()
                stl_reader.Read(source_shape,
                                temp_path.as_posix() + '/' + "origin-inlet.stl")
                air_terminal_box = None  # TopoDS_Shape()
                # stl_reader = StlAPI_Reader()
                # stl_reader.Read(air_terminal_box,
                #                 temp_path.as_posix() + '/' + "box_3.stl")
            else:
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
            shapelist = [shp for shp in [diffuser_shape, source_shape,
                                         air_terminal_box] if
                         shp is not None]
            for shp in shapelist:
                builder.Add(air_terminal_compound, shp)
            air_terminal_compound = BRepLib_FuseEdges(
                air_terminal_compound).Shape()
            air_terminal_compound = PyOCCTools.simple_bounding_box_shape(
                air_terminal_compound)

            compound_bbox = PyOCCTools.simple_bounding_box(
                air_terminal_compound)
            compound_center = PyOCCTools.get_center_of_shape(
                air_terminal_compound).Coord()
            compound_center_lower = gp_Pnt(compound_center[0],
                                           compound_center[1],
                                           compound_bbox[0][2])
            for airt in air_terminals:

                airt_center = PyOCCTools.get_center_of_shape(airt.shape).Coord()
                airt_bbox = PyOCCTools.simple_bounding_box(
                    airt.shape)
                airt_center_lower = gp_Pnt(airt_center[0],
                                           airt_center[1],
                                           airt_bbox[0][2]).Coord()
                # new compounds
                if 'zuluft' in airt.name.lower():
                    trsf_inlet = gp_Trsf()
                    trsf_inlet.SetTranslation(compound_center_lower,
                                              gp_Pnt(*airt_center_lower))
                    inlet_shape = BRepBuilderAPI_Transform(
                        air_terminal_compound,
                        trsf_inlet).Shape()
                    inlet_diffuser_shape = None
                    inlet_source_shape = None
                    inlet_box_shape = None
                    if diffuser_shape:
                        inlet_diffuser_shape = BRepBuilderAPI_Transform(
                            diffuser_shape,
                            trsf_inlet).Shape()
                    if source_shape:
                        inlet_source_shape = BRepBuilderAPI_Transform(
                            source_shape,
                            trsf_inlet).Shape()
                    if air_terminal_box:
                        inlet_box_shape = BRepBuilderAPI_Transform(
                            air_terminal_box,
                            trsf_inlet).Shape()
                    inlet_shapes = [inlet_diffuser_shape, inlet_source_shape,
                                    inlet_box_shape]
                    inlet_min_max = PyOCCTools.simple_bounding_box(inlet_shape)
                    inlet_min_max_box = BRepPrimAPI_MakeBox(
                        gp_Pnt(*inlet_min_max[0]),
                        gp_Pnt(
                            *inlet_min_max[1]))
                    faces = PyOCCTools.get_faces_from_shape(
                        inlet_min_max_box.Shape())
                    shell = PyOCCTools.make_shell_from_faces(faces)
                    inlet_solid = PyOCCTools.make_solid_from_shell(shell)
                    inlet_shapes.extend(
                        [inlet_min_max_box.Shape(), inlet_min_max])
                    inlet = AirTerminal(f'inlet_{len(inlets)}', inlet_shapes,
                                        openfoam_case.openfoam_triSurface_dir,
                                        inlet_type)
                    inlet.solid = inlet_solid
                    inlets.append(inlet)
                if 'abluft' in airt.name.lower():
                    trsf_outlet = gp_Trsf()
                    trsf_outlet.SetTranslation(compound_center_lower,
                                               gp_Pnt(*airt_center_lower))
                    outlet_shape = BRepBuilderAPI_Transform(
                        air_terminal_compound,
                        trsf_outlet).Shape()
                    # Todo: remove hardcoded rotations
                    apply_rotation = None
                    box_diff = (abs(PyOCCTools.get_shape_volume(
                        PyOCCTools.simple_bounding_box_shape([
                            outlet_shape, airt.shape])) -
                                    PyOCCTools.get_shape_volume(
                                        outlet_shape)) /
                                PyOCCTools.get_shape_volume(
                                    outlet_shape))
                    if box_diff > 0.4:
                        apply_rotation = True
                    if apply_rotation:
                        outlet_shape = PyOCCTools.rotate_by_deg(outlet_shape,
                                                                axis='z',
                                                                rotation=90
                                                                )
                    outlet_diffuser_shape = None
                    outlet_source_shape = None
                    outlet_box_shape = None
                    if outlet_type != 'None':
                        outlet_diffuser_shape = BRepBuilderAPI_Transform(
                            diffuser_shape,
                            trsf_outlet).Shape()
                        if apply_rotation:
                            outlet_diffuser_shape = PyOCCTools.rotate_by_deg(
                                outlet_diffuser_shape,
                                axis='z',
                                rotation=90)
                    if source_shape:
                        outlet_source_shape = BRepBuilderAPI_Transform(
                            source_shape,
                            trsf_outlet).Shape()
                        if apply_rotation:
                            outlet_source_shape = PyOCCTools.rotate_by_deg(
                                outlet_source_shape,
                                axis='z',
                                rotation=90)

                    if air_terminal_box:
                        outlet_box_shape = BRepBuilderAPI_Transform(
                            air_terminal_box,
                            trsf_outlet).Shape()
                        if apply_rotation:
                            outlet_box_shape = PyOCCTools.rotate_by_deg(
                                outlet_box_shape,
                                axis='z',
                                rotation=90)
                    outlet_shapes = [outlet_diffuser_shape, outlet_source_shape,
                                     outlet_box_shape]
                    outlet_min_max = PyOCCTools.simple_bounding_box(
                        outlet_shape)
                    outlet_min_max_box = BRepPrimAPI_MakeBox(
                        gp_Pnt(*outlet_min_max[0]),
                        gp_Pnt(
                            *outlet_min_max[1]))
                    faces = PyOCCTools.get_faces_from_shape(
                        outlet_min_max_box.Shape())
                    shell = PyOCCTools.make_shell_from_faces(faces)
                    outlet_solid = PyOCCTools.make_solid_from_shell(shell)
                    outlet_shapes.extend(
                        [outlet_min_max_box.Shape(), outlet_min_max])
                    outlet = AirTerminal(f'outlet{len(outlets)}', outlet_shapes,
                                         openfoam_case.openfoam_triSurface_dir,
                                         outlet_type)
                    outlet.solid = outlet_solid
                    outlets.append(outlet)
                cut_ceiling = PyOCCTools.triangulate_bound_shape(
                    air_terminal_surface.bound.bound_shape,
                    [*[inl.solid for inl in inlets],
                     *[out.solid for out in outlets]])

                air_terminal_surface.tri_geom = cut_ceiling
                air_terminal_surface.bound_area = PyOCCTools.get_shape_area(
                    cut_ceiling)
                # export stl geometry of surrounding surfaces again (including cut
                # ceiling)
                # create instances of air terminal class and return them?
            if len(outlets) == 0 or len(inlets) == 0:
                # check for cases with overflow from other spaces
                stl_bounds = filter_elements(openfoam_elements, 'StlBound')
                door_sbs = [sb for sb in stl_bounds
                            if 'door' in sb.bound_element_type.lower()]
                door_outlet_height = 0.02

                if len(inlets) > 0:
                    # define additional outlet below door

                    # case 1 (simplification):
                    # all doors are used as outlets
                    for i, dsb in enumerate(door_sbs):
                        dsb_shape = dsb.tri_geom
                        dsb_min_max = PyOCCTools.get_minimal_bounding_box(
                            dsb_shape)
                        dsb_outlet_cut_shape = PyOCCTools.make_faces_from_pnts([
                            gp_Pnt(*dsb_min_max[0]),
                            gp_Pnt(dsb_min_max[1][0], dsb_min_max[1][1],
                                   dsb_min_max[0][2]),
                            gp_Pnt(dsb_min_max[1][0], dsb_min_max[1][1],
                                   dsb_min_max[0][
                                       2] + door_outlet_height),
                            gp_Pnt(dsb_min_max[0][0], dsb_min_max[0][1],
                                   dsb_min_max[0][
                                       2] + door_outlet_height)])
                        new_door_shape = PyOCCTools.triangulate_bound_shape(
                            dsb_shape, [dsb_outlet_cut_shape])
                        dsb.tri_geom = new_door_shape
                        dsb.bound_area = PyOCCTools.get_shape_area(
                            new_door_shape)
                        outlet_shapes = [None, dsb_outlet_cut_shape, None,
                                         PyOCCTools.simple_bounding_box_shape(
                                             dsb_outlet_cut_shape),
                                         PyOCCTools.get_minimal_bounding_box(
                                             dsb_outlet_cut_shape)]
                        outlet = AirTerminal(f'outlet_overflow_{i}',
                                             outlet_shapes,
                                             openfoam_case.openfoam_triSurface_dir,
                                             inlet_outlet_type='None')
                        outlets.append(outlet)
                        # todo: case 2 (only doors to rooms with outlets are
                        # considered
                        # for overflow)

                if len(outlets) > 0:
                    # define additional inlet at upper part of door
                    for i, dsb in enumerate(door_sbs):
                        dsb_shape = dsb.tri_geom
                        dsb_min_max = PyOCCTools.get_minimal_bounding_box(
                            dsb_shape)
                        dsb_inlet_cut_shape = PyOCCTools.make_faces_from_pnts([
                            gp_Pnt(dsb_min_max[0][0], dsb_min_max[0][1],
                                   dsb_min_max[1][2] - door_outlet_height),
                            gp_Pnt(dsb_min_max[1][0], dsb_min_max[1][1],
                                   dsb_min_max[1][2] - door_outlet_height),
                            gp_Pnt(*dsb_min_max[1]),
                            gp_Pnt(dsb_min_max[0][0], dsb_min_max[0][1],
                                   dsb_min_max[1][2])])
                        new_door_shape = PyOCCTools.triangulate_bound_shape(
                            dsb_shape, [dsb_inlet_cut_shape])
                        dsb.tri_geom = new_door_shape
                        dsb.bound_area = PyOCCTools.get_shape_area(
                            new_door_shape)
                        inlet_shapes = [None, dsb_inlet_cut_shape, None,
                                        PyOCCTools.simple_bounding_box_shape(
                                            dsb_inlet_cut_shape),
                                        PyOCCTools.get_minimal_bounding_box(
                                            dsb_inlet_cut_shape)]
                        inlet = AirTerminal(f'inlet_overflow_{i}',
                                            inlet_shapes,
                                            openfoam_case.openfoam_triSurface_dir,
                                            inlet_outlet_type='None')
                        inlets.append(inlet)
        else:
            ceiling_roof = []
            for bound in stl_bounds:
                if (bound.bound_element_type in ['Ceiling', 'Roof']):
                    # or (
                    # bound.bound_element_type in ['Floor', 'InnerFloor']
                    # and bound.bound.top_bottom == 'TOP')):
                    ceiling_roof.append(bound)
            if len(ceiling_roof) == 1:
                air_terminal_surface = ceiling_roof[0]
            elif len(ceiling_roof) > 1:
                logger.warning(
                    'multiple ceilings/roofs detected. Not implemented. '
                    'Merge shapes before proceeding to avoid errors. ')
                air_terminal_surface = ceiling_roof[0]
            # todo: add simsettings for outlet choice!
            inlet, outlet = self.create_airterminal_shapes(
                openfoam_case,
                air_terminal_surface,
                inlet_type, outlet_type)
            inlets.append(inlet)
            outlets.append(outlet)
        for inlet in inlets:
            openfoam_elements[inlet.solid_name] = inlet
        for outlet in outlets:
            openfoam_elements[outlet.solid_name] = outlet

    def create_airterminal_shapes(self, openfoam_case, air_terminal_surface,
                                  inlet_type, outlet_type):
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
        if inlet_type == 'SimpleStlDiffusor':
            for m in mesh.Mesh.from_multi_file(
                    Path(__file__).parent.parent / 'assets' / 'geometry' /
                    'air' / 'drallauslass_ersatzmodell.stl'):
                meshes.append(m)
        else:
            for m in mesh.Mesh.from_multi_file(
                    Path(__file__).parent.parent / 'assets' / 'geometry' /
                    'air' / 'AirTerminal.stl'):
                meshes.append(m)
                # print(str(m.name, encoding='utf-8'))
        temp_path = openfoam_case.openfoam_triSurface_dir / 'Temp'
        temp_path.mkdir(exist_ok=True)
        for m in meshes:
            curr_name = temp_path.as_posix() + '/' + str(m.name,
                                                         encoding='utf-8') + '.stl'
            with open(curr_name, 'wb+') as output_file:
                m.save(str(m.name, encoding='utf-8'), output_file,
                       mode=stl.Mode.ASCII)
            output_file.close()
        # read individual files from temp directory.
        if inlet_type == 'SimpleStlDiffusor':
            diffuser_shape = TopoDS_Shape()
            stl_reader = StlAPI_Reader()
            stl_reader.Read(diffuser_shape,
                            temp_path.as_posix() + '/' + "origin-w_drallauslass.stl")
            source_shape = TopoDS_Shape()
            stl_reader = StlAPI_Reader()
            stl_reader.Read(source_shape,
                            temp_path.as_posix() + '/' + "origin-inlet.stl")
            air_terminal_box = None  # TopoDS_Shape()
            # stl_reader = StlAPI_Reader()
            # stl_reader.Read(air_terminal_box,
            #                 temp_path.as_posix() + '/' + "box_3.stl")
        else:
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
        shapelist = [shape for shape in [diffuser_shape, source_shape,
                                         air_terminal_box] if shape is not None]
        for shape in shapelist:
            builder.Add(air_terminal_compound, shape)
        air_terminal_compound = BRepLib_FuseEdges(air_terminal_compound).Shape()
        air_terminal_compound = PyOCCTools.simple_bounding_box_shape(
            air_terminal_compound)

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
        inlet_diffuser_shape = None
        inlet_source_shape = None
        inlet_box_shape = None
        if diffuser_shape:
            inlet_diffuser_shape = BRepBuilderAPI_Transform(diffuser_shape,
                                                            trsf_inlet).Shape()
        if source_shape:
            inlet_source_shape = BRepBuilderAPI_Transform(source_shape,
                                                          trsf_inlet).Shape()
        if air_terminal_box:
            inlet_box_shape = BRepBuilderAPI_Transform(air_terminal_box,
                                                       trsf_inlet).Shape()
        inlet_shapes = [inlet_diffuser_shape, inlet_source_shape,
                        inlet_box_shape]
        trsf_outlet = gp_Trsf()
        trsf_outlet.SetTranslation(compound_center_lower, gp_Pnt(*outlet_pos))
        outlet_shape = BRepBuilderAPI_Transform(air_terminal_compound,
                                                trsf_outlet).Shape()
        outlet_diffuser_shape = None
        outlet_source_shape = None
        outlet_box_shape = None
        if outlet_type != 'None':
            outlet_diffuser_shape = BRepBuilderAPI_Transform(diffuser_shape,
                                                             trsf_outlet).Shape()
        if source_shape:
            outlet_source_shape = BRepBuilderAPI_Transform(source_shape,
                                                           trsf_outlet).Shape()
        if air_terminal_box:
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
        air_terminal_surface.bound_area = PyOCCTools.get_shape_area(cut_ceiling)
        # export stl geometry of surrounding surfaces again (including cut
        # ceiling)
        # create instances of air terminal class and return them?
        inlet = AirTerminal('inlet', inlet_shapes,
                            openfoam_case.openfoam_triSurface_dir, inlet_type)
        outlet = AirTerminal('outlet', outlet_shapes,
                             openfoam_case.openfoam_triSurface_dir,
                             outlet_type)
        # export moved inlet and outlet shapes

        return inlet, outlet

    def adjust_refinements(self, case, openfoam_elements):
        """
        Compute surface and region refinements for air terminals and other
        interior elements.
        """
        bM_size = self.playground.sim_settings.mesh_size
        if self.playground.sim_settings.add_airterminals:
            air_terminals = filter_elements(openfoam_elements, 'AirTerminal')
            for air_t in air_terminals:
                if ('INLET' in air_t.air_type.upper() and
                    self.playground.sim_settings.inlet_type == 'Plate') or \
                        ('OUTLET' in air_t.air_type.upper() and \
                         self.playground.sim_settings.outlet_type == 'Plate'):
                    diff = air_t.diffuser.tri_geom
                    box = air_t.box.tri_geom
                    dist = OpenFOAMUtils.get_min_refdist_between_shapes(
                        diff, box)
                    ref_level = OpenFOAMUtils.get_refinement_level(dist,
                                                                   bM_size)
                    air_t.diffuser.refinement_level = ref_level
                    air_t.box.refinement_level = ref_level
                    air_t.refinement_zone_level_small[1] = \
                        air_t.diffuser.refinement_level[0]
                    air_t.refinement_zone_level_large[1] = \
                        air_t.diffuser.refinement_level[0] - 1
                else:
                    for part in [p for p in [air_t.diffuser, air_t.box,
                                     air_t.source_sink] if p.tri_geom is not
                                                           None]:
                        verts, edges = OpenFOAMUtils.detriangulize(
                            OpenFOAMUtils, part.tri_geom)
                        min_dist = OpenFOAMUtils.get_min_internal_dist(verts)
                        edge_lengths = OpenFOAMUtils.get_edge_lengths(edges)
                        median_dist = np.median(edge_lengths)
                        self.logger.info(f"{air_t.solid_name}:\tPrev: "
                                         f"{part.refinement_level}")
                        part.refinement_level = \
                            OpenFOAMUtils.get_refinement_level(min_dist, bM_size,
                                                               median_dist)
                        self.logger.info(f"{air_t.solid_name}:\tNEW: "
                                         f"{part.refinement_level}")
                    air_t.refinement_zone_level_small[1] = \
                        air_t.diffuser.refinement_level[0]
                    air_t.refinement_zone_level_large[1] = \
                        air_t.diffuser.refinement_level[0] - 1

        interior = dict()  # Add other interior equipment and topoDS Shape
        if self.playground.sim_settings.add_heating:
            heaters = filter_elements(openfoam_elements, 'Heater')
            interior.update({h: h.heater_surface.tri_geom for h in heaters})
        if self.playground.sim_settings.add_furniture:
            furniture = filter_elements(openfoam_elements, 'Furniture')
            interior.update({f: f.tri_geom for f in furniture})
        if self.playground.sim_settings.add_people:
            people = filter_elements(openfoam_elements, 'People')
            interior.update({p: p.tri_geom for p in people})
        for int_elem, int_geom in interior.items():
            self.logger.info(f"Updating refinements for {int_elem.solid_name}.")
            verts, edges = OpenFOAMUtils.detriangulize(OpenFOAMUtils, int_geom)
            int_dist = OpenFOAMUtils.get_min_internal_dist(verts)
            edge_lengths = OpenFOAMUtils.get_edge_lengths(edges)
            median_int_dist = np.median(edge_lengths)
            wall_dist = OpenFOAMUtils.get_min_refdist_between_shapes(
                int_geom, case.current_zone.space_shape)
            if wall_dist > 1e-6:
                obj_dist = wall_dist
            else:
                obj_dist = 1000
            if len(interior) > 1:
                for key, obj_geom in interior.items():
                    if key == int_elem:
                        continue
                    new_dist = OpenFOAMUtils.get_min_refdist_between_shapes(
                        int_geom, obj_geom)
                    if new_dist < obj_dist and new_dist > 1e-6:
                        obj_dist = new_dist
            if wall_dist > 1e-6:
                min_dist_ext = min(wall_dist, obj_dist)
            else:
                min_dist_ext = obj_dist
            ref_level_reg = OpenFOAMUtils.get_refinement_level(min_dist_ext,
                                                               bM_size, median_int_dist)
            if int_dist < min_dist_ext:
                ref_level_surf = OpenFOAMUtils.get_refinement_level(
                    int_dist, bM_size, median_int_dist)
            else:
                ref_level_surf = ref_level_reg
            self.logger.info(f"{int_elem.solid_name}:\tPREV: "
                             f"{int_elem.refinement_level},\tNEW: {ref_level_surf}")
            int_elem.refinement_level = ref_level_surf

    def init_furniture(self, openfoam_case, elements, openfoam_elements):
        if not self.playground.sim_settings.add_furniture:
            return
        furniture_surface = openfoam_case.furniture_surface

        if 'Furniture' in [name.__class__.__name__ for name in
                           list(elements.values())]:
            # todo: get product shape of furniture
            # identify furniture in current zone (maybe flag is already
            # set from preprocessing in bim2sim
            # get TopoDS_Shape for further preprocessing of the shape.
            raise NotImplementedError('Furniture found in bim2sim, it cannot '
                                      'be handled yet. No furniture is added.')
            pass
        furniture = self.create_furniture_shapes(openfoam_case,
                                                 furniture_surface)
        if isinstance(furniture, list):
            for elem in furniture:
                openfoam_elements[elem.solid_name] = elem
        else:
            openfoam_elements[furniture.solid_name] = furniture

    def create_furniture_shapes(self, openfoam_case, furniture_surface,
                                x_gap=0.8, y_gap=0.8, side_gap=0.8):
        doors = []
        for bound in openfoam_case.current_bounds:
            if bound.bound_element:
                if "DOOR" in bound.bound_element.element_type.upper():
                    doors.append(bound)
        meshes = []
        chair_shape = None
        desk_shape = None
        table = None
        furniture_setting = self.playground.sim_settings.furniture_setting
        furniture_path = (Path(__file__).parent.parent / 'assets' / 'geometry' /
                          'furniture')
        furniture_shapes = []

        if furniture_setting in ['Office', 'Concert', 'Meeting', 'Classroom',
                                     'GroupTable', 'TwoSideTable']:
            chair_shape = TopoDS_Shape()
            stl_reader = StlAPI_Reader()
            stl_reader.Read(chair_shape,
                            furniture_path.as_posix() + '/' +
                            "DIN1729_ChairH460.stl")
            furniture_shapes.append(chair_shape)
            if furniture_setting in ['Office', 'Meeting', 'Classroom',
                                     'GroupTable', 'TwoSideTable']:
                desk_shape = TopoDS_Shape()
                stl_reader = StlAPI_Reader()
                stl_reader.Read(desk_shape,
                                furniture_path.as_posix() + '/' +
                                "Table1400x800H760.stl")
                table = Table(furniture_setting, desk_shape,
                              triSurface_path=openfoam_case.openfoam_triSurface_dir,
                              furniture_type='Table',
                              bbox_min_max=PyOCCTools.simple_bounding_box(
                                  [desk_shape]),
                              chair_bbox_min_max=PyOCCTools.simple_bounding_box(
                                  [chair_shape]))
                chair_shapes = [BRepBuilderAPI_Transform(chair_shape,
                                                         tr).Shape() for tr in
                                table.chair_trsfs]
                furniture_shapes += chair_shapes
                furniture_shapes.append(desk_shape)

        # furniture_path = (Path(__file__).parent.parent / 'assets' / 'geometry' /
        #                   'furniture_people_compositions')
        # furniture_shapes = []
        # if self.playground.sim_settings.furniture_setting in ['Office',
        #                                                       'Concert',
        #                                                       'Meeting',
        #                                                       'Classroom']:
        #     chair_shape = TopoDS_Shape()
        #     stl_reader = StlAPI_Reader()
        #     stl_reader.Read(chair_shape,
        #                     furniture_path.as_posix() + '/' +
        #                     "new_compChair.stl")
        #     furniture_shapes.append(chair_shape)
        # if self.playground.sim_settings.furniture_setting in ['Office',
        #                                                       'Meeting']:
        #     desk_shape = TopoDS_Shape()
        #     stl_reader = StlAPI_Reader()
        #     stl_reader.Read(desk_shape,
        #                     furniture_path.as_posix() + '/' +
        #                     "new_compDesk.stl")
        #     furniture_shapes.append(desk_shape)
        # elif self.playground.sim_settings.furniture_setting in ['Classroom']:
        #     desk_shape = TopoDS_Shape()
        #     stl_reader = StlAPI_Reader()
        #     stl_reader.Read(desk_shape,
        #                     furniture_path.parent.as_posix() + 'furniture/' +
        #                     "Table1200x600H760.stl")
        #     furniture_shapes.append(desk_shape)

        furniture_compound = TopoDS_Compound()
        builder = TopoDS_Builder()
        builder.MakeCompound(furniture_compound)
        shapelist = [shape for shape in furniture_shapes if shape is not None]
        for shape in shapelist:
            builder.Add(furniture_compound, shape)
        requested_amount = self.playground.sim_settings.furniture_amount

        # todo: Algorithm for furniture setup based on furniture amount,
        #  limited by furniture_surface area (or rather lx-ly-dimensions of the
        #  area)

        if self.playground.sim_settings.furniture_setting in ['Concert',
                                                              'Classroom',
                                                              'Office',
                                                              'Meeting',
                                     'GroupTable', 'TwoSideTable']:
            # todo: remove Office and Meeting setup here and replace by
            #  appropriate other setup
            #  Meeting: 1 two-sided table (rotate every other table by 180deg)
            #  Office: similar to meeting, but spread tables in Office.
            # calculate amount of rows
            if self.playground.sim_settings.furniture_setting == 'Concert':
                min_x_space = 0.5  # space for each seat SBauVO NRW 2019
                min_y_distance = 0.4  # between rows SBauVO NRW 2019
                max_rows_per_block = 15  # SBauVO NRW: max 30 rows per block
                max_obj_single_escape = 10  # SBauVO NRW: max 10 seats per
                # row if only a single escape route is available
                max_obj_two_escape = 20  # SBauVO NRW: max 20 seats in a row
                # if two escape routes are available
                if requested_amount <= 200:
                    escape_route_width = 0.9
                else:
                    escape_route_width = 1.2
                furniture_locations, furniture_trsfs = (
                    self.generate_grid_positions_w_constraints(
                    furniture_surface, furniture_compound,
                    requested_amount, min_x_space, min_y_distance,
                        max_rows_per_block, max_obj_single_escape,
                        max_obj_two_escape, escape_route_width, doors,
                        min_dist_all_sides=0.15))
            elif self.playground.sim_settings.furniture_setting in [
                'Classroom', 'TwoSideTable']:
                min_x_space = 0.0  # space for each seat SBauVO NRW 2019
                min_y_distance = 1.5  # between rows SBauVO NRW 2019
                max_rows_per_block = 5  # SBauVO NRW: max 30 rows per block
                max_obj_single_escape = 5  # SBauVO NRW: max 10 seats per
                # row if only a single escape route is available
                max_obj_two_escape = 10  # SBauVO NRW: max 20 seats in a row
                # if two escape routes are available
                if requested_amount <= 200:
                    escape_route_width = 0.9
                else:
                    escape_route_width = 1.2
                chair_bbox = PyOCCTools.simple_bounding_box([chair_shape])
                add_chair_depth = chair_bbox[1][1] - chair_bbox[0][1]
                furniture_locations, furniture_trsfs = (
                    self.generate_grid_positions_w_constraints(
                    furniture_surface, desk_shape,
                    requested_amount, min_x_space, min_y_distance,
                        max_rows_per_block, max_obj_single_escape,
                        max_obj_two_escape, escape_route_width, doors,
                        min_distance_last_row=add_chair_depth+0.15,
                        min_dist_all_sides=0.15))
            elif self.playground.sim_settings.furniture_setting in [
                'GroupTable']:
                chair_bbox = PyOCCTools.simple_bounding_box([chair_shape])
                add_chair_depth = chair_bbox[1][1] - chair_bbox[0][1]
                table_bbox = PyOCCTools.simple_bounding_box([desk_shape])
                add_table_width = table_bbox[1][0] - table_bbox[0][0]
                min_x_space = 1.5 + add_table_width # space for each seat
                # SBauVO NRW 2019
                min_y_distance = 1.5  # between rows SBauVO NRW 2019
                max_rows_per_block = 5  # SBauVO NRW: max 30 rows per block
                max_obj_single_escape = 5  # SBauVO NRW: max 10 seats per
                # row if only a single escape route is available
                max_obj_two_escape = 10  # SBauVO NRW: max 20 seats in a row
                # if two escape routes are available
                if requested_amount <= 200:
                    escape_route_width = 0.0# 0.9
                else:
                    escape_route_width = 1.2
                min_seats_single_escape = 1
                min_rows_per_block = 1

                furniture_locations, furniture_trsfs = (
                    self.generate_grid_positions_w_constraints(
                    furniture_surface, desk_shape,
                    requested_amount, min_x_space, min_y_distance,
                        max_rows_per_block, max_obj_single_escape,
                        max_obj_two_escape, escape_route_width, doors,
                        min_dist_all_sides=add_chair_depth+0.15,
                        min_seats_single_escape=min_seats_single_escape,
                        min_rows_per_block=min_rows_per_block))
            else:
                furniture_locations, furniture_trsfs = self.generate_grid_positions(
                    furniture_surface, furniture_compound,
                    requested_amount, x_gap, y_gap, side_gap)
        furniture_items = []
        global_chair_trsfs = []

        for i, trsf in enumerate(furniture_trsfs):
            furniture_shape = BRepBuilderAPI_Transform(furniture_compound,
                                                       trsf).Shape()
            furniture_min_max = PyOCCTools.simple_bounding_box(furniture_shape)
            if chair_shape:
                if table:
                    for j, chair_trsf in enumerate(table.chair_trsfs):
                        global_trsf = trsf.Multiplied(chair_trsf)
                        global_chair_trsfs.append(global_trsf)
                        new_chair_shape = BRepBuilderAPI_Transform(
                            chair_shape, trsf.Multiplied(chair_trsf)).Shape()
                        chair = Furniture(new_chair_shape,
                                          openfoam_case.openfoam_triSurface_dir,
                                          f'Tab{i}_Chair{j}')
                        furniture_items.append(chair)
                else:
                    new_chair_shape = BRepBuilderAPI_Transform(chair_shape,
                                                               trsf).Shape()
                    global_chair_trsfs.append(trsf)
                    chair = Furniture(new_chair_shape,
                                      openfoam_case.openfoam_triSurface_dir,
                                      f'Chair{i}')
                    furniture_items.append(chair)
            if desk_shape:
                new_desk_shape = BRepBuilderAPI_Transform(desk_shape,
                                                          trsf).Shape()
                desk = Furniture(new_desk_shape,
                                 openfoam_case.openfoam_triSurface_dir,
                                 f'Desk{i}')
                furniture_items.append(desk)

        openfoam_case.furniture_trsfs = furniture_trsfs
        openfoam_case.chair_trsfs = global_chair_trsfs
        return furniture_items

    def init_people(self, openfoam_case, elements, openfoam_elements):
        if not self.playground.sim_settings.add_people:
            return
        furniture_surface = openfoam_case.furniture_surface
        people = self.create_people_shapes(openfoam_case, furniture_surface)
        if isinstance(people, list):
            for elem in people:
                openfoam_elements[elem.solid_name] = elem
        else:
            openfoam_elements[people.solid_name] = people

    def create_people_shapes(self, openfoam_case, furniture_surface):

        furniture_path = (Path(__file__).parent.parent / 'assets' / 'geometry' /
                          'furniture_people_compositions')
        # people_shapes = []
        people_items = []
        if self.playground.sim_settings.use_energyplus_people_amount:
            people_amount = math.ceil(openfoam_case.timestep_df.filter(
                like=openfoam_case.current_zone.guid.upper()
                                                  +':Zone People'))
        else:
            people_amount = self.playground.sim_settings.people_amount

        if self.playground.sim_settings.people_setting in ['Seated']:
            available_trsfs = openfoam_case.chair_trsfs

            person_path = (furniture_path.as_posix() + '/' +
                           "DIN1729_manikin_split_19parts.stl")
            part_meshes = []
            for m in mesh.Mesh.from_multi_file(person_path):
                part_meshes.append(m)
            combined_data = np.concatenate([m.data.copy() for m in part_meshes])
            combined_mesh = mesh.Mesh(combined_data)
            temp_path = openfoam_case.openfoam_triSurface_dir / 'Temp'
            temp_path.mkdir(exist_ok=True)
            combined_mesh.save(openfoam_case.openfoam_triSurface_dir /
                               'Temp' / 'combined_person.stl')
            person_shape = TopoDS_Shape()
            stl_reader = StlAPI_Reader()
            stl_reader.Read(person_shape,
                            str(openfoam_case.openfoam_triSurface_dir /
                                'Temp' / 'combined_person.stl'))
            # people_shapes.append(person_shape)
            if people_amount > len(available_trsfs):
                people_amount = len(available_trsfs)
        elif (self.playground.sim_settings.people_setting in ['Standing'] and
              len(openfoam_case.chair_trsfs) == 0):
            person_path = (Path(__file__).parent.parent / 'assets' /
                           'geometry' / 'people' / "manikin_standing.stl")
            person_shape = TopoDS_Shape()
            stl_reader = StlAPI_Reader()
            stl_reader.Read(person_shape, person_path.as_posix())
            # people_shapes.append(person_shape)
            people_locations, available_trsfs = self.generate_grid_positions(
                furniture_surface, person_shape,
                people_amount, x_gap=0.6, y_gap=0.6, side_gap=0.4)
        else:
            self.logger.warning('Standing people are currently not supported '
                                'combined with furniture setups. No people '
                                'are added.')
            return
        random_people_choice = random.sample(range(len(available_trsfs)),
                                             people_amount)
        for i, trsf in enumerate(available_trsfs):
            if i not in random_people_choice:
                continue
            if i == people_amount:
                break
            new_person_shape = BRepBuilderAPI_Transform(person_shape,
                                                        trsf).Shape()
            person = People(
                new_person_shape, trsf, person_path,
                openfoam_case.openfoam_triSurface_dir, f'Person{i}',
                radiation_model=openfoam_case.radiation_model,
                power=openfoam_case.current_zone.fixed_heat_flow_rate_persons.to(
                        ureg.watt).m,
                scale=self.playground.sim_settings.scale_person_for_eval, 
                add_scaled_shape=self.playground.sim_settings.add_air_volume_evaluation)
            people_items.append(person)
        return people_items

    @staticmethod
    def export_stlbound_triSurface(openfoam_case, openfoam_elements):
        stl_bounds = filter_elements(openfoam_elements, 'StlBound')
        temp_stl_path = Path(
            tempfile.TemporaryDirectory(
                prefix='bim2sim_temp_stl_files_').name)
        temp_stl_path.mkdir(exist_ok=True)
        with (open(openfoam_case.openfoam_triSurface_dir /
                   str("space_" + openfoam_case.current_zone.guid + ".stl"),
                   'wb+') as output_file):
            for stl_bound in stl_bounds:
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

    @staticmethod
    def export_heater_triSurface(openfoam_elements):
        heaters = filter_elements(openfoam_elements, 'Heater')
        for heater in heaters:
            create_stl_from_shape_single_solid_name(
                heater.heater_surface.tri_geom,
                heater.heater_surface.stl_file_path_name,
                heater.heater_surface.solid_name)
            create_stl_from_shape_single_solid_name(
                heater.porous_media.tri_geom,
                heater.porous_media.stl_file_path_name,
                heater.porous_media.solid_name)

    @staticmethod
    def export_airterminal_triSurface(openfoam_elements):
        air_terminals = filter_elements(openfoam_elements, 'AirTerminal')
        for air_terminal in air_terminals:
            if air_terminal.diffuser.tri_geom:
                create_stl_from_shape_single_solid_name(
                    air_terminal.diffuser.tri_geom,
                    air_terminal.diffuser.stl_file_path_name,
                    air_terminal.diffuser.solid_name)
            if air_terminal.source_sink.tri_geom:
                create_stl_from_shape_single_solid_name(
                    air_terminal.source_sink.tri_geom,
                    air_terminal.source_sink.stl_file_path_name,
                    air_terminal.source_sink.solid_name)
            if air_terminal.box.tri_geom:
                create_stl_from_shape_single_solid_name(
                    air_terminal.box.tri_geom,
                    air_terminal.box.stl_file_path_name,
                    air_terminal.box.solid_name)

    @staticmethod
    def export_furniture_triSurface(openfoam_elements):
        furnitures = filter_elements(openfoam_elements, 'Furniture')
        for furniture in furnitures:
            if furniture.tri_geom:
                create_stl_from_shape_single_solid_name(
                    furniture.tri_geom,
                    furniture.stl_file_path_name,
                    furniture.solid_name)

    @staticmethod
    def export_people_triSurface(openfoam_elements):
        people = filter_elements(openfoam_elements, 'People')
        for person in people:
            for body_part in person.body_parts_dict.values():
                if body_part.tri_geom:
                    create_stl_from_shape_single_solid_name(
                        body_part.tri_geom,
                        body_part.stl_file_path_name,
                        body_part.solid_name)

    def generate_grid_positions(self, furniture_surface, obj_to_be_placed,
                                requested_amount,
                                x_gap=0.2, y_gap=0.35,
                                side_gap=0.6):
        furniture_surface_z = PyOCCTools.get_center_of_shape(
            furniture_surface).Z()

        surf_min_max = PyOCCTools.simple_bounding_box(furniture_surface)
        lx = surf_min_max[1][0] - surf_min_max[0][0]
        ly = surf_min_max[1][1] - surf_min_max[0][1]

        compound_bbox = PyOCCTools.simple_bounding_box(obj_to_be_placed)
        lx_comp = compound_bbox[1][0] - compound_bbox[0][0]
        ly_comp = compound_bbox[1][1] - compound_bbox[0][1]

        compound_center = PyOCCTools.get_center_of_shape(
            PyOCCTools.simple_bounding_box_shape(obj_to_be_placed)).Coord()
        compound_center_lower = gp_Pnt(compound_center[0], compound_center[1],
                                       compound_bbox[0][2])

        x_max_number = math.floor((lx - side_gap * 2 + x_gap) / (lx_comp +
                                                                 x_gap))
        y_max_number = math.floor((ly - side_gap * 2 + y_gap) / (ly_comp +
                                                                 y_gap))

        max_amount = x_max_number * y_max_number
        if requested_amount > max_amount:
            self.logger.warning(
                f'You requested an amount of '
                f'{requested_amount}, but only '
                f'{max_amount} is possible. Using this maximum '
                f'allowed amount.')
            requested_amount = max_amount

        # set number of rows to maximum number in y direction
        obj_rows = y_max_number
        obj_locations = []
        for row in range(obj_rows):
            if row == 0:
                y_loc = (surf_min_max[0][1] + side_gap + (row * y_gap) +
                         ly_comp / 2)
            else:
                y_loc = (surf_min_max[0][1] + side_gap +
                         (row * (y_gap + ly_comp)) + ly_comp / 2)
            x_loc = surf_min_max[0][0] + side_gap
            for x_pos in range(x_max_number):
                if x_pos == 0:
                    x_loc += lx_comp / 2
                else:
                    x_loc += x_gap + lx_comp
                pos = gp_Pnt(x_loc, y_loc, furniture_surface_z)
                obj_locations.append(pos)
                if len(obj_locations) == requested_amount:
                    break
            if len(obj_locations) == requested_amount:
                break
        obj_trsfs = PyOCCTools.generate_obj_trsfs(obj_locations,
                                            compound_center_lower)
        return obj_locations, obj_trsfs

    def generate_grid_positions_w_constraints(self, furniture_surface,
                                              obj_to_be_placed,
                                              requested_amount,
                                              min_x_space=0.5,
                                              min_y_distance=0.4,
                                              max_obj_rows_per_block=30,
                                              max_obj_single_escape=10,
                                              max_obj_two_escape=20,
                                              escape_route_width=1.2,
                                              doors=[],
                                              min_distance_last_row=0.0,
                                              min_dist_all_sides=0.1,
                                              min_rows_per_block=3,
                                              min_seats_single_escape=3):
        furniture_surface_z = PyOCCTools.get_center_of_shape(
            furniture_surface).Z()

        max_row_blocks = 0  # possible blocks of rows
        max_single_escape_blocks = 0  # possible blocks with single escape route
        max_double_escape_blocks = 0
        max_seats_single_escape_blocks = [0,0]
        max_seats_double_escape_blocks = [0]
        max_rows_per_block = [0]
        rotation_angle = 0
        switch = False
        surf_min_max = PyOCCTools.simple_bounding_box(furniture_surface)
        global_x_position = surf_min_max[0][0]
        global_y_position = surf_min_max[0][1]
        temp_lx = surf_min_max[1][0] - surf_min_max[0][0]
        temp_ly = surf_min_max[1][1] - surf_min_max[0][1]
        if self.playground.sim_settings.furniture_orientation == 'long_side':
            if temp_lx < temp_ly:
                lx = temp_ly
                ly = temp_lx
                global_x_position = surf_min_max[0][1]
                global_y_position = surf_min_max[0][0]
                rotation_angle = 270
                switch = True
            else:
                lx = temp_lx
                ly = temp_ly
        elif self.playground.sim_settings.furniture_orientation == "short_side":
            if temp_lx > temp_ly:
                lx = temp_ly
                ly = temp_lx
                global_x_position = surf_min_max[0][1]
                global_y_position = surf_min_max[0][0]
                rotation_angle = 270
                switch = True
            else:
                lx = temp_lx
                ly = temp_ly
        else:
            lx = temp_lx
            ly = temp_ly

        global_y_position += min_distance_last_row
        ly -= min_distance_last_row
        global_x_position += min_dist_all_sides
        global_y_position += min_dist_all_sides
        lx -= 2*min_dist_all_sides
        ly -= 2*min_dist_all_sides

        # calculate areas in front of doors to guarantee escape
        door_escapes = []
        for door in doors:
            reverse=False
            (min_box, max_box) = PyOCCTools.simple_bounding_box([
                door.bound_shape])
            door_lower_pnt1 = gp_Pnt(*min_box)
            door_lower_pnt2 = gp_Pnt(max_box[0], max_box[1], min_box[2])
            base_line_pnt1 = door_lower_pnt1
            base_line_pnt2 = door_lower_pnt2
            door_width = door_lower_pnt1.Distance(door_lower_pnt2)
            # add square space in front of doors, depth = escape route width
            d = gp_Dir(gp_Vec(base_line_pnt1, base_line_pnt2))
            new_dir = d.Rotated(gp_Ax1(base_line_pnt1, gp_Dir(0, 0, 1)),
                     math.radians(90))
            moved_pnt1 = PyOCCTools.move_bound_in_direction_of_normal(
                                BRepBuilderAPI_MakeVertex(base_line_pnt1).Vertex(),
                                escape_route_width, move_dir=new_dir, reverse=reverse)
            moved_dist = BRepExtrema_DistShapeShape(moved_pnt1,
                                                  furniture_surface,
                                                  Extrema_ExtFlag_MIN).Value()
            if abs(moved_dist) > 1e-3:
                reverse = True
                moved_pnt1 = PyOCCTools.move_bound_in_direction_of_normal(
                    BRepBuilderAPI_MakeVertex(base_line_pnt1).Vertex(),
                    max(escape_route_width, door_width), move_dir=new_dir, reverse=reverse)
            if reverse:
                moved_pnt2 = PyOCCTools.move_bound_in_direction_of_normal(
                    BRepBuilderAPI_MakeVertex(base_line_pnt2).Vertex(),
                    max(escape_route_width, door_width), move_dir=new_dir, reverse=reverse)
            else:
                moved_pnt2 = PyOCCTools.move_bound_in_direction_of_normal(
                    BRepBuilderAPI_MakeVertex(base_line_pnt2).Vertex(),
                    max(escape_route_width, door_width), move_dir=new_dir, reverse=reverse)
            add_escape_shape = PyOCCTools.make_faces_from_pnts([base_line_pnt1,
                                                                base_line_pnt2,
                                                                BRep_Tool.Pnt(moved_pnt2),
                                                                BRep_Tool.Pnt(moved_pnt1)])
            door_escapes.append(add_escape_shape)
        swp_x1 = gp_Pnt(
            global_x_position, global_y_position, furniture_surface_z)
        swp_x2 = gp_Pnt(
            global_x_position, global_y_position+ly, furniture_surface_z)
        swp_dir_x = gp_Pnt(
            global_x_position+lx, global_y_position, furniture_surface_z)

        (translated_lines_x, intersection_points_x, min_t_x, min_delta_x,
         min_pnt_x) = (
            PyOCCTools.sweep_line_find_intersections_multiple_shapes(
            swp_x1, swp_x2, [PyOCCTools.extrude_face_in_direction(s) for s in door_escapes], gp_Dir(gp_Vec(swp_x1, swp_dir_x))))
        if door_escapes:
            inside_door_escape = True if min([BRepExtrema_DistShapeShape(
                BRepBuilderAPI_MakeEdge(swp_x1, swp_x2).Edge(), d,
                Extrema_ExtFlag_MIN).Value() for d in door_escapes]) < 1e-4 else (
                False)
        else:
            inside_door_escape = False
        # these intersections are relative to the global positions
        intersect_dict_x = {}
        for p in set([round(p[1], 3) for p in intersection_points_x]):
            count = 0
            for i in [round(p[1], 3) for p in intersection_points_x]:
                if i == p:
                    count += 1
            if count > 4:
                intersect_dict_x.update({p: count})
        sorted_intersections_x = dict(sorted(intersect_dict_x.items()))

        compound_bbox = PyOCCTools.simple_bounding_box(obj_to_be_placed)
        lx_comp = compound_bbox[1][0] - compound_bbox[0][0]
        ly_comp = compound_bbox[1][1] - compound_bbox[0][1]

        lx_comp_width = max(lx_comp, min_x_space)
        ly_comp_width = ly_comp + min_y_distance

        compound_center = PyOCCTools.get_center_of_shape(
            PyOCCTools.simple_bounding_box_shape(obj_to_be_placed)).Coord()
        compound_center_lower = gp_Pnt(compound_center[0], compound_center[1],
                                       compound_bbox[0][2])
        # calculate footprint shape of setup
        x_diff = lx_comp_width - lx_comp
        if x_diff < 0:
            x_diff = 0
        footprint_shape = PyOCCTools.make_faces_from_pnts(
            [gp_Pnt(compound_bbox[0][0]
                    - x_diff / 2,
                    compound_bbox[0][1],
                    compound_bbox[0][2]),
             gp_Pnt(compound_bbox[0][0] - x_diff / 2,
                    compound_bbox[0][1] + ly_comp_width,
                    compound_bbox[0][2]),
             gp_Pnt(compound_bbox[0][0] + lx_comp_width - x_diff / 2,
                    compound_bbox[0][1] + ly_comp_width,
                    compound_bbox[0][2]),
             gp_Pnt(compound_bbox[0][0] + lx_comp_width - x_diff / 2,
                    compound_bbox[0][1],
                    compound_bbox[0][2])])
        unavail_x_pos = []
        temp_x_pos = 0
        reset_x_pos = False
        if inside_door_escape:
            k = 1
        else:
            k = 0
        for i, key in enumerate(list(sorted_intersections_x.keys())):
            if (i+k) % 2 == 0:
                if (key - temp_x_pos) < lx_comp_width * min_seats_single_escape:
                    if unavail_x_pos and unavail_x_pos[-1][1] == temp_x_pos:
                        unavail_x_pos[-1][1] = key
                    else:
                        unavail_x_pos.append([temp_x_pos, key])
            else:
                if unavail_x_pos and unavail_x_pos[-1][1] == temp_x_pos:
                    unavail_x_pos[-1][1] = key
                else:
                    unavail_x_pos.append([temp_x_pos, key])
            temp_x_pos = key
        if temp_x_pos != 0 and abs(lx - temp_x_pos)>1e-3:
            if abs(temp_x_pos - lx) < lx_comp_width * min_seats_single_escape:
                if unavail_x_pos and unavail_x_pos[-1][1] == temp_x_pos:
                    unavail_x_pos[-1][1] = lx
                else:
                    unavail_x_pos.append([temp_x_pos, lx])

        available_x_list = []
        if unavail_x_pos:
            for i, uxp in enumerate(unavail_x_pos):
                if uxp[1] - uxp[0] < escape_route_width:
                    add_escape_dist = escape_route_width - (uxp[1] - uxp[0])
                else:
                    add_escape_dist = 0
                if i == 0 and uxp[0] == 0:
                    available_x_list.append('MinXEscape')
                if i == len(unavail_x_pos) - 1:
                    x_width_available = abs(lx - uxp[1] - add_escape_dist)
                    if abs(uxp[1] - lx) < 1e-3:
                        available_x_list.append('MaxXEscape')
                    else:
                        available_x_list.append(x_width_available)
                    continue
                else:
                    x_width_available = unavail_x_pos[i + 1][0] - uxp[
                        1] - add_escape_dist
                available_x_list.append(x_width_available)
        else:
            x_width_available = abs(lx - escape_route_width)
            available_x_list.append(x_width_available)

        if 'MinXEscape' in available_x_list and 'MaxXEscape' in \
            available_x_list:
            max_single_escape_blocks = 0
            max_seats_single_escape_blocks = [0, 0]
            for avail_x in available_x_list:
                if isinstance(avail_x, str):
                    continue
                else:
                    x_max_number = math.floor(avail_x / lx_comp_width)
                    if x_max_number > max_obj_two_escape:
                        temp_max_double_escape_blocks = avail_x / (
                                escape_route_width + max_obj_two_escape * lx_comp_width)
                        if temp_max_double_escape_blocks < 1:
                            max_double_escape_blocks += 1
                            if sum(max_seats_double_escape_blocks) == 0:
                                max_seats_double_escape_blocks = [
                                    max_obj_two_escape] * max_double_escape_blocks
                            else:
                                max_seats_double_escape_blocks += [
                                    max_obj_two_escape] * max_double_escape_blocks
                        else:
                            max_double_escape_blocks += math.ceil(
                                temp_max_double_escape_blocks)
                            temp_max_seats = math.floor(((avail_x - (math.ceil(
                                temp_max_double_escape_blocks))*
                                                        escape_route_width)/lx_comp_width))
                            add_seats = [
                                temp_max_seats//math.ceil(
                                temp_max_double_escape_blocks)
                                for s in range(max_double_escape_blocks)]
                            if (abs(sum(add_seats)-temp_max_seats) > 0 and
                                    add_seats):
                                add_seats[-1] +=abs(sum(
                                    add_seats)-temp_max_seats)
                            if add_seats:
                                if sum(max_seats_double_escape_blocks) == 0:
                                    max_seats_single_escape_blocks = add_seats
                                else:
                                    max_seats_single_escape_blocks += add_seats
                    else:
                        max_double_escape_blocks = 1
                        max_seats_double_escape_blocks = [x_max_number]


        elif 'MinXEscape' in available_x_list or 'MaxXEscape' in available_x_list:
            if len(available_x_list) <= 2:
                for avail_x in available_x_list:
                    if isinstance(avail_x, str):
                        continue
                    x_max_number = math.floor(avail_x/lx_comp_width)
                    if x_max_number < max_obj_single_escape:
                        set_single_number = x_max_number
                        remaining_number = 0
                        max_single_escape_blocks = 1
                    else:
                        set_single_number = max_obj_single_escape
                        remaining_number = x_max_number - set_single_number
                        max_single_escape_blocks = 1
                    if 'MinXEscape' in available_x_list:
                        max_seats_single_escape_blocks = [0, set_single_number]
                    else:
                        max_seats_single_escape_blocks = [set_single_number, 0]
                    if remaining_number > min_seats_single_escape:
                        remaining_x_width = math.floor(
                            remaining_number*lx_comp_width)

                        temp_max_double_escape_blocks = remaining_x_width / (
                                escape_route_width + max_obj_two_escape * lx_comp_width)
                        if temp_max_double_escape_blocks < 1:
                            avail_seats = math.floor((
                            remaining_x_width-escape_route_width) / (
                                 lx_comp_width))
                            max_double_escape_blocks += 1
                            max_seats_double_escape_blocks.append(
                                avail_seats)
                        else:
                            max_double_escape_blocks += math.ceil(
                                temp_max_double_escape_blocks)
                            temp_max_seats = math.floor(
                                ((avail_x - (math.ceil(
                                    temp_max_double_escape_blocks) *
                                            escape_route_width)) /
                                 lx_comp_width))
                            add_seats = [temp_max_seats // math.ceil(
                                temp_max_double_escape_blocks)
                                for s in range(max_double_escape_blocks)]
                            if (abs(sum(add_seats) - temp_max_seats) > 0 and
                                    add_seats):
                                add_seats[-1] += abs(sum(
                                    add_seats) - temp_max_seats)
                            if add_seats:
                                if sum(max_seats_double_escape_blocks) == 0:
                                    max_seats_single_escape_blocks = add_seats
                                else:
                                    max_seats_single_escape_blocks += add_seats

        else:
            for i, avail_x in enumerate(available_x_list):
                x_max_number = math.floor(avail_x / lx_comp_width)
                if x_max_number > 2*max_obj_single_escape:
                    temp_max_double_escape_blocks = avail_x / (
                        escape_route_width + max_obj_two_escape * lx_comp_width)
                    if temp_max_double_escape_blocks < 1 and (i == 0 and len(
                            available_x_list) == 1):
                        max_single_escape_blocks = 2
                        max_seats_single_escape_blocks = [max_obj_single_escape,
                                                          max_obj_single_escape]
                    else:
                        if 0 < i < len(available_x_list):
                            temp_max_double_escape_blocks = math.floor(
                                temp_max_double_escape_blocks)
                        else:
                            temp_max_double_escape_blocks = math.ceil(
                                temp_max_double_escape_blocks)
                        max_double_escape_blocks += temp_max_double_escape_blocks
                        temp_max_seats = math.floor(
                            ((avail_x - (temp_max_double_escape_blocks *
                                         escape_route_width)) / lx_comp_width))
                        if temp_max_double_escape_blocks > 0:
                            add_seats = [temp_max_seats // temp_max_double_escape_blocks
                                         for s in range(temp_max_double_escape_blocks)]
                            if (abs(sum(add_seats) - temp_max_seats) > 0 and
                                    add_seats):
                                add_seats[-1] += abs(sum(
                                    add_seats) - temp_max_seats)
                            if add_seats:
                                if sum(max_seats_double_escape_blocks) == 0:
                                    max_seats_single_escape_blocks = add_seats
                                else:
                                    max_seats_single_escape_blocks += add_seats

                        remaining_x_width = avail_x - \
                            (temp_max_double_escape_blocks*escape_route_width + sum(add_seats) *
                             lx_comp_width)
                        temp_num_seats_single_escape = math.floor(
                            remaining_x_width/lx_comp_width)
                        if not 0 < i < len(available_x_list):
                            if temp_num_seats_single_escape < min_seats_single_escape:
                                req_num_seats_single_escape = (
                                    min_seats_single_escape - temp_num_seats_single_escape)
                                max_seats_double_escape_blocks[0] = \
                                    max_seats_double_escape_blocks[0] - req_num_seats_single_escape
                                max_single_escape_blocks = 1

                                if i == 0:
                                    max_seats_single_escape_blocks = [min_seats_single_escape,
                                                                      0]
                                else:
                                    max_seats_single_escape_blocks = [0,
                                                                      min_seats_single_escape]
                            elif (min_seats_single_escape < temp_num_seats_single_escape <
                                    2*min_seats_single_escape):
                                if i == 0:
                                    max_seats_single_escape_blocks = [temp_num_seats_single_escape,
                                                                      0]
                                else:
                                    max_seats_single_escape_blocks = [0,
                                                                      temp_num_seats_single_escape]
                                max_single_escape_blocks = 1
                            elif (2*min_seats_single_escape < temp_num_seats_single_escape
                                  <=2*max_obj_single_escape):
                                smaller_half_of_seats = temp_num_seats_single_escape//2
                                max_seats_single_escape_blocks = [smaller_half_of_seats,
                                    temp_num_seats_single_escape-smaller_half_of_seats]
                                max_single_escape_blocks = 2
                            elif temp_num_seats_single_escape > 2*max_obj_single_escape:
                                max_seats_single_escape_blocks = [max_obj_single_escape,
                                    max_obj_single_escape]
                                max_single_escape_blocks = 2
                            else:
                                raise NotImplementedError("The requested number of seats "
                                                          "cannot be processed.")
                else:
                    if x_max_number < min_seats_single_escape:
                        max_seats_single_escape_blocks = [x_max_number, 0]
                        max_single_escape_blocks = 1
                    elif x_max_number < 2*min_seats_single_escape:
                        max_seats_single_escape_blocks = [x_max_number, 0]
                        max_single_escape_blocks = 1
                    else:
                        smaller_half_of_seats = x_max_number // 2
                        max_seats_single_escape_blocks = \
                            [smaller_half_of_seats, x_max_number -
                             smaller_half_of_seats]
                        max_single_escape_blocks = 2

        # # todo: generalize implementation using divmod
        # if x_max_number > 2*max_obj_single_escape:
        #     x_width_available = lx - 2*escape_route_width
        #     x_max_number = math.floor(x_width_available / lx_comp_width)
        # if x_max_number > (max_obj_two_escape + 2*max_obj_single_escape):
        #     x_width_available = lx - 3*escape_route_width
        #     x_max_number = math.floor(x_width_available / lx_comp_width)
        # if x_max_number > (2*max_obj_two_escape + 2*max_obj_single_escape):
        #     self.logger.warning(f'More than '
        #                         f'{2*max_obj_two_escape + 2*max_obj_single_escape} '
        #                         f'seats in a row are not '
        #                         f'supported. Using the maximum of '
        #                         f'{2*max_obj_two_escape + 2*max_obj_single_escape} '
        #                         f'seats '
        #                         f'instead, subdivided in multiple blocks')
        #     x_max_number = 2*max_obj_two_escape + 2*max_obj_single_escape

        y_width_available = ly - escape_route_width
        y_max_number = math.floor(y_width_available / ly_comp_width)
        if y_max_number > max_obj_rows_per_block:
            temp_max_row_blocks = y_width_available / (
                escape_route_width + max_obj_rows_per_block * ly_comp_width)
            if temp_max_row_blocks < 1:
                max_row_blocks = 1  # only one block with one escape route
                max_rows_per_block = [max_obj_rows_per_block]
            else:
                max_row_blocks = math.floor(temp_max_row_blocks)
                max_rows_per_block = [max_obj_rows_per_block]*max_row_blocks
                remaining_y_width = y_width_available - \
                    (max_row_blocks * ly_comp_width
                     * max_obj_rows_per_block + max_row_blocks*escape_route_width)
                temp_num_remaining_rows = math.floor(remaining_y_width /
                                                     ly_comp_width)
                if temp_num_remaining_rows < min_rows_per_block:
                    required_rows = min_rows_per_block - temp_num_remaining_rows
                    max_rows_per_block[0] = max_rows_per_block[0]-required_rows
                    max_rows_per_block.append(required_rows)
                    max_row_blocks += 1
                else:
                    max_rows_per_block.append(temp_num_remaining_rows)
                    max_row_blocks += 1
        else:
            max_rows_per_block = [y_max_number]
            max_row_blocks = 1

        max_amount = (sum(max_seats_double_escape_blocks)+sum(
            max_seats_single_escape_blocks)) * sum(max_rows_per_block)
        if requested_amount > max_amount:
            self.logger.warning(
                f'You requested an amount of '
                f'{requested_amount}, but only '
                f'{max_amount} is possible. Using this maximum '
                f'allowed amount.')
            requested_amount = max_amount
        elif requested_amount < max_amount:
            # remove outer blocks to reduce total number of available chair
            # positions
            diff_amount = max_amount - requested_amount
            if (diff_amount >
                    sum(max_rows_per_block)*max_seats_single_escape_blocks[1]):
                diff_amount -= max_seats_single_escape_blocks[1]*sum(max_rows_per_block)
                max_seats_single_escape_blocks[1] = 0
                max_single_escape_blocks = 1
                if diff_amount >sum(max_rows_per_block)*max_seats_single_escape_blocks[0]:
                    diff_amount -= max_seats_single_escape_blocks[0]*sum(max_rows_per_block)
                    max_seats_single_escape_blocks[0] = 0
                    max_single_escape_blocks = 0

        # set number of rows to maximum number in y direction
        obj_locations = []
        y_loc = global_y_position
        if 'MinXEscape' in available_x_list:
            global_x_position += unavail_x_pos[0][1]
        for num_rows_in_block in max_rows_per_block:
            obj_rows = num_rows_in_block
            for row in range(obj_rows):
                if row == 0:
                    y_loc += ly_comp / 2
                else:
                    y_loc += ly_comp_width
                x_loc = global_x_position
                if max_seats_single_escape_blocks[0] > 0:
                    for x_pos in range(max_seats_single_escape_blocks[0]):
                        if x_pos == 0:
                            x_loc += lx_comp_width / 2
                        else:
                            x_loc += lx_comp_width
                        pos = gp_Pnt(x_loc, y_loc, furniture_surface_z)
                        obj_locations.append(pos)
                        if len(obj_locations) == requested_amount:
                            break
                    x_loc += lx_comp_width / 2
                    if len(obj_locations) == requested_amount:
                        break
                if max_seats_double_escape_blocks[0] > 0:
                    for seats_in_row in max_seats_double_escape_blocks:
                        x_loc += escape_route_width
                        for x_pos in range(seats_in_row):
                            if x_pos == 0:
                                x_loc += lx_comp_width / 2
                            else:
                                x_loc += lx_comp_width
                            pos = gp_Pnt(x_loc, y_loc, furniture_surface_z)
                            obj_locations.append(pos)
                            if len(obj_locations) == requested_amount:
                                break
                        x_loc += lx_comp_width / 2
                        if len(obj_locations) == requested_amount:
                            break
                    if len(obj_locations) == requested_amount:
                        break
                if max_seats_single_escape_blocks[1] > 0:
                    if 'MinXEscape' in available_x_list and x_loc \
                            == global_x_position:
                        pass
                    else:
                        x_loc += escape_route_width
                    for x_pos in range(max_seats_single_escape_blocks[1]):
                        if x_pos == 0:
                            x_loc += lx_comp_width / 2
                        else:
                            x_loc += lx_comp_width
                        pos = gp_Pnt(x_loc, y_loc, furniture_surface_z)
                        obj_locations.append(pos)
                        if len(obj_locations) == requested_amount:
                            break
                    x_loc += lx_comp_width / 2
                if len(obj_locations) == requested_amount:
                    break
            y_loc += ly_comp / 2 + escape_route_width
        if switch:
            old_obj_locations = obj_locations
            new_obj_locations = []
            for loc in obj_locations:
                new_obj_locations.append(gp_Pnt(loc.Y(), loc.X(), loc.Z()))
            obj_locations = new_obj_locations
        obj_trsfs = PyOCCTools.generate_obj_trsfs(obj_locations,
                                                  compound_center_lower,
                                                  rotation_angle)
        footprints = []
        for trsf in obj_trsfs:
            footprints.append(
                BRepBuilderAPI_Transform(footprint_shape, trsf).Shape())
        escape_shape = PyOCCTools.triangulate_bound_shape(furniture_surface,
                                                          footprints)
        add_new_escape_shapes = []
        for door in doors:
            reverse=False
            (min_box, max_box) = PyOCCTools.simple_bounding_box([
                door.bound_shape])
            door_lower_pnt1 = gp_Pnt(*min_box)
            door_lower_pnt2 = gp_Pnt(max_box[0], max_box[1], min_box[2])
            base_line_pnt1 = door_lower_pnt1
            base_line_pnt2 = door_lower_pnt2
            door_width = door_lower_pnt1.Distance(door_lower_pnt2)
            p1 = PyOCCTools.get_points_of_minimum_point_shape_distance(
                door_lower_pnt1, escape_shape)
            p2 = PyOCCTools.get_points_of_minimum_point_shape_distance(
                door_lower_pnt2, escape_shape)
            if ((p1[0][2] or p2[0][2]) and BRepExtrema_DistShapeShape(
                    door.bound_shape, escape_shape,
                           Extrema_ExtFlag_MIN).Value()) > 0.001:
                # add closest path to escape route
                # ensure that neither the lower points of the door nor
                # the door shape itself touches the escape
                # shape. The escape shape may be smaller than the escape
                # route shape
                if p1[0][1].Distance(p2[0][1]) > 0.9:
                    # check of the closest points on the escape_shape are
                    # very close to each other. In this case, the generation
                    # of a new escape path cannot be guaranteed
                    reverse = False
                    # add_escape_shape = PyOCCTools.make_faces_from_pnts([p1[0][0],
                    #                                                    p2[0][0],
                    #                                                    p2[0][1], p1[0][1]])
                    # if add_escape_shape.IsNull():
                    add_escape_shape = PyOCCTools.get_projection_of_bounding_box(
                        [BRepBuilderAPI_MakeVertex(
                            p).Vertex()
                         for p in [p1[0][0], p2[0][0],
                                   p2[0][1],
                                   p1[0][1]]], proj_type='z', value=p1[0][1].Z())
                    add_new_escape_shapes.append(add_escape_shape)
                else:
                    if p1[0][2] > p2[0][2]:
                        base_line_pnt1 = p1[0][0]
                        base_line_pnt2 = p1[0][1]
                    else:
                        base_line_pnt1 = p2[0][0]
                        base_line_pnt2 = p2[0][1]

            # add square space in front of doors, depth = escape route width
            d = gp_Dir(gp_Vec(base_line_pnt1, base_line_pnt2))
            new_dir = d.Rotated(gp_Ax1(base_line_pnt1, gp_Dir(0, 0, 1)),
                     math.radians(90))
            moved_pnt1 = PyOCCTools.move_bound_in_direction_of_normal(
                                BRepBuilderAPI_MakeVertex(base_line_pnt1).Vertex(),
                                max(escape_route_width, door_width),
                          move_dir=new_dir, reverse=reverse)
            moved_dist = BRepExtrema_DistShapeShape(moved_pnt1,
                                                  furniture_surface,
                                                  Extrema_ExtFlag_MIN).Value()
            if abs(moved_dist) > 1e-3:
                reverse = True
                moved_pnt1 = PyOCCTools.move_bound_in_direction_of_normal(
                    BRepBuilderAPI_MakeVertex(base_line_pnt1).Vertex(),
                    max(escape_route_width, door_width), move_dir=new_dir, reverse=reverse)
            if reverse:
                moved_pnt2 = PyOCCTools.move_bound_in_direction_of_normal(
                    BRepBuilderAPI_MakeVertex(base_line_pnt2).Vertex(),
                    max(escape_route_width, door_width), move_dir=new_dir, reverse=reverse)
            else:
                moved_pnt2 = PyOCCTools.move_bound_in_direction_of_normal(
                    BRepBuilderAPI_MakeVertex(base_line_pnt2).Vertex(),
                    max(escape_route_width, door_width), move_dir=new_dir,
                                                         reverse=reverse)
            add_escape_shape = PyOCCTools.make_faces_from_pnts([base_line_pnt1,
                                                                base_line_pnt2,
                                                                BRep_Tool.Pnt(moved_pnt2),
                                                                BRep_Tool.Pnt(moved_pnt1)])
            add_new_escape_shapes.append(add_escape_shape)
            distance_new_escape = BRepExtrema_DistShapeShape(
                add_escape_shape, escape_shape).Value()
            distance_mp1 = BRepExtrema_DistShapeShape(
                moved_pnt1, escape_shape).Value()
            distance_mp2 = BRepExtrema_DistShapeShape(
                moved_pnt2, escape_shape).Value()
            if distance_new_escape > 1e-3:
                new_dist_pnts2 = PyOCCTools.get_points_of_minimum_point_shape_distance(
                    BRep_Tool.Pnt(moved_pnt2), escape_shape)
                new_dist_pnts1 = (
                    PyOCCTools.get_points_of_minimum_point_shape_distance(
                    BRep_Tool.Pnt(moved_pnt1), escape_shape))
                add_escape_shape2 = PyOCCTools.make_faces_from_pnts([
                    new_dist_pnts1[0][0], new_dist_pnts2[0][0],
                    new_dist_pnts2[0][1], new_dist_pnts1[0][1]])
                add_new_escape_shapes.append(add_escape_shape2)
            elif (distance_mp1 and distance_mp2) > 1e-3:
                if reverse:
                    min_dist_dir = gp_Dir(*[-1 * d for d in new_dir.Coord()])
                else:
                    min_dist_dir = new_dir
                extruded_escape_shape = PyOCCTools.extrude_face_in_direction(escape_shape,
                                                                 0.1)
                min_p1_new = PyOCCTools.find_min_distance_along_direction(
                    BRep_Tool.Pnt(moved_pnt1), min_dist_dir,
                    extruded_escape_shape)
                min_p2_new = PyOCCTools.find_min_distance_along_direction(
                    BRep_Tool.Pnt(moved_pnt2), min_dist_dir,
                    extruded_escape_shape)

                add_escape_shape3 = \
                    PyOCCTools.get_projection_of_bounding_box([moved_pnt1, moved_pnt2,
                                              *[BRepBuilderAPI_MakeVertex(
                                                  p).Vertex()
                                               for p in
                                               [min_p2_new[1], min_p1_new[1]]]],
                                              proj_type='z',
                                              value=p1[0][1].Z())
                add_new_escape_shapes.append(add_escape_shape3)

        if add_new_escape_shapes:
            sewed_shape = PyOCCTools.fuse_shapes([escape_shape,
                                                  *add_new_escape_shapes])
        else:
            sewed_shape = escape_shape
        # unified_sewed_shape = PyOCCTools.unify_shape(sewed_shape)
        solid_sewed_shape = PyOCCTools.make_solid_from_shape(PyOCCTools,
                                                            sewed_shape)
        # unified_sewed_shape = PyOCCTools.unify_shape(solid_sewed_shape)

        cleaned_obj_trsfs = []
        cleaned_obj_locations = []
        cleaned_footprints = []
        escape_area = PyOCCTools.get_shape_area(sewed_shape)
        box_footprints = [PyOCCTools.enlarge_bounding_box_shape_in_dir(f) for
                          f in footprints]
        solid_box_footprints = [PyOCCTools.make_solid_from_shape(
            PyOCCTools, ft) for ft in box_footprints]

        for i, footprint in enumerate(solid_box_footprints):
            foot_dist = BRepExtrema_DistShapeShape(sewed_shape, footprint,
                                                   Extrema_ExtFlag_MIN).Value()
            if abs(foot_dist) < 1e-3:
                common_algo = BRepAlgoAPI_Common(sewed_shape, footprint)
                common_algo.Build()
                if not common_algo.IsDone():
                    raise RuntimeError("Intersection computation failed.")
                overlap_shape = common_algo.Shape()
                # explorer = TopExp_Explorer(overlap_shape, TopAbs_SOLID)
                # has_overlap = explorer.More()
                if overlap_shape:
                    overlap_area = PyOCCTools.get_shape_area(overlap_shape)
                    # print(overlap_area)
                    if overlap_area < 0.02: # allow small overlapping
                        # with escape routes (10cm2)
                        cleaned_obj_trsfs.append(obj_trsfs[i])
                        cleaned_footprints.append(footprints[i])
                        cleaned_obj_locations.append(obj_locations[i])
                else:
                    cleaned_obj_trsfs.append(obj_trsfs[i])
                    cleaned_footprints.append(footprints[i])
                    cleaned_obj_locations.append(obj_locations[i])
            else:
                cleaned_obj_trsfs.append(obj_trsfs[i])
                cleaned_obj_locations.append(obj_locations[i])
                cleaned_footprints.append(footprints[i])

        self.logger.warning(f"removed {len(obj_trsfs)-len(cleaned_obj_trsfs)} "
                            f"furniture objects to guarantee escape route "
                            f"compliance. A total number of "
                            f"{len(cleaned_obj_trsfs)} furniture elements is "
                            f"positioned, based on "
                            f"{self.playground.sim_settings.furniture_amount} "
                            f"requested elements. ")
        return cleaned_obj_locations, cleaned_obj_trsfs


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
