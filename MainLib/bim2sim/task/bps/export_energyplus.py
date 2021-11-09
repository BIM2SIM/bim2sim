# todo delete this after seperating energyplus tasks into single tasks
"""This module holds tasks related to bps"""
import copy
import json
import math
import os
from pathlib import Path

import ifcopenshell
import pandas as pd
import matplotlib.pyplot as plt

from OCC.Display.SimpleGui import init_display
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_Transform, BRepBuilderAPI_MakeVertex
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from OCC.Core.gp import gp_Trsf, gp_Vec, gp_XYZ, gp_Pln, gp_Pnt, gp_Dir
from OCC.Core.TopoDS import topods_Wire, topods_Face
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_WIRE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepTools import BRepTools_WireExplorer, breptools_UVBounds
from OCC.Core._Geom import Handle_Geom_Plane_DownCast
from geomeppy import IDF
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCC.Core.StlAPI import StlAPI_Writer
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.BRepGProp import brepgprop_SurfaceProperties
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Sewing
from OCC.Core.BRepGProp import brepgprop_VolumeProperties
from stl import stl
from stl import mesh

from bim2sim.kernel.elements import bps
from bim2sim.task.base import ITask
from bim2sim.decision import BoolDecision, DecisionBunch
from bim2sim.kernel.elements.bps import SpaceBoundary, ExternalSpatialElement
from bim2sim.kernel.aggregation import AggregatedThermalZone
# todo new name :)
import bim2sim
from bim2sim.task.common.inner_loop_remover import is_convex_no_holes, convex_decomposition
from bim2sim.utilities.common_functions import filter_instances
from bim2sim.utilities.pyocc_tools import PyOCCTools


def _string_to_datetime(date_str):
    """
    Converts a date string in the format MM:DD hh:mm:ss into a datetime object.
    :param date_str: A date string in the specified format.
    :return: The converted datetime object.
    """
    date_str = date_str.strip()

    if date_str[7:9] != '24':
        return pd.to_datetime(date_str, format=' %m/%d  %H:%M:%S')

    # If the time is 24, set it to 0 and increment day by 1
    date_str = date_str[0:7] + '00' + date_str[9:]
    return pd.to_datetime(date_str, format=' %m/%d  %H:%M:%S') + pd.Timedelta(days=1)


