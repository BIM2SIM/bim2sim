import shutil
import tempfile
from pathlib import Path

import stl
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from OCC.Core.StlAPI import StlAPI_Writer
from OCC.Core.TopoDS import TopoDS_Compound, TopoDS_Builder
from OCC.Core.gp import gp_Pnt, gp_XYZ
from stl import mesh

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
        # setup geometry for constant
        self.export_stlbound_triSurface(openfoam_case, openfoam_elements)
        self.export_heater_triSurface(openfoam_elements)

        return openfoam_case, openfoam_elements

    @staticmethod
    def init_zone(openfoam_case, elements, idf, openfoam_elements,
                  space_guid='2RSCzLOBz4FAK$_wE8VckM'):
        # guid '2RSCzLOBz4FAK$_wE8VckM' Single office has no 2B bounds
        # guid '3$f2p7VyLB7eox67SA_zKE' Traffic area has 2B bounds

        openfoam_case.current_zone = elements[space_guid]
        openfoam_case.current_bounds = openfoam_case.current_zone.space_boundaries
        if hasattr(openfoam_case.current_zone, 'space_boundaries_2B'):
            openfoam_case.current_bounds += openfoam_case.current_zone.space_boundaries_2B
        for bound in openfoam_case.current_bounds:
            new_stl_bound = StlBound(bound, idf)
            openfoam_elements[new_stl_bound.solid_name] = new_stl_bound
            # openfoam_case.stl_bounds.append(new_stl_bound)

    def init_heater(self, openfoam_case, elements, openfoam_elements):
        # create Shape for heating in front of window unless space heater is
        # available in ifc.
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
                        #abs(openfoam_case.current_zone.zone_heat_conduction))
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
