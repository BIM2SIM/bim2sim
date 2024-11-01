import math
import pathlib
import random
import shutil
import tempfile
from pathlib import Path
import stl
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex, \
    BRepBuilderAPI_Transform
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.BRepLib import BRepLib_FuseEdges
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from OCC.Core.StlAPI import StlAPI_Writer, StlAPI_Reader
from OCC.Core.TopoDS import TopoDS_Compound, TopoDS_Builder, TopoDS_Shape
from OCC.Core.gp import gp_Pnt, gp_XYZ, gp_Trsf
from stl import mesh

from bim2sim.elements.mapping.units import ureg
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.utils.utils_visualization import \
    VisualizationUtils
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.airterminal import \
    AirTerminal
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.furniture import \
    Furniture
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
            if bound.bound_element_type in ['Floor']:
                floor.append(bound)
        if len(floor) == 1:
            furniture_surface = floor[0]
        elif len(floor) > 1:
            # raise NotImplementedError('multiple floors detected. Not '
            #                           'implemented. Merge shapes before '
            #                           'proceeding to avoid errors. ')
            furniture_surface = floor[0]
        openfoam_case.furniture_surface = furniture_surface

    @staticmethod
    def init_zone(openfoam_case, elements, idf, openfoam_elements,
                  space_guid='2RSCzLOBz4FAK$_wE8VckM'):
        # guid '2RSCzLOBz4FAK$_wE8VckM' Single office has no 2B bounds
        # guid '3$f2p7VyLB7eox67SA_zKE' Traffic area has 2B bounds

        openfoam_case.current_zone = elements[space_guid]
        openfoam_case.current_bounds = openfoam_case.current_zone.space_boundaries
        if hasattr(openfoam_case.current_zone, 'space_boundaries_2B'):  # todo
            # remove 2b
            openfoam_case.current_bounds += openfoam_case.current_zone.space_boundaries_2B
        for bound in openfoam_case.current_bounds:
            new_stl_bound = StlBound(bound, idf)
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
        if bim2sim_heaters:
            # todo: get product shape of space heater
            # identify space heater in current zone (maybe flag is already
            # set from preprocessing in bim2sim
            # get TopoDS_Shape for further preprocessing of the shape.
            if not hasattr(openfoam_case.current_zone, 'heaters'):
                openfoam_case.current_zone.heaters = []
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
                front_surface_min_max = (
                heater_bbox_shape[0], (heater_bbox_shape[1][0],
                                       heater_bbox_shape[0][1],
                                       heater_bbox_shape[1][2]))
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
            #raise NotImplementedError(f"geometric preprocessing is not "
            #                          f"implemented for IFC-based
            #                          SpaceHeaters")
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
                    print('more than one heater required, not implemented. '
                          'Heater may be unreasonably large. ')
                    heater_window = openings[0]

            else:
                print('No window found for positioning of heater.')
                return
            heater_shape = self.get_boundaries_of_heater(openfoam_case,
                                                         heater_window)
            heater_shapes.append(heater_shape)

        # heater_shape holds side surfaces of space heater.
        for i, shape in enumerate(heater_shapes):

            heater = Heater(f'heater{i}', shape,
                            openfoam_case.openfoam_triSurface_dir)
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
            print('multiple ceilings/roofs detected. Not implemented. '
                  'Merge shapes before proceeding to avoid errors. ')
            air_terminal_surface = ceiling_roof[0]
        bim2sim_airterminals = filter_elements(elements, 'AirTerminal')
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
                source_shape = PyOCCTools.scale_shape(inlet_base_shape, 0.3,
                                     predefined_center=PyOCCTools.get_center_of_face(inlet_base_shape))
                diffuser_shape = PyOCCTools.triangulate_bound_shape(
                    inlet_base_shape, [source_shape])
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
                    inlet_shape = BRepBuilderAPI_Transform(air_terminal_compound,
                                                           trsf_inlet).Shape()
                    inlet_diffuser_shape = None
                    inlet_source_shape = None
                    inlet_box_shape = None
                    if diffuser_shape:
                        inlet_diffuser_shape = BRepBuilderAPI_Transform(
                            diffuser_shape,
                            trsf_inlet).Shape()
                    if source_shape:
                        inlet_source_shape = BRepBuilderAPI_Transform(source_shape,
                                                                      trsf_inlet).Shape()
                    if air_terminal_box:
                        inlet_box_shape = BRepBuilderAPI_Transform(air_terminal_box,
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
                    inlet_shapes.extend([inlet_min_max_box.Shape(), inlet_min_max])
                    inlet = AirTerminal(f'inlet_{len(inlets)}', inlet_shapes,
                                        openfoam_case.openfoam_triSurface_dir,
                                        inlet_type)
                    inlet.solid = inlet_solid
                    inlets.append(inlet)
                if 'abluft' in airt.name.lower():
                    trsf_outlet = gp_Trsf()
                    trsf_outlet.SetTranslation(compound_center_lower,
                                               gp_Pnt(*airt_center_lower))
                    outlet_shape = BRepBuilderAPI_Transform(air_terminal_compound,
                                                            trsf_outlet).Shape()
                    # Todo: remove hardcoded rotations
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
                        outlet_diffuser_shape = PyOCCTools.rotate_by_deg(outlet_diffuser_shape,
                                                                axis='z',
                                                                rotation=90)
                    if source_shape:
                        outlet_source_shape = BRepBuilderAPI_Transform(source_shape,
                                                                       trsf_outlet).Shape()
                        outlet_source_shape = PyOCCTools.rotate_by_deg(outlet_source_shape,
                                                                axis='z',
                                                                rotation=90)

                    if air_terminal_box:
                        outlet_box_shape = BRepBuilderAPI_Transform(
                            air_terminal_box,
                            trsf_outlet).Shape()
                        outlet_box_shape = PyOCCTools.rotate_by_deg(
                            outlet_box_shape,
                            axis='z',
                            rotation=90)
                    outlet_shapes = [outlet_diffuser_shape, outlet_source_shape,
                                     outlet_box_shape]
                    outlet_min_max = PyOCCTools.simple_bounding_box(outlet_shape)
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


                # export moved inlet and outlet shapes
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
                print('multiple ceilings/roofs detected. Not implemented. '
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

    def adjust_refinements(self, case, elements):
        """
        Compute surface and region refinements for air terminals and other
        interior elements.
        """
        bM_size = self.playground.sim_settings.mesh_size
        if self.playground.sim_settings.add_airterminals:
            for terminal in [elements['inlet_AirTerminal'], elements[
                'outlet_AirTerminal']]:
                if (terminal.air_type == 'inlet' and
                    self.playground.sim_settings.inlet_type == 'Plate') or \
                        (terminal.air_type == 'outlet' and \
                         self.playground.sim_settings.outlet_type == 'Plate'):
                    diff = terminal.diffuser.tri_geom
                    box = terminal.box.tri_geom
                    dist = OpenFOAMUtils.get_min_refdist_between_shapes(
                        diff, box)
                    ref_level = OpenFOAMUtils.get_refinement_level(dist,
                                                                   bM_size)
                    terminal.diffuser.refinement_level = \
                        terminal.box.refinement_level = ref_level
                    terminal.refinement_zone_level_small[1] = \
                        terminal.diffuser.refinement_level[0]
                    terminal.refinement_zone_level_large[1] = \
                        terminal.diffuser.refinement_level[0] - 1
                else:
                    verts = OpenFOAMUtils.detriangulize(OpenFOAMUtils,
                                                        terminal.diffuser.tri_geom)
                    min_dist = OpenFOAMUtils.get_min_internal_dist(verts)
                    terminal.diffuser.refinement_level = \
                        OpenFOAMUtils.get_refinement_level(min_dist, bM_size)
                    terminal.refinement_zone_level_small[1] = \
                        terminal.diffuser.refinement_level[0]
                    terminal.refinement_zone_level_large[1] = \
                        terminal.diffuser.refinement_level[0] - 1

        interior = dict()  # Add other interior equipment and topoDS Shape
        if self.playground.sim_settings.add_heating:
            interior = {elements['heater1']: elements[
                'heater1'].heater_surface.tri_geom}
        for i, elem in enumerate(interior.keys()):
            verts = OpenFOAMUtils.detriangulize(OpenFOAMUtils, interior[elem])
            int_dist = OpenFOAMUtils.get_min_internal_dist(verts)
            wall_dist = OpenFOAMUtils.get_min_refdist_between_shapes(interior[
                                                                         elem],
                                                                     case.current_zone.space_shape)
            obj_dist = wall_dist
            if len(interior) > 1:
                for objs in list(interior.keys())[i:]:
                    new_dist = OpenFOAMUtils.get_min_refdist_between_shapes(
                        interior[elem], interior[objs])
                    if new_dist < obj_dist: obj_dist = new_dist
            min_dist_ext = min(wall_dist, obj_dist)
            ref_level_reg = OpenFOAMUtils.get_refinement_level(min_dist_ext,
                                                               bM_size)
            if int_dist < min_dist_ext:
                ref_level_surf = OpenFOAMUtils.get_refinement_level(
                    int_dist, bM_size)
            else:
                ref_level_surf = ref_level_reg
            elem.refinement_level = ref_level_reg
            interior[elem].refinement_level = ref_level_surf

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
                                x_gap=0.1, y_gap=0.1, side_gap=0.2):
        meshes = []
        chair_shape = None
        desk_shape = None
        furniture_path = (Path(__file__).parent.parent / 'assets' / 'geometry' /
                          'furniture_people_compositions')
        furniture_shapes = []
        if self.playground.sim_settings.furniture_setting in ['Office',
                                                              'Concert',
                                                              'Meeting',
                                                              'Classroom']:
            chair_shape = TopoDS_Shape()
            stl_reader = StlAPI_Reader()
            stl_reader.Read(chair_shape,
                            furniture_path.as_posix() + '/' +
                            "new_compChair.stl")
            furniture_shapes.append(chair_shape)
        if self.playground.sim_settings.furniture_setting in ['Office',
                                                              'Meeting',
                                                              'Classroom']:
            desk_shape = TopoDS_Shape()
            stl_reader = StlAPI_Reader()
            stl_reader.Read(desk_shape,
                            furniture_path.as_posix() + '/' +
                            "new_compDesk.stl")
            furniture_shapes.append(desk_shape)

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
                                                              'Meeting']:
            # todo: remove Office and Meeting setup here and replace by
            #  appropriate other setup
            #  Meeting: 1 two-sided table (rotate every other table by 180deg)
            #  Office: similar to meeting, but spread tables in Office.
            # calculate amount of rows
            furniture_locations, furniture_trsfs = self.generate_grid_positions(
                furniture_surface.bound, furniture_compound,
                requested_amount, x_gap, y_gap, side_gap)

        # furniture_position = gp_Pnt(
        #     furniture_surface.bound.bound_center.X(),  #+ lx / 4,
        #     furniture_surface.bound.bound_center.Y(), # + ly / 4,
        #     furniture_surface.bound.bound_center.Z(),
        # )
        furniture_items = []

        for i, trsf in enumerate(furniture_trsfs):
            furniture_shape = BRepBuilderAPI_Transform(furniture_compound,
                                                       trsf).Shape()
            furniture_min_max = PyOCCTools.simple_bounding_box(furniture_shape)
            if chair_shape:
                new_chair_shape = BRepBuilderAPI_Transform(chair_shape,
                                                           trsf).Shape()
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
        available_trsfs = openfoam_case.furniture_trsfs

        furniture_path = (Path(__file__).parent.parent / 'assets' / 'geometry' /
                          'furniture_people_compositions')
        # people_shapes = []
        people_items = []
        people_amount = self.playground.sim_settings.people_amount

        if self.playground.sim_settings.people_setting in ['Seated']:
            person_path = (furniture_path.as_posix() + '/' +
                           "manikin_split_body_head.stl")
            person_shape = TopoDS_Shape()
            stl_reader = StlAPI_Reader()
            stl_reader.Read(person_shape, person_path)
            # people_shapes.append(person_shape)
            if people_amount > len(available_trsfs):
                people_amount = len(available_trsfs)
        elif (self.playground.sim_settings.people_setting in ['Standing'] and
              len(available_trsfs) == 0):
            person_path = (Path(__file__).parent.parent / 'assets' /
                           'geometry' / 'people' / "manikin_standing.stl")
            person_shape = TopoDS_Shape()
            stl_reader = StlAPI_Reader()
            stl_reader.Read(person_shape, person_path.as_posix())
            # people_shapes.append(person_shape)
            people_locations, available_trsfs = self.generate_grid_positions(
                furniture_surface.bound, person_shape,
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
            person = People(new_person_shape, trsf, person_path,
                            openfoam_case.openfoam_triSurface_dir, f'Person{i}',
                            power=openfoam_case.current_zone.fixed_heat_flow_rate_persons.to(
                                ureg.watt).m)
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

    def generate_grid_positions(self, bound, obj_to_be_placed,
                                requested_amount,
                                x_gap=0.2, y_gap=0.35,
                                side_gap=0.6):
        surf_min_max = PyOCCTools.simple_bounding_box(bound.bound_shape)
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
                pos = gp_Pnt(x_loc, y_loc, bound.bound_center.Z())
                obj_locations.append(pos)
                if len(obj_locations) == requested_amount:
                    break
            if len(obj_locations) == requested_amount:
                break
        obj_trsfs = self.generate_obj_trsfs(obj_locations,
                                            compound_center_lower)
        return obj_locations, obj_trsfs

    def generate_obj_trsfs(self, obj_locations: list[gp_Pnt],
                           obj_pos_to_be_transformed: gp_Pnt):
        obj_trsfs = []
        for loc in obj_locations:
            trsf = gp_Trsf()
            trsf.SetTranslation(obj_pos_to_be_transformed,
                                loc)
            obj_trsfs.append(trsf)
        return obj_trsfs


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