class ExportEP(ITask):
    """Exports an EnergyPlus model based on IFC information"""

    ENERGYPLUS_VERSION = "9-4-0"

    reads = ('instances', 'ifc')
    final = True

    def run(self, workflow, instances, ifc):
        self._add_bounds_to_instances(instances)
        IfcValidation(ifc, self.paths)
        self.logger.info("Geometric preprocessing for EnergyPlus Export started ...")
        self._get_parents_and_children(instances)
        self._move_children_to_parents(instances)
        self._fix_surface_orientation(instances)  # todo: Check if working properly
        split_bounds = BoolDecision(
            question="Do you want to decompose non-convex space boundaries into convex boundaries?",
            global_key='EnergyPlus.SplitConvexBounds')
        yield DecisionBunch([split_bounds])
        if split_bounds.value:
            self.logger.info("Split non-convex surfaces")
            self._split_non_convex_bounds(instances)
        self.logger.info("Get neighboring space boundaries")
        # self._get_neighbor_bounds(instances)
        # self._compute_2b_bound_gaps(instances) # todo: fix
        self.logger.info("Geometric preprocessing for EnergyPlus Export finished!")
        self.logger.info("IDF generation started ...")
        self.logger.info("Init thermal zones ...")
        idf = self._init_idf(self.paths)
        self._init_zone(instances, idf)
        self._init_zonelist(idf)
        self._init_zonegroups(instances, idf)
        self.logger.info("Get predefined materials and construction ...")
        self._get_preprocessed_materials_and_constructions(instances, idf)
        # self._get_bs2021_materials_and_constructions(idf)
        add_shadings = BoolDecision(
            question="Do you want to add shadings if available?",
            global_key='EnergyPlus.AddShadings')
        split_shadings = BoolDecision(
            question="Do you want to decompose non-convex shadings into convex shadings?",
            global_key='EnergyPlus.SplitConvexShadings')
        yield DecisionBunch([add_shadings, split_shadings])
        if add_shadings.value:
            self.logger.info("Add Shadings ...")
            self._add_shadings(instances, split_shadings.value, idf)
        self.logger.info("Set Simulation Control ...")
        self._set_simulation_control(idf)
        idf.set_default_constructions()
        self.logger.info("Export IDF geometry")
        self._export_geom_to_idf(instances, idf)
        self._set_output_variables(idf)
        self._idf_validity_check(idf)
        idf.save()
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

    def _add_bounds_to_instances(self, instances):
        self.logger.info("Creates python representation of relevant ifc types")
        for inst in list(instances):
            if instances[inst].ifc.is_a("IfcSpace"):
                for bound in instances[inst].space_boundaries:
                    instances[bound.guid] = bound

    @staticmethod
    def _extract_cols_from_df(df, col_name_part):
        col = [col for col in df.columns if col_name_part in col]
        return_df = df[col].copy()
        return_df["Date/Time"] = df["Date/Time"].copy()
        return_df = return_df.set_index("Date/Time", drop=True).dropna()
        return return_df

    def _visualize_results(self, csv_name, period="week",
                           number=28, date=False):
        """
        Plot Zone Mean Air Temperature (Hourly) vs Outdoor Temperature per zone and as an overview on all zones.
        :param csv_name: path to energyplus outputs (eplusout.csv)
        :param period: choose plotting period ("year"/"month"/"week"/"day"/"date")
        :param number: choose number of day or week (0...365 (day) or 0...52 (week))
        :param date: only required if period == date. enter date in format date=[int(month), int(day)]
        :return:
        """
        res_df = pd.read_csv(csv_name)
        res_df["Date/Time"] = res_df["Date/Time"].apply(_string_to_datetime)
        # df = res_df.loc[:, ~res_df.columns.str.contains('Surface Inside Face Temperature']
        zone_mean_air = self._extract_cols_from_df(res_df, "Zone Mean Air Temperature")
        ideal_loads = self._extract_cols_from_df(res_df, "IDEAL LOADS AIR SYSTEM:Zone Ideal Loads Zone Sensible")
        equip_rate = self._extract_cols_from_df(res_df, "Zone Electric Equipment Convective Heating Rate")
        people_rate = self._extract_cols_from_df(res_df, "Zone People Convective Heating Rate")
        rad_dir = self._extract_cols_from_df(res_df, "Site Direct Solar Radiation Rate per Area")
        # rad_dir_h = rad_dir.resample('1h').mean()
        temp = self._extract_cols_from_df(res_df, "Outdoor Air Drybulb Temperature [C](Hourly)")
        t_mean = temp.resample('24h').mean()
        zone_id_list = []
        for col in zone_mean_air.columns:
            z_id = col.partition(':')
            if z_id[0] not in zone_id_list:
                zone_id_list.append(z_id[0])
        if period == "year":
            for col in zone_mean_air.columns:
                ax = zone_mean_air.plot(y=[col], figsize=(10, 5), grid=True)
                # temp.plot(ax=ax)
                t_mean.plot(ax=ax)
                plt.show()
            axc = zone_mean_air.iloc[:].plot(figsize=(10, 5), grid=True)
            t_mean.iloc[:].plot(ax=axc)
            plt.show()
            return
        elif period == "month":
            for col in zone_mean_air.columns:
                ax = zone_mean_air[zone_mean_air.index.month == number].plot(y=[col], figsize=(10, 5), grid=True)
                # temp.plot(ax=ax)
                temp[temp.index.month == number].plot(ax=ax)
                plt.show()
            axc = zone_mean_air[zone_mean_air.index.month == number].plot(figsize=(10, 5), grid=True)
            temp[temp.index.month == number].plot(ax=axc)
            plt.show()
            return
        elif period == "date":
            month = date[0]
            day = date[1]
            for col in zone_mean_air.columns:
                ax = zone_mean_air.loc[((zone_mean_air.index.month == month) & (zone_mean_air.index.day == day))] \
                    .plot(y=[col], figsize=(10, 5), grid=True)
                # temp.plot(ax=ax)
                temp.loc[((temp.index.month == month) & (temp.index.day == day))].plot(ax=ax)
                plt.show()
            axc = zone_mean_air.loc[((zone_mean_air.index.month == month) & (zone_mean_air.index.day == day))] \
                .plot(figsize=(10, 5), grid=True)
            temp.loc[((temp.index.month == month) & (temp.index.day == day))].plot(ax=axc)
            plt.show()
            return
        elif period == "week":
            min = number * 168
            max = (number + 1) * 168
        elif period == "day":
            min = number * 24
            max = (number + 1) * 24
        for col in zone_mean_air.columns:
            ax = zone_mean_air.iloc[min:max].plot(y=[col], figsize=(10, 5), grid=True)
            # temp.plot(ax=ax)
            temp.iloc[min:max].plot(ax=ax)
            plt.show()
        axc = zone_mean_air.iloc[min:max].plot(figsize=(10, 5), grid=True)
        temp.iloc[min:max].plot(ax=axc)
        plt.show()

        for zid in zone_id_list:
            fig, (ax1, ax2) = plt.subplots(2, sharex=True, figsize=(10, 8))
            fig.suptitle("Zone " + zid, y=1.00)
            z_col = [col for col in ideal_loads.columns if zid in col]
            zma_col = [col for col in zone_mean_air.columns if zid in col]
            ideal_loads[z_col].iloc[min:max].plot(ax=ax1, grid=True)
            # ax1b = ax1.twinx()
            # rad_dir_h.iloc[min:max].plot(ax=ax1b)
            zone_mean_air[zma_col].iloc[min:max].plot(ax=ax2, grid=True, color='green')
            temp.iloc[min:max].plot(ax=ax2, color='black')
            ax1.set_title("Loads")
            ax2.set_title("Temperatures")
            ax1.autoscale()
            ax2.autoscale()
            fig.tight_layout(rect=[0, 0.03, 1, 0.8])
            plt.show()

    def _export_geom_to_idf(self, instances, idf):
        for inst in instances:
            if not instances[inst].ifc.is_a("IfcRelSpaceBoundary"):
                continue
            inst_obj = instances[inst]
            idfp = IdfObject(inst_obj, idf)
            if idfp.skip_bound:
                idf.popidfobject(idfp.key, -1)
                self.logger.warning("Boundary with the GUID %s (%s) is skipped (due to missing boundary conditions)!",
                                    idfp.name, idfp.surface_type)
                continue
        for inst in instances:
            if not instances[inst].ifc.is_a("IfcSpace"):
                continue
            bound_obj = instances[inst]
            if not hasattr(bound_obj, "space_boundaries_2B"):
                continue
            for b_bound in bound_obj.space_boundaries_2B:
                idfp = IdfObject(b_bound, idf)
                if idfp.skip_bound:
                    # idf.popidfobject(idfp.key, -1)
                    self.logger.warning(
                        "Boundary with the GUID %s (%s) is skipped (due to missing boundary conditions)!", idfp.name,
                        idfp.surface_type)
                    continue

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
                    save(mesh_name, output_file, mode=stl.Mode.ASCII)

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
                    save(mesh_name, output_file, mode=stl.Mode.ASCII)

    @staticmethod
    def _init_idf(paths):
        """
        Initialize the idf with general idf settings and set default weather data.
        :return:
        """
        # path = '/usr/local/EnergyPlus-9-2-0/'
        # path = '/usr/local/EnergyPlus-9-3-0/'
        path = f'/usr/local/EnergyPlus-{ExportEP.ENERGYPLUS_VERSION}/'
        # path = f'D:/04_Programme/EnergyPlus-{ExportEP.ENERGYPLUS_VERSION}/'
        # path = r'C:/Program Files (x86)/EnergyPlusV9-4-0/'
        plugin_ep_path = str(Path(__file__).parent.parent.parent.parent.parent / 'PluginEnergyPlus')
        IDF.setiddname(path + 'Energy+.idd')
        idf = IDF(plugin_ep_path + '/data/Minimal.idf')
        ifc_name = os.listdir(paths.ifc)[0].strip('.ifc')
        idf.idfname = str(paths.export) + '/' + ifc_name + '.idf'
        schedules_idf = IDF(plugin_ep_path + '/data/Schedules.idf')
        schedules = schedules_idf.idfobjects["Schedule:Compact".upper()]
        sch_typelim = schedules_idf.idfobjects["ScheduleTypeLimits".upper()]
        for s in schedules:
            idf.copyidfobject(s)
        for t in sch_typelim:
            idf.copyidfobject(t)
        idf.epw = str(paths.root / 'resources/DEU_NW_Aachen.105010_TMYx.epw')
        return idf

    def _get_ifc_spaces(self, instances):
        """
        Extracts ifc spaces from an instance dictionary while also unpacking spaces from aggregated thermal zones.
        :param instances: The instance dictionary
        :return: A list of ifc spaces
        """
        unpacked_instances = []
        for instance in instances.values():
            if isinstance(instance, AggregatedThermalZone):
                unpacked_instances.extend(instance.elements)
            elif instance.ifc.is_a("IfcSpace"):
                unpacked_instances.append(instance)
        return unpacked_instances

    def _init_zone(self, instances, idf):
        """
        Creates one idf zone per space and initializes with default HVAC Template
        :param idf: idf file object
        :param stat: HVAC Template
        :param space: Space (created from IfcSpace)
        :return: idf file object, idf zone object
        """
        for instance in self._get_ifc_spaces(instances):
            space = instance
            space.storey = bps.Storey(space.get_storey())
            stat_name = "STATS " + space.usage.replace(',', '')
            if idf.getobject("HVACTEMPLATE:THERMOSTAT", stat_name) is None:
                stat = self._set_day_hvac_template(idf, space, stat_name)
            else:
                stat = idf.getobject("HVACTEMPLATE:THERMOSTAT", stat_name)
            zone = idf.newidfobject(
                'ZONE',
                Name=space.ifc.GlobalId,
                Volume=space.space_volume.m
            )
            cooling_availability = "On"
            heating_availability = "On"

            # if room['with_heating']:
            #     heating_availability = "On"
            # else:
            #     heating_availability = "Off"
            # if room['with_cooling']:
            #     cooling_availability = "On"
            # else:
            #     cooling_availability = "Off"

            idf.newidfobject(
                "HVACTEMPLATE:ZONE:IDEALLOADSAIRSYSTEM",
                Zone_Name=zone.Name,
                Template_Thermostat_Name=stat.Name,
                Heating_Availability_Schedule_Name=heating_availability,
                Cooling_Availability_Schedule_Name=cooling_availability
            )
            self._set_infiltration(idf, name=zone.Name, zone_name=zone.Name, space=space)
            self._set_people(idf, name=zone.Name, zone_name=zone.Name, space=space)
            self._set_equipment(idf, name=zone.Name, zone_name=zone.Name, space=space)
            self._set_lights(idf, name=zone.Name, zone_name=zone.Name, space=space)

    @staticmethod
    def _init_zonelist(idf, name=None, zones_in_list=None):
        if zones_in_list is None:
            idf_zones = idf.idfobjects["ZONE"]
            if len(idf_zones) > 20:
                return
        else:
            all_idf_zones = idf.idfobjects["ZONE"]
            idf_zones = [zone for zone in all_idf_zones if zone.Name in zones_in_list]
            if len(idf_zones) == 0:
                return
        if name is None:
            name = "All_Zones"
        zs = {}
        for i, z in enumerate(idf_zones):
            zs.update({"Zone_" + str(i + 1) + "_Name": z.Name})
        idf.newidfobject("ZONELIST", Name=name, **zs)

    def _init_zonegroups(self, instances, idf):
        """
        Assign a zonegroup per storey
        :param instances:
        :param idf:
        :return:
        """
        storeys = []
        for inst in instances:
            if instances[inst].ifc.is_a("IfcBuildingStorey"):
                storeys.append(instances[inst])
                instances[inst].spaces = []
        for inst in instances:
            if not instances[inst].ifc.is_a("IfcSpace"):
                continue
            space = instances[inst]
            for st in storeys:
                if st.guid == space.storey.guid:
                    st.spaces.append(space)
        for st in storeys:
            space_ids = []
            for space in st.spaces:
                space_ids.append(space.guid)
            self._init_zonelist(idf, name=st.ifc.Name, zones_in_list=space_ids)
            # print(st.name, space_ids)
        zonelists = [zlist for zlist in idf.idfobjects["ZONELIST"] if zlist.Name != "All_Zones"]

        for zlist in zonelists:
            idf.newidfobject("ZONEGROUP",
                             Name=zlist.Name,
                             Zone_List_Name=zlist.Name,
                             Zone_List_Multiplier=1
                             )

    def _get_preprocessed_materials_and_constructions(self, instances, idf):
        bounds = filter_instances(instances, 'SpaceBoundary')
        for bound in bounds:
            rel_elem = bound.bound_instance
            if not rel_elem:
                continue
            if not rel_elem.ifc.is_a('IfcWindow'):
                self._set_preprocessed_construction_elem(rel_elem, rel_elem.layers, idf)
                for layer in rel_elem.layers:
                    self._set_preprocessed_material_elem(layer, idf)
            else:
                self._set_preprocessed_window_material_elem(rel_elem, idf)

        idf.newidfobject("CONSTRUCTION:AIRBOUNDARY",
                         Name='Air Wall',
                         Solar_and_Daylighting_Method='GroupedZones',
                         Radiant_Exchange_Method='GroupedZones',
                         Air_Exchange_Method='SimpleMixing',
                         Simple_Mixing_Air_Changes_per_Hour=0.5,
                         )

    def _get_bs2021_materials_and_constructions(self, idf, year=2008, ctype="heavy",
                                                wtype=["Alu", "Waermeschutz", "zwei"]):
        materials = []
        mt_path = self.paths.root / 'MaterialTemplates/MaterialTemplates.json'
        be_path = self.paths.root / 'MaterialTemplates/TypeBuildingElements.json'
        with open(mt_path) as json_file:
            mt_file = json.load(json_file)
        with open(be_path) as json_file:
            be_file = json.load(json_file)

        be_dict = dict([k for k in be_file.items() if type(k[1]) == dict])
        applicable_dict = {k: v for k, v in be_dict.items() if
                           (v['construction_type'] == ctype and v['building_age_group'][0] <= year <=
                            v['building_age_group'][1])}
        window_dict = {k: v for k, v in be_dict.items() if
                       (all(p in v['construction_type'] for p in wtype) and
                        v['building_age_group'][0] <= year <= v['building_age_group'][1])}
        window = window_dict.get(list(window_dict)[0])
        window_materials = [*list(*self._set_construction_elem(window, "BS Exterior Window", idf)), window['g_value']]
        door = list({k: v for k, v in [k for k in mt_file.items() if type(k[1]) == dict] if (v['name'] == 'hardwood')})[
            0]
        idf.newidfobject("CONSTRUCTION",
                         Name="BS Door",
                         Outside_Layer=mt_file[door]['name'] + "_" + str(0.04)
                         )
        materials.extend([(door, 0.04)])
        outer_wall = applicable_dict.get([k for k in applicable_dict.keys() if "OuterWall" in k][0])
        materials.extend(self._set_construction_elem(outer_wall, "BS Exterior Wall", idf))
        inner_wall = applicable_dict.get([k for k in applicable_dict.keys() if "InnerWall" in k][0])
        materials.extend(self._set_construction_elem(inner_wall, "BS Interior Wall", idf))
        ground_floor = applicable_dict.get([k for k in applicable_dict.keys() if "GroundFloor" in k][0])
        materials.extend(self._set_construction_elem(ground_floor, "BS Ground Floor", idf))
        floor = applicable_dict.get([k for k in applicable_dict.keys() if "Floor" in k][0])
        materials.extend(self._set_construction_elem(floor, "BS Interior Floor", idf))
        ceiling = applicable_dict.get([k for k in applicable_dict.keys() if "Ceiling" in k][0])
        materials.extend(self._set_construction_elem(ceiling, "BS Ceiling", idf))
        roof = applicable_dict.get([k for k in applicable_dict.keys() if "Roof" in k][0])
        materials.extend(self._set_construction_elem(roof, "BS Flat Roof", idf))
        for mat in materials:
            self._set_material_elem(mt_file[mat[0]], mat[1], idf)
        self._set_window_material_elem(mt_file[window_materials[0]], window_materials[1], window_materials[2], idf)
        idf.newidfobject("CONSTRUCTION:AIRBOUNDARY",
                         Name='Air Wall',
                         Solar_and_Daylighting_Method='GroupedZones',
                         Radiant_Exchange_Method='GroupedZones',
                         Air_Exchange_Method='SimpleMixing',
                         Simple_Mixing_Air_Changes_per_Hour=0.5,
                         )
        idf.newidfobject("WINDOWPROPERTY:FRAMEANDDIVIDER",
                         Name="Default",
                         # Frame_Width=0.095,
                         # Frame_Conductance=3,
                         Outside_Reveal_Solar_Absorptance=0.7,
                         Inside_Reveal_Solar_Absorptance=0.7,
                         Divider_Width=0.1,
                         Number_of_Horizontal_Dividers=2,
                         Number_of_Vertical_Dividers=2,
                         Divider_Conductance=3
                         )

    def _set_preprocessed_construction_elem(self, rel_elem, layers, idf):
        """use preprocessed data to define idf construction elements and return a list of used materials"""
        construction_name = rel_elem.key + '_' + str(len(layers)) + '_' + '_'.join(
            [str(l.thickness.m) for l in layers])  # todo: find a unique key for construction name
        if idf.getobject("CONSTRUCTION", construction_name) is None:
            outer_layer = layers[-1]
            other_layer_list = layers[:-1]
            other_layer_list.reverse()
            other_layers = {}
            for i, l in enumerate(other_layer_list):
                other_layers.update({'Layer_' + str(i + 2): l.material + "_" + str(l.thickness.m)})

            idf.newidfobject("CONSTRUCTION",
                             Name=construction_name,
                             Outside_Layer=outer_layer.material + "_" + str(outer_layer.thickness.m),
                             **other_layers
                             )
        # materials = pd.unique([(lay.material, lay.thickness.m) for lay in layers]).tolist()
        # return materials

    def _set_construction_elem(self, elem, name, idf):
        layer = elem.get('layer')
        outer_layer = layer.get(list(layer)[-1])
        other_layer_list = list(layer)[:-1]
        other_layer_list.reverse()
        other_layers = {}
        for i, l in enumerate(other_layer_list):
            lay = layer.get(l)
            other_layers.update({'Layer_' + str(i + 2): lay['material']['name'] + "_" + str(lay['thickness'])})

        idf.newidfobject("CONSTRUCTION",
                         Name=name,
                         Outside_Layer=outer_layer['material']['name'] + "_" + str(outer_layer['thickness']),
                         **other_layers
                         )
        materials = [(layer.get(k)['material']['material_id'], layer.get(k)['thickness']) for k in layer.keys()]
        return materials

    def _set_material_elem(self, mat_dict, thickness, idf):
        if idf.getobject("MATERIAL", mat_dict['name'] + "_" + str(thickness)) != None:
            return
        specific_heat = mat_dict['heat_capac'] * 1000  # *mat_dict['density']*thickness
        if specific_heat < 100:
            specific_heat = 100
        idf.newidfobject("MATERIAL",
                         Name=mat_dict['name'] + "_" + str(thickness),
                         Roughness="MediumRough",
                         Thickness=thickness,
                         Conductivity=mat_dict['thermal_conduc'],
                         Density=mat_dict['density'],
                         Specific_Heat=specific_heat
                         )

    def _set_preprocessed_material_elem(self, layer, idf):
        material_name = layer.material + "_" + str(layer.thickness.m)
        if idf.getobject("MATERIAL", material_name):
            return
        specific_heat = layer.heat_capac.m * 1000  # *mat_dict['density']*thickness
        if specific_heat < 100:
            specific_heat = 100
        idf.newidfobject("MATERIAL",
                         Name=material_name,
                         Roughness="MediumRough",
                         Thickness=layer.thickness.m,
                         Conductivity=layer.thermal_conduc.m,
                         Density=layer.density.m,
                         Specific_Heat=specific_heat
                         )

    def _set_window_material_elem(self, mat_dict, thickness, g_value, idf):
        if idf.getobject("WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM", mat_dict['name'] + "_" + str(thickness)) != None:
            return
        if g_value >=1:
            old_g_value = g_value
            g_value = 0.999
            self.logger.warning("G-Value was set to %f, but has to be smaller than 1, so overwritten by %f", old_g_value, g_value)
        idf.newidfobject("WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM",
                         Name=mat_dict['name'] + "_" + str(thickness),
                         UFactor=1 / (0.04 + thickness / mat_dict['thermal_conduc'] + 0.13),
                         Solar_Heat_Gain_Coefficient=g_value,
                         # Visible_Transmittance=0.8    # optional
                         )

    def _set_preprocessed_window_material_elem(self, rel_elem, idf):
        """ constructs windows with a Windowmaterial:SimpleGlazingSystem consisting of
        the outermost layer of the providing related element.
        This is a simplification, needs to be extended to hold multilayer window constructions."""
        material_name = 'WM_'+ rel_elem.layers[0].material \
                        + '_' + str(rel_elem.layers[0].thickness.m)
        if idf.getobject("WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM", material_name):
            return
        if rel_elem.u_value.m > 0:
            ufactor = 1 / (0.04 + 1 / rel_elem.u_value.m + 0.13)
        else:
            ufactor = 1 / (0.04 + rel_elem.layers[0].thickness.m / rel_elem.layers[0].thermal_conduc.m + 0.13)
        if rel_elem.g_value >=1:
            old_g_value = rel_elem.g_value
            rel_elem.g_value = 0.999
            self.logger.warning("G-Value was set to %f, but has to be smaller than 1, so overwritten by %f",
                                old_g_value, rel_elem.g_value)

        idf.newidfobject("WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM",
                         Name=material_name,
                         UFactor=ufactor,
                         Solar_Heat_Gain_Coefficient=rel_elem.g_value,
                         # Visible_Transmittance=0.8    # optional
                         )
        #todo: enable use of multilayer windows
        construction_name = 'Window_'+ material_name
        if idf.getobject("CONSTRUCTION", construction_name) is None:
            idf.newidfobject("CONSTRUCTION",
                             Name=construction_name,
                             Outside_Layer=material_name
                             )

    def _get_room_from_zone_dict(self, key):
        zone_dict = {
            "Schlafzimmer": "Bed room",
            "Wohnen": "Living",
            "Galerie": "Living",
            "Küche": "Living",
            "Flur": "Traffic area",
            "Buero": "Single office",
            "Besprechungsraum": 'Meeting, Conference, seminar',
            "Seminarraum": 'Meeting, Conference, seminar',
            "Technikraum": "Stock, technical equipment, archives",
            "Dachboden": "Traffic area",
            "WC": "WC and sanitary rooms in non-residential buildings",
            "Bad": "WC and sanitary rooms in non-residential buildings",
            "Labor": "Laboratory"
        }
        uc_path = Path(bim2sim.__file__).parent.parent.parent / 'PluginEnergyPlus' / 'data' / 'UseConditions.json'
        # uc_path = self.paths.root / 'MaterialTemplates/UseConditions.json' #todo: use this file (error in people?)
        with open(uc_path) as json_file:
            uc_file = json.load(json_file)
        room_key = []
        if key is not None:
            room_key = [v for k, v in zone_dict.items() if k in key]
        if not room_key:
            room_key = ['Single office']
        room = dict([k for k in uc_file.items() if type(k[1]) == dict])[room_key[0]]
        return room, room_key

    def _set_people(self, idf, name, zone_name, space, method='area'):
        schedule_name = "Schedule " + "People " + space.usage.replace(',', '')
        profile_name = 'persons_profile'
        self._set_day_week_year_schedule(idf, space.persons_profile[:24], profile_name, schedule_name)
        # set default activity schedule
        if idf.getobject("SCHEDULETYPELIMITS", "Any Number") is None:
            idf.newidfobject("SCHEDULETYPELIMITS", Name="Any Number")
        activity_schedule_name = "Schedule Activity " + str(space.fixed_heat_flow_rate_persons)
        if idf.getobject("SCHEDULE:COMPACT", activity_schedule_name) is None:
            idf.newidfobject("SCHEDULE:COMPACT",
                             Name=activity_schedule_name,
                             Schedule_Type_Limits_Name="Any Number",
                             Field_1="Through: 12/31",
                             Field_2="For: Alldays",
                             Field_3="Until: 24:00",
                             Field_4=space.fixed_heat_flow_rate_persons  # in W/Person
                             )  # other method for Field_4 (not used here) ="persons_profile"*"activity_degree_persons"*58,1*1,8 (58.1 W/(m2*met), 1.8m2/Person)

        people = idf.newidfobject(
            "PEOPLE",
            Name=name,
            Zone_or_ZoneList_Name=zone_name,
            Number_of_People_Calculation_Method="People/Area",
            People_per_Zone_Floor_Area=space.persons,
            Activity_Level_Schedule_Name=activity_schedule_name,
            Number_of_People_Schedule_Name=schedule_name,
            Fraction_Radiant=space.ratio_conv_rad_persons
        )

    def _set_day_week_year_schedule(self, idf, schedule, profile_name, schedule_name):
        if idf.getobject("SCHEDULE:DAY:HOURLY", name=schedule_name) == None:
            limits_name = 'Fraction'
            hours = {}
            if profile_name in {'heating_profile', 'cooling_profile'}:
                limits_name = 'Temperature'
                if idf.getobject("SCHEDULETYPELIMITS", "Temperature") is None:
                    idf.newidfobject("SCHEDULETYPELIMITS", Name="Temperature")
            for i, l in enumerate(schedule[:24]):
                if profile_name in {'heating_profile', 'cooling_profile'}:
                    if schedule[i] > 270:
                        schedule[i] = schedule[i] - 273.15
                    # set cooling profile manually to 25°C, #bs2021
                    if profile_name == 'cooling_profile':
                        schedule[i] = 25
                hours.update({'Hour_' + str(i + 1): schedule[i]})
            idf.newidfobject("SCHEDULE:DAY:HOURLY", Name=schedule_name, Schedule_Type_Limits_Name=limits_name, **hours)
        if idf.getobject("SCHEDULE:WEEK:COMPACT", name=schedule_name) == None:
            idf.newidfobject("SCHEDULE:WEEK:COMPACT", Name=schedule_name, DayType_List_1="AllDays",
                             ScheduleDay_Name_1=schedule_name)
        if idf.getobject("SCHEDULE:YEAR", name=schedule_name) == None:
            idf.newidfobject("SCHEDULE:YEAR", Name=schedule_name,
                             Schedule_Type_Limits_Name=limits_name,
                             ScheduleWeek_Name_1=schedule_name,
                             Start_Month_1=1,
                             Start_Day_1=1,
                             End_Month_1=12,
                             End_Day_1=31)

    def _set_equipment(self, idf, name, zone_name, space, method='area'):
        schedule_name = "Schedule " + "Equipment " + space.usage.replace(',', '')
        profile_name = 'machines_profile'
        self._set_day_week_year_schedule(idf, space.machines_profile[:24], profile_name, schedule_name)
        idf.newidfobject(
            "ELECTRICEQUIPMENT",
            Name=name,
            Zone_or_ZoneList_Name=zone_name,
            Schedule_Name=schedule_name,
            Design_Level_Calculation_Method="Watts/Area",
            Watts_per_Zone_Floor_Area=space.machines
        )

    def _set_lights(self, idf, name, zone_name, space, method='area'):
        # TODO: Define lighting parameters based on IFC (and User-Input otherwise)
        schedule_name = "Schedule " + "Lighting " + space.usage.replace(',', '')
        profile_name = 'lighting_profile'
        self._set_day_week_year_schedule(idf, space.lighting_profile[:24], profile_name, schedule_name)
        mode = "Watts/Area"
        watts_per_zone_floor_area = space.lighting_power
        return_air_fraction = 0.0
        fraction_radiant = 0.42  # cf. Table 1.28 in InputOutputReference EnergyPlus (Version 9.4.0), p. 506
        fraction_visible = 0.18  # Todo: fractions do not match with .json Data. Maybe set by user-input later

        idf.newidfobject(
            "LIGHTS",
            Name=name,
            Zone_or_ZoneList_Name=zone_name,
            Schedule_Name=schedule_name,
            Design_Level_Calculation_Method=mode,
            Watts_per_Zone_Floor_Area=watts_per_zone_floor_area,
            Return_Air_Fraction=return_air_fraction,
            Fraction_Radiant=fraction_radiant,
            Fraction_Visible=fraction_visible
        )

    @staticmethod
    def _set_infiltration(idf, name, zone_name, space):
        idf.newidfobject(
            "ZONEINFILTRATION:DESIGNFLOWRATE",
            Name=name,
            Zone_or_ZoneList_Name=zone_name,
            Schedule_Name="Continuous",
            Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
            Air_Changes_per_Hour=space.infiltration_rate
        )

    def _set_day_hvac_template(self, idf, space, name):
        clg_schedule_name = ''
        htg_schedule_name = "Schedule " + "Heating " + space.usage.replace(',', '')
        self._set_day_week_year_schedule(idf, space.heating_profile[:24], 'heating_profile', htg_schedule_name)

        # if room['with_cooling']:
        clg_schedule_name = "Schedule " + "Cooling " + space.usage.replace(',', '')
        self._set_day_week_year_schedule(idf, space.cooling_profile[:24], 'cooling_profile', clg_schedule_name)
        stat = idf.newidfobject(
            "HVACTEMPLATE:THERMOSTAT",
            Name=name,
            Heating_Setpoint_Schedule_Name=htg_schedule_name,
            Cooling_Setpoint_Schedule_Name=clg_schedule_name
        )
        return stat

    def _set_hvac_template(self, idf, name, heating_sp, cooling_sp, mode='setback'):
        """
        Set default HVAC Template
        :param idf: idf file object
        :return: stat (HVAC Template)
        """
        if cooling_sp < 20:
            cooling_sp = 26
        elif cooling_sp < 24:
            cooling_sp = 23

        setback_htg = 18  # "T_threshold_heating"
        setback_clg = 26  # "T_threshold_cooling"

        # ensure setback temperature actually performs a setback on temperature
        if setback_htg > heating_sp:
            setback_htg = heating_sp
        if setback_clg < cooling_sp:
            setback_clg = cooling_sp

        if mode == "setback":
            htg_alldays = self._define_schedule_part('Alldays', [('5:00', setback_htg), ('21:00', heating_sp),
                                                                 ('24:00', setback_htg)])
            clg_alldays = self._define_schedule_part('Alldays', [('5:00', setback_clg), ('21:00', cooling_sp),
                                                                 ('24:00', setback_clg)])
            htg_name = "H_SetBack_" + str(heating_sp)
            clg_name = "C_SetBack_" + str(cooling_sp)
            if idf.getobject("SCHEDULE:COMPACT", htg_name) is None:
                htg_sched = self._write_schedule(idf, htg_name, [htg_alldays, ])
            else:
                htg_sched = idf.getobject("SCHEDULE:COMPACT", htg_name)
            if idf.getobject("SCHEDULE:COMPACT", clg_name) is None:
                clg_sched = self._write_schedule(idf, clg_name, [clg_alldays, ])
            else:
                clg_sched = idf.getobject("SCHEDULE:COMPACT", clg_name)
            stat = idf.newidfobject(
                "HVACTEMPLATE:THERMOSTAT",
                Name="STAT_" + name,
                Heating_Setpoint_Schedule_Name=htg_name,
                Cooling_Setpoint_Schedule_Name=clg_name,
            )

        if mode == "constant":
            stat = idf.newidfobject(
                "HVACTEMPLATE:THERMOSTAT",
                Name="STAT_" + name,
                Constant_Heating_Setpoint=heating_sp,
                Constant_Cooling_Setpoint=cooling_sp,
            )
        return stat

    @staticmethod
    def _write_schedule(idf, sched_name, sched_part_list):
        """
        Write schedule from list of schedule parts
        :param name: Name of the schedule
        :param sched_part_list: List of schedule parts
        :return:
        """
        sched_list = {}
        field_count = 1
        for parts in sched_part_list:
            field_count += 1
            sched_list.update({'Field_' + str(field_count): 'For: ' + parts[0]})
            part = parts[1]
            for set in part:
                field_count += 1
                sched_list.update({'Field_' + str(field_count): 'Until: ' + str(set[0])})
                field_count += 1
                sched_list.update({'Field_' + str(field_count): str(set[1])})
        if idf.getobject("SCHEDULETYPELIMITS", "Temperature") is None:
            idf.newidfobject("SCHEDULETYPELIMITS", Name="Temperature")

        sched = idf.newidfobject(
            "SCHEDULE:COMPACT",
            Name=sched_name,
            Schedule_Type_Limits_Name="Temperature",
            Field_1="Through: 12/31",
            **sched_list
        )
        return sched

    @staticmethod
    def _define_schedule_part(days, til_time_temp):
        """
        Define part of a schedule
        :param days: string: Weekdays, Weekends, Alldays, AllOtherDays, Saturdays, Sundays, ...
        :param til_time_temp: List of tuples (until-time format 'h:mm' (24h) as str), temperature until this time in Celsius), e.g. (05:00, 18)
        :return:
        """
        return [days, til_time_temp]

    def _add_shadings(self, instances, split_shadings, idf):
        spatials = []
        for inst in instances:
            if isinstance(instances[inst], ExternalSpatialElement):
                for sb in instances[inst].space_boundaries:
                    spatials.append(sb)
        if not spatials:
            return
        if split_shadings:
            self._split_non_convex_shadings(instances, spatials)
        pure_spatials = []
        for s in spatials:
            # only consider almost horizontal 2b shapes (roof-like SBs)
            if s.level_description == '2b':
                angle = math.degrees(gp_Dir(s.bound_normal).Angle(gp_Dir(gp_XYZ(0, 0, 1))))
                if not ((-45 < angle < 45) or (135 < angle < 225)):
                    continue
            if s.related_bound and s.related_bound.ifc.RelatingSpace.is_a('IfcSpace'):
                continue
            pure_spatials.append(s)

        for s in pure_spatials:
            obj = idf.newidfobject('SHADING:BUILDING:DETAILED',
                                   Name=s.guid,
                                   )
            obj_pnts = PyOCCTools.get_points_of_face(s.bound_shape)
            obj_coords = []
            for pnt in obj_pnts:
                co = tuple(round(p, 3) for p in pnt.Coord())
                obj_coords.append(co)
            obj.setcoords(obj_coords)

    @staticmethod
    def _set_simulation_control(idf):
        """
        Set simulation control parameters.
        :param idf: idf file object
        :return: idf file object
        """
        for sim_control in idf.idfobjects["SIMULATIONCONTROL"]:
            print("")
            # sim_control.Do_Zone_Sizing_Calculation = "Yes"
            sim_control.Do_System_Sizing_Calculation = "Yes"
            # sim_control.Do_Plant_Sizing_Calculation = "Yes"
            sim_control.Run_Simulation_for_Sizing_Periods = "No"
            sim_control.Run_Simulation_for_Weather_File_Run_Periods = "Yes"
        # return idf

    @staticmethod
    def _set_output_variables(idf):
        """
        Adds userdefined output variables to the idf file
        :param idf: idf file object
        :return: idf file object
        """
        out_control = idf.idfobjects['OUTPUTCONTROL:TABLE:STYLE']
        out_control[0].Column_Separator = 'CommaAndHTML'

        # remove all existing output variables with reporting frequency "Timestep"
        out_var = [v for v in idf.idfobjects['OUTPUT:VARIABLE']
                   if v.Reporting_Frequency.upper() == "TIMESTEP"]
        for var in out_var:
            idf.removeidfobject(var)

        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Ideal Loads Supply Air Total Heating Energy",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Ideal Loads Supply Air Total Cooling Energy",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Site Outdoor Air Drybulb Temperature",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Mean Air Temperature",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Operative Temperature",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Infiltration Mass Flow Rate",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone People Occupant Count",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone People Convective Heating Rate",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Electric Equipment Convective Heating Rate",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Lights Convective Heating Rate",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Ideal Loads Zone Sensible Cooling Rate",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Ideal Loads Zone Sensible Heating Rate",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Windows Total Heat Gain Rate",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Windows Total Heat Gain Energy",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Air Heat Balance Internal Convective Heat Gain Rate",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Air Heat Balance Surface Convection Rate",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Air Heat Balance Outdoor Air Transfer Rate",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Air Heat Balance Air Energy Storage Rate",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Site Outdoor Air Humidity Ratio",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Site Outdoor Air Relative Humidity",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Site Outdoor Air Barometric Pressure",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Mixing Current Density Volume Flow Rate",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Mixing Sensible Heat Gain Rate",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Air Relative Humidity",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Air System Sensible Heating Energy",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Air System Sensible Cooling Energy",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Windows Total Transmitted Solar Radiation Energy",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Surface Window Heat Gain Energy",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Surface Inside Face Convection Heat Gain Energy",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Surface Outside Face Convection Heat Gain Energy",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Opaque Surface Outside Face Conduction",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Infiltration Sensible Heat Gain Energy",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Infiltration Sensible Heat Loss Energy",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Infiltration Standard Density Volume Flow Rate",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Air Relative Humidity",
            Reporting_Frequency="Hourly",
        )
        # idf.newidfobject(
        #     "OUTPUT:VARIABLE",
        #     Variable_Name="Surface Inside Face Temperature",
        #     Reporting_Frequency="Hourly",
        # )
        idf.newidfobject(
            "OUTPUT:METER",
            Key_Name="Heating:EnergyTransfer",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:METER",
            Key_Name="Cooling:EnergyTransfer",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject("OUTPUT:SURFACES:DRAWING",
                         Report_Type="DXF")
        idf.newidfobject("OUTPUT:DIAGNOSTICS",
                         Key_1="DisplayAdvancedReportVariables",
                         Key_2="DisplayExtraWarnings")
        return idf

    def _idf_validity_check(self, idf):
        """basic validity check of idf.
        Remove openings from adiabatic surfaces
        """
        self.logger.info('Start IDF Validity Checker')

        fenestration = idf.idfobjects['FENESTRATIONSURFACE:DETAILED']
        for f in fenestration:
            if not f.Building_Surface_Name:
                self.logger.info('Removed Fenestration: %s' % f.Name)
                idf.removeidfobject(f)
            fbco = f.Building_Surface_Name
            bs = idf.getobject('BUILDINGSURFACE:DETAILED', fbco)
            if bs.Outside_Boundary_Condition == 'Adiabatic':
                self.logger.info('Removed Fenestration: %s' % f.Name)
                idf.removeidfobject(f)
        for f in fenestration:
            fbco = f.Building_Surface_Name
            bs = idf.getobject('BUILDINGSURFACE:DETAILED', fbco)
            if bs.Outside_Boundary_Condition == 'Adiabatic':
                self.logger.info('Removed Fenestration in second try: %s' % f.Name)
                idf.removeidfobject(f)

        sfs = idf.getsurfaces()
        small_area_obj = [s for s in sfs
                          if PyOCCTools.get_shape_area(PyOCCTools.make_faces_from_pnts(s.coords)) < 1e-2]

        for obj in small_area_obj:
            self.logger.info('Removed small area: %s' % obj.Name)
            idf.removeidfobject(obj)

        shadings = idf.getshadingsurfaces()
        small_area_obj = [s for s in shadings
                          if PyOCCTools.get_shape_area(PyOCCTools.make_faces_from_pnts(s.coords)) < 1e-2]

        for obj in small_area_obj:
            self.logger.info('Removed small area: %s' % obj.Name)
            idf.removeidfobject(obj)

        bsd = idf.idfobjects['BUILDINGSURFACE:DETAILED']
        for sf in bsd:
            if sf.Construction_Name == 'BS Exterior Window':
                self.logger.info('Surface due to invalid material: %s' % sf.Name)
                idf.removeidfobject(sf)
        self.logger.info('IDF Validity Checker done')

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

    def _move_children_to_parents(self, instances):
        """move external opening boundaries to related parent boundary (e.g. wall)"""
        self.logger.info("Move openings to base surface, if needed")
        for inst in instances:
            if hasattr(instances[inst], 'related_parent_bound'):
                opening_obj = instances[inst]
                # only external openings need to be moved
                # all other are properly placed within parent boundary
                if opening_obj.is_external:
                    distance = BRepExtrema_DistShapeShape(
                        opening_obj.bound_shape,
                        opening_obj.related_parent_bound.bound_shape,
                        Extrema_ExtFlag_MIN
                    ).Value()
                    if distance < 0.001:
                        continue
                    prod_vec = []
                    for i in opening_obj.bound_normal.Coord():
                        prod_vec.append(distance * i)

                    # moves opening to parent boundary
                    trsf = gp_Trsf()
                    coord = gp_XYZ(*prod_vec)
                    vec = gp_Vec(coord)
                    trsf.SetTranslation(vec)

                    opening_obj.bound_shape_org = opening_obj.bound_shape
                    opening_obj.bound_shape = BRepBuilderAPI_Transform(opening_obj.bound_shape, trsf).Shape()

                    # check if opening has been moved to boundary correctly
                    # and otherwise move again in reversed direction
                    new_distance = BRepExtrema_DistShapeShape(
                        opening_obj.bound_shape,
                        opening_obj.related_parent_bound.bound_shape,
                        Extrema_ExtFlag_MIN
                    ).Value()
                    if new_distance > 1e-3:
                        prod_vec = []
                        op_normal = opening_obj.bound_normal.Reversed()
                        for i in op_normal.Coord():
                            prod_vec.append(new_distance * i)
                        trsf = gp_Trsf()
                        coord = gp_XYZ(*prod_vec)
                        vec = gp_Vec(coord)
                        trsf.SetTranslation(vec)
                        opening_obj.bound_shape = BRepBuilderAPI_Transform(opening_obj.bound_shape, trsf).Shape()
                    # update bound center attribute for new shape location
                    opening_obj.bound_center = SpaceBoundary.get_bound_center(opening_obj, 'bound_center')

    def _get_parents_and_children(self, instances):
        """get parent-children relationships between IfcElements (e.g. Windows, Walls)
        and the corresponding relationships of their space boundaries"""
        self.logger.info("Compute relationships between space boundaries")
        self.logger.info("Compute relationships between openings and their base surfaces")
        drop_list = {}  # HACK: dictionary for bounds which have to be removed from instances (due to duplications)
        for inst in instances:
            inst_obj = instances[inst]
            if not inst_obj.ifc.is_a('IfcRelSpaceBoundary'):
                continue
            if inst_obj.level_description == "2b":
                continue
            inst_obj_space = inst_obj.ifc.RelatingSpace
            b_inst = inst_obj.bound_instance
            if b_inst is None:
                continue
            # assign opening elems (Windows, Doors) to parents and vice versa
            if not hasattr(b_inst.ifc, 'HasOpenings'):
                continue
            if len(b_inst.ifc.HasOpenings) == 0:
                continue
            for opening in b_inst.ifc.HasOpenings:
                if hasattr(opening.RelatedOpeningElement, 'HasFillings'):
                    for fill in opening.RelatedOpeningElement.HasFillings:
                        opening_obj = instances[fill.RelatedBuildingElement.GlobalId]
                        if not hasattr(b_inst, 'related_openings'):
                            setattr(b_inst, 'related_openings', [])
                        if opening_obj in b_inst.related_openings:
                            continue
                        b_inst.related_openings.append(opening_obj)
                        if not hasattr(opening_obj, 'related_parent'):
                            setattr(opening_obj, 'related_parent', [])
                        opening_obj.related_parent = b_inst
            # assign space boundaries of opening elems (Windows, Doors) to parents and vice versa
            if not hasattr(b_inst, 'related_openings'):
                continue
            if not hasattr(inst_obj, 'related_opening_bounds'):
                setattr(inst_obj, 'related_opening_bounds', [])
            for opening in b_inst.related_openings:
                for op_bound in opening.space_boundaries:
                    if op_bound.ifc.RelatingSpace == inst_obj_space:
                        if op_bound in inst_obj.related_opening_bounds:
                            continue
                        distance = BRepExtrema_DistShapeShape(
                            op_bound.bound_shape,
                            inst_obj.bound_shape,
                            Extrema_ExtFlag_MIN
                        ).Value()
                        if distance > 0.3:
                            continue
                        center_shape = BRepBuilderAPI_MakeVertex(gp_Pnt(op_bound.bound_center)).Shape()
                        center_dist = BRepExtrema_DistShapeShape(
                            inst_obj.bound_shape,
                            center_shape,
                            Extrema_ExtFlag_MIN
                        ).Value()
                        if center_dist > 0.3:
                            continue
                        # HACK:
                        # some space boundaries have inner loops which are removed for vertical bounds in
                        # calc_bound_shape (elements.py). Those inner loops contain an additional vertical bound (wall)
                        # which is "parent" of an opening. EnergyPlus does not accept openings having a parent surface
                        # of same size as the opening. Thus, since inner loops are removed from shapes beforehand,
                        # those boundaries are removed from "instances" and the openings are assigned to have the larger
                        # boundary as a parent.
                        #
                        # find cases where opening area matches area of corresponding wall (within inner loop)
                        if (inst_obj.bound_area - op_bound.bound_area).m < 0.01:
                            rel_bound = None
                            drop_list[inst] = inst_obj
                            ib = [b for b in b_inst.space_boundaries if
                                  b.ifc.ConnectionGeometry.SurfaceOnRelatingElement.InnerBoundaries if
                                  b.bound_thermal_zone == op_bound.bound_thermal_zone]
                            if len(ib) == 1:
                                rel_bound = ib[0]
                            elif len(ib) > 1:
                                for b in ib:
                                    # check if orientation of possibly related bound is the same as opening
                                    angle = math.degrees(gp_Dir(b.bound_normal).Angle(gp_Dir(op_bound.bound_normal)))
                                    if not (angle < 0.1 or angle > 179.9):
                                        continue
                                    distance = BRepExtrema_DistShapeShape(
                                        b.bound_shape,
                                        op_bound.bound_shape,
                                        Extrema_ExtFlag_MIN
                                    ).Value()
                                    if distance > 0.4:
                                        continue
                                    else:
                                        rel_bound = b
                            elif not rel_bound:
                                tzb = [b for b in op_bound.bound_thermal_zone.space_boundaries if
                                       b.ifc.ConnectionGeometry.SurfaceOnRelatingElement.InnerBoundaries]
                                for b in tzb:
                                    # check if orientation of possibly related bound is the same as opening
                                    try:
                                        angle = math.degrees(
                                            gp_Dir(b.bound_normal).Angle(gp_Dir(op_bound.bound_normal)))
                                    except:
                                        pass
                                    if not (angle < 0.1 or angle > 179.9):
                                        continue
                                    distance = BRepExtrema_DistShapeShape(
                                        b.bound_shape,
                                        op_bound.bound_shape,
                                        Extrema_ExtFlag_MIN
                                    ).Value()
                                    if distance > 0.4:
                                        continue
                                    else:
                                        rel_bound = b
                                if not rel_bound:
                                    continue
                            else:
                                continue
                            if not rel_bound:
                                continue
                            if not hasattr(rel_bound, 'related_opening_bounds'):
                                setattr(rel_bound, 'related_opening_bounds', [])
                            rel_bound.related_opening_bounds.append(op_bound)
                            if not hasattr(op_bound, 'related_parent_bound'):
                                setattr(op_bound, 'related_parent_bound', [])
                            op_bound.related_parent_bound = rel_bound
                        else:
                            inst_obj.related_opening_bounds.append(op_bound)
                            if not hasattr(op_bound, 'related_parent_bound'):
                                setattr(op_bound, 'related_parent_bound', [])
                            op_bound.related_parent_bound = inst_obj
        # remove boundaries from instances if they are false duplicates of windows in shape of walls
        instances = {k: v for k, v in instances.items() if k not in drop_list}

    def _split_non_convex_bounds(self, instances):
        bounds = [instances[i] for i in instances if instances[i].ifc.is_a('IfcRelSpaceBoundary')]
        bounds_except_openings = [b for b in bounds if not hasattr(b, 'related_parent_bound')]
        conv = []
        nconv = []
        others = []
        processed_id = []
        for bound in bounds_except_openings:
            if hasattr(bound, 'convex_processed'):
                continue
            if hasattr(bound, 'related_opening_bounds'): # check all space boundaries that are not parent to an opening bound
                if bim2sim.task.common.inner_loop_remover.is_convex_slow(bound.bound_shape):
                    continue
                # handle shapes that contain opening bounds
                convex_shapes = convex_decomposition(bound.bound_shape,
                                                     [op.bound_shape for op in bound.related_opening_bounds])
            else:
                if is_convex_no_holes(bound.bound_shape):
                    continue
                convex_shapes = convex_decomposition(bound.bound_shape)
            nconv.append(bound)
            if hasattr(bound, 'bound_normal'):
                del bound.__dict__['bound_normal']
            new_space_boundaries = self._create_new_convex_bounds(convex_shapes, bound, bound.related_bound)
            bound.convex_processed = True
            if (bound.related_bound and bound.related_bound.ifc.RelatingSpace.is_a('IfcSpace')) \
                    and not bound.ifc.Description == '2b':
                nconv.append(bound.related_bound)
                del instances[bound.related_bound.guid]
                bounds_except_openings.remove(bound.related_bound)
                bound.related_bound.convex_processed = True
            del instances[bound.guid]
            for new_bound in new_space_boundaries:
                instances[new_bound.guid] = new_bound
                conv.append(new_bound)
        pass

    def _split_non_convex_shadings(self, instances, spatial_bounds):
        spatial_elem = instances[[inst for inst in instances if isinstance(instances[inst], ExternalSpatialElement)][
            0]]
        for spatial in spatial_bounds:
            if is_convex_no_holes(spatial.bound_shape):
                continue
            convex_shapes = convex_decomposition(spatial.bound_shape)
            new_space_boundaries = self._create_new_convex_bounds(convex_shapes, spatial)
            spatial_bounds.remove(spatial)
            if spatial in spatial_elem.space_boundaries:
                spatial_elem.space_boundaries.remove(spatial)
            for new_bound in new_space_boundaries:
                spatial_bounds.append(new_bound)
                spatial_elem.space_boundaries.append(new_bound)
        pass

    def _create_copy_of_space_boundary(self, bound):
        new_bound = copy.copy(bound)
        new_bound.guid = ifcopenshell.guid.new()
        if hasattr(new_bound, 'bound_center'):
            del new_bound.__dict__['bound_center']
        if hasattr(new_bound, 'bound_normal'):
            del new_bound.__dict__['bound_normal']
        return new_bound

    def _create_new_convex_bounds(self, convex_shapes, bound, related_bound=None):
        bound.non_convex_guid = bound.guid
        new_space_boundaries = []
        openings = []
        if hasattr(bound, 'related_opening_bounds'):
            openings.extend(bound.related_opening_bounds)
        for shape in convex_shapes:
            new_bound = self._create_copy_of_space_boundary(bound)
            new_bound.bound_shape = shape
            new_bound.bound_area = SpaceBoundary.get_bound_area(new_bound, 'name')
            if openings:
                delattr(new_bound, 'related_opening_bounds')
                for opening in openings:
                    distance = BRepExtrema_DistShapeShape(
                        new_bound.bound_shape,
                        opening.bound_shape,
                        Extrema_ExtFlag_MIN
                    ).Value()
                    if distance < 1e-3:
                        if not hasattr(new_bound, 'related_opening_bounds'):
                            setattr(new_bound, 'related_opening_bounds', [])
                        new_bound.related_opening_bounds.append(opening)
                        opening.related_parent_bound = new_bound
            if not all([abs(i) < 1e-3 for i in ((new_bound.bound_normal - bound.bound_normal).Coord())]):
                new_bound.bound_shape = PyOCCTools.flip_orientation_of_face(new_bound.bound_shape)
                new_bound.bound_normal = PyOCCTools.simple_face_normal(new_bound.bound_shape)
            if (related_bound and bound.related_bound.ifc.RelatingSpace.is_a('IfcSpace')) \
                    and not bound.ifc.Description == '2b':
                distance = BRepExtrema_DistShapeShape(
                    bound.bound_shape,
                    related_bound.bound_shape,
                    Extrema_ExtFlag_MIN
                ).Value()
                new_rel_bound = self._create_copy_of_space_boundary(related_bound)
                related_bound.non_convex_guid = related_bound.guid
                if distance > 1e-3:
                    new_rel_shape = PyOCCTools._move_bound_in_direction_of_normal(new_bound, distance, reversed=False)
                else:
                    new_rel_shape = new_bound.bound_shape
                new_rel_bound.bound_shape = new_rel_shape
                new_rel_bound.bound_shape = PyOCCTools.flip_orientation_of_face(new_rel_bound.bound_shape)
                new_rel_bound.bound_normal = PyOCCTools.simple_face_normal(new_rel_bound.bound_shape)
                new_rel_bound.bound_area = SpaceBoundary.get_bound_area(new_rel_bound, 'name')
                if hasattr(new_bound, 'related_opening_bounds'):
                    for op in new_bound.related_opening_bounds:
                        if not op.related_bound:
                            continue
                        new_rel_bound.related_opening_bounds.append(op.related_bound)
                        op.related_bound.related_parent_bound = new_rel_bound
                new_bound.related_bound = new_rel_bound
                new_rel_bound.related_bound = new_bound
                new_space_boundaries.append(new_rel_bound)
            new_space_boundaries.append(new_bound)
        return new_space_boundaries


    @staticmethod
    def _display_shape_of_space_boundaries(instances):
        """Display topoDS_shapes of space boundaries"""
        display, start_display, add_menu, add_function_to_menu = init_display()
        colors = ['blue', 'red', 'magenta', 'yellow', 'green', 'white', 'cyan']
        col = 0
        for inst in instances:
            if instances[inst].ifc.is_a('IfcRelSpaceBoundary'):
                col += 1
                bound = instances[inst]
                if bound.bound_instance is None:
                    continue
                if not bound.bound_instance.ifc.is_a("IfcWall"):
                    pass
                try:
                    display.DisplayShape(bound.bound_shape, color=colors[(col - 1) % len(colors)])
                except:
                    continue
        display.FitAll()
        start_display()

    @staticmethod
    def _display_bound_normal_orientation(instances):
        display, start_display, add_menu, add_function_to_menu = init_display()
        col = 0
        for inst in instances:
            if not instances[inst].ifc.is_a('IfcSpace'):
                continue
            space = instances[inst]
            for bound in space.space_boundaries:
                face_towards_center = space.space_center.XYZ() - bound.bound_center
                face_towards_center.Normalize()
                dot = face_towards_center.Dot(bound.bound_normal)
                if dot > 0:
                    display.DisplayShape(bound.bound_shape, color="red")
                else:
                    display.DisplayShape(bound.bound_shape, color="green")
        display.FitAll()
        start_display()

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

    def _fix_surface_orientation(self, instances):
        """
        Fix orientation of space boundaries.
        Fix orientation of all surfaces but openings by sewing followed by disaggregation.
        Fix orientation of openings afterwards according to orientation of parent bounds.
        """
        self.logger.info("Fix surface orientation")
        for inst in instances:
            if not instances[inst].ifc.is_a('IfcSpace'):
                continue
            space = instances[inst]
            face_list = []
            for bound in space.space_boundaries:
                if hasattr(bound, 'related_parent_bound'):
                    continue
                exp = TopExp_Explorer(bound.bound_shape, TopAbs_FACE)
                face = exp.Current()
                try:
                    face = topods_Face(face)
                    face_list.append(face)
                except:
                    exp1 = TopExp_Explorer(bound.bound_shape, TopAbs_WIRE)
                    wire = exp1.Current()
                    face = BRepBuilderAPI_MakeFace(wire).Face()
                    face_list.append(face)
            if not face_list:
                continue
            if hasattr(space, 'space_boundaries_2B'):
                for bound in space.space_boundaries_2B:
                    exp = TopExp_Explorer(bound.bound_shape, TopAbs_FACE)
                    face = exp.Current()
                    face = topods_Face(face)
                    face_list.append(face)
            sew = BRepBuilderAPI_Sewing(0.0001)
            for fc in face_list:
                sew.Add(fc)
            sew.Perform()
            sewed_shape = sew.SewedShape()
            fixed_shape = sewed_shape
            p = GProp_GProps()
            brepgprop_VolumeProperties(fixed_shape, p)
            if p.Mass() < 0:
                fixed_shape.Complement()
            f_exp = TopExp_Explorer(fixed_shape, TopAbs_FACE)
            fixed_faces = []
            while f_exp.More():
                fixed_faces.append(topods_Face(f_exp.Current()))
                f_exp.Next()
            for fc in fixed_faces:
                an_exp = TopExp_Explorer(fc, TopAbs_FACE)
                a_face = an_exp.Current()
                face = topods_Face(a_face)
                surf = BRep_Tool.Surface(face)
                obj = surf
                assert obj.DynamicType().Name() == "Geom_Plane"
                plane = Handle_Geom_Plane_DownCast(surf)
                face_normal = plane.Axis().Direction().XYZ()
                p = GProp_GProps()
                brepgprop_SurfaceProperties(face, p)
                face_center = p.CentreOfMass().XYZ()
                complemented = False
                for bound in space.space_boundaries:
                    if (gp_Pnt(bound.bound_center).Distance(gp_Pnt(face_center)) > 1e-3):
                        continue
                    if ((bound.bound_area.m - p.Mass()) ** 2 < 0.01):
                        if fc.Orientation() == 1:
                            bound.bound_shape.Complement()
                            complemented = True
                        elif face_normal.Dot(bound.bound_normal) < 0:
                            bound.bound_shape.Complement()
                            complemented = True
                        if not complemented:
                            continue
                        # if hasattr(bound, 'bound_normal'):
                        #     del bound.__dict__['bound_normal']
                        if hasattr(bound, 'related_opening_bounds'):
                            op_bounds = bound.related_opening_bounds
                            for op in op_bounds:
                                op.bound_shape.Complement()
                                # if hasattr(op, 'bound_normal'):
                                #     del op.__dict__['bound_normal']
                        break
                if not hasattr(space, 'space_boundaries_2B'):
                    continue
                for bound in space.space_boundaries_2B:
                    if gp_Pnt(bound.bound_center).Distance(gp_Pnt(face_center)) < 1e-6:
                        bound.bound_shape = face
                        if hasattr(bound, 'bound_normal'):
                            del bound.__dict__['bound_normal']
                        break

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

    # def _check_for_vertex_duplicates(self):
    #     if self.related_bound is not None:
    #         nb_vert_this = self.get_number_of_vertices(self.bound_shape)
    #         nb_vert_other = self.get_number_of_vertices(self.related_bound.bound_shape)
    #         # if nb_vert_this != nb_vert_other:
    #         setattr(self, 'bound_shape_org', self.bound_shape)
    #         vert_list1 = self.get_vertex_list_from_face(self.bound_shape)
    #         vert_list1 = self.remove_vertex_duplicates(vert_list1)
    #         vert_list1.reverse()
    #         vert_list1 = self.remove_vertex_duplicates(vert_list1)
    #
    #         setattr(self.related_bound, 'bound_shape_org', self.related_bound.bound_shape)
    #         vert_list2 = self.get_vertex_list_from_face(self.related_bound.bound_shape)
    #         vert_list2 = self.remove_vertex_duplicates(vert_list2)
    #         vert_list2.reverse()
    #         vert_list2 = self.remove_vertex_duplicates(vert_list2)
    #
    #         if len(vert_list1) == len(vert_list2):
    #             self.bound_shape = self.make_face_from_vertex_list(vert_list1)
    #             self.related_bound.bound_shape = self.make_face_from_vertex_list(vert_list2)

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

    # @staticmethod
    # def remove_vertex_duplicates(vert_list):
    #     for i, vert in enumerate(vert_list):
    #         edge_pp_p = BRepBuilderAPI_MakeEdge(vert_list[(i) % (len(vert_list) - 1)],
    #                                             vert_list[(i + 1) % (len(vert_list) - 1)]).Shape()
    #         distance = BRepExtrema_DistShapeShape(vert_list[(i + 2) % (len(vert_list) - 1)], edge_pp_p,
    #                                               Extrema_ExtFlag_MIN)
    #         if 0 < distance.Value() < 0.001:
    #             # first: project close vertex to edge
    #             edge = BRepBuilderAPI_MakeEdge(vert_list[(i) % (len(vert_list) - 1)],
    #                                                 vert_list[(i + 1) % (len(vert_list) - 1)]).Edge()
    #             projector = GeomAPI_ProjectPointOnCurve(BRep_Tool.Pnt(vert_list[(i + 2) % (len(vert_list) - 1)]),
    #                                                     BRep_Tool.Curve(edge)[0])
    #             np = projector.NearestPoint()
    #             vert_list[(i + 2) % (len(vert_list) - 1)] = BRepBuilderAPI_MakeVertex(np).Vertex()
    #             # delete additional vertex
    #             vert_list.pop((i + 1) % (len(vert_list) - 1))
    #     return vert_list
    #
    # @staticmethod
    # def make_face_from_vertex_list(vert_list):
    #     an_edge = []
    #     for i in range(len(vert_list[:-1])):
    #         edge = BRepBuilderAPI_MakeEdge(vert_list[i], vert_list[i + 1]).Edge()
    #         an_edge.append(edge)
    #     a_wire = BRepBuilderAPI_MakeWire()
    #     for edge in an_edge:
    #         a_wire.Add(edge)
    #     a_wire = a_wire.Wire()
    #     a_face = BRepBuilderAPI_MakeFace(a_wire).Face()
    #
    #     return a_face.Reversed()
    #
    # @staticmethod
    # def get_vertex_list_from_face(face):
    #     an_exp = TopExp_Explorer(face, TopAbs_WIRE)
    #     vert_list = []
    #     while an_exp.More():
    #         wire = topods_Wire(an_exp.Current())
    #         w_exp = BRepTools_WireExplorer(wire)
    #         while w_exp.More():
    #             vert1 = w_exp.CurrentVertex()
    #             vert_list.append(vert1)
    #             w_exp.Next()
    #         an_exp.Next()
    #     vert_list.append(vert_list[0])
    #
    #     return vert_list
    #
    # @staticmethod
    # def get_number_of_vertices(shape):
    #     shape_analysis = ShapeAnalysis_ShapeContents()
    #     shape_analysis.Perform(shape)
    #     nb_vertex = shape_analysis.NbVertices()
    #
    #     return nb_vertex
    #


class IfcValidation:
    def __init__(self, ifc, paths):
        self.error_summary = {}
        self.bounds = ifc.by_type('IfcRelSpaceBoundary')
        self.id_list = [e.GlobalId for e in ifc.by_type("IfcRoot")]
        self.paths = paths
        self.logger.info("Check syntax of IfcRelSpaceBoundary")
        self._check_space_boundaries()
        self._write_errors_to_json()
        self.logger.info("All tests done!")
        self._evaluate_checks(ifc)

    def _check_space_boundaries(self):
        for bound in self.bounds:
            sbv = SpaceBoundaryValidation(bound, self.id_list)
            if len(sbv.error) > 0:
                self.error_summary.update({bound.GlobalId: sbv.error})

    def _write_errors_to_json(self):
        with open(str(self.paths.root) + "/export/" + 'ifc_SB_error_summary.json', 'w+') as fp:
            json.dump(self.error_summary, fp, indent="\t")

    def _evaluate_checks(self):
        if len(self.error_summary) == 0:
            self.logger.info(
                "All %d IfcRelSpaceBoundary entities PASSED the syntax validation process." % len(self.bounds))
        else:
            self.logger.warning("%d out of %d IfcRelSpaceBoundary entities FAILED the syntax validation process. \n"
                                "Occuring sets of errors: %s \n"
                                "See ifc_SB_error_summary.json for further information on the errors."
                                % (len(self.error_summary),
                                   len(self.bounds),
                                   set(tuple(s) for s in [vals for key, vals in self.error_summary.items()])))


class SpaceBoundaryValidation(IfcValidation):
    def __init__(self, bound, id_list):
        self.error = []
        self.bound = bound
        self.id_list = id_list

        self._validate_space_boundaries()

    def _validate_space_boundaries(self):
        self._apply_validation_function(self._check_unique(), 'GlobalId')
        self._apply_validation_function(self._check_level(), '2ndLevel')
        self._apply_validation_function(self._check_description(), 'Description')
        self._apply_validation_function(self._check_rel_space(), 'RelatingSpace')
        self._apply_validation_function(self._check_rel_building_elem(), 'RelatedBuildingElement')
        self._apply_validation_function(self._check_conn_geom(), 'ConnectionGeometry')
        self._apply_validation_function(self._check_phys_virt_bound(), 'PhysicalOrVirtualBoundary')
        self._apply_validation_function(self._check_int_ext_bound(), 'InternalOrExternalBoundary')
        self._apply_validation_function(self._check_on_relating_elem(), 'SurfaceOnRelatingElement')
        self._apply_validation_function(self._check_on_related_elem(), 'SurfaceOnRelatedElement')
        self._apply_validation_function(self._check_basis_surface(), 'BasisSurface')
        self._apply_validation_function(self._check_inner_boundaries(), 'InnerBoundaries')
        if hasattr(self.bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary, 'Segments'):
            self._apply_validation_function(self._check_outer_boundary_composite(), 'OuterBoundaryCompositeCurve')
            self._apply_validation_function(self._check_segments(), 'Segments')
            self._apply_validation_function(self._check_segments_poly(), 'SegmentsPolyline')
            self._apply_validation_function(self._check_segments_poly_coord(), 'SegmentsPolylineCoordinates')
        else:
            self._apply_validation_function(self._check_outer_boundary_poly(), 'OuterBoundaryPolyline')
            self._apply_validation_function(self._check_outer_boundary_poly_coord(), 'OuterBoundaryPolylineCoordinates')
        self._apply_validation_function(self._check_plane_position(), 'Position')
        self._apply_validation_function(self._check_location(), 'Location')
        self._apply_validation_function(self._check_axis(), 'Axis')
        self._apply_validation_function(self._check_refdirection(), 'RefDirection')
        self._apply_validation_function(self._check_location_coord(), 'LocationCoordinates')
        self._apply_validation_function(self._check_axis_dir_ratios(), 'AxisDirectionRatios')
        self._apply_validation_function(self._check_refdirection_dir_ratios(), 'RefDirectionDirectionRatios')

    def _apply_validation_function(self, fct, err_name):
        if not fct:
            self.error.append(err_name)

    def _check_unique(self):
        return self.id_list.count(self.bound.GlobalId) == 1

    def _check_level(self):
        return self.bound.Name == "2ndLevel"

    def _check_description(self):
        return self.bound.Description in {'2a', '2b'}

    def _check_rel_space(self):
        return any(
            [self.bound.RelatingSpace.is_a('IfcSpace') or self.bound.RelatingSpace.is_a('IfcExternalSpatialElement')])

    def _check_rel_building_elem(self):
        if self.bound.RelatedBuildingElement is not None:
            return self.bound.RelatedBuildingElement.is_a('IfcBuildingElement')

    def _check_conn_geom(self):
        return self.bound.ConnectionGeometry.is_a('IfcConnectionSurfaceGeometry')

    def _check_phys_virt_bound(self):
        return self.bound.PhysicalOrVirtualBoundary.upper() in {'PHYSICAL', 'VIRTUAL'}

    def _check_int_ext_bound(self):
        return self.bound.InternalOrExternalBoundary.upper() in {'INTERNAL',
                                                                 'EXTERNAL',
                                                                 'EXTERNAL_EARTH',
                                                                 'EXTERNAL_FIRE',
                                                                 'EXTERNAL_WATER'
                                                                 }

    def _check_on_relating_elem(self):
        return self.bound.ConnectionGeometry.SurfaceOnRelatingElement.is_a('IfcCurveBoundedPlane')

    def _check_on_related_elem(self):
        return self.bound.ConnectionGeometry.SurfaceOnRelatedElement is None

    def _check_basis_surface(self):
        return self.bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.is_a('IfcPlane')

    def _check_outer_boundary_composite(self):
        return self.bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary.is_a('IfcCompositeCurve')

    def _check_outer_boundary_poly(self):
        return self._check_poly_points(self.bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary)

    def _check_outer_boundary_poly_coord(self):
        return all(self.bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary)

    def _check_inner_boundaries(self):
        return (self.bound.ConnectionGeometry.SurfaceOnRelatingElement.InnerBoundaries is None) or \
               (i.is_a('IfcCompositeCurve')
                for i in self.bound.ConnectionGeometry.SurfaceOnRelatingElement.InnerBoundaries)

    def _check_segments(self):
        return (s.is_a('IfcPolyline')
                for s in self.bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary.Segments)

    def _check_segments_poly(self):
        return all(self._check_poly_points(s.ParentCurve)
                   for s in self.bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary.Segments)

    def _check_segments_poly_coord(self):
        return all(self._check_poly_points_coord(s.ParentCurve)
                   for s in self.bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary.Segments)

    def _check_plane_position(self):
        return self.bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.is_a('IfcAxis2Placement3D')

    def _check_poly_points(self, polyline):
        return polyline.is_a('IfcPolyline')

    def _check_location(self):
        return self.bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.Location.is_a(
            'IfcCartesianPoint')

    def _check_axis(self):
        return self.bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.Axis.is_a('IfcDirection')

    def _check_refdirection(self):
        return self.bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.RefDirection.is_a(
            'IfcDirection')

    def _check_coords(self, points):
        return points.is_a('IfcCartesianPoint') and 1 <= len(points.Coordinates) <= 4

    def _check_dir_ratios(self, dir_ratios):
        return 2 <= len(dir_ratios.DirectionRatios) <= 3

    def _check_poly_points_coord(self, polyline):
        return all(self._check_coords(p) for p in polyline.Points)

    def _check_location_coord(self):
        return self._check_coords(self.bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.Location)

    def _check_axis_dir_ratios(self):
        return self._check_dir_ratios(self.bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.Axis)

    def _check_refdirection_dir_ratios(self):
        return self._check_dir_ratios(
            self.bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.RefDirection)
