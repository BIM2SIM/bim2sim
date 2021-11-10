# todo delete this after seperating energyplus tasks into single tasks
"""This module holds tasks related to bps"""
import os

import ifcopenshell
import pandas as pd

from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeVertex
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from OCC.Core.gp import gp_XYZ, gp_Pln, gp_Pnt
from OCC.Core.TopoDS import topods_Wire, topods_Face
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_WIRE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepTools import BRepTools_WireExplorer, breptools_UVBounds
from OCC.Core._Geom import Handle_Geom_Plane_DownCast
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCC.Core.StlAPI import StlAPI_Writer
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.BRepGProp import brepgprop_SurfaceProperties
from OCC.Core.GProp import GProp_GProps
from stl import stl
from stl import mesh

from bim2sim.task.base import ITask
from bim2sim.decision import BoolDecision, DecisionBunch
# todo new name :)
from bim2sim.utilities.pyocc_tools import PyOCCTools


class ExportEP(ITask):
    """Exports an EnergyPlus model based on IFC information"""

    ENERGYPLUS_VERSION = "9-4-0"

    reads = ('instances', 'ifc', 'idf',)
    final = True

    def run(self, workflow, instances, ifc, idf):
        # self._get_neighbor_bounds(instances)
        # self._compute_2b_bound_gaps(instances) # todo: fix
        # subprocess.run(['energyplus', '-x', '-c', '--convert-only', '-d', self.paths.export, idf.idfname])
        self._export_surface_areas(instances, idf)  # todo: fix
        self._export_space_info(instances, idf)
        self._export_boundary_report(instances, idf, ifc)
        self.logger.info("IDF generation finished!")

        # idf.view_model()
        # self._export_to_stl_for_cfd(instances, idf)
        # self._display_shape_of_space_boundaries(instances)
        run_decision = BoolDecision(
            question="Do you want to run the full energyplus simulation"
                     " (annual, readvars)?",
            global_key='EnergyPlus.FullRun')
        yield DecisionBunch([run_decision])
        ep_full = run_decision.value
        design_day = False
        if not ep_full:
            design_day = True
        output_string = str(self.paths.export / 'EP-results/')
        idf.run(output_directory=output_string, readvars=ep_full, annual=ep_full, design_day=design_day)
        # self._visualize_results(csv_name=paths.export / 'EP-results/eplusout.csv')


    def _export_to_stl_for_cfd(self, instances, idf):
        self.logger.info("Export STL for CFD")
        stl_name = idf.idfname.replace('.idf', '')
        stl_name = stl_name.replace(str(self.paths.export), '')
        self.export_bounds_to_stl(instances, stl_name)
        self.export_bounds_per_space_to_stl(instances, stl_name)
        self.export_2B_bounds_to_stl(instances, stl_name)
        self.combine_stl_files(stl_name)
        self.export_space_bound_list(instances)

    @staticmethod
    def export_space_bound_list(instances, paths):
        stl_dir = str(paths.export)
        space_bound_df = pd.DataFrame(columns=["space_id", "bound_ids"])
        for inst in instances:
            if not instances[inst].ifc.is_a("IfcSpace"):
                continue
            space = instances[inst]
            bound_names = []
            for bound in space.space_boundaries:
                bound_names.append(bound.guid)
            space_bound_df = space_bound_df.append({'space_id': space.guid, 'bound_ids': bound_names},
                                                   ignore_index=True)
        space_bound_df.to_csv(stl_dir + "space_bound_list.csv")

    @staticmethod
    def combine_stl_files(stl_name, paths):
        stl_dir = str(paths.export)
        with open(stl_dir + stl_name + "_combined_STL.stl", 'wb+') as output_file:
            for i in os.listdir(stl_dir + 'STL/'):
                if os.path.isfile(os.path.join(stl_dir + 'STL/', i)) and (stl_name + "_cfd_") in i:
                    sb_mesh = mesh.Mesh.from_file(stl_dir + 'STL/' + i)
                    mesh_name = i.split("_", 1)[-1]
                    mesh_name = mesh_name.replace(".stl", "")
                    mesh_name = mesh_name.replace("$", "___")
                    sb_mesh.save(mesh_name, output_file, mode=stl.Mode.ASCII)

    @staticmethod
    def combine_space_stl_files(stl_name, space_name, paths):
        stl_dir = str(paths.export)
        os.makedirs(os.path.dirname(stl_dir + "space_stl/"), exist_ok=True)

        with open(stl_dir + "space_stl/" + "space_" + space_name + ".stl", 'wb+') as output_file:
            for i in os.listdir(stl_dir + 'STL/' + space_name + "/"):
                if os.path.isfile(os.path.join(stl_dir + 'STL/' + space_name + "/", i)) and (stl_name + "_cfd_") in i:
                    sb_mesh = mesh.Mesh.from_file(stl_dir + 'STL/' + i)
                    mesh_name = i.split("_", 1)[-1]
                    mesh_name = mesh_name.replace(".stl", "")
                    mesh_name = mesh_name.replace("$", "___")
                    sb_mesh.save(mesh_name, output_file, mode=stl.Mode.ASCII)

    def _export_surface_areas(self, instances, idf):
        """ combines sets of area sums and exports to csv """
        area_df = pd.DataFrame(
            columns=["granularity", "ID", "long_name", "out_bound_cond", "area_wall", "area_ceiling", "area_floor",
                     "area_roof", "area_window", "area_door", "total_surface_area", "total_opening_area"])
        surf = [s for s in idf.idfobjects['BuildingSurface:Detailed'.upper()] if s.Construction_Name != 'Air Wall']
        glazing = [g for g in idf.idfobjects['FenestrationSurface:Detailed'.upper()]]
        area_df = self._append_set_of_area_sum(area_df, granularity="GLOBAL", guid="GLOBAL", long_name="GLOBAL",
                                               surface=surf, glazing=glazing)
        zones = [z for z in idf.idfobjects['zone'.upper()]]
        zone_names = [z.Name for z in zones]

        for z_name in zone_names:
            surf_zone = [s for s in surf if s.Zone_Name == z_name]
            surf_names = [s.Name for s in surf_zone]
            long_name = instances[z_name].ifc.LongName
            glazing_zone = [g for g in glazing for s_name in surf_names if g.Building_Surface_Name == s_name]
            area_df = self._append_set_of_area_sum(area_df, granularity="ZONE", guid=z_name, long_name=long_name,
                                                   surface=surf_zone, glazing=glazing_zone)
        area_df.to_csv(path_or_buf=str(self.paths.export) + "/area.csv")

    def _append_set_of_area_sum(self, area_df, granularity, guid, long_name, surface, glazing):
        """ generate set of area sums for a given granularity for outdoor, surface and adiabatic boundary conditions.
        Appends set to a given dataframe.
        """
        surf_outdoors = [s for s in surface if s.Outside_Boundary_Condition == "Outdoors"]
        surf_surface = [s for s in surface if s.Outside_Boundary_Condition == "Surface"]
        surf_adiabatic = [s for s in surface if s.Outside_Boundary_Condition == "Adiabatic"]
        glazing_outdoors = [g for g in glazing if g.Outside_Boundary_Condition_Object == ""]
        glazing_surface = [g for g in glazing if g.Outside_Boundary_Condition_Object != ""]
        glazing_adiabatic = []
        area_df = area_df.append([
            self._sum_of_surface_area(granularity=granularity, guid=guid, long_name=long_name, out_bound_cond="ALL",
                                      surface=surface, glazing=glazing),
            self._sum_of_surface_area(granularity=granularity, guid=guid, long_name=long_name,
                                      out_bound_cond="Outdoors",
                                      surface=surf_outdoors, glazing=glazing_outdoors),
            self._sum_of_surface_area(granularity=granularity, guid=guid, long_name=long_name, out_bound_cond="Surface",
                                      surface=surf_surface, glazing=glazing_surface),
            self._sum_of_surface_area(granularity=granularity, guid=guid, long_name=long_name,
                                      out_bound_cond="Adiabatic",
                                      surface=surf_adiabatic, glazing=glazing_adiabatic)
        ],
            ignore_index=True
        )
        return area_df

    @staticmethod
    def _sum_of_surface_area(granularity, guid, long_name, out_bound_cond, surface, glazing):
        """ generate row with sum of surface and opening areas to be appended to larger dataframe"""
        row = {
            "granularity": granularity,
            "ID": guid,
            "long_name": long_name,
            "out_bound_cond": out_bound_cond,
            "area_wall": sum(s.area for s in surface if s.Surface_Type == "Wall"),
            "area_ceiling": sum(s.area for s in surface if s.Surface_Type == "Ceiling"),
            "area_floor": sum(s.area for s in surface if s.Surface_Type == "Floor"),
            "area_roof": sum(s.area for s in surface if s.Surface_Type == "Roof"),
            "area_window": sum(g.area for g in glazing if g.Surface_Type == "Window"),
            "area_door": sum(g.area for g in glazing if g.Surface_Type == "Door"),
            "total_surface_area": sum(s.area for s in surface),
            "total_opening_area": sum(g.area for g in glazing)
        }
        return row

    def _export_space_info(self, instances, idf):
        space_df = pd.DataFrame(
            columns=["ID", "long_name", "space_center", "space_volume"])
        for inst in instances:
            if not instances[inst].ifc.is_a("IfcSpace"):
                continue
            space = instances[inst]
            space_df = space_df.append([
                {
                    "ID": space.guid,
                    "long_name": space.ifc.LongName,
                    "space_center": space.space_center.XYZ().Coord(),
                    "space_volume": space.space_volume.m
                }],
                ignore_index=True
            )
        space_df.to_csv(path_or_buf=str(self.paths.export) + "/space.csv")

    def _export_boundary_report(self, instances, idf, ifc):
        bound_count = pd.DataFrame(
            columns=["IFC_SB_all", "IFC_SB_2a", "IFC_SB_2b",
                     "BIM2SIM_SB_2b",
                     "IDF_all", "IDF_all_B", "IDF_ADB", "IDF_SFB", "IDF_ODB", "IDF_GDB", "IDF_VTB", "IDF_all_F",
                     "IDF_ODF", "IDF_INF"])
        ifc_bounds = ifc.by_type('IfcRelSpaceBoundary')
        bounds_2b = [instances[inst] for inst in instances if instances[inst].__class__.__name__ == "SpaceBoundary2B"]
        idf_all_b = [s for s in idf.idfobjects["BUILDINGSURFACE:DETAILED"]]
        idf_adb = [s for s in idf.idfobjects["BUILDINGSURFACE:DETAILED"] if s.Outside_Boundary_Condition == "Adiabatic"]
        idf_sfb = [s for s in idf.idfobjects["BUILDINGSURFACE:DETAILED"] if s.Outside_Boundary_Condition == "Surface"]
        idf_odb = [s for s in idf.idfobjects["BUILDINGSURFACE:DETAILED"] if s.Outside_Boundary_Condition == "Outdoors"]
        idf_gdb = [s for s in idf.idfobjects["BUILDINGSURFACE:DETAILED"] if s.Outside_Boundary_Condition == "Ground"]
        idf_vtb = [s for s in idf.idfobjects["BUILDINGSURFACE:DETAILED"] if s.Construction_Name == "Air Wall"]
        idf_all_f = [f for f in idf.idfobjects["FENESTRATIONSURFACE:DETAILED"]]
        idf_odf = [f for f in idf.idfobjects["FENESTRATIONSURFACE:DETAILED"] if
                   f.Outside_Boundary_Condition_Object == '']
        idf_inf = [f for f in idf.idfobjects["FENESTRATIONSURFACE:DETAILED"] if
                   f.Outside_Boundary_Condition_Object != '']
        bound_count = bound_count.append([
            {
                "IFC_SB_all": len(ifc_bounds),
                "IFC_SB_2a": len([b for b in ifc_bounds if b.Description == "2a"]),
                "IFC_SB_2b": len([b for b in ifc_bounds if b.Description == "2b"]),
                "BIM2SIM_SB_2b": len(bounds_2b),
                "IDF_all": len(idf_all_b) + len(idf_all_f),
                "IDF_all_B": len(idf_all_b),
                "IDF_ADB": len(idf_adb),
                "IDF_SFB": len(idf_sfb),
                "IDF_ODB": len(idf_odb),
                "IDF_GDB": len(idf_gdb),
                "IDF_VTB": len(idf_vtb),
                "IDF_all_F": len(idf_all_f),
                "IDF_ODF": len(idf_odf),
                "IDF_INF": len(idf_inf)
            }],
            ignore_index=True
        )
        bound_count.to_csv(path_or_buf=str(self.paths.export) + "/bound_count.csv")

    @staticmethod
    def _get_neighbor_bounds(instances):
        for inst in instances:
            this_obj = instances[inst]
            if not this_obj.ifc.is_a('IfcRelSpaceBoundary'):
                continue
            neighbors = this_obj.bound_neighbors

    def export_bounds_to_stl(self, instances, stl_name):
        """
        This function exports a space to an idf file.
        :param idf: idf file object
        :param space: Space instance
        :param zone: idf zone object
        :return:
        """
        for inst in instances:
            if not instances[inst].ifc.is_a("IfcRelSpaceBoundary"):
                continue
            inst_obj = instances[inst]
            if inst_obj.physical:
                name = inst_obj.guid
                stl_dir = str(self.paths.root) + "/export/STL/"
                this_name = stl_dir + str(stl_name) + "_cfd_" + str(name) + ".stl"
                os.makedirs(os.path.dirname(stl_dir), exist_ok=True)

                inst_obj.cfd_face = inst_obj.bound_shape
                if hasattr(inst_obj, 'related_opening_bounds'):
                    for opening in inst_obj.related_opening_bounds:
                        inst_obj.cfd_face = BRepAlgoAPI_Cut(inst_obj.cfd_face, opening.bound_shape).Shape()
                triang_face = BRepMesh_IncrementalMesh(inst_obj.cfd_face, 1)
                # Export to STL
                stl_writer = StlAPI_Writer()
                stl_writer.SetASCIIMode(True)
                stl_writer.Write(triang_face.Shape(), this_name)

    def export_bounds_per_space_to_stl(self, instances, stl_name):
        """
        This function exports a space to an idf file.
        :param idf: idf file object
        :param space: Space instance
        :param zone: idf zone object
        :return:
        """
        for inst in instances:
            if not instances[inst].ifc.is_a("IfcSpace"):
                continue
            space_obj = instances[inst]
            space_name = space_obj.guid
            stl_dir = str(self.paths.root) + "/export/STL/" + space_name + "/"
            os.makedirs(os.path.dirname(stl_dir), exist_ok=True)
            for inst_obj in space_obj.space_boundaries:
                if not inst_obj.physical:
                    continue
                bound_name = inst_obj.guid
                this_name = stl_dir + str(stl_name) + "_cfd_" + str(bound_name) + ".stl"
                inst_obj.cfd_face = inst_obj.bound_shape
                if hasattr(inst_obj, 'related_opening_bounds'):
                    for opening in inst_obj.related_opening_bounds:
                        inst_obj.cfd_face = BRepAlgoAPI_Cut(inst_obj.cfd_face, opening.bound_shape).Shape()
                triang_face = BRepMesh_IncrementalMesh(inst_obj.cfd_face, 1)
                # Export to STL
                stl_writer = StlAPI_Writer()
                stl_writer.SetASCIIMode(True)
                stl_writer.Write(triang_face.Shape(), this_name)
            self.combine_space_stl_files(stl_name, space_name)

    def _compute_2b_bound_gaps(self, instances):
        self.logger.info("Generate space boundaries of type 2B")
        inst_2b = dict()
        for inst in instances:
            if not instances[inst].ifc.is_a("IfcSpace"):
                continue
            space_obj = instances[inst]
            space_obj.b_bound_shape = space_obj.space_shape
            for bound in space_obj.space_boundaries:
                if bound.bound_area.m == 0:
                    continue
                bound_prop = GProp_GProps()
                brepgprop_SurfaceProperties(space_obj.b_bound_shape, bound_prop)
                b_bound_area = bound_prop.Mass()
                if b_bound_area == 0:
                    continue
                distance = BRepExtrema_DistShapeShape(
                    space_obj.b_bound_shape,
                    bound.bound_shape,
                    Extrema_ExtFlag_MIN).Value()
                if distance > 1e-6:
                    continue
                space_obj.b_bound_shape = BRepAlgoAPI_Cut(space_obj.b_bound_shape, bound.bound_shape).Shape()
            faces = PyOCCTools.get_faces_from_shape(space_obj.b_bound_shape)
            inst_2b.update(self.create_2B_space_boundaries(faces, space_obj))
        instances.update(inst_2b)

    def export_2B_bounds_to_stl(self, instances, stl_name):
        for inst in instances:
            if instances[inst].ifc.is_a("IfcSpace"):
                continue
            space_obj = instances[inst]
            if not hasattr(space_obj, "b_bound_shape"):
                continue
            bound_prop = GProp_GProps()
            brepgprop_SurfaceProperties(space_obj.b_bound_shape, bound_prop)
            area = bound_prop.Mass()
            if area > 0:
                name = space_obj.guid + "_2B"
                stl_dir = str(self.paths.root) + "/export/STL/"
                this_name = stl_dir + str(stl_name) + "_cfd_" + str(name) + ".stl"
                os.makedirs(os.path.dirname(stl_dir), exist_ok=True)
                triang_face = BRepMesh_IncrementalMesh(space_obj.b_bound_shape, 1)
                # Export to STL
                stl_writer = StlAPI_Writer()
                stl_writer.SetASCIIMode(True)
                stl_writer.Write(triang_face.Shape(), this_name)

    def create_2B_space_boundaries(self, faces, space_obj):
        settings = ifcopenshell.geom.main.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings.set(settings.INCLUDE_CURVES, True)
        inst_2b = dict()
        space_obj.space_boundaries_2B = []
        bound_obj = []
        for bound in space_obj.space_boundaries:
            if bound.bound_instance is not None:
                bi = bound.bound_instance.ifc
                bound.bound_instance.shape = ifcopenshell.geom.create_shape(settings, bi).geometry
                bound_obj.append(bound.bound_instance)
        for i, face in enumerate(faces):
            b_bound = SpaceBoundary2B()
            b_bound.bound_shape = face
            if b_bound.bound_area.m < 1e-6:
                continue
            b_bound.guid = space_obj.guid + "_2B_" + str("%003.f" % (i + 1))
            b_bound.thermal_zones.append(space_obj)
            for instance in bound_obj:
                if hasattr(instance, 'related_parent'):
                    continue
                center_shape = BRepBuilderAPI_MakeVertex(gp_Pnt(b_bound.bound_center)).Shape()
                distance = BRepExtrema_DistShapeShape(center_shape, instance.shape, Extrema_ExtFlag_MIN).Value()
                if distance < 1e-3:
                    b_bound.bound_instance = instance
                    break
            space_obj.space_boundaries_2B.append(b_bound)
            inst_2b[b_bound.guid] = b_bound
            for bound in space_obj.space_boundaries:
                distance = BRepExtrema_DistShapeShape(bound.bound_shape, b_bound.bound_shape,
                                                      Extrema_ExtFlag_MIN).Value()
                if distance == 0:
                    b_bound.bound_neighbors.append(bound)
                    if not hasattr(bound, 'bound_neighbors_2b'):
                        bound.bound_neighbors_2b = []
                    bound.bound_neighbors_2b.append(b_bound)
        return inst_2b


