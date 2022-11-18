"""
This module includes all functions for exporting EnergyPlus Input files (idf)
based on the previously preprocessed SpaceBoundary geometry from the
ep_geom_preprocessing module. Geometric preprocessing (includes EnergyPlus
specific space boundary enrichment) must be executed before this module.
"""

import json
import logging
import math
import os
from pathlib import Path, PosixPath
from typing import Union

from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCC.Core.BRepTools import breptools_UVBounds, BRepTools_WireExplorer
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_WIRE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods_Face, topods_Wire
from OCC.Core._Geom import Handle_Geom_Plane_DownCast

from OCC.Core.gp import gp_Dir, gp_XYZ, gp_Pln
from geomeppy import IDF

import bim2sim
from bim2sim.kernel.aggregation import AggregatedThermalZone
from bim2sim.kernel.element import IFCBased
from bim2sim.kernel.elements import bps
from bim2sim.kernel.elements.bps import ExternalSpatialElement, SpaceBoundary2B, \
    ThermalZone, Storey, Layer, Window, SpaceBoundary
from bim2sim.kernel.units import ureg
from bim2sim.task.base import ITask
from bim2sim.utilities.common_functions import filter_instances
from bim2sim.utilities.pyocc_tools import PyOCCTools
from bim2sim.workflow import Workflow

logger = logging.getLogger(__name__)


