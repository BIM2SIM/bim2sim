import pathlib
import shutil
import tempfile
from pathlib import Path

import stl
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex, \
    BRepBuilderAPI_Transform
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from OCC.Core.StlAPI import StlAPI_Writer, StlAPI_Reader
from OCC.Core.TopoDS import TopoDS_Compound, TopoDS_Builder, TopoDS_Shape
from OCC.Core.gp import gp_Pnt, gp_XYZ, gp_Trsf
from stl import mesh

from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.airterminal import \
    AirTerminal
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.furniture import \
    Furniture
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.heater import \
    Heater
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.stlbound import \
    StlBound
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
        self.init_furniture(openfoam_case, elements, openfoam_elements)
        # setup geometry for constant
        self.export_stlbound_triSurface(openfoam_case, openfoam_elements)
        self.export_heater_triSurface(openfoam_elements)
        self.export_airterminal_triSurface(openfoam_elements)
        self.export_furniture_triSurface(openfoam_elements)

        return openfoam_case, openfoam_elements

    @staticmethod
    def init_zone(openfoam_case, elements, idf, openfoam_elements,
                  space_guid='2RSCzLOBz4FAK$_wE8VckM'):
        # guid '2RSCzLOBz4FAK$_wE8VckM' Single office has no 2B bounds
        # guid '3$f2p7VyLB7eox67SA_zKE' Traffic area has 2B bounds

        openfoam_case.current_zone = elements[space_guid]
        openfoam_case.current_bounds = openfoam_case.current_zone.space_boundaries
        if hasattr(openfoam_case.current_zone, 'space_boundaries_2B'): # todo
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
        if bim2sim_heaters:
            # todo: get product shape of space heater
            # identify space heater in current zone (maybe flag is already
            # set from preprocessing in bim2sim
            # get TopoDS_Shape for further preprocessing of the shape.
            raise NotImplementedError(f"geometric preprocessing is not "
                                      f"implemented for IFC-based SpaceHeaters")
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
        # heater_shape holds side surfaces of space heater.
        heater = Heater('heater1', heater_shape,
                        openfoam_case.openfoam_triSurface_dir)
        # abs(openfoam_case.current_zone.zone_heat_conduction))
        openfoam_elements[heater.solid_name] = heater

        pass

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
        air_terminal_surface = None
        stl_bounds = filter_elements(openfoam_elements, 'StlBound')

        if 'AirTerminal' in [name.__class__.__name__ for name in
                             list(elements.values())]:
            # todo: get product shape of air terminals
            # identify air terminals in current zone (maybe flag is already
            # set from preprocessing in bim2sim
            # get TopoDS_Shape for further preprocessing of the shape.
            pass
        else:
            ceiling_roof = []
            for bound in stl_bounds:
                if (bound.bound_element_type in ['Ceiling', 'Roof'] ):
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
        inlet, outlet = self.create_airterminal_shapes(openfoam_case,
                                                       air_terminal_surface,
                                                       inlet_type, outlet_type)
        openfoam_elements[inlet.solid_name] = inlet
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
                    Path(__file__).parent.parent / 'data' / 'geometry' /
                    'drallauslass_ersatzmodell.stl'):
                meshes.append(m)
        else:
            for m in mesh.Mesh.from_multi_file(
                    Path(__file__).parent.parent / 'data' / 'geometry' /
                    'AirTerminal.stl'):
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

    def init_furniture(self, openfoam_case, elements, openfoam_elements):
        if not self.playground.sim_settings.add_furniture:
            return
        furniture_surface = None
        stl_bounds = filter_elements(openfoam_elements, 'StlBound')

        if 'Furniture' in [name.__class__.__name__ for name in
                           list(elements.values())]:
            # todo: get product shape of furniture
            # identify furniture in current zone (maybe flag is already
            # set from preprocessing in bim2sim
            # get TopoDS_Shape for further preprocessing of the shape.
            raise NotImplementedError('Furniture found in bim2sim, it cannot '
                                      'be handled yet. No furniture is added.')
            pass
        else:
            floor = []
            for bound in stl_bounds:
                if bound.bound_element_type in ['Floor']:
                    floor.append(bound)
            if len(floor) == 1:
                furniture_surface = floor[0]
            elif len(floor) > 1:
                raise NotImplementedError('multiple floors detected. Not '
                                          'implemented. Merge shapes before '
                                          'proceeding to avoid errors. ')
                furniture_surface = floor[0]

        furniture = self.create_furniture_shapes(openfoam_case,
                                                furniture_surface)
        openfoam_elements[furniture.solid_name] = furniture

    def create_furniture_shapes(self, openfoam_case, furniture_surface):
        surf_min_max = PyOCCTools.simple_bounding_box(
            furniture_surface.bound.bound_shape)
        lx = surf_min_max[1][0] - surf_min_max[0][0]
        ly = surf_min_max[1][1] - surf_min_max[0][1]
        meshes = []

        furniture_shape = TopoDS_Shape()
        furniture_path = (Path(__file__).parent.parent / 'data' / 'geometry' /
                          'DeskAndChairWithMen.stl')
        stl_reader = StlAPI_Reader()
        stl_reader.Read(furniture_shape, furniture_path.as_posix())

        furniture_compound = TopoDS_Compound()
        builder = TopoDS_Builder()
        builder.MakeCompound(furniture_compound)
        shapelist = [shape for shape in [furniture_shape] if shape is not None]
        for shape in shapelist:
            builder.Add(furniture_compound, shape)

        compound_bbox = PyOCCTools.simple_bounding_box(furniture_compound)
        compound_center = PyOCCTools.get_center_of_shape(
            furniture_compound).Coord()
        compound_center_lower = gp_Pnt(compound_center[0], compound_center[1],
                                       compound_bbox[0][2])
        trsf_furniture = gp_Trsf()
        furniture_position = gp_Pnt(
            furniture_surface.bound.bound_center.X() + lx/4,
            furniture_surface.bound.bound_center.Y() + ly/4,
            furniture_surface.bound.bound_center.Z(),
        )
        trsf_furniture.SetTranslation(compound_center_lower,
                                      furniture_position)
        furniture_shape = BRepBuilderAPI_Transform(furniture_shape,
                                                   trsf_furniture).Shape()
        furniture_min_max = PyOCCTools.simple_bounding_box(furniture_shape)
        furniture = Furniture(furniture_shape, openfoam_case.openfoam_triSurface_dir,
                              'DeskAndChairWithMen', furniture_min_max)
        return furniture

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