class IdfObject():
    def __init__(self, inst_obj, idf):
        self.name = inst_obj.guid
        self.building_surface_name = None
        self.key = None
        self.out_bound_cond = ''
        self.out_bound_cond_obj = ''
        self.sun_exposed = ''
        self.wind_exposed = ''
        self.surface_type = None
        self.physical = inst_obj.physical
        self.construction_name = None
        self.related_bound = inst_obj.related_bound
        self.this_bound = inst_obj
        self.skip_bound = False
        self.bound_shape = inst_obj.bound_shape
        if not hasattr(inst_obj.bound_thermal_zone, 'guid'):
            self.skip_bound = True
            return
        self.zone_name = inst_obj.bound_thermal_zone.guid
        if hasattr(inst_obj, 'related_parent_bound'):
            self.key = "FENESTRATIONSURFACE:DETAILED"
        else:
            self.key = "BUILDINGSURFACE:DETAILED"
        if hasattr(inst_obj, 'related_parent_bound'):
            self.building_surface_name = inst_obj.related_parent_bound.guid
        self._map_surface_types(inst_obj)
        self._map_boundary_conditions(inst_obj)
        # todo: fix material definitions!
        # self._set_bs2021_construction_name()
        self.set_preprocessed_construction_name()
        if self.construction_name == None:
            self._set_construction_name()
        obj = self._set_idfobject_attributes(idf)
        if obj is not None:
            self._set_idfobject_coordinates(obj, idf, inst_obj)


    def _set_construction_name(self):
        if self.surface_type == "Wall":
            self.construction_name = "Project Wall"
            # construction_name = "FZK Exterior Wall"
        if self.surface_type == "Roof":
            # construction_name = "Project Flat Roof"
            self.construction_name = "Project Flat Roof"
        if self.surface_type == "Ceiling":
            self.construction_name = "Project Ceiling"
        if self.surface_type == "Floor":
            self.construction_name = "Project Floor"
        if self.surface_type == "Door":
            self.construction_name = "Project Door"
        if self.surface_type == "Window":
            self.construction_name = "Project External Window"

    def _set_bs2021_construction_name(self):
        if self.surface_type == "Wall":
            if self.out_bound_cond == "Outdoors":
                self.construction_name = "BS Exterior Wall"
            elif self.out_bound_cond in {"Surface", "Adiabatic"}:
                self.construction_name = "BS Interior Wall"
            elif self.out_bound_cond == "Ground":
                self.construction_name = "BS Exterior Wall"
        elif self.surface_type == "Roof":
            self.construction_name = "BS Flat Roof"
        elif self.surface_type == "Ceiling":
            self.construction_name = "BS Ceiling"
        elif self.surface_type == "Floor":
            if self.out_bound_cond in {"Surface", "Adiabatic"}:
                self.construction_name = "BS Interior Floor"
            elif self.out_bound_cond == "Ground":
                self.construction_name = "BS Ground Floor"
        elif self.surface_type == "Door":
            self.construction_name = "BS Door"
        elif self.surface_type == "Window":
            self.construction_name = "BS Exterior Window"
        if not self.physical:
            if self.out_bound_cond == "Surface":
                self.construction_name = "Air Wall"

    def set_preprocessed_construction_name(self):
        """ set constructions of idf surfaces to preprocessed constructions.
            Virtual space boundaries are set to be an air wall (not defined in preprocessing)
        """
        if not self.physical:
            if self.out_bound_cond == "Surface":
                self.construction_name = "Air Wall"
        else:
            rel_elem = self.this_bound.bound_instance
            if not rel_elem:
                return
            if rel_elem.ifc.is_a('IfcWindow'):
                self.construction_name = 'Window_WM_' + rel_elem.layers[0].material \
                                         + '_' + str(rel_elem.layers[0].thickness.m)
            else:
                self.construction_name = rel_elem.key + '_' + str(len(rel_elem.layers)) + '_'\
                                         + '_'.join([str(l.thickness.m) for l in rel_elem.layers])


    def _set_idfobject_coordinates(self, obj, idf, inst_obj):
        # validate bound_shape
        # self._check_for_vertex_duplicates()
        # write validated bound_shape to obj
        obj_pnts = PyOCCTools.get_points_of_face(self.bound_shape)
        obj_coords = []
        # obj_pnts_new = PyOCCTools.remove_coincident_vertices(obj_pnts)
        # obj_pnts_new = PyOCCTools.remove_collinear_vertices2(obj_pnts_new)
        # #todo: check if corresponding boundaries still have matching partner
        # if len(obj_pnts_new) < 3:
        #     self.skip_bound = True
        #     return
        # else:
        #     obj_pnts = obj_pnts_new
        for pnt in obj_pnts:
            co = tuple(round(p, 3) for p in pnt.Coord())
            obj_coords.append(co)
        try:
            obj.setcoords(obj_coords)
        except:
            self.skip_bound = True
            return
        circular_shape = self.get_circular_shape(obj_pnts)
        try:
            if (3 <= len(obj_coords) <= 120 and self.key == "BUILDINGSURFACE:DETAILED") \
                    or (3 <= len(obj_coords) <= 4 and self.key == "FENESTRATIONSURFACE:DETAILED"):
                obj.setcoords(obj_coords)
            elif circular_shape is True and self.surface_type != 'Door':
                self._process_circular_shapes(idf, obj_coords, obj, inst_obj)
            else:
                self._process_other_shapes(inst_obj, obj)
        except:
            print("Element", self.name, "NOT EXPORTED")

    def _set_idfobject_attributes(self, idf):
        if self.surface_type is not None:
            if self.key == "BUILDINGSURFACE:DETAILED":
                if self.surface_type.lower() in {"DOOR".lower(), "Window".lower()}:
                    self.surface_type = "Wall"
                obj = idf.newidfobject(
                    self.key,
                    Name=self.name,
                    Surface_Type=self.surface_type,
                    Construction_Name=self.construction_name,
                    Outside_Boundary_Condition=self.out_bound_cond,
                    Outside_Boundary_Condition_Object=self.out_bound_cond_obj,
                    Zone_Name=self.zone_name,
                    Sun_Exposure=self.sun_exposed,
                    Wind_Exposure=self.wind_exposed,
                )
            # elif self.building_surface_name is None or self.out_bound_cond_obj is None:
            #     self.skip_bound = True
            #     return
            else:
                obj = idf.newidfobject(
                    self.key,
                    Name=self.name,
                    Surface_Type=self.surface_type,
                    Construction_Name=self.construction_name,
                    Building_Surface_Name=self.building_surface_name,
                    Outside_Boundary_Condition_Object=self.out_bound_cond_obj,
                    # Frame_and_Divider_Name="Default"
                )
            return obj

    def _map_surface_types(self, inst_obj):
        """
        This function maps the attributes of a SpaceBoundary instance to idf surface type
        :param elem: SpaceBoundary instance
        :return: idf surface_type
        """
        elem = inst_obj.bound_instance
        surface_type = None
        if elem != None:
            if elem.ifc.is_a("IfcWall"):
                surface_type = 'Wall'
            elif elem.ifc.is_a("IfcDoor"):
                surface_type = "Door"
            elif elem.ifc.is_a("IfcWindow"):
                surface_type = "Window"
            elif elem.ifc.is_a("IfcRoof"):
                surface_type = "Roof"
            elif elem.ifc.is_a("IfcSlab"):
                if elem.predefined_type.lower() == 'baseslab':
                    surface_type = 'Floor'
                elif elem.predefined_type.lower() == 'roof':
                    surface_type = 'Roof'
                elif elem.predefined_type.lower() == 'floor':
                    if inst_obj.top_bottom == "BOTTOM":
                        surface_type = "Floor"
                    elif inst_obj.top_bottom == "TOP":
                        surface_type = "Ceiling"
                    elif inst_obj.top_bottom == "VERTICAL":
                        surface_type = "Wall"
                    else:
                        surface_type = "Floor"
            elif elem.ifc.is_a("IfcBeam"):
                if not PyOCCTools._compare_direction_of_normals(inst_obj.bound_normal, gp_XYZ(0, 0, 1)):
                    surface_type = 'Wall'
                else:
                    surface_type = 'Ceiling'
            elif elem.ifc.is_a('IfcColumn'):
                surface_type = 'Wall'
            elif inst_obj.top_bottom == "BOTTOM":
                surface_type = "Floor"
            elif inst_obj.top_bottom == "TOP":
                surface_type = "Ceiling"
                if inst_obj.related_bound is None or inst_obj.is_external:
                    surface_type = "Roof"
            elif inst_obj.top_bottom == "VERTICAL":
                surface_type = "Wall"
            else:
                if not PyOCCTools._compare_direction_of_normals(inst_obj.bound_normal, gp_XYZ(0, 0, 1)):
                    surface_type = 'Wall'
                elif inst_obj.top_bottom == "BOTTOM":
                    surface_type = "Floor"
                elif inst_obj.top_bottom == "TOP":
                    surface_type = "Ceiling"
                    if inst_obj.related_bound is None or inst_obj.is_external:
                        surface_type = "Roof"
        elif inst_obj.physical == False:
            if not PyOCCTools._compare_direction_of_normals(inst_obj.bound_normal, gp_XYZ(0, 0, 1)):
                surface_type = 'Wall'
            else:
                if inst_obj.top_bottom == "BOTTOM":
                    surface_type = "Floor"
                elif inst_obj.top_bottom == "TOP":
                    surface_type = "Ceiling"
        self.surface_type = surface_type

    def _map_boundary_conditions(self, inst_obj):
        """
        This function maps the boundary conditions of a SpaceBoundary instance
        to the idf space boundary conditions
        :return:
        """
        if inst_obj.level_description == '2b' or inst_obj.related_adb_bound is not None:
            self.out_bound_cond = 'Adiabatic'
            self.sun_exposed = 'NoSun'
            self.wind_exposed = 'NoWind'
        elif (hasattr(inst_obj.ifc, 'CorrespondingBoundary')
              and ((inst_obj.ifc.CorrespondingBoundary is not None)
                   and (inst_obj.ifc.CorrespondingBoundary.InternalOrExternalBoundary.upper() == 'EXTERNAL_EARTH'))
              and (self.key == "BUILDINGSURFACE:DETAILED")
              and not (hasattr(inst_obj, 'related_opening_bounds') and (len(inst_obj.related_opening_bounds) > 0))):
            self.out_bound_cond = "Ground"
            self.sun_exposed = 'NoSun'
            self.wind_exposed = 'NoWind'
        elif inst_obj.is_external and inst_obj.physical and not self.surface_type == 'Floor':
            self.out_bound_cond = 'Outdoors'
            self.sun_exposed = 'SunExposed'
            self.wind_exposed = 'WindExposed'
            self.out_bound_cond_obj = ''
        elif self.surface_type == "Floor" and \
                (inst_obj.related_bound is None
                 or inst_obj.related_bound.ifc.RelatingSpace.is_a('IfcExternalSpatialElement')):
            self.out_bound_cond = "Ground"
            self.sun_exposed = 'NoSun'
            self.wind_exposed = 'NoWind'
        elif inst_obj.related_bound is not None \
                and not inst_obj.related_bound.ifc.RelatingSpace.is_a('IfcExternalSpatialElement'):  # or elem.virtual_physical == "VIRTUAL": # elem.internal_external == "INTERNAL"
            self.out_bound_cond = 'Surface'
            self.out_bound_cond_obj = inst_obj.related_bound.guid
            self.sun_exposed = 'NoSun'
            self.wind_exposed = 'NoWind'
        # elif inst_obj.bound_instance is not None and inst_obj.bound_instance.ifc.is_a() == "IfcWindow":
        elif self.key == "FENESTRATIONSURFACE:DETAILED":
            # if elem.rel_elem.type == "IfcWindow":
            self.out_bound_cond = 'Outdoors'
            self.sun_exposed = 'SunExposed'
            self.wind_exposed = 'WindExposed'
            self.out_bound_cond_obj = ''
        elif self.related_bound is None:
            self.out_bound_cond = 'Outdoors'
            self.sun_exposed = 'SunExposed'
            self.wind_exposed = 'WindExposed'
            self.out_bound_cond_obj = ''
        else:
            self.skip_bound = True

    @staticmethod
    def get_circular_shape(obj_pnts):
        """
        This function checks if a SpaceBoundary has a circular shape.
        :param obj_pnts: SpaceBoundary vertices (list of coordinate tuples)
        :return: True if shape is circular
        """
        circular_shape = False
        # compute if shape is circular:
        if len(obj_pnts) > 4:
            pnt = obj_pnts[0]
            pnt2 = obj_pnts[1]
            distance_prev = pnt.Distance(pnt2)
            pnt = pnt2
            for pnt2 in obj_pnts[2:]:
                distance = pnt.Distance(pnt2)
                if (distance_prev - distance) ** 2 < 0.01:
                    circular_shape = True
                    pnt = pnt2
                    distance_prev = distance
                else:
                    continue
        return circular_shape

    def _process_circular_shapes(self, idf, obj_coords, obj, inst_obj):
        """
        This function processes circular boundary shapes. It converts circular shapes
        to triangular shapes.
        :param idf: idf file object
        :param obj_coords: coordinates of an idf object
        :param obj: idf object
        :param elem: SpaceBoundary instance
        :return:
        """
        drop_count = int(len(obj_coords) / 8)
        drop_list = obj_coords[0::drop_count]
        pnt = drop_list[0]
        counter = 0
        # del inst_obj.__dict__['bound_center']
        for pnt2 in drop_list[1:]:
            counter += 1
            new_obj = idf.copyidfobject(obj)
            new_obj.Name = str(obj.Name) + '_' + str(counter)
            fc = PyOCCTools.make_faces_from_pnts([pnt, pnt2, inst_obj.bound_center.Coord()])
            fcsc = PyOCCTools.scale_face(fc, 0.99)
            new_pnts = PyOCCTools.get_points_of_face(fcsc)
            new_coords = []
            for pnt in new_pnts:
                new_coords.append(pnt.Coord())
            new_obj.setcoords(new_coords)
            pnt = pnt2
        new_obj = idf.copyidfobject(obj)
        new_obj.Name = str(obj.Name) + '_' + str(counter + 1)
        fc = PyOCCTools.make_faces_from_pnts(
            [drop_list[-1], drop_list[0], inst_obj.bound_center.Coord()])
        fcsc = PyOCCTools.scale_face(fc, 0.99)
        new_pnts = PyOCCTools.get_points_of_face(fcsc)
        new_coords = []
        for pnt in new_pnts:
            new_coords.append(pnt.Coord())
        new_obj.setcoords(new_coords)
        idf.removeidfobject(obj)

    @staticmethod
    def _process_other_shapes(inst_obj, obj):
        """
        This function processes non-circular shapes with too many vertices
        by approximation of the shape utilizing the UV-Bounds from OCC
        (more than 120 vertices for BUILDINGSURFACE:DETAILED
        and more than 4 vertices for FENESTRATIONSURFACE:DETAILED)
        :param elem: SpaceBoundary Instance
        :param obj: idf object
        :return:
        """
        # print("TOO MANY EDGES")
        obj_pnts = []
        exp = TopExp_Explorer(inst_obj.bound_shape, TopAbs_FACE)
        face = topods_Face(exp.Current())
        umin, umax, vmin, vmax = breptools_UVBounds(face)
        surf = BRep_Tool.Surface(face)
        plane = Handle_Geom_Plane_DownCast(surf)
        plane = gp_Pln(plane.Location(), plane.Axis().Direction())
        new_face = BRepBuilderAPI_MakeFace(plane,
                                           umin,
                                           umax,
                                           vmin,
                                           vmax).Face().Reversed()
        face_exp = TopExp_Explorer(new_face, TopAbs_WIRE)
        w_exp = BRepTools_WireExplorer(topods_Wire(face_exp.Current()))
        while w_exp.More():
            wire_vert = w_exp.CurrentVertex()
            obj_pnts.append(BRep_Tool.Pnt(wire_vert))
            w_exp.Next()
        obj_coords = []
        for pnt in obj_pnts:
            obj_coords.append(pnt.Coord())
        obj.setcoords(obj_coords)