class CreateIdf(ITask):
    """
    Task to create an EnergyPlus Input file based on the for EnergyPlus
    preprocessed space boundary geometries.
    """
    ENERGYPLUS_VERSION = "9-4-0"

    reads = ('instances', 'ep_decisions', 'weather_file',)
    touches = ('idf',)

    def __init__(self):
        super().__init__()
        self.idf = None

    def run(self, workflow, instances, ep_decisions, weather_file):
        self.logger.info("IDF generation started ...")
        self.logger.info("Init thermal zones ...")
        idf = self._init_idf(self.paths, weather_file)
        self._init_zone(instances, idf)
        self._init_zonelist(idf)
        self._init_zonegroups(instances, idf)
        self.logger.info("Get predefined materials and construction ...")
        self._get_preprocessed_materials_and_constructions(instances, idf)
        # self._get_bs2021_materials_and_constructions(idf)
        add_shadings = ep_decisions['EnergyPlus.AddShadings']
        if add_shadings:
            self.logger.info("Add Shadings ...")
            self._add_shadings(instances, idf)
        self.logger.info("Set Simulation Control ...")
        self._set_simulation_control(idf)
        idf.set_default_constructions()
        self.logger.info("Export IDF geometry")
        self._export_geom_to_idf(instances, idf)
        self._set_ground_temperature(idf, t_ground=self._get_ifc_spaces(
            instances)[0].t_ground)  # assuming all zones have same ground
        self._set_output_variables(idf, workflow)
        self._idf_validity_check(idf)
        idf.save(idf.idfname)

        return idf,

    @staticmethod
    def _init_idf(paths, weather_file: PosixPath):
        """
        Initialize the EnergyPlus input file (idf) with general idf settings
        and set default weather
        data.
        Args:
            paths: BIM2SIM FolderStructure
            weather_file: PosixPath to *.epw weather file
        """
        # set the installation path for the EnergyPlus installation
        # ep_install_path = '/usr/local/EnergyPlus-9-2-0/'
        # ep_install_path = '/usr/local/EnergyPlus-9-3-0/'
        ep_install_path = f'/usr/local/EnergyPlus' \
                          f'-{CreateIdf.ENERGYPLUS_VERSION}/'
        # ep_install_path = f'C:/Program Files/EnergyPlus' \
        #                   f'V{CreateIdf.ENERGYPLUS_VERSION}/'
        # ep_install_path = r'C:/Program Files (x86)/EnergyPlusV9-4-0/'
        # ep_install_path = f'C:/EnergyPlus/EnergyPlus' \
        #                   f'V{CreateIdf.ENERGYPLUS_VERSION}/'

        # set the plugin path of the PluginEnergyPlus within the BIM2SIM Tool
        plugin_ep_path = str(Path(__file__).parent.parent.parent)
        # set Energy+.idd as base for new idf
        IDF.setiddname(ep_install_path + 'Energy+.idd')
        # initialize the idf with a minimal idf setup
        idf = IDF(plugin_ep_path + '/data/Minimal.idf')
        # rename the idf to the ifc name
        ifc_name = os.listdir(paths.ifc)[0].strip('.ifc')
        idf.idfname = str(paths.export) + '/' + ifc_name + '.idf'
        # load and set basic compact schedules and ScheduleTypeLimits
        schedules_idf = IDF(plugin_ep_path + '/data/Schedules.idf')
        schedules = schedules_idf.idfobjects["Schedule:Compact".upper()]
        sch_typelim = schedules_idf.idfobjects["ScheduleTypeLimits".upper()]
        for s in schedules:
            idf.copyidfobject(s)
        for t in sch_typelim:
            idf.copyidfobject(t)
        # set weather file
        idf.epw = str(weather_file)
        return idf

    def _init_zone(self, instances: dict, idf: IDF):
        """
        Creates one idf zone per space and sets heating and cooling
        templates, infiltration and internal loads (occupancy (people),
        equipment, lighting).
        Args:
            instances: dict[guid: element]
            idf: idf file object
        """
        spaces = filter_instances(instances, ThermalZone)
        for space in spaces:
            zone = idf.newidfobject(
                'ZONE',
                Name=space.ifc.GlobalId,
                Volume=space.space_shape_volume.to(ureg.meter ** 3).m
            )
            self._set_heating_and_cooling(idf, zone_name=zone.Name, space=space)
            self._set_infiltration(idf, name=zone.Name, zone_name=zone.Name,
                                   space=space)
            self._set_people(idf, name=zone.Name, zone_name=zone.Name,
                             space=space)
            self._set_equipment(idf, name=zone.Name, zone_name=zone.Name,
                                space=space)
            self._set_lights(idf, name=zone.Name, zone_name=zone.Name,
                             space=space)

    @staticmethod
    def _init_zonelist(
            idf: IDF,
            name: str = None,
            zones_in_list: list[str] = None):
        """
        Inits a list of zones in the idf. If the zones_in_list is not set,
        all zones are assigned to a general zone, unless the number of total
        zones is greater than 20 (max. allowed number of zones in a zonelist
        in an idf).
        Args:
            idf: idf file object
            name: str with name of zone list
            zones_in_list: list with the guids of the zones to be included in
                the list
        """
        if zones_in_list is None:
            # assign all zones to one list unless the total number of zones
            # is larger than 20.
            idf_zones = idf.idfobjects["ZONE"]
            if len(idf_zones) > 20:
                return
        else:
            # assign all zones with the zone names that are included in
            # zones_in_list to the zonelist.
            all_idf_zones = idf.idfobjects["ZONE"]
            idf_zones = [zone for zone in all_idf_zones if zone.Name
                         in zones_in_list]
            if len(idf_zones) > 20:
                return
            if len(idf_zones) == 0:
                return
        if name is None:
            name = "All_Zones"
        zs = {}
        for i, z in enumerate(idf_zones):
            zs.update({"Zone_" + str(i + 1) + "_Name": z.Name})
        idf.newidfobject("ZONELIST", Name=name, **zs)

    def _init_zonegroups(self, instances: dict, idf: IDF):
        """
        Assign one zonegroup per storey.
        Args:
            instances: dict[guid: element]
            idf: idf file object
        """
        spaces = filter_instances(instances, ThermalZone)
        # assign storeys to spaces (ThermalZone)
        for space in spaces:
            if space.storeys:
                space.storey = space.storeys[0]  # Zone can only have one storey
            else:
                space.storey = None
        # add zonelist per storey
        storeys = filter_instances(instances, Storey)
        for st in storeys:
            space_ids = []
            for space in st.thermal_zones:
                space_ids.append(space.guid)
            self._init_zonelist(idf, name=st.ifc.Name, zones_in_list=space_ids)

        # add zonelist for All_Zones
        zone_lists = [zlist for zlist in idf.idfobjects["ZONELIST"]
                      if zlist.Name != "All_Zones"]

        # add zonegroup for each zonegroup in zone_lists.
        for zlist in zone_lists:
            idf.newidfobject("ZONEGROUP",
                             Name=zlist.Name,
                             Zone_List_Name=zlist.Name,
                             Zone_List_Multiplier=1
                             )

    def _get_preprocessed_materials_and_constructions(self, instances: dict,
                                                      idf: IDF):
        """
        This function sets preprocessed construction and material for
        building surfaces and fenestration. For virtual bounds, an air
        boundary construction is set.
        Args:
            instances: dict[guid: element]
            idf: idf file object
        """
        bounds = filter_instances(instances, 'SpaceBoundary')
        for bound in bounds:
            rel_elem = bound.bound_instance
            if not rel_elem:
                continue
            if not rel_elem.ifc.is_a('IfcWindow'):
                # set construction for all but fenestration
                self._set_preprocessed_construction_elem(
                    rel_elem, rel_elem.layerset.layers, idf)
                for layer in rel_elem.layerset.layers:
                    self._set_preprocessed_material_elem(layer, idf)
            else:
                # set construction elements for windows
                self._set_preprocessed_window_material_elem(rel_elem, idf)

        # Add air boundaries as construction as a material for virtual bounds
        if CreateIdf.ENERGYPLUS_VERSION in ["9-2-0", "9-4-0"]:
            idf.newidfobject("CONSTRUCTION:AIRBOUNDARY",
                             Name='Air Wall',
                             Solar_and_Daylighting_Method='GroupedZones',
                             Radiant_Exchange_Method='GroupedZones',
                             Air_Exchange_Method='SimpleMixing',
                             Simple_Mixing_Air_Changes_per_Hour=0.5,
                             )
        else:
            idf.newidfobject("CONSTRUCTION:AIRBOUNDARY",
                             Name='Air Wall',
                             Air_Exchange_Method='SimpleMixing',
                             Simple_Mixing_Air_Changes_per_Hour=0.5,
                             )

    @staticmethod
    def _set_preprocessed_construction_elem(
            rel_elem: IFCBased,
            layers: list[Layer],
            idf: IDF):
        """
        This function uses preprocessed data to define idf construction
        elements.
        Args:
            rel_elem: any subclass of IFCBased (e.g., Wall)
            layers: list of Layer
            idf: idf file object
        """
        construction_name = rel_elem.key + '_' + str(len(layers)) + '_' + '_' \
            .join([str(l.thickness.to(ureg.metre).m) for l in layers])
        # todo: find a unique key for construction name
        if idf.getobject("CONSTRUCTION", construction_name) is None:
            outer_layer = layers[-1]
            other_layer_list = layers[:-1]
            other_layer_list.reverse()
            other_layers = {}
            for i, l in enumerate(other_layer_list):
                other_layers.update(
                    {'Layer_' + str(i + 2): l.material.name + "_" + str(
                        l.thickness.to(ureg.metre).m)})
            idf.newidfobject("CONSTRUCTION",
                             Name=construction_name,
                             Outside_Layer=outer_layer.material.name + "_" +
                                           str(outer_layer.thickness.to(
                                               ureg.metre).m),
                             **other_layers
                             )

    @staticmethod
    def _set_preprocessed_material_elem(layer: Layer, idf: IDF):
        """
        This function sets a preprocessed material element.
        Args:
            layer: Layer Instance
            idf: idf file object
        """
        material_name = layer.material.name + "_" + str(
            layer.thickness.to(ureg.metre).m)
        if idf.getobject("MATERIAL", material_name):
            return
        specific_heat = \
            layer.material.spec_heat_capacity.to(ureg.joule / ureg.kelvin /
                                                 ureg.kilogram).m
        if specific_heat < 100:
            specific_heat = 100
        idf.newidfobject("MATERIAL",
                         Name=material_name,
                         Roughness="MediumRough",
                         Thickness=layer.thickness.to(ureg.metre).m,
                         Conductivity=layer.material.thermal_conduc.to(
                             ureg.W / (ureg.m * ureg.K)).m,
                         Density=layer.material.density.to(
                             ureg.kg / ureg.m ** 3).m,
                         Specific_Heat=specific_heat
                         )

    @staticmethod
    def _set_preprocessed_window_material_elem(rel_elem: Window,
                                               idf: IDF):
        """
        This function constructs windows with a
        WindowMaterial:SimpleGlazingSystem consisting of the outermost layer
        of the providing related element. This is a simplification, needs to
        be extended to hold multilayer window constructions.
        Args:
            rel_elem: Window instance
            idf: idf file object
        """
        material_name = \
            'WM_' + rel_elem.layerset.layers[0].material.name + '_' \
            + str(rel_elem.layerset.layers[0].thickness.to(ureg.m).m)
        if idf.getobject("WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM", material_name):
            return
        if rel_elem.u_value.to(ureg.W / ureg.K / ureg.meter ** 2).m > 0:
            ufactor = 1 / (0.04 + 1 / rel_elem.u_value.to(ureg.W / ureg.K /
                                                          ureg.meter ** 2).m
                           + 0.13)
        else:
            ufactor = 1 / (0.04 + rel_elem.layerset.layers[0].thickness.to(
                ureg.metre).m /
                           rel_elem.layerset.layers[0].thermal_conduc.to(
                               ureg.W / (ureg.m * ureg.K)).m +
                           0.13)
        if rel_elem.g_value >= 1:
            old_g_value = rel_elem.g_value
            rel_elem.g_value = 0.999
            logger.warning("G-Value was set to %f, "
                           "but has to be smaller than 1, so overwritten by %f",
                           old_g_value, rel_elem.g_value)

        idf.newidfobject("WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM",
                         Name=material_name,
                         UFactor=ufactor,
                         Solar_Heat_Gain_Coefficient=rel_elem.g_value,
                         # Visible_Transmittance=0.8    # optional
                         )
        # todo: enable use of multilayer windows
        construction_name = 'Window_' + material_name
        if idf.getobject("CONSTRUCTION", construction_name) is None:
            idf.newidfobject("CONSTRUCTION",
                             Name=construction_name,
                             Outside_Layer=material_name
                             )

    def _set_heating_and_cooling(self, idf: IDF, zone_name: str,
                                 space: ThermalZone):
        """
        This function sets heating and cooling parameters based on the data
        available from BIM2SIM Preprocessing (either IFC-based or
        Template-based).
        Args:
            idf: idf file object
            zone_name: str
            space: ThermalZone instance
        """
        stat_name = "STATS " + space.usage.replace(',', '')
        if idf.getobject("HVACTEMPLATE:THERMOSTAT", stat_name) is None:
            stat = self._set_day_hvac_template(idf, space, stat_name)
        else:
            stat = idf.getobject("HVACTEMPLATE:THERMOSTAT", stat_name)

        cooling_availability = "Off"
        heating_availability = "Off"

        if space.with_cooling:
            cooling_availability = "On"
        if space.with_heating:
            heating_availability = "On"

        idf.newidfobject(
            "HVACTEMPLATE:ZONE:IDEALLOADSAIRSYSTEM",
            Zone_Name=zone_name,
            Template_Thermostat_Name=stat.Name,
            Heating_Availability_Schedule_Name=heating_availability,
            Cooling_Availability_Schedule_Name=cooling_availability
        )

    def _set_people(self, idf: IDF, name: str, zone_name: str,
                    space: ThermalZone):
        """
        This function sets schedules and internal loads from people (occupancy)
        based on the BIM2SIM Preprocessing, i.e. based on IFC data if
        available or on templates.
        Args:
            idf: idf file object
            name: name of the new people idf object
            zone_name: name of zone or zone_list
            space: ThermalZone instance
        """
        schedule_name = "Schedule " + "People " + space.usage.replace(',', '')
        profile_name = 'persons_profile'
        self._set_day_week_year_schedule(idf, space.persons_profile[:24],
                                         profile_name, schedule_name)
        # set default activity schedule
        if idf.getobject("SCHEDULETYPELIMITS", "Any Number") is None:
            idf.newidfobject("SCHEDULETYPELIMITS", Name="Any Number")
        activity_schedule_name = "Schedule Activity " + str(
            space.fixed_heat_flow_rate_persons)
        if idf.getobject("SCHEDULE:COMPACT", activity_schedule_name) is None:
            idf.newidfobject("SCHEDULE:COMPACT",
                             Name=activity_schedule_name,
                             Schedule_Type_Limits_Name="Any Number",
                             Field_1="Through: 12/31",
                             Field_2="For: Alldays",
                             Field_3="Until: 24:00",
                             Field_4=space.fixed_heat_flow_rate_persons.to(
                                 ureg.watt).m  # in W/Person
                             )  # other method for Field_4 (not used here)
            # ="persons_profile"*"activity_degree_persons"*58,1*1,8
            # (58.1 W/(m2*met), 1.8m2/Person)
        if CreateIdf.ENERGYPLUS_VERSION in ["9-2-0", "9-4-0"]:
            idf.newidfobject(
                "PEOPLE",
                Name=name,
                Zone_or_ZoneList_Name=zone_name,
                Number_of_People_Calculation_Method="People/Area",
                People_per_Zone_Floor_Area=space.persons,
                Activity_Level_Schedule_Name=activity_schedule_name,
                Number_of_People_Schedule_Name=schedule_name,
                Fraction_Radiant=space.ratio_conv_rad_persons
            )
        else:
            idf.newidfobject(
                "PEOPLE",
                Name=name,
                Zone_or_ZoneList_or_Space_or_SpaceList_Name=zone_name,
                Number_of_People_Calculation_Method="People/Area",
                People_per_Floor_Area=space.persons,
                Activity_Level_Schedule_Name=activity_schedule_name,
                Number_of_People_Schedule_Name=schedule_name,
                Fraction_Radiant=space.ratio_conv_rad_persons
            )

    @staticmethod
    def _set_day_week_year_schedule(idf: IDF, schedule: list[float],
                                    profile_name: str,
                                    schedule_name: str):
        """
        This function sets an hourly day, week and year schedule.
        Args:
            idf: idf file object
            schedule: list of float values for the schedule (e.g.,
                temperatures, loads)
            profile_name: string
            schedule_name: str
        """
        if idf.getobject("SCHEDULE:DAY:HOURLY", name=schedule_name) is None:
            limits_name = 'Fraction'
            hours = {}
            if profile_name in {'heating_profile', 'cooling_profile'}:
                limits_name = 'Temperature'
                if idf.getobject("SCHEDULETYPELIMITS", "Temperature") is None:
                    idf.newidfobject("SCHEDULETYPELIMITS", Name="Temperature")
            for i, l in enumerate(schedule[:24]):
                if profile_name in {'heating_profile', 'cooling_profile'}:
                    # convert Kelvin to Celsius for EnergyPlus Export
                    if schedule[i] > 270:
                        schedule[i] = schedule[i] - 273.15
                hours.update({'Hour_' + str(i + 1): schedule[i]})
            idf.newidfobject("SCHEDULE:DAY:HOURLY", Name=schedule_name,
                             Schedule_Type_Limits_Name=limits_name, **hours)
        if idf.getobject("SCHEDULE:WEEK:COMPACT", name=schedule_name) is None:
            idf.newidfobject("SCHEDULE:WEEK:COMPACT", Name=schedule_name,
                             DayType_List_1="AllDays",
                             ScheduleDay_Name_1=schedule_name)
        if idf.getobject("SCHEDULE:YEAR", name=schedule_name) is None:
            idf.newidfobject("SCHEDULE:YEAR", Name=schedule_name,
                             Schedule_Type_Limits_Name=limits_name,
                             ScheduleWeek_Name_1=schedule_name,
                             Start_Month_1=1,
                             Start_Day_1=1,
                             End_Month_1=12,
                             End_Day_1=31)

    def _set_equipment(self, idf: IDF, name: str, zone_name: str,
                       space: ThermalZone):
        """
        This function sets schedules and internal loads from equipment based
        on the BIM2SIM Preprocessing, i.e. based on IFC data if available or on
        templates.
        Args:
            idf: idf file object
            name: name of the new people idf object
            zone_name: name of zone or zone_list
            space: ThermalZone instance
        """
        schedule_name = "Schedule " + "Equipment " + space.usage.replace(',',
                                                                         '')
        profile_name = 'machines_profile'
        self._set_day_week_year_schedule(idf, space.machines_profile[:24],
                                         profile_name, schedule_name)
        if CreateIdf.ENERGYPLUS_VERSION in ["9-2-0", "9-4-0"]:
            idf.newidfobject(
                "ELECTRICEQUIPMENT",
                Name=name,
                Zone_or_ZoneList_Name=zone_name,
                Schedule_Name=schedule_name,
                Design_Level_Calculation_Method="Watts/Area",
                Watts_per_Zone_Floor_Area=space.machines.to(ureg.watt).m
            )
        else:
            idf.newidfobject(
                "ELECTRICEQUIPMENT",
                Name=name,
                Zone_or_ZoneList_or_Space_or_SpaceList_Name=zone_name,
                Schedule_Name=schedule_name,
                Design_Level_Calculation_Method="Watts/Area",
                Watts_per_Zone_Floor_Area=space.machines.to(ureg.watt).m
            )

    def _set_lights(self, idf: IDF, name: str, zone_name: str,
                    space: ThermalZone):
        """
        This function sets schedules and lighting based on the
        BIM2SIM Preprocessing, i.e. based on IFC data if available or on
        templates.
        Args:
            idf: idf file object
            name: name of the new people idf object
            zone_name: name of zone or zone_list
            space: ThermalZone instance
        """
        schedule_name = "Schedule " + "Lighting " + space.usage.replace(',', '')
        profile_name = 'lighting_profile'
        self._set_day_week_year_schedule(idf, space.lighting_profile[:24],
                                         profile_name, schedule_name)
        mode = "Watts/Area"
        watts_per_zone_floor_area = space.lighting_power.to(ureg.watt).m
        return_air_fraction = 0.0
        fraction_radiant = 0.42  # fraction radiant: cf. Table 1.28 in
        # InputOutputReference EnergyPlus (Version 9.4.0), p. 506
        fraction_visible = 0.18  # Todo: fractions do not match with .json
        # Data. Maybe set by user-input later
        if CreateIdf.ENERGYPLUS_VERSION in ["9-2-0", "9-4-0"]:
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
        else:
            idf.newidfobject(
                "LIGHTS",
                Name=name,
                Zone_or_ZoneList_or_Space_or_SpaceList_Name=zone_name,
                Schedule_Name=schedule_name,
                Design_Level_Calculation_Method=mode,
                Watts_per_Zone_Floor_Area=watts_per_zone_floor_area,
                Return_Air_Fraction=return_air_fraction,
                Fraction_Radiant=fraction_radiant,
                Fraction_Visible=fraction_visible
            )

    @staticmethod
    def _set_infiltration(idf: IDF, name: str, zone_name: str,
                          space: ThermalZone):
        """
        This function sets the infiltration rate per space based on the
        BIM2SIM preprocessing values (IFC-based if available or
        template-based).
        Args:
            idf: idf file object
            name: name of the new people idf object
            zone_name: name of zone or zone_list
            space: ThermalZone instance
        """
        idf.newidfobject(
            "ZONEINFILTRATION:DESIGNFLOWRATE",
            Name=name,
            Zone_or_ZoneList_Name=zone_name,
            Schedule_Name="Continuous",
            Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
            Air_Changes_per_Hour=space.infiltration_rate
        )

    def _set_day_hvac_template(self, idf: IDF, space: ThermalZone, name: str):
        """
        This function sets idf schedules with 24hour schedules for heating and
        cooling.
        Args:
            idf: idf file object
            space: ThermalZone
            name: IDF Thermostat Name
        """
        htg_schedule_name = "Schedule " + "Heating " + space.usage.replace(
            ',', '')
        self._set_day_week_year_schedule(idf, space.heating_profile[:24],
                                         'heating_profile',
                                         htg_schedule_name)

        clg_schedule_name = "Schedule " + "Cooling " + space.usage.replace(
            ',', '')
        self._set_day_week_year_schedule(idf, space.cooling_profile[:24],
                                         'cooling_profile',
                                         clg_schedule_name)
        stat = idf.newidfobject(
            "HVACTEMPLATE:THERMOSTAT",
            Name=name,
            Heating_Setpoint_Schedule_Name=htg_schedule_name,
            Cooling_Setpoint_Schedule_Name=clg_schedule_name
        )
        return stat

    def _set_hvac_template(self, idf: IDF, name: str,
                           heating_sp: Union[int, float],
                           cooling_sp: Union[int, float],
                           mode='setback'):
        """
        This function manually sets heating and cooling templates.
        Args:
            idf: idf file object
            heating_sp: float or int for heating set point
            cooling_sp: float or int for cooling set point
            name: IDF Thermostat Name
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
            htg_alldays = self._define_schedule_part('Alldays',
                                                     [('5:00', setback_htg),
                                                      ('21:00', heating_sp),
                                                      ('24:00', setback_htg)])
            clg_alldays = self._define_schedule_part('Alldays',
                                                     [('5:00', setback_clg),
                                                      ('21:00', cooling_sp),
                                                      ('24:00', setback_clg)])
            htg_name = "H_SetBack_" + str(heating_sp)
            clg_name = "C_SetBack_" + str(cooling_sp)
            if idf.getobject("SCHEDULE:COMPACT", htg_name) is None:
                self._write_schedule(idf, htg_name, [htg_alldays, ])
            else:
                idf.getobject("SCHEDULE:COMPACT", htg_name)
            if idf.getobject("SCHEDULE:COMPACT", clg_name) is None:
                self._write_schedule(idf, clg_name, [clg_alldays, ])
            else:
                idf.getobject("SCHEDULE:COMPACT", clg_name)
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
    def _write_schedule(idf: IDF, sched_name: str, sched_part_list: list):
        """
        This function writes a schedule to the idf. Only used for manual
        setup of schedules (combined with _set_hvac_template).
        Args:
            idf: idf file object
            sched_name: str with name of the schedule
            sched_part_list: list of schedule parts (cf. function
                _define_schedule_part)
        """
        sched_list = {}
        field_count = 1
        for parts in sched_part_list:
            field_count += 1
            sched_list.update({'Field_' + str(field_count): 'For: ' + parts[0]})
            part = parts[1]
            for set in part:
                field_count += 1
                sched_list.update(
                    {'Field_' + str(field_count): 'Until: ' + str(set[0])})
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
    def _define_schedule_part(
            days: str, til_time_temp: list[tuple[str, Union[int, float]]]):
        """
        Defines a part of a schedule
        Args:
            days: string: Weekdays, Weekends, Alldays, AllOtherDays, Saturdays,
                Sundays, ...
            til_time_temp: List of tuples
                (until-time format 'hh:mm' (24h) as str),
                temperature until this time in Celsius),
                e.g. (05:00, 18)
        :return:
        """
        return [days, til_time_temp]

    @staticmethod
    def _add_shadings(instances: dict, idf: IDF):
        """
        This function adds shading boundaries to idf.
        Args:
            instances: dict[guid: element]
            idf: idf file object
        """
        spatials = []
        ext_spatial_elem = filter_instances(instances, ExternalSpatialElement)
        for elem in ext_spatial_elem:
            for sb in elem.space_boundaries:
                spatials.append(sb)
        if not spatials:
            return
        pure_spatials = []
        description_list = [s.ifc.Description for s in spatials]
        descriptions = list(dict.fromkeys(description_list))
        shades_included = ("Shading:Building" or "Shading:Site") in descriptions

        # check if ifc has dedicated shading space boundaries included and
        # append them to pure_spatials for further processing
        if shades_included:
            for s in spatials:
                if s.ifc.Description in ["Shading:Building", "Shading:Site"]:
                    pure_spatials.append(s)
        # if no shading boundaries are included in ifc, derive these from the
        # set of given space boundaries and append them to pure_spatials for
        # further processing
        else:
            for s in spatials:
                # only consider almost horizontal 2b shapes (roof-like SBs)
                if s.level_description == '2b':
                    angle = math.degrees(
                        gp_Dir(s.bound_normal).Angle(gp_Dir(gp_XYZ(0, 0, 1))))
                    if not ((-45 < angle < 45) or (135 < angle < 225)):
                        continue
                if s.related_bound and s.related_bound.ifc.RelatingSpace.is_a(
                        'IfcSpace'):
                    continue
                pure_spatials.append(s)

        # create idf shadings from set of pure_spatials
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
        This function sets general simulation control parameters. These can
        be easily overwritten in the exported idf.
        Args:
            idf: idf file object
        """
        # todo: set these in general settings
        for sim_control in idf.idfobjects["SIMULATIONCONTROL"]:
            # sim_control.Do_Zone_Sizing_Calculation = "Yes"
            sim_control.Do_System_Sizing_Calculation = "Yes"
            # sim_control.Do_Plant_Sizing_Calculation = "Yes"
            sim_control.Run_Simulation_for_Sizing_Periods = "No"
            sim_control.Run_Simulation_for_Weather_File_Run_Periods = "Yes"

        for building in idf.idfobjects['BUILDING']:
            building.Solar_Distribution = 'FullExterior'

    @staticmethod
    def _set_ground_temperature(idf: IDF, t_ground: ureg.Quantity):
        """
        This function sets the round temperature within the idf.
        Args:
            idf: idf file object
            t_ground: ground temperature as ureg.Quantity
        """
        string = '_Ground_Temperature'
        month_list = ['January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October',
                      'November', 'December']
        temp_dict = {}
        for month in month_list:
            temp_dict.update({month + string: t_ground.to(ureg.degC).m})
        idf.newidfobject("SITE:GROUNDTEMPERATURE:BUILDINGSURFACE", **temp_dict)

    @staticmethod
    def _set_output_variables(idf: IDF, workflow: Workflow):
        """
        This function adds user defined output variables to the idf file
        Args:
            idf: idf file object
            workflow: BIM2SIM Workflow
        """
        # general output settings. May be moved to general settings
        out_control = idf.idfobjects['OUTPUTCONTROL:TABLE:STYLE']
        out_control[0].Column_Separator = 'CommaAndHTML'
        out_control[0].Unit_Conversion = 'JtoKWH'

        # remove all existing output variables with reporting frequency
        # "Timestep"
        out_var = [v for v in idf.idfobjects['OUTPUT:VARIABLE']
                   if v.Reporting_Frequency.upper() == "TIMESTEP"]
        for var in out_var:
            idf.removeidfobject(var)

        # idf.newidfobject(
        #     "OUTPUT:VARIABLE",
        #     Variable_Name="Zone Ideal Loads Supply Air Total Heating Energy",
        #     Reporting_Frequency="Hourly",
        # )
        # idf.newidfobject(
        #     "OUTPUT:VARIABLE",
        #     Variable_Name="Zone Ideal Loads Supply Air Total Cooling Energy",
        #     Reporting_Frequency="Hourly",
        # )
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
        # idf.newidfobject(
        #     "OUTPUT:VARIABLE",
        #     Variable_Name="Zone Infiltration Mass Flow Rate",
        #     Reporting_Frequency="Hourly",
        # )
        # idf.newidfobject(
        #     "OUTPUT:VARIABLE",
        #     Variable_Name="Zone People Occupant Count",
        #     Reporting_Frequency="Hourly",
        # )
        # idf.newidfobject(
        #     "OUTPUT:VARIABLE",
        #     Variable_Name="Zone People Convective Heating Rate",
        #     Reporting_Frequency="Hourly",
        # )
        # idf.newidfobject(
        #     "OUTPUT:VARIABLE",
        #     Variable_Name="Zone Electric Equipment Convective Heating Rate",
        #     Reporting_Frequency="Hourly",
        # )
        # idf.newidfobject(
        #     "OUTPUT:VARIABLE",
        #     Variable_Name="Zone Lights Convective Heating Rate",
        #     Reporting_Frequency="Hourly",
        # )
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
            Variable_Name="Zone Total Internal Total Heating Energy",
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
            Variable_Name="Zone Air Heat Balance Internal Convective Heat "
                          "Gain Rate",
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
        # idf.newidfobject(
        #     "OUTPUT:VARIABLE",
        #     Variable_Name="Zone Air Heat Balance Air Energy Storage Rate",
        #     Reporting_Frequency="Hourly",
        # )
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
        # idf.newidfobject(
        #     "OUTPUT:VARIABLE",
        #     Variable_Name="Site Outdoor Air Barometric Pressure",
        #     Reporting_Frequency="Hourly",
        # )
        # idf.newidfobject(
        #     "OUTPUT:VARIABLE",
        #     Variable_Name="Zone Mixing Current Density Volume Flow Rate",
        #     Reporting_Frequency="Hourly",
        # )
        # idf.newidfobject(
        #     "OUTPUT:VARIABLE",
        #     Variable_Name="Zone Mixing Sensible Heat Gain Rate",
        #     Reporting_Frequency="Hourly",
        # )
        # idf.newidfobject(
        #     "OUTPUT:VARIABLE",
        #     Variable_Name="Zone Air Relative Humidity",
        #     Reporting_Frequency="Hourly",
        # )
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
        # idf.newidfobject(
        #     "OUTPUT:VARIABLE",
        #     Variable_Name="Zone Windows Total Transmitted Solar Radiation
        #     Energy",
        #     Reporting_Frequency="Hourly",
        # )
        # idf.newidfobject(
        #     "OUTPUT:VARIABLE",
        #     Variable_Name="Surface Window Heat Gain Energy",
        #     Reporting_Frequency="Hourly",
        # )
        # idf.newidfobject(
        #     "OUTPUT:VARIABLE",
        #     Variable_Name="Surface Inside Face Convection Heat Gain Energy",
        #     Reporting_Frequency="Hourly",
        # )
        # idf.newidfobject(
        #     "OUTPUT:VARIABLE",
        #     Variable_Name="Surface Outside Face Convection Heat Gain Energy",
        #     Reporting_Frequency="Hourly",
        # )
        # idf.newidfobject(
        #     "OUTPUT:VARIABLE",
        #     Variable_Name="Zone Opaque Surface Outside Face Conduction",
        #     Reporting_Frequency="Hourly",
        # )
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
        # idf.newidfobject(
        #     "OUTPUT:VARIABLE",
        #     Variable_Name="Zone Infiltration Standard Density Volume Flow
        #     Rate",
        #     Reporting_Frequency="Hourly",
        # )
        # idf.newidfobject(
        #     "OUTPUT:VARIABLE",
        #     Variable_Name="Zone Air Relative Humidity",
        #     Reporting_Frequency="Hourly",
        # )
        if workflow.cfd_export:
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Surface Inside Face Temperature",
                Reporting_Frequency="Hourly",
            )
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

    def _export_geom_to_idf(self, instances: dict, idf: IDF):
        """
        This function converts the space boundary bound_shape from
        OpenCascade to idf geometry.
        Args:
            instances: dict[guid: element]
            idf: idf file object
        """
        bounds = filter_instances(instances, SpaceBoundary)
        for bound in bounds:
            idfp = IdfObject(bound, idf)
            if idfp.skip_bound:
                idf.popidfobject(idfp.key, -1)
                logger.warning(
                    "Boundary with the GUID %s (%s) is skipped (due to "
                    "missing boundary conditions)!",
                    idfp.name, idfp.surface_type)
                continue
        bounds_2b = filter_instances(instances, SpaceBoundary2B)
        for b_bound in bounds_2b:
            idfp = IdfObject(b_bound, idf)
            if idfp.skip_bound:
                logger.warning(
                    "Boundary with the GUID %s (%s) is skipped (due to "
                    "missing boundary conditions)!",
                    idfp.name, idfp.surface_type)
                continue

    @staticmethod
    def _idf_validity_check(idf):
        """
        This function performs a basic validity check of the resulting idf.
        It removes openings from adiabatic surfaces and very small surfaces.
        Args:
            idf: idf file object
        """
        logger.info('Start IDF Validity Checker')

        fenestration = idf.idfobjects['FENESTRATIONSURFACE:DETAILED']
        for f in fenestration:
            if not f.Building_Surface_Name:
                logger.info('Removed Fenestration: %s' % f.Name)
                idf.removeidfobject(f)
            fbco = f.Building_Surface_Name
            bs = idf.getobject('BUILDINGSURFACE:DETAILED', fbco)
            if bs.Outside_Boundary_Condition == 'Adiabatic':
                logger.info('Removed Fenestration: %s' % f.Name)
                idf.removeidfobject(f)
        for f in fenestration:
            fbco = f.Building_Surface_Name
            bs = idf.getobject('BUILDINGSURFACE:DETAILED', fbco)
            if bs.Outside_Boundary_Condition == 'Adiabatic':
                logger.info(
                    'Removed Fenestration in second try: %s' % f.Name)
                idf.removeidfobject(f)

        sfs = idf.getsurfaces()
        small_area_obj = [s for s in sfs
                          if PyOCCTools.get_shape_area(
                PyOCCTools.make_faces_from_pnts(s.coords)) < 1e-2]

        for obj in small_area_obj:
            logger.info('Removed small area: %s' % obj.Name)
            idf.removeidfobject(obj)

        shadings = idf.getshadingsurfaces()
        small_area_obj = [s for s in shadings if PyOCCTools.get_shape_area(
            PyOCCTools.make_faces_from_pnts(s.coords)) < 1e-2]

        for obj in small_area_obj:
            logger.info('Removed small area: %s' % obj.Name)
            idf.removeidfobject(obj)

        bsd = idf.idfobjects['BUILDINGSURFACE:DETAILED']
        for sf in bsd:
            if sf.Construction_Name == 'BS Exterior Window':
                logger.info(
                    'Surface due to invalid material: %s' % sf.Name)
                idf.removeidfobject(sf)
        logger.info('IDF Validity Checker done')

    @staticmethod
    def _get_ifc_spaces(instances: dict):
        """
        This function extracts ifc spaces from an instance dictionary while
        also unpacking spaces from aggregated thermal zones.
        Args:
            instances: dict[guid: element]
        """
        return filter_instances(instances, ThermalZone)


