import json
from pathlib import Path

import pandas as pd
from geomeppy import IDF

from bim2sim.elements.bps_elements import ThermalZone
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements


class IdfPostprocessing(ITask):
    """Idf Postprocessin task.

    See run function for further details. """
    reads = ('elements', 'idf', 'ifc_files', 'sim_results_path')

    def run(self, elements: dict, idf: IDF, ifc_files: list,
            sim_results_path: Path):
        """EnergyPlus postprocessing for further evaluation and debugging.

        This task holds export functions for further evaluation and
        debugging. Information on spaces and space boundaries are exported
        and the zone names are exported in json format.

        Args:
            elements (dict): dictionary in the format dict[guid: element],
                holds preprocessed elements including space boundaries.
            idf (IDF): eppy idf, EnergyPlus input file.
            ifc_files (list): list of ifc files used in this project
            sim_results_path (Path): path to simulation results.
            """

        self.logger.info("IDF Postprocessing started...")

        self._export_surface_areas(elements, idf)
        self._export_space_info(elements, idf)
        self._export_boundary_report(elements, idf, ifc_files)
        self.write_zone_names(idf, elements,
                              sim_results_path / self.prj_name)
        self.logger.info("IDF Postprocessing finished!")


    @staticmethod
    def write_zone_names(idf, elements, exportpath: Path):
        """
        Write a dictionary of the bim2sim ThermalZone names and usages.

        This method creates a dict and exports it to a json file (
        zone_dict.json) to the path defined in exportpath. This dict
        includes the zone name and the selected usage within bim2sim. All
        zones are considered that are created within the bim2sim elements.

        Args:
            idf: eppy idf
            elements: bim2sim elements
            exportpath: base path to place the resulting zone_dict.json

        """
        zones = idf.idfobjects['ZONE']
        zone_dict = {}
        ifc_zones = filter_elements(elements, ThermalZone)
        for zone in zones:
            usage = [z.usage for z in ifc_zones if z.guid == zone.Name]
            zone_dict.update({zone.Name: usage[0]})

        with open(exportpath / 'zone_dict.json', 'w+') as file:
            json.dump(zone_dict, file, indent=4)

    def _export_surface_areas(self, elements, idf):
        """ combines sets of area sums and exports to csv """
        area_df = pd.DataFrame(
            columns=["granularity", "ID", "long_name", "out_bound_cond",
                     "area_wall", "area_ceiling", "area_floor",
                     "area_roof", "area_window", "area_door",
                     "total_surface_area", "total_opening_area"])
        surf = [s for s in idf.idfobjects['BuildingSurface:Detailed'.upper()]
                if s.Construction_Name != 'Air Wall']
        glazing = [g for g in idf.idfobjects[
            'FenestrationSurface:Detailed'.upper()]]
        area_df = self._append_set_of_area_sum(area_df, granularity="GLOBAL",
                                               guid="GLOBAL",
                                               long_name="GLOBAL",
                                               surface=surf, glazing=glazing)
        zones = [z for z in idf.idfobjects['zone'.upper()]]
        zone_names = [z.Name for z in zones]

        for z_name in zone_names:
            surf_zone = [s for s in surf if s.Zone_Name == z_name]
            surf_names = [s.Name for s in surf_zone]
            long_name = elements[z_name].ifc.LongName
            glazing_zone = [g for g in glazing for s_name in surf_names if
                            g.Building_Surface_Name == s_name]
            area_df = self._append_set_of_area_sum(area_df, granularity="ZONE",
                                                   guid=z_name,
                                                   long_name=long_name,
                                                   surface=surf_zone,
                                                   glazing=glazing_zone)
        area_df.to_csv(path_or_buf=str(self.paths.export) + "/area.csv")

    def _append_set_of_area_sum(self, area_df, granularity, guid, long_name,
                                surface, glazing):
        """ generate set of area sums for a given granularity for outdoor,
        surface and adiabatic boundary conditions.
        Appends set to a given dataframe.
        """
        surf_outdoors = [s for s in surface if s.Outside_Boundary_Condition ==
                         "Outdoors" or s.Outside_Boundary_Condition == "Ground"]
        surf_surface = [s for s in surface if s.Outside_Boundary_Condition ==
                        "Surface"]
        surf_adiabatic = [s for s in surface if s.Outside_Boundary_Condition ==
                          "Adiabatic"]
        glazing_outdoors = [g for g in glazing if
                            g.Outside_Boundary_Condition_Object == ""]
        glazing_surface = [g for g in glazing if
                           g.Outside_Boundary_Condition_Object != ""]
        glazing_adiabatic = []

        area_df = pd.concat([area_df, pd.DataFrame.from_records([
            self._sum_of_surface_area(
                granularity=granularity, guid=guid, long_name=long_name,
                out_bound_cond="ALL", surface=surface, glazing=glazing),
            self._sum_of_surface_area(
                granularity=granularity, guid=guid, long_name=long_name,
                out_bound_cond="Outdoors",surface=surf_outdoors,
                glazing=glazing_outdoors),
            self._sum_of_surface_area(
                granularity=granularity, guid=guid, long_name=long_name,
                out_bound_cond="Surface", surface=surf_surface,
                glazing=glazing_surface),
            self._sum_of_surface_area(
                granularity=granularity, guid=guid, long_name=long_name,
                out_bound_cond="Adiabatic", surface=surf_adiabatic,
                glazing=glazing_adiabatic)
        ])],
                             ignore_index=True)
        return area_df

    @staticmethod
    def _sum_of_surface_area(granularity, guid, long_name, out_bound_cond,
                             surface, glazing):
        """ generate row with sum of surface and opening areas to be appended
        to larger dataframe"""
        row = {
            "granularity": granularity,
            "ID": guid,
            "long_name": long_name,
            "out_bound_cond": out_bound_cond,
            "area_wall": sum(s.area for s in surface if s.Surface_Type ==
                             "Wall"),
            "area_ceiling": sum(s.area for s in surface if s.Surface_Type ==
                                "Ceiling"),
            "area_floor": sum(s.area for s in surface if s.Surface_Type ==
                              "Floor"),
            "area_roof": sum(s.area for s in surface if s.Surface_Type ==
                             "Roof"),
            "area_window": sum(g.area for g in glazing if g.Surface_Type ==
                               "Window"),
            "area_door": sum(g.area for g in glazing if g.Surface_Type ==
                             "Door"),
            "total_surface_area": sum(s.area for s in surface),
            "total_opening_area": sum(g.area for g in glazing)
        }
        return row

    def _export_space_info(self, elements, idf):
        space_df = pd.DataFrame(
            columns=["ID", "long_name", "space_center", "space_volume"])
        spaces = filter_elements(elements, 'ThermalZone')
        for space in spaces:
            space_df = pd.concat([space_df, pd.DataFrame.from_records([{
                    "ID": space.guid,
                    "long_name": space.ifc.LongName,
                    "space_center": space.space_center.XYZ().Coord(),
                    "space_volume": space.space_shape_volume.m
                }])],
                ignore_index=True)
        space_df.to_csv(path_or_buf=str(self.paths.export) + "/space.csv")

    def _export_boundary_report(self, elements, idf, ifc_files):
        """Export a report on the number of space boundaries.
        Creates a report as a DataFrame and exports it to csv.

        Columns:
            IFC_SB_all: Number of IfcRelSpaceBoundary elements included in
                the given IFC files,
            IFC_SB_2a: Number of IfcRelSpaceBoundary elements included in
                the given IFC files of type 2a,
            IFC_SB_2b: Number of IfcRelSpaceBoundary elements included in
                the given IFC files of type 2b,
            BIM2SIM_SB_2b: Number of SpaceBoundary elements created within
                the bim2sim tool generated from gaps within the IfcSpaces,
            IDF_all: Total number of FENESTRATIONSURFACE:DETAILED and
                BUILDINGSURFACE:DETAILED elements in the resulting IDF,
            IDF_all_B: Total number of BUILDINGSURFACE:DETAILED elements in
                the resulting IDF,
            IDF_ADB: Number of BUILDINGSURFACE:DETAILED elements with
                adiabatic boundary conditions,
            IDF_SFB: Number of BUILDINGSURFACE:DETAILED elements with
                "surface" boundary conditions,
            IDF_ODB: Number of BUILDINGSURFACE:DETAILED elements with
                outdoor boundary conditions,
            IDF_GDB: Number of BUILDINGSURFACE:DETAILED elements with
                ground boundary conditions,
            IDF_VTB:  Number of BUILDINGSURFACE:DETAILED elements with
                an air wall construction,
            IDF_all_F: Total number of FENESTRATIONSURFACE:DETAILED elements in
                the resulting IDF,
            IDF_ODF: Number of FENESTRATIONSURFACE:DETAILED elements in
                the resulting IDF without outside boundary condition object,
            IDF_INF: Total number of FENESTRATIONSURFACE:DETAILED elements in
                the resulting IDF with an outside boundary condition object.
        """
        bound_count = pd.DataFrame(
            columns=["IFC_SB_all", "IFC_SB_2a", "IFC_SB_2b", "BIM2SIM_SB_2b",
                     "IDF_all", "IDF_all_B", "IDF_ADB", "IDF_SFB",
                     "IDF_ODB", "IDF_GDB", "IDF_VTB", "IDF_all_F",
                     "IDF_ODF", "IDF_INF"])
        ifc_bounds = []
        for ifc in ifc_files:
            ifc_bounds.extend(ifc.file.by_type('IfcRelSpaceBoundary'))
        bounds_2b = filter_elements(elements, 'SpaceBoundary2B')
        idf_all_b = [s for s in idf.idfobjects["BUILDINGSURFACE:DETAILED"]]
        idf_adb = [s for s in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
                   if s.Outside_Boundary_Condition == "Adiabatic"]
        idf_sfb = [s for s in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
                   if s.Outside_Boundary_Condition == "Surface"]
        idf_odb = [s for s in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
                   if s.Outside_Boundary_Condition == "Outdoors"]
        idf_gdb = [s for s in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
                   if s.Outside_Boundary_Condition == "Ground"]
        idf_vtb = [s for s in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
                   if s.Construction_Name == "Air Wall"]
        idf_all_f = [f for f in idf.idfobjects["FENESTRATIONSURFACE:DETAILED"]]
        idf_odf = [f for f in idf.idfobjects["FENESTRATIONSURFACE:DETAILED"] if
                   f.Outside_Boundary_Condition_Object == '']
        idf_inf = [f for f in idf.idfobjects["FENESTRATIONSURFACE:DETAILED"] if
                   f.Outside_Boundary_Condition_Object != '']

        bound_count = pd.concat([bound_count, pd.DataFrame.from_records([{
            "IFC_SB_all": len(ifc_bounds),
            "IFC_SB_2a": len([b for b in ifc_bounds if b.Description ==
                              "2a"]),
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
        }])],
            ignore_index=True)
        bound_count.to_csv(
            path_or_buf=str(self.paths.export) + "/bound_count.csv")