class IdfObject:
    """
    This class holds all data required for the idf setup of
    BUILDINGSURFACE:DETAILED and FENESTRATIONSURFACE:DETAILED.
    This includes further methods for processing the preprocessed information
    from the BIM2SIM process for the use in idf (e.g., surface type mapping).
    """

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
        if inst_obj.parent_bound:
            self.key = "FENESTRATIONSURFACE:DETAILED"
        else:
            self.key = "BUILDINGSURFACE:DETAILED"
        if inst_obj.parent_bound:
            self.building_surface_name = inst_obj.parent_bound.guid
        self._map_surface_types(inst_obj)
        self._map_boundary_conditions(inst_obj)
        self.set_preprocessed_construction_name()
        if self.construction_name is None:
            self._set_construction_name()
        obj = self._set_idfobject_attributes(idf)
        if obj is not None:
            self._set_idfobject_coordinates(obj, idf, inst_obj)
        else:
            pass

    def _set_construction_name(self):
        """
        This function sets default constructions for all idf surface types.
        Should only be used if no construction is available for the current
        object.
        """
        if self.surface_type == "Wall":
            self.construction_name = "Project Wall"
        elif self.surface_type == "Roof":
            self.construction_name = "Project Flat Roof"
        elif self.surface_type == "Ceiling":
            self.construction_name = "Project Ceiling"
        elif self.surface_type == "Floor":
            self.construction_name = "Project Floor"
        elif self.surface_type == "Door":
            self.construction_name = "Project Door"
        elif self.surface_type == "Window":
            self.construction_name = "Project External Window"

    def set_preprocessed_construction_name(self):
        """
        This function sets constructions of idf surfaces to preprocessed
        constructions. Virtual space boundaries are set to be an air wall
        (not defined in preprocessing).
        """
        # set air wall for virtual bounds
        if not self.physical:
            if self.out_bound_cond == "Surface":
                self.construction_name = "Air Wall"
        else:
            rel_elem = self.this_bound.bound_instance
            if not rel_elem:
                return
            if rel_elem.ifc.is_a('IfcWindow'):
                self.construction_name = 'Window_WM_' + \
                                         rel_elem.layerset.layers[
                                             0].material.name \
                                         + '_' + str(
                    rel_elem.layerset.layers[0].thickness.to(ureg.metre).m)
            else:
                self.construction_name = rel_elem.key + '_' + str(
                    len(rel_elem.layerset.layers)) + '_' \
                                         + '_'.join(
                    [str(l.thickness.to(ureg.metre).m) for l in
                     rel_elem.layerset.layers])

    def _set_idfobject_coordinates(self, obj, idf: IDF,
                                   inst_obj: Union[SpaceBoundary,
                                                   SpaceBoundary2B]):
        """
        This function exports the surface coordinates from the BIM2SIM Space
        Boundary instance to idf.
        Circular shapes and shapes with more than 120 vertices
        (BuildingSurfaces) or more than 4 vertices (fenestration) are
        simplified.
        Args:
            obj: idf-surface object (buildingSurface:Detailed or fenestration)
            idf: idf file object
            inst_obj: SpaceBoundary instance
        """
        # write bound_shape to obj
        obj_pnts = PyOCCTools.get_points_of_face(self.bound_shape)
        obj_coords = []
        for pnt in obj_pnts:
            co = tuple(round(p, 3) for p in pnt.Coord())
            obj_coords.append(co)
        try:
            obj.setcoords(obj_coords)
        except Exception as ex:
            logger.warning(f"Unexpected {ex=}. Setting coordinates for "
                           f"{inst_obj.guid} failed. This element is not "
                           f"exported."
                           f"{type(ex)=}")
            self.skip_bound = True
            return
        circular_shape = self.get_circular_shape(obj_pnts)
        try:
            if (3 <= len(obj_coords) <= 120
                and self.key == "BUILDINGSURFACE:DETAILED") \
                    or (3 <= len(obj_coords) <= 4
                        and self.key == "FENESTRATIONSURFACE:DETAILED"):
                obj.setcoords(obj_coords)
            elif circular_shape is True and self.surface_type != 'Door':
                self._process_circular_shapes(idf, obj_coords, obj, inst_obj)
            else:
                self._process_other_shapes(inst_obj, obj)
        except Exception as ex:
            logger.warning(f"Unexpected {ex=}. Setting coordinates for "
                           f"{inst_obj.guid} failed. This element is not "
                           f"exported."
                           f"{type(ex)=}")

    def _set_idfobject_attributes(self, idf):
        if self.surface_type is not None:
            if self.key == "BUILDINGSURFACE:DETAILED":
                if self.surface_type.lower() in {"DOOR".lower(),
                                                 "Window".lower()}:
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
            else:
                obj = idf.newidfobject(
                    self.key,
                    Name=self.name,
                    Surface_Type=self.surface_type,
                    Construction_Name=self.construction_name,
                    Building_Surface_Name=self.building_surface_name,
                    Outside_Boundary_Condition_Object=self.out_bound_cond_obj,
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
                if not PyOCCTools.compare_direction_of_normals(
                        inst_obj.bound_normal, gp_XYZ(0, 0, 1)):
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
                if not PyOCCTools.compare_direction_of_normals(
                        inst_obj.bound_normal, gp_XYZ(0, 0, 1)):
                    surface_type = 'Wall'
                elif inst_obj.top_bottom == "BOTTOM":
                    surface_type = "Floor"
                elif inst_obj.top_bottom == "TOP":
                    surface_type = "Ceiling"
                    if inst_obj.related_bound is None or inst_obj.is_external:
                        surface_type = "Roof"
        elif inst_obj.physical == False:
            if not PyOCCTools.compare_direction_of_normals(
                    inst_obj.bound_normal, gp_XYZ(0, 0, 1)):
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
                   and (
                           inst_obj.ifc.CorrespondingBoundary.InternalOrExternalBoundary.upper() == 'EXTERNAL_EARTH'))
              and (self.key == "BUILDINGSURFACE:DETAILED")
              and not (len(inst_obj.opening_bounds) > 0)):
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
                 or inst_obj.related_bound.ifc.RelatingSpace.is_a(
                            'IfcExternalSpatialElement')):
            self.out_bound_cond = "Ground"
            self.sun_exposed = 'NoSun'
            self.wind_exposed = 'NoWind'
        elif inst_obj.related_bound is not None \
                and not inst_obj.related_bound.ifc.RelatingSpace.is_a(
            'IfcExternalSpatialElement'):  # or elem.virtual_physical == "VIRTUAL": # elem.internal_external == "INTERNAL"
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
            fc = PyOCCTools.make_faces_from_pnts(
                [pnt, pnt2, inst_obj.bound_center.Coord()])
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
