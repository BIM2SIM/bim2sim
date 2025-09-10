from __future__ import annotations

import logging
import math
import os
from pathlib import Path, PosixPath
from typing import Union, TYPE_CHECKING

import pandas as pd
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCC.Core.BRepTools import breptools_UVBounds, BRepTools_WireExplorer
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_WIRE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods_Face, topods_Wire
from OCC.Core._Geom import Handle_Geom_Plane_DownCast

from OCC.Core.gp import gp_Dir, gp_XYZ, gp_Pln
from geomeppy import IDF

from bim2sim.elements.base_elements import IFCBased
from bim2sim.elements.bps_elements import (ExternalSpatialElement,
                                           SpaceBoundary2B, ThermalZone, Storey,
                                           Layer, Window, SpaceBoundary, Wall,
                                           Door, Roof, Slab, InnerFloor,
                                           GroundFloor)
from bim2sim.elements.mapping.units import ureg
from bim2sim.project import FolderStructure
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements, \
    get_spaces_with_bounds, all_subclasses
from bim2sim.utilities.pyocc_tools import PyOCCTools
from bim2sim.utilities.types import BoundaryOrientation

if TYPE_CHECKING:
    from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus import \
        EnergyPlusSimSettings

logger = logging.getLogger(__name__)


class CreateIdf(ITask):
    """Create an EnergyPlus Input file.

    Task to create an EnergyPlus Input file based on the for EnergyPlus
    preprocessed space boundary geometries. See detailed explanation in the run
    function below.
    """

    reads = ('elements', 'weather_file',)
    touches = ('idf', 'sim_results_path')

    def __init__(self, playground):
        super().__init__(playground)
        self.idf = None

    def run(self, elements: dict, weather_file: Path) -> tuple[IDF, Path]:
        """Execute all methods to export an IDF from BIM2SIM.

        This task includes all functions for exporting EnergyPlus Input files
        (idf) based on the previously preprocessed SpaceBoundary geometry from
        the ep_geom_preprocessing task. Geometric preprocessing (includes
        EnergyPlus-specific space boundary enrichment) must be executed
        before this task.
        In this task, first, the IDF itself is initialized. Then, the zones,
        materials and constructions, shadings and control parameters are set
        in the idf. Within the export of the idf, the final mapping of the
        bim2sim elements and the idf components is executed. Shading control
        is added if required, and the ground temperature of the building
        surrounding ground is set, as well as the output variables of the
        simulation. Finally, the generated idf is validated, and minor
        corrections are performed, e.g., tiny surfaces are deleted that
        would cause errors during the EnergyPlus Simulation run.

        Args:
            elements (dict): dictionary in the format dict[guid: element],
                holds preprocessed elements including space boundaries.
            weather_file (Path): path to weather file in .epw data format
        Returns:
            idf (IDF): EnergyPlus input file
            sim_results_path (Path): path to the simulation results.
        """
        logger.info("IDF generation started ...")
        idf, sim_results_path = self.init_idf(self.playground.sim_settings,
                                              self.paths, weather_file,
                                              self.prj_name)
        self.init_zone(self.playground.sim_settings, elements, idf)
        self.init_zonegroups(elements, idf)
        self.get_preprocessed_materials_and_constructions(
            self.playground.sim_settings, elements, idf)
        if self.playground.sim_settings.add_shadings:
            self.add_shadings(elements, idf)
        self.set_simulation_control(self.playground.sim_settings, idf)
        idf.set_default_constructions()
        self.export_geom_to_idf(self.playground.sim_settings, elements, idf)
        if self.playground.sim_settings.add_window_shading:
            self.add_shading_control(
                self.playground.sim_settings.add_window_shading, elements,
                idf)
        self.set_ground_temperature(idf, t_ground=get_spaces_with_bounds(
            elements)[0].t_ground)  # assuming all zones have same ground
        self.set_output_variables(idf, self.playground.sim_settings)
        self.idf_validity_check(idf)
        logger.info("Save idf ...")
        idf.save(idf.idfname)
        logger.info("Idf file successfully saved.")
        if (self.playground.sim_settings.weather_file_for_sizing or
                self.playground.sim_settings.enforce_system_sizing):
            # apply HVAC system sizing based on weather file
            if self.playground.sim_settings.weather_file_for_sizing:
                weather_file_sizing = (
                    self.playground.sim_settings.weather_file_for_sizing)
            else:
                weather_file_sizing = str(weather_file)
            self.apply_system_sizing(
                idf, weather_file_sizing,
                sim_results_path)
            logger.info("Idf has been updated with limits from weather file "
                        "sizing.")

        return idf, sim_results_path

    def apply_system_sizing(self, idf, sizing_weather_file, sim_results_path):
        """
        Apply system sizing based on weather file, sizes for maximum without
        buffer.

        Args:
            idf: Eppy IDF
            sizing_weather_file: Weather file for system sizing
            sim_results_path: path to energyplus simulation results.

        Returns:

        """
        IDF.setiddname(
            self.playground.sim_settings.ep_install_path / 'Energy+.idd')
        export_path = sim_results_path / self.prj_name

        # initialize the idf with a minimal idf setup
        idf2 = IDF(export_path / str(self.prj_name + '.idf'))
        idf2.save(export_path / str(self.prj_name + '_before_sizing.idf'))
        idf2.save(export_path / str(self.prj_name + '_sizing.idf'))
        idf3 = IDF(export_path / str(self.prj_name + '_sizing.idf'))
        idf3.removeallidfobjects('OUTPUT:VARIABLE')
        idf3.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Ideal Loads Supply Air Total Cooling Rate",
            Reporting_Frequency="Hourly",
        )
        idf3.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Ideal Loads Supply Air Total Heating Rate",
            Reporting_Frequency="Hourly",
        )
        idf3.epw = sizing_weather_file
        for sim_control in idf3.idfobjects["SIMULATIONCONTROL"]:
            sim_control.Run_Simulation_for_Sizing_Periods = 'Yes'
            sim_control.Run_Simulation_for_Weather_File_Run_Periods = 'No'
        idf3.run(output_directory=export_path, readvars=True, annual=False)
        res_sizing = pd.read_csv(export_path / 'epluszsz.csv')
        res_sizing = res_sizing.set_index('Time')
        peak = res_sizing.loc['Peak']
        peak_heating = peak.filter(like='Des Heat Load')
        peak_cooling = peak.filter(like='Des Sens Cool Load')
        for obj in idf.idfobjects['HVACTEMPLATE:ZONE:IDEALLOADSAIRSYSTEM']:
            curr_heating = peak_heating.filter(like=obj.Zone_Name.upper()).max()
            curr_cooling = peak_cooling.filter(like=obj.Zone_Name.upper()).max()
            obj.Heating_Limit = 'LimitCapacity'
            obj.Cooling_Limit = 'LimitCapacity'
            obj.Maximum_Sensible_Heating_Capacity = curr_heating
            obj.Maximum_Total_Cooling_Capacity = curr_cooling
        for sim_control in idf.idfobjects["SIMULATIONCONTROL"]:
            sim_control.Do_System_Sizing_Calculation = 'Yes'
        idf.save(idf.idfname)

    @staticmethod
    def init_idf(sim_settings: EnergyPlusSimSettings, paths: FolderStructure,
                 weather_file: PosixPath, ifc_name: str) -> tuple[IDF, Path]:
        """ Initialize the EnergyPlus input file.

        Initialize the EnergyPlus input file (idf) with general idf settings
        and set default weather
        data.

        Args:
            sim_settings: EnergyPlusSimSettings
            paths: BIM2SIM FolderStructure
            weather_file: PosixPath to *.epw weather file
            ifc_name: str of name of ifc
        Returns:
            idf file of type IDF, sim_results_path
        """
        logger.info("Initialize the idf ...")
        # set the installation path for the EnergyPlus installation
        ep_install_path = sim_settings.ep_install_path
        # set the plugin path of the PluginEnergyPlus within the BIM2SIM Tool
        plugin_ep_path = str(Path(__file__).parent.parent.parent)
        # set Energy+.idd as base for new idf
        IDF.setiddname(ep_install_path / 'Energy+.idd')
        # initialize the idf with a minimal idf setup
        idf = IDF(plugin_ep_path + '/data/Minimal.idf')
        # remove location and design days
        idf.removeallidfobjects('SIZINGPERIOD:DESIGNDAY')
        idf.removeallidfobjects('SITE:LOCATION')
        if sim_settings.system_weather_sizing != 'DesignDay':
            # enable system sizing for extreme or typical days.
            if sim_settings.system_weather_sizing == 'Extreme':
                period_selection = 'Extreme'
            elif sim_settings.system_weather_sizing == 'Typical':
                period_selection = 'Typical'
            idf.newidfobject("SIZINGPERIOD:WEATHERFILECONDITIONTYPE",
                             Name='Summer Design Day from Weather File',
                             Period_Selection=f'Summer{period_selection}',
                             Day_of_Week_for_Start_Day='SummerDesignDay'
                             )
            idf.newidfobject("SIZINGPERIOD:WEATHERFILECONDITIONTYPE",
                             Name='Winter Design Day from Weather File',
                             Period_Selection=f'Winter{period_selection}',
                             Day_of_Week_for_Start_Day='WinterDesignDay'
                             )
        else:
            # use default Design day (July 21, December 21) for system sizing
            idf.newidfobject("SIZINGPERIOD:WEATHERFILEDAYS",
                             Name='Summer Design Day from Weather File',
                             Begin_Month=7,
                             Begin_Day_of_Month=21,
                             End_Month=7,
                             End_Day_of_Month=21,
                             Day_of_Week_for_Start_Day='SummerDesignDay'
                             )
            idf.newidfobject("SIZINGPERIOD:WEATHERFILEDAYS",
                             Name='Winter Design Day from Weather File',
                             Begin_Month=12,
                             Begin_Day_of_Month=21,
                             End_Month=12,
                             End_Day_of_Month=21,
                             Day_of_Week_for_Start_Day='WinterDesignDay'
                             )

        sim_results_path = paths.export/'EnergyPlus'/'SimResults'
        export_path = sim_results_path / ifc_name
        if not os.path.exists(export_path):
            os.makedirs(export_path)
        idf.idfname = export_path / str(ifc_name + '.idf')
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
        return idf, sim_results_path

    def init_zone(self, sim_settings: EnergyPlusSimSettings, elements: dict,
                  idf: IDF):
        """Initialize zone settings.

        Creates one idf zone per space and sets heating and cooling
        templates, infiltration and internal loads (occupancy (people),
        equipment, lighting).

        Args:
            sim_settings: BIM2SIM simulation settings
            elements: dict[guid: element]
            idf: idf file object
        """
        logger.info("Init thermal zones ...")
        spaces = get_spaces_with_bounds(elements)
        for space in spaces:
            if space.space_shape_volume:
                volume = space.space_shape_volume.to(ureg.meter ** 3).m
            # for some shapes, shape volume calculation might not work
            else:
                volume = space.volume.to(ureg.meter ** 3).m
            zone = idf.newidfobject(
                'ZONE',
                Name=space.ifc.GlobalId,
                Volume=volume
            )
            self.set_heating_and_cooling(idf, zone_name=zone.Name, space=space)
            self.set_infiltration(
                idf, name=zone.Name, zone_name=zone.Name, space=space,
                ep_version=sim_settings.ep_version)
            if (not space.with_cooling and
                    self.playground.sim_settings.add_natural_ventilation):
                self.set_natural_ventilation(
                    idf, name=zone.Name, zone_name=zone.Name, space=space,
                    ep_version=sim_settings.ep_version,
                    residential=sim_settings.residential,
                    ventilation_method=
                    sim_settings.natural_ventilation_approach)
            self.set_people(sim_settings, idf, name=zone.Name,
                            zone_name=zone.Name, space=space)
            self.set_equipment(sim_settings, idf, name=zone.Name,
                               zone_name=zone.Name, space=space)
            self.set_lights(sim_settings, idf, name=zone.Name, zone_name=zone.Name,
                            space=space)
            if sim_settings.building_rotation_overwrite != 0:
                idf.idfobjects['BUILDING'][0].North_Axis = (
                    sim_settings.building_rotation_overwrite)
                idf.idfobjects['GLOBALGEOMETRYRULES'][0].Coordinate_System =\
                    'Relative'

    @staticmethod
    def init_zonelist(
            idf: IDF,
            name: str = None,
            zones_in_list: list[str] = None):
        """Initialize zone lists.

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
            if len(idf_zones) > 99:
                logger.warning("Trying to assign more than 99 zones to a "
                               "single zone list. May require changes in "
                               "Energy+.idd to successfully execute "
                               "simulation.")
        else:
            # assign all zones with the zone names that are included in
            # zones_in_list to the zonelist.
            all_idf_zones = idf.idfobjects["ZONE"]
            idf_zones = [zone for zone in all_idf_zones if zone.Name
                         in zones_in_list]
            if len(idf_zones) > 99:
                logger.warning("Trying to assign more than 99 zones to a "
                               "single zone list. May require changes in "
                               "Energy+.idd to successfully execute "
                               "simulation.")
            if len(idf_zones) == 0:
                return
        if name is None:
            name = "All_Zones"
        zs = {}
        for i, z in enumerate(idf_zones):
            zs.update({"Zone_" + str(i + 1) + "_Name": z.Name})
        idf.newidfobject("ZONELIST", Name=name, **zs)

    def init_zonegroups(self, elements: dict, idf: IDF):
        """Assign one zonegroup per storey.

        Args:
            elements: dict[guid: element]
            idf: idf file object
        """
        spaces = get_spaces_with_bounds(elements)
        space_usage_dict = {}
        for space in spaces:
            if space.usage.replace(',', '') not in space_usage_dict.keys():
                space_usage_dict.update({space.usage.replace(',',
                                                             ''): [space.guid]})
            else:
                space_usage_dict[space.usage.replace(',', '')].append(
                    space.guid)

        for key, value in space_usage_dict.items():
            if not idf.getobject('ZONELIST', key):
                self.init_zonelist(idf, name=key, zones_in_list=value)
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
    @staticmethod
    def check_preprocessed_materials_and_constructions(rel_elem, layers):
        """Check if preprocessed materials and constructions are valid."""
        correct_preprocessing = False
        # check if thickness and material parameters are available from
        # preprocessing
        if all(layer.thickness for layer in layers):
            for layer in rel_elem.layerset.layers:
                if None in (layer.material.thermal_conduc,
                            layer.material.spec_heat_capacity,
                            layer.material.density):
                    return correct_preprocessing
                elif 0 in (layer.material.thermal_conduc.m,
                            layer.material.spec_heat_capacity.m,
                            layer.material.density.m):
                    return correct_preprocessing
                else:
                    pass

            correct_preprocessing = True

        return correct_preprocessing

    def get_preprocessed_materials_and_constructions(
            self, sim_settings: EnergyPlusSimSettings, elements: dict, idf: IDF):
        """Get preprocessed materials and constructions.

        This function sets preprocessed construction and material for
        building surfaces and fenestration. For virtual bounds, an air
        boundary construction is set.

        Args:
            sim_settings: BIM2SIM simulation settings
            elements: dict[guid: element]
            idf: idf file object
        """
        logger.info("Get predefined materials and construction ...")
        bounds = filter_elements(elements, 'SpaceBoundary')
        for bound in bounds:
            rel_elem = bound.bound_element
            if not rel_elem:
                continue
            if not any([isinstance(rel_elem, window) for window in
                        all_subclasses(Window, include_self=True)]):
                # set construction for all but fenestration
                if self.check_preprocessed_materials_and_constructions(
                        rel_elem, rel_elem.layerset.layers):
                    self.set_preprocessed_construction_elem(
                        rel_elem, rel_elem.layerset.layers, idf)
                    for layer in rel_elem.layerset.layers:
                        self.set_preprocessed_material_elem(layer, idf)
                else:
                    logger.warning("No preprocessed construction and "
                                   "material found for space boundary %s on "
                                   "related building element %s. Using "
                                   "default values instead.",
                                   bound.guid, rel_elem.guid)
            else:
                # set construction elements for windows
                self.set_preprocessed_window_material_elem(
                    rel_elem, idf, sim_settings.add_window_shading)

        # Add air boundaries as construction as a material for virtual bounds
        if sim_settings.ep_version in ["9-2-0", "9-4-0"]:
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
    def set_preprocessed_construction_elem(
            rel_elem: IFCBased,
            layers: list[Layer],
            idf: IDF):
        """Write preprocessed constructions to idf.

        This function uses preprocessed data to define idf construction
        elements.

        Args:
            rel_elem: any subclass of IFCBased (e.g., Wall)
            layers: list of Layer
            idf: idf file object
        """
        construction_name = (rel_elem.key.replace('Disaggregated', '') + '_'
                             + str(len(layers)) + '_' + '_' \
            .join([str(l.thickness.to(ureg.metre).m) for l in layers]))
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
    def set_preprocessed_material_elem(layer: Layer, idf: IDF):
        """Set a preprocessed material element.

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
        conductivity = layer.material.thermal_conduc.to(
                             ureg.W / (ureg.m * ureg.K)).m
        density = layer.material.density.to(ureg.kg / ureg.m ** 3).m
        if conductivity == 0:
            logger.error(f"Conductivity of {layer.material} is 0. Simulation "
                         f"will crash, please correct input or resulting idf "
                         f"file.")
        if density == 0:
            logger.error(f"Density of {layer.material} is 0. Simulation "
                         f"will crash, please correct input or resulting idf "
                         f"file.")
        idf.newidfobject("MATERIAL",
                         Name=material_name,
                         Roughness="MediumRough",
                         Thickness=layer.thickness.to(ureg.metre).m,
                         Conductivity=conductivity,
                         Density=density,
                         Specific_Heat=specific_heat
                         )

    @staticmethod
    def set_preprocessed_window_material_elem(rel_elem: Window,
                                              idf: IDF,
                                              add_window_shading: False):
        """Set preprocessed window material.

        This function constructs windows with a
        WindowMaterial:SimpleGlazingSystem consisting of the outermost layer
        of the providing related element. This is a simplification, needs to
        be extended to hold multilayer window constructions.

        Args:
            rel_elem: Window instance
            idf: idf file object
            add_window_shading: Add window shading (options: 'None',
            'Interior', 'Exterior')
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
                           rel_elem.layerset.layers[
                               0].material.thermal_conduc.to(
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
        if add_window_shading:
            default_shading_name = "DefaultWindowShade"
            if not idf.getobject("WINDOWMATERIAL:SHADE", default_shading_name):
                idf.newidfobject("WINDOWMATERIAL:SHADE",
                                 Name=default_shading_name,
                                 Solar_Transmittance=0.3,
                                 Solar_Reflectance=0.5,
                                 Visible_Transmittance=0.3,
                                 Visible_Reflectance=0.5,
                                 Infrared_Hemispherical_Emissivity=0.9,
                                 Infrared_Transmittance=0.05,
                                 Thickness=0.003,
                                 Conductivity=0.1)
            construction_name = 'Window_' + material_name + "_" \
                                + add_window_shading
            if idf.getobject("CONSTRUCTION", construction_name) is None:
                if add_window_shading == 'Interior':
                    idf.newidfobject("CONSTRUCTION",
                                     Name=construction_name,
                                     Outside_Layer=material_name,
                                     Layer_2=default_shading_name
                                     )
                else:
                    idf.newidfobject("CONSTRUCTION",
                                     Name=construction_name,
                                     Outside_Layer=default_shading_name,
                                     Layer_2=material_name
                                     )
        # todo: enable use of multilayer windows
        # set construction without shading anyways
        construction_name = 'Window_' + material_name
        if idf.getobject("CONSTRUCTION", construction_name) is None:
            idf.newidfobject("CONSTRUCTION",
                             Name=construction_name,
                             Outside_Layer=material_name
                             )

    def set_heating_and_cooling(self, idf: IDF, zone_name: str,
                                space: ThermalZone):
        """Set heating and cooling parameters.

        This function sets heating and cooling parameters based on the data
        available from BIM2SIM Preprocessing (either IFC-based or
        Template-based).

        Args:
            idf: idf file object
            zone_name: str
            space: ThermalZone instance
        """
        stat_name = "STATS " + space.usage.replace(',', '')
        if self.playground.sim_settings.control_operative_temperature:
            # set control for operative temperature instead of air temperature
            operative_stats_name = space.usage.replace(',', '') + ' THERMOSTAT'
            htg_schedule_name = "Schedule " + "Heating " + space.usage.replace(
                ',', '')
            self.set_day_week_year_schedule(idf, space.heating_profile[:24],
                                            'heating_profile',
                                            htg_schedule_name)
            clg_schedule_name = "Schedule " + "Cooling " + space.usage.replace(
                ',', '')
            self.set_day_week_year_schedule(idf, space.cooling_profile[:24],
                                            'cooling_profile',
                                            clg_schedule_name)
            if idf.getobject('THERMOSTATSETPOINT:DUALSETPOINT',
                             htg_schedule_name + ' ' + clg_schedule_name) is None:
                idf.newidfobject(
                    'THERMOSTATSETPOINT:DUALSETPOINT',
                    Name=htg_schedule_name + ' ' + clg_schedule_name,
                    Heating_Setpoint_Temperature_Schedule_Name
                    =htg_schedule_name,
                    Cooling_Setpoint_Temperature_Schedule_Name=clg_schedule_name
                )
            if idf.getobject("ZONECONTROL:THERMOSTAT:OPERATIVETEMPERATURE",
                             zone_name + ' ' + operative_stats_name) is None:
                idf.newidfobject(
                    "ZONECONTROL:THERMOSTAT:OPERATIVETEMPERATURE",
                    Thermostat_Name=zone_name + ' ' + operative_stats_name,
                    Radiative_Fraction_Input_Mode='constant',
                    Fixed_Radiative_Fraction=0.5
                )
            if idf.getobject("ZONECONTROL:THERMOSTAT",
                             operative_stats_name) is None:
                stat = idf.newidfobject(
                    "ZONECONTROL:THERMOSTAT",
                    Name=operative_stats_name,
                    Zone_or_ZoneList_Name=space.usage.replace(',', ''),
                    Control_Type_Schedule_Name='Zone Control Type Sched',
                    Control_1_Object_Type='ThermostatSetpoint:DualSetpoint',
                    Control_1_Name=htg_schedule_name + ' ' + clg_schedule_name,
                    # Temperature_Difference_Between_Cutout_And_Setpoint=0.2,
                    # temperature difference disables operative control
                )
            else:
                stat = idf.getobject('ZONECONTROL:THERMOSTAT',
                                     operative_stats_name)
            if idf.getobject("SCHEDULE:COMPACT",
                             'Zone Control Type Sched') is None:
                idf.newidfobject("SCHEDULE:COMPACT",
                                 Name='Zone Control Type Sched',
                                 Schedule_Type_Limits_Name='Control Type',
                                 Field_1='Through: 12/31',
                                 Field_2='For: AllDays',
                                 Field_3='Until: 24:00',
                                 Field_4='4',
                                 )
            if idf.getobject("SCHEDULETYPELIMITS", 'Control Type') is None:
                idf.newidfobject('SCHEDULETYPELIMITS',
                                 Name='Control Type',
                                 Lower_Limit_Value=0,
                                 Upper_Limit_Value=4,
                                 Numeric_Type='DISCRETE')
            template_thermostat_name = ''
        elif idf.getobject("HVACTEMPLATE:THERMOSTAT", stat_name) is None:
            # if air temperature is controlled, create thermostat if it is
            # not available
            stat = self.set_day_hvac_template(idf, space, stat_name)
            template_thermostat_name = stat.Name
        else:
            # assign available thermostats for air control
            stat = idf.getobject("HVACTEMPLATE:THERMOSTAT", stat_name)
            template_thermostat_name = stat.Name

        # initialize heating and cooling availability, and capacity
        cooling_availability = "Off"
        heating_availability = "Off"
        heating_limit = 'NoLimit'
        cooling_limit = 'NoLimit'
        maximum_cooling_capacity = 'autosize'
        maximum_cooling_rate = 'autosize'
        outdoor_air_method = 'None'
        # convert from l/s to m3/s
        outdoor_air_person = (
            self.playground.sim_settings.outdoor_air_per_person) / 1000
        outdoor_air_area = (
            self.playground.sim_settings.outdoor_air_per_area) / 1000
        ventilation_demand_control = 'None'
        outdoor_air_economizer = 'NoEconomizer'
        heat_recovery_type = 'None'
        heat_recovery_sensible = (
            self.playground.sim_settings.heat_recovery_sensible)
        heat_recovery_latent = self.playground.sim_settings.heat_recovery_latent

        # initialize night setback if required
        if self.playground.sim_settings.hvac_off_at_night and idf.getobject(
                "SCHEDULE:COMPACT", "On_except_10pm_to_6am") is None:
            idf.newidfobject(
                "SCHEDULE:COMPACT",
                Name='On_except_10pm_to_6am',
                Schedule_Type_Limits_Name='on/off',
                Field_1='Through: 12/31',
                Field_2='For: AllDays',
                Field_3='Until: 06:00',
                Field_4='0',
                Field_5='Until: 22:00',
                Field_6='1',
                Field_7='Until: 24:00',
                Field_8='0'
            )

        # overwrite heating / cooling availability if required
        if space.with_cooling:
            cooling_availability = "On"
            if self.playground.sim_settings.hvac_off_at_night:
                cooling_availability = 'On_except_10pm_to_6am'
            cooling_limit = 'LimitFlowRateAndCapacity'

        if space.with_heating:
            heating_availability = "On"
            if self.playground.sim_settings.hvac_off_at_night:
                heating_availability = 'On_except_10pm_to_6am'

        if space.with_cooling or \
            not self.playground.sim_settings.add_natural_ventilation:
            outdoor_air_method = 'Sum'
            ventilation_demand_control = (
                self.playground.sim_settings.ventilation_demand_control)
            outdoor_air_economizer = (
                self.playground.sim_settings.outdoor_air_economizer)
            heat_recovery_type = self.playground.sim_settings.heat_recovery_type

        # initialize ideal loads air system according to the settings
        idf.newidfobject(
            "HVACTEMPLATE:ZONE:IDEALLOADSAIRSYSTEM",
            Zone_Name=zone_name,
            Template_Thermostat_Name=template_thermostat_name,
            Heating_Availability_Schedule_Name=heating_availability,
            Cooling_Availability_Schedule_Name=cooling_availability,
            Heating_Limit=heating_limit,
            Cooling_Limit=cooling_limit,
            Maximum_Cooling_Air_Flow_Rate=maximum_cooling_rate,
            Maximum_Total_Cooling_Capacity=maximum_cooling_capacity,
            Outdoor_Air_Method=outdoor_air_method,
            Outdoor_Air_Flow_Rate_per_Person=outdoor_air_person,
            Outdoor_Air_Flow_Rate_per_Zone_Floor_Area=outdoor_air_area,
            Demand_Controlled_Ventilation_Type=ventilation_demand_control,
            Outdoor_Air_Economizer_Type=outdoor_air_economizer,
            Heat_Recovery_Type=heat_recovery_type,
            Sensible_Heat_Recovery_Effectiveness=heat_recovery_sensible,
            Latent_Heat_Recovery_Effectiveness=heat_recovery_latent,
        )

    def set_people(self, sim_settings: EnergyPlusSimSettings, idf: IDF, name: str,
                   zone_name: str, space: ThermalZone):
        """Set occupancy schedules.

        This function sets schedules and internal loads from people (occupancy)
        based on the BIM2SIM Preprocessing, i.e. based on IFC data if
        available or on templates.

        Args:
            sim_settings: BIM2SIM simulation settings
            idf: idf file object
            name: name of the new people idf object
            zone_name: name of zone or zone_list
            space: ThermalZone instance
        """
        schedule_name = "Schedule " + "People " + space.usage.replace(',', '')
        profile_name = 'persons_profile'
        self.set_day_week_year_schedule(idf, space.persons_profile[:24],
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
                                 ureg.watt).m#*1.8  # in W/Person
                             )  # other method for Field_4 (not used here)
            # ="persons_profile"*"activity_degree_persons"*58,1*1,8
            # (58.1 W/(m2*met), 1.8m2/Person)
        if sim_settings.ep_version in ["9-2-0", "9-4-0"]:
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
    def set_day_week_year_schedule(idf: IDF, schedule: list[float],
                                   profile_name: str,
                                   schedule_name: str):
        """Set day, week and year schedule (hourly).

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

    def set_equipment(self, sim_settings: EnergyPlusSimSettings, idf: IDF,
                      name: str, zone_name: str,
                      space: ThermalZone):
        """Set internal loads from equipment.

        This function sets schedules and internal loads from equipment based
        on the BIM2SIM Preprocessing, i.e. based on IFC data if available or on
        templates.

        Args:
            sim_settings: BIM2SIM simulation settings
            idf: idf file object
            name: name of the new people idf object
            zone_name: name of zone or zone_list
            space: ThermalZone instance
        """
        schedule_name = "Schedule " + "Equipment " + space.usage.replace(',',
                                                                         '')
        profile_name = 'machines_profile'
        self.set_day_week_year_schedule(idf, space.machines_profile[:24],
                                        profile_name, schedule_name)
        if sim_settings.ep_version in ["9-2-0", "9-4-0"]:
            idf.newidfobject(
                "ELECTRICEQUIPMENT",
                Name=name,
                Zone_or_ZoneList_Name=zone_name,
                Schedule_Name=schedule_name,
                Design_Level_Calculation_Method="Watts/Area",
                Watts_per_Zone_Floor_Area=space.machines.to(
                    ureg.watt / ureg.meter ** 2).m
            )
        else:
            idf.newidfobject(
                "ELECTRICEQUIPMENT",
                Name=name,
                Zone_or_ZoneList_or_Space_or_SpaceList_Name=zone_name,
                Schedule_Name=schedule_name,
                Design_Level_Calculation_Method="Watts/Area",
                Watts_per_Zone_Floor_Area=space.machines.to(
                    ureg.watt / ureg.meter ** 2).m
            )

    def set_lights(self, sim_settings: EnergyPlusSimSettings, idf: IDF, name: str,
                   zone_name: str, space: ThermalZone):
        """Set internal loads from lighting.

        This function sets schedules and lighting based on the
        BIM2SIM Preprocessing, i.e. based on IFC data if available or on
        templates.

        Args:
            sim_settings: BIM2SIM simulation settings
            idf: idf file object
            name: name of the new people idf object
            zone_name: name of zone or zone_list
            space: ThermalZone instance
        """
        schedule_name = "Schedule " + "Lighting " + space.usage.replace(',', '')
        profile_name = 'lighting_profile'
        self.set_day_week_year_schedule(idf, space.lighting_profile[:24],
                                        profile_name, schedule_name)
        mode = "Watts/Area"
        watts_per_zone_floor_area = space.lighting_power.to(
            ureg.watt / ureg.meter ** 2).m
        return_air_fraction = 0.0
        fraction_radiant = 0.42  # fraction radiant: cf. Table 1.28 in
        # InputOutputReference EnergyPlus (Version 9.4.0), p. 506
        fraction_visible = 0.18  # Todo: fractions do not match with .json
        # Data. Maybe set by user-input later
        if sim_settings.ep_version in ["9-2-0", "9-4-0"]:
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
    def set_infiltration(idf: IDF,
                         name: str, zone_name: str,
                         space: ThermalZone, ep_version: str):
        """Set infiltration rate.

        This function sets the infiltration rate per space based on the
        BIM2SIM preprocessing values (IFC-based if available or
        template-based).

        Args:
            idf: idf file object
            name: name of the new people idf object
            zone_name: name of zone or zone_list
            space: ThermalZone instance
            ep_version: Used version of EnergyPlus
        """
        if ep_version in ["9-2-0", "9-4-0"]:
            idf.newidfobject(
                "ZONEINFILTRATION:DESIGNFLOWRATE",
                Name=name,
                Zone_or_ZoneList_Name=zone_name,
                Schedule_Name="Continuous",
                Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
                Air_Changes_per_Hour=space.base_infiltration
            )
        else:
            idf.newidfobject(
                "ZONEINFILTRATION:DESIGNFLOWRATE",
                Name=name,
                Zone_or_ZoneList_or_Space_or_SpaceList_Name=zone_name,
                Schedule_Name="Continuous",
                Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
                Air_Changes_per_Hour=space.base_infiltration
            )

    @staticmethod
    def set_natural_ventilation(idf: IDF, name: str, zone_name: str,
                                space: ThermalZone, ep_version,
                                min_in_temp=22, residential=False,
                                ventilation_method="Simple"):
        """Set natural ventilation.

        This function sets the natural ventilation per space based on the
        BIM2SIM preprocessing values (IFC-based if available or
        template-based). Natural ventilation is defined for winter, summer
        and overheating cases, setting the air change per hours and minimum
        and maximum outdoor temperature if applicable.

        Args:
            idf: idf file object
            name: name of the new people idf object
            zone_name: name of zone or zone_list
            space: ThermalZone instance
            ep_version: Used version of EnergyPlus

        """
        if ep_version in ["9-2-0", "9-4-0"]:
            if ventilation_method == 'DIN4108':
                space_volume = space.space_shape_volume.m
                space_area = space.net_area.m
                if residential:
                    occupied_air_exchange = 0.5
                    unoccupied_air_exchange = 0.5
                    occupied_increased_exchange = 3
                    unoccupied_increased_exchange = 2
                else:
                    occupied_air_exchange = 4 * space_area/space_volume
                    unoccupied_air_exchange = 0.24
                    occupied_increased_exchange = 3
                    unoccupied_increased_exchange = 2

                if residential:
                    occupied_schedule_name = 'residential_occupied_hours'
                    unoccupied_schedule_name = 'residential_unoccupied_hours'
                    if idf.getobject("SCHEDULE:COMPACT",
                                     occupied_schedule_name) is None:
                        idf.newidfobject("SCHEDULE:COMPACT",
                                         Name=occupied_schedule_name,
                                         Schedule_Type_Limits_Name='Continuous',
                                         Field_1='Through: 12/31',
                                         Field_2='For: AllDays',
                                         Field_3='Until: 6:00',
                                         Field_4='0',
                                         Field_5='Until: 23:00',
                                         Field_6='1',
                                         Field_7='Until: 24:00',
                                         Field_8='0',
                                         )
                    if idf.getobject("SCHEDULE:COMPACT",
                                     unoccupied_schedule_name) is None:
                        idf.newidfobject("SCHEDULE:COMPACT",
                                         Name=unoccupied_schedule_name,
                                         Schedule_Type_Limits_Name='Continuous',
                                         Field_1='Through: 12/31',
                                         Field_2='For: AllDays',
                                         Field_3='Until: 6:00',
                                         Field_4='1',
                                         Field_5='Until: 23:00',
                                         Field_6='0',
                                         Field_7='Until: 24:00',
                                         Field_8='1',
                                         )
                else:
                    occupied_schedule_name = 'non_residential_occupied_hours'
                    unoccupied_schedule_name = 'non_residential_unoccupied_hours'
                    if idf.getobject("SCHEDULE:COMPACT",
                                     occupied_schedule_name) is None:
                        idf.newidfobject("SCHEDULE:COMPACT",
                                         Name=occupied_schedule_name,
                                         Schedule_Type_Limits_Name='Continuous',
                                         Field_1='Through: 12/31',
                                         Field_2='For: AllDays',
                                         Field_3='Until: 7:00',
                                         Field_4='0',
                                         Field_5='Until: 18:00',
                                         Field_6='1',
                                         Field_7='Until: 24:00',
                                         Field_8='0',
                                         )
                    if idf.getobject("SCHEDULE:COMPACT",
                                     unoccupied_schedule_name) is None:
                        idf.newidfobject("SCHEDULE:COMPACT",
                                         Name=unoccupied_schedule_name,
                                         Schedule_Type_Limits_Name='Continuous',
                                         Field_1='Through: 12/31',
                                         Field_2='For: AllDays',
                                         Field_3='Until: 7:00',
                                         Field_4='1',
                                         Field_5='Until: 18:00',
                                         Field_6='0',
                                         Field_7='Until: 24:00',
                                         Field_8='1',
                                         )
                idf.newidfobject(
                    "ZONEVENTILATION:DESIGNFLOWRATE",
                    Name=name + '_occupied_ventilation',
                    Zone_or_ZoneList_Name=zone_name,
                    Schedule_Name=occupied_schedule_name,
                    Ventilation_Type="Natural",
                    Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
                    Air_Changes_per_Hour=occupied_air_exchange,
                )
                idf.newidfobject(
                    "ZONEVENTILATION:DESIGNFLOWRATE",
                    Name=name + '_occupied_ventilation_increased',
                    Zone_or_ZoneList_Name=zone_name,
                    Schedule_Name=occupied_schedule_name,
                    Ventilation_Type="Natural",
                    Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
                    Air_Changes_per_Hour=max(
                        occupied_increased_exchange-occupied_air_exchange, 0),
                    Minimum_Indoor_Temperature=23,
                    Maximum_Indoor_Temperature=26,
                    Minimum_Outdoor_Temperature=12,
                    Delta_Temperature=0,
                )
                idf.newidfobject(
                    "ZONEVENTILATION:DESIGNFLOWRATE",
                    Name=name + '_occupied_ventilation_increased_overheating',
                    Zone_or_ZoneList_Name=zone_name,
                    Schedule_Name=occupied_schedule_name,
                    Ventilation_Type="Natural",
                    Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
                    Air_Changes_per_Hour=max(
                        occupied_increased_exchange-occupied_air_exchange, 0),
                    Minimum_Indoor_Temperature=26,
                    Delta_Temperature=0,
                )
                idf.newidfobject(
                    "ZONEVENTILATION:DESIGNFLOWRATE",
                    Name=name + '_unoccupied_ventilation',
                    Zone_or_ZoneList_Name=zone_name,
                    Schedule_Name=unoccupied_schedule_name,
                    Ventilation_Type="Natural",
                    Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
                    Air_Changes_per_Hour=unoccupied_air_exchange,
                )
                idf.newidfobject(
                    "ZONEVENTILATION:DESIGNFLOWRATE",
                    Name=name + '_unoccupied_ventilation_increased',
                    Zone_or_ZoneList_Name=zone_name,
                    Schedule_Name=unoccupied_schedule_name,
                    Ventilation_Type="Natural",
                    Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
                    Air_Changes_per_Hour=max(
                        unoccupied_increased_exchange-unoccupied_air_exchange, 0),
                    Minimum_Indoor_Temperature=23,
                    Maximum_Indoor_Temperature=26,
                    Minimum_Outdoor_Temperature=15,
                    Delta_Temperature=0,
                )
                idf.newidfobject(
                    "ZONEVENTILATION:DESIGNFLOWRATE",
                    Name=name + '_unoccupied_ventilation_increased_overheating',
                    Zone_or_ZoneList_Name=zone_name,
                    Schedule_Name=unoccupied_schedule_name,
                    Ventilation_Type="Natural",
                    Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
                    Air_Changes_per_Hour=max(
                        unoccupied_increased_exchange-unoccupied_air_exchange, 0),
                    Minimum_Indoor_Temperature=26,
                    # Minimum_Outdoor_Temperature=10,
                    Delta_Temperature=0,
                )
            else:
                # use bim2sim standard zone ventilation based on TEASER
                # templates
                idf.newidfobject(
                    "ZONEVENTILATION:DESIGNFLOWRATE",
                    Name=name + '_winter',
                    Zone_or_ZoneList_Name=zone_name,
                    Schedule_Name="Continuous",
                    Ventilation_Type="Natural",
                    Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
                    Air_Changes_per_Hour=space.winter_reduction_infiltration[0],
                    Minimum_Outdoor_Temperature=
                    space.winter_reduction_infiltration[1] - 273.15,
                    Maximum_Outdoor_Temperature=
                    space.winter_reduction_infiltration[2] - 273.15,
                )

                idf.newidfobject(
                    "ZONEVENTILATION:DESIGNFLOWRATE",
                    Name=name + '_summer',
                    Zone_or_ZoneList_Name=zone_name,
                    Schedule_Name="Continuous",
                    Ventilation_Type="Natural",
                    Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
                    Air_Changes_per_Hour=space.max_summer_infiltration[0],
                    Minimum_Outdoor_Temperature
                    =space.max_summer_infiltration[1] - 273.15,
                    Maximum_Outdoor_Temperature
                    =space.max_summer_infiltration[2] - 273.15,
                )

                idf.newidfobject(
                    "ZONEVENTILATION:DESIGNFLOWRATE",
                    Name=name + '_overheating',
                    Zone_or_ZoneList_Name=zone_name,
                    Schedule_Name="Continuous",
                    Ventilation_Type="Natural",
                    Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
                    # calculation of overheating infiltration is a simplification
                    # compared to the corresponding TEASER implementation which
                    # dynamically computes thresholds for overheating infiltration
                    # based on the zone temperature and additional factors.
                    Air_Changes_per_Hour=space.max_overheating_infiltration[0],
                    Minimum_Outdoor_Temperature
                    =space.max_summer_infiltration[2] - 273.15,
                )
        else:
            # use bim2sim standard zone ventilation based on TEASER templates
            idf.newidfobject(
                "ZONEVENTILATION:DESIGNFLOWRATE",
                Name=name + '_winter',
                Zone_or_ZoneList_or_Space_or_SpaceList_Name=zone_name,
                Schedule_Name="Continuous",
                Ventilation_Type="Natural",
                Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
                Air_Changes_per_Hour=space.winter_reduction_infiltration[0],
                Minimum_Outdoor_Temperature=
                space.winter_reduction_infiltration[1] - 273.15,
                Maximum_Outdoor_Temperature=
                space.winter_reduction_infiltration[2] - 273.15,
            )

            idf.newidfobject(
                "ZONEVENTILATION:DESIGNFLOWRATE",
                Name=name + '_summer',
                Zone_or_ZoneList_or_Space_or_SpaceList_Name=zone_name,
                Schedule_Name="Continuous",
                Ventilation_Type="Natural",
                Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
                Air_Changes_per_Hour=space.max_summer_infiltration[0],
                Minimum_Outdoor_Temperature
                =space.max_summer_infiltration[1] - 273.15,
                Maximum_Outdoor_Temperature
                =space.max_summer_infiltration[2] - 273.15,
            )

            idf.newidfobject(
                "ZONEVENTILATION:DESIGNFLOWRATE",
                Name=name + '_overheating',
                Zone_or_ZoneList_or_Space_or_SpaceList_Name=zone_name,
                Schedule_Name="Continuous",
                Ventilation_Type="Natural",
                Design_Flow_Rate_Calculation_Method="AirChanges/Hour",
                # calculation of overheating infiltration is a simplification
                # compared to the corresponding TEASER implementation which
                # dynamically computes thresholds for overheating infiltration
                # based on the zone temperature and additional factors.
                Air_Changes_per_Hour=space.max_overheating_infiltration[0],
                Minimum_Outdoor_Temperature
                =space.max_summer_infiltration[2] - 273.15,
            )

    def set_day_hvac_template(self, idf: IDF, space: ThermalZone, name: str):
        """Set 24 hour hvac template.

        This function sets idf schedules with 24hour schedules for heating and
        cooling.

        Args:
            idf: idf file object
            space: ThermalZone
            name: IDF Thermostat Name
        """
        htg_schedule_name = "Schedule " + "Heating " + space.usage.replace(
            ',', '')
        self.set_day_week_year_schedule(idf, space.heating_profile[:24],
                                        'heating_profile',
                                        htg_schedule_name)

        clg_schedule_name = "Schedule " + "Cooling " + space.usage.replace(
            ',', '')
        self.set_day_week_year_schedule(idf, space.cooling_profile[:24],
                                        'cooling_profile',
                                        clg_schedule_name)
        stat = idf.newidfobject(
            "HVACTEMPLATE:THERMOSTAT",
            Name=name,
            Heating_Setpoint_Schedule_Name=htg_schedule_name,
            Cooling_Setpoint_Schedule_Name=clg_schedule_name
        )
        return stat

    def set_hvac_template(self, idf: IDF, name: str,
                          heating_sp: Union[int, float],
                          cooling_sp: Union[int, float],
                          mode='setback'):
        """Set heating and cooling templates (manually).

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
                self.write_schedule(idf, htg_name, [htg_alldays, ])
            else:
                idf.getobject("SCHEDULE:COMPACT", htg_name)
            if idf.getobject("SCHEDULE:COMPACT", clg_name) is None:
                self.write_schedule(idf, clg_name, [clg_alldays, ])
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
    def write_schedule(idf: IDF, sched_name: str, sched_part_list: list):
        """Write schedules to idf.

        This function writes a schedule to the idf. Only used for manual
        setup of schedules (combined with set_hvac_template).

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
        """Defines a part of a schedule.

        Args:
            days: string: Weekdays, Weekends, Alldays, AllOtherDays, Saturdays,
                Sundays, ...
            til_time_temp: List of tuples
                (until-time format 'hh:mm' (24h) as str),
                temperature until this time in Celsius),
                e.g. (05:00, 18)
        """
        return [days, til_time_temp]

    @staticmethod
    def add_shadings(elements: dict, idf: IDF):
        """Add shading boundaries to idf.

        Args:
            elements: dict[guid: element]
            idf: idf file object
        """
        logger.info("Add Shadings ...")
        spatials = []
        ext_spatial_elem = filter_elements(elements, ExternalSpatialElement)
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

    def add_shading_control(self, shading_type, elements,
                            idf, solar=150):
        """Add a default shading control to IDF.
        Two criteria must be met such that the window shades are set: the
        indoor air temperature must exceed a certain temperature and the solar
        radiation [W/m²] must be greater than a certain heat flow.
        Args:
            shading_type: shading type, 'Interior' or 'Exterior'
            elements: elements
            idf: idf
            solar: solar radiation on window surface [W/m²]
        """
        zones = filter_elements(elements, ThermalZone)

        for zone in zones:
            zone_name = zone.guid
            zone_openings = [sb for sb in zone.space_boundaries if
                             isinstance(sb.bound_element, Window)]
            if not zone_openings:
                continue
            fenestration_dict = {}
            for i, opening in enumerate(zone_openings):
                fenestration_dict.update({'Fenestration_Surface_' + str(
                    i+1) + '_Name': opening.guid})
            shade_control_name = "ShadeControl_" + zone_name
            opening_obj = idf.getobject(
                'FENESTRATIONSURFACE:DETAILED', zone_openings[
                    0].guid)
            if opening_obj:
                construction_name = opening_obj.Construction_Name + "_" + \
                                    shading_type
            else:
                continue
            if not idf.getobject(
                "WINDOWSHADINGCONTROL", shade_control_name):
                # temperature setpoint for indoor air temperature [°C], set to
                # 2K higher than the maximum heating profile temperature within
                # the current thermal zone.
                idf.newidfobject("WINDOWSHADINGCONTROL",
                                 Name=shade_control_name,
                                 Zone_Name=zone_name,
                                 Shading_Type=shading_type+"Shade",
                                 Construction_with_Shading_Name=construction_name,
                                 Shading_Control_Type=
                                 'OnIfHighZoneAirTempAndHighSolarOnWindow',
                                 # only close blinds if heating setpoint
                                 # temperature is already exceeded (save energy)
                                 Setpoint=max(zone.heating_profile)+2 - 273.15,
                                 Setpoint_2=solar,
                                 Multiple_Surface_Control_Type='Group',
                                 **fenestration_dict
                                 )

    @staticmethod
    def set_simulation_control(sim_settings: EnergyPlusSimSettings, idf):
        """Set simulation control parameters.

        This function sets general simulation control parameters. These can
        be easily overwritten in the exported idf.
        Args:
            sim_settings: EnergyPlusSimSettings
            idf: idf file object
        """
        logger.info("Set Simulation Control ...")
        for sim_control in idf.idfobjects["SIMULATIONCONTROL"]:
            if sim_settings.system_sizing or sim_settings.weather_file_for_sizing:
                sim_control.Do_System_Sizing_Calculation = 'Yes'
            else:
                sim_control.Do_System_Sizing_Calculation = 'No'
            if sim_settings.run_for_sizing_periods or not sim_settings.run_full_simulation:
                sim_control.Run_Simulation_for_Sizing_Periods = 'Yes'
            else:
                sim_control.Run_Simulation_for_Sizing_Periods = 'No'
            if sim_settings.run_for_weather_period:
                sim_control.Run_Simulation_for_Weather_File_Run_Periods = 'Yes'
            else:
                sim_control.Run_Simulation_for_Weather_File_Run_Periods = 'No'
            if sim_settings.set_run_period or sim_settings.run_full_simulation:
                sim_control.Run_Simulation_for_Weather_File_Run_Periods = 'Yes'
            else:
                sim_control.Run_Simulation_for_Weather_File_Run_Periods = 'No'

        if sim_settings.set_run_period:
            for run_period in idf.idfobjects["RUNPERIOD"]:
                run_period.Begin_Month = sim_settings.run_period_start_month
                run_period.Begin_Day_of_Month = (
                    sim_settings.run_period_start_day)
                run_period.End_Month = sim_settings.run_period_end_month
                run_period.End_Day_of_Month = sim_settings.run_period_end_day

        for building in idf.idfobjects['BUILDING']:
            building.Solar_Distribution = sim_settings.solar_distribution

    @staticmethod
    def set_ground_temperature(idf: IDF, t_ground: ureg.Quantity):
        """Set the ground temperature in the idf.

        Args:
            idf: idf file object
            t_ground: ground temperature as ureg.Quantity
        """
        logger.info("Set ground temperature...")

        string = '_Ground_Temperature'
        month_list = ['January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October',
                      'November', 'December']
        temp_dict = {}
        for month in month_list:
            temp_dict.update({month + string: t_ground.to(ureg.degC).m})
        idf.newidfobject("SITE:GROUNDTEMPERATURE:BUILDINGSURFACE", **temp_dict)

    @staticmethod
    def set_output_variables(idf: IDF, sim_settings: EnergyPlusSimSettings):
        """Set user defined output variables in the idf file.

        Args:
            idf: idf file object
            sim_settings: BIM2SIM simulation settings
        """
        logger.info("Set output variables ...")

        # general output settings. May be moved to general settings
        out_control = idf.idfobjects['OUTPUTCONTROL:TABLE:STYLE']
        out_control[0].Column_Separator = sim_settings.output_format
        out_control[0].Unit_Conversion = sim_settings.unit_conversion

        # remove all existing output variables with reporting frequency
        # "Timestep"
        out_var = [v for v in idf.idfobjects['OUTPUT:VARIABLE']
                   if v.Reporting_Frequency.upper() == "TIMESTEP"]
        for var in out_var:
            idf.removeidfobject(var)
        if 'output_outdoor_conditions' in sim_settings.output_keys:
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Site Outdoor Air Drybulb Temperature",
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
                Variable_Name="Site Diffuse Solar Radiation Rate per Area",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Site Direct Solar Radiation Rate per Area",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Site Ground Temperature",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Site Wind Speed",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Site Wind Direction",
                Reporting_Frequency="Hourly",
            )
        if 'output_zone_temperature' in sim_settings.output_keys:
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
                Variable_Name="Zone Air Relative Humidity",
                Reporting_Frequency="Hourly",
            )
        if 'output_internal_gains' in sim_settings.output_keys:
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Zone People Occupant Count",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Zone People Total Heating Rate",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Zone Electric Equipment Total Heating Rate",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Zone Lights Total Heating Rate",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Zone Total Internal Total Heating Rate",
                Reporting_Frequency="Hourly",
            )
        if 'output_zone' in sim_settings.output_keys:
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Zone Thermostat Heating Setpoint Temperature",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Zone Thermostat Cooling Setpoint Temperature",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Zone Ideal Loads Supply Air Total Heating "
                              "Energy",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Zone Ideal Loads Supply Air Total Cooling "
                              "Energy",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Zone Ideal Loads Outdoor Air Total Cooling Rate",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Zone Ideal Loads Outdoor Air Total Heating Rate",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Zone Ideal Loads Supply Air Total Cooling Rate",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Zone Ideal Loads Supply Air Total Heating Rate",
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
                Variable_Name="Zone Windows Total Transmitted Solar Radiation "
                              "Energy",
                Reporting_Frequency="Hourly",
            )
        if 'output_infiltration' in sim_settings.output_keys:
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
                Variable_Name="Zone Infiltration Air Change Rate",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Zone Ventilation Air Change Rate",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Zone Ventilation Standard Density Volume Flow "
                              "Rate",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Zone Ventilation Total Heat Gain Energy",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Zone Ventilation Total Heat Loss Energy",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Zone Mechanical Ventilation Air Changes per "
                              "Hour",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Zone Mechanical Ventilation Standard Density "
                              "Volume Flow Rate",
                Reporting_Frequency="Hourly",
            )


        if 'output_meters' in sim_settings.output_keys:
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
            idf.newidfobject(
                "OUTPUT:METER",
                Key_Name="DistrictHeating:HVAC",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:METER",
                Key_Name="DistrictCooling:HVAC",
                Reporting_Frequency="Hourly",
            )
        if 'output_dxf' in sim_settings.output_keys:
            idf.newidfobject("OUTPUT:SURFACES:DRAWING",
                             Report_Type="DXF")
        if sim_settings.cfd_export:
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Surface Inside Face Temperature",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name=
                "Surface Inside Face Conduction Heat Transfer Rate per Area",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name=
                "Surface Inside Face Conduction Heat Transfer Rate",
                Reporting_Frequency="Hourly",
            )
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name=
                "Surface Window Net Heat Transfer Rate",
                Reporting_Frequency="Hourly",
            )
        idf.newidfobject("OUTPUT:DIAGNOSTICS",
                         Key_1="DisplayAdvancedReportVariables",
                         Key_2="DisplayExtraWarnings")
        return idf

    @staticmethod
    def export_geom_to_idf(sim_settings: EnergyPlusSimSettings,
                           elements: dict, idf: IDF):
        """Write space boundary geometry to idf.

        This function converts the space boundary bound_shape from
        OpenCascade to idf geometry.

        Args:
            elements: dict[guid: element]
            idf: idf file object
        """
        logger.info("Export IDF geometry")
        bounds = filter_elements(elements, SpaceBoundary)
        for bound in bounds:
            idfp = IdfObject(sim_settings, bound, idf)
            if idfp.skip_bound:
                idf.popidfobject(idfp.key, -1)
                logger.warning(
                    "Boundary with the GUID %s (%s) is skipped (due to "
                    "missing boundary conditions)!",
                    idfp.name, idfp.surface_type)
                continue
        bounds_2b = filter_elements(elements, SpaceBoundary2B)
        for b_bound in bounds_2b:
            idfp = IdfObject(sim_settings, b_bound, idf)
            if idfp.skip_bound:
                logger.warning(
                    "Boundary with the GUID %s (%s) is skipped (due to "
                    "missing boundary conditions)!",
                    idfp.name, idfp.surface_type)
                continue

    @staticmethod
    def idf_validity_check(idf):
        """Perform idf validity check and simple fixes.

        This function performs a basic validity check of the resulting idf.
        It removes openings from adiabatic surfaces and very small surfaces.

        Args:
            idf: idf file object
        """
        logger.info('Start IDF Validity Checker')

        # remove erroneous fenestration surfaces which do may crash
        # EnergyPlus simulation
        fenestrations = idf.idfobjects['FENESTRATIONSURFACE:DETAILED']

        # Create a list of fenestrations to remove
        to_remove = []

        for fenestration in fenestrations:
            should_remove = False

            # Check for missing building surface reference
            if not fenestration.Building_Surface_Name:
                should_remove = True
            else:
                # Check if the referenced surface is adiabatic
                building_surface = idf.getobject(
                    'BUILDINGSURFACE:DETAILED',
                    fenestration.Building_Surface_Name
                )
                if building_surface and building_surface.Outside_Boundary_Condition == 'Adiabatic':
                    should_remove = True

            if should_remove:
                to_remove.append(fenestration)

        # Remove the collected fenestrations
        for fenestration in to_remove:
            logger.info('Removed Fenestration: %s' % fenestration.Name)
            idf.removeidfobject(fenestration)

        # Check if shading control elements contain unavailable fenestration
        fenestration_updated = idf.idfobjects['FENESTRATIONSURFACE:DETAILED']
        shading_control = idf.idfobjects['WINDOWSHADINGCONTROL']
        fenestration_guids = [fe.Name for fe in fenestration_updated]
        for shc in shading_control:
            # create a list with current fenestration guids (only available
            # fenestration)
            fenestration_guids_new = []
            skipped_fenestration = False  # flag for unavailable fenestration
            for attr_name in dir(shc):
                if ('Fenestration_Surface' in attr_name):
                    if (getattr(shc, attr_name) in
                            fenestration_guids):
                        fenestration_guids_new.append(getattr(shc, attr_name))
                    elif (getattr(shc, attr_name) not in
                          fenestration_guids) and getattr(shc, attr_name):
                        skipped_fenestration = True
            # if the shading control element containes unavailable
            # fenestration objects, the shading control must be updated to
            # prevent errors in simulation
            if fenestration_guids_new and skipped_fenestration:
                fenestration_dict = {}
                for i, guid in enumerate(fenestration_guids_new):
                    fenestration_dict.update({'Fenestration_Surface_' + str(
                        i + 1) + '_Name': guid})
                # remove previous shading control from idf and create a new one
                # removing individual attributes of the shading element
                # caused errors, so new shading control is created
                idf.removeidfobject(shc)
                idf.newidfobject("WINDOWSHADINGCONTROL", Name=shc.Name,
                                 Zone_Name=shc.Zone_Name,
                                 Shading_Type=shc.Shading_Type,
                                 Construction_with_Shading_Name=
                                 shc.Construction_with_Shading_Name,
                                 Shading_Control_Type=shc.Shading_Control_Type,
                                 Setpoint=shc.Setpoint,
                                 Setpoint_2=shc.Setpoint_2,
                                 Multiple_Surface_Control_Type=
                                 shc.Multiple_Surface_Control_Type,
                                 **fenestration_dict)
                logger.info('Updated Shading Control due to unavailable '
                            'fenestration:  %s' % shc.Name)

        # check for small building surfaces and remove them
        sfs = idf.getsurfaces()
        small_area_obj = [s for s in sfs
                          if PyOCCTools.get_shape_area(
                PyOCCTools.make_faces_from_pnts(s.coords)) < 1e-2]

        for obj in small_area_obj:
            logger.info('Removed small area: %s' % obj.Name)
            idf.removeidfobject(obj)

        # check for small shading surfaces and remove them
        shadings = idf.getshadingsurfaces()
        small_area_obj = [s for s in shadings if PyOCCTools.get_shape_area(
            PyOCCTools.make_faces_from_pnts(s.coords)) < 1e-2]

        for obj in small_area_obj:
            logger.info('Removed small area: %s' % obj.Name)
            idf.removeidfobject(obj)

        # Check for building surfaces holding default window materials
        bsd = idf.idfobjects['BUILDINGSURFACE:DETAILED']
        for sf in bsd:
            if sf.Construction_Name == 'BS Exterior Window':
                logger.info(
                    'Surface due to invalid material: %s' % sf.Name)
                idf.removeidfobject(sf)
        logger.info('IDF Validity Checker done')


class IdfObject:
    """Create idf elements for surfaces.

    This class holds all data required for the idf setup of
    BUILDINGSURFACE:DETAILED and FENESTRATIONSURFACE:DETAILED.
    This includes further methods for processing the preprocessed information
    from the BIM2SIM process for the use in idf (e.g., surface type mapping).
    """

    def __init__(self, sim_settings, inst_obj, idf):
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
        self.add_window_shade = False
        if not hasattr(inst_obj.bound_thermal_zone, 'guid'):
            self.skip_bound = True
            return
        self.zone_name = inst_obj.bound_thermal_zone.guid
        if inst_obj.parent_bound:
            self.key = "FENESTRATIONSURFACE:DETAILED"
            if sim_settings.add_window_shading == 'Interior':
                self.add_window_shade = 'Interior'
            elif sim_settings.add_window_shading == 'Exterior':
                self.add_window_shade = 'Exterior'
        else:
            self.key = "BUILDINGSURFACE:DETAILED"
        if inst_obj.parent_bound:
            self.building_surface_name = inst_obj.parent_bound.guid
        self.map_surface_types(inst_obj)
        self.map_boundary_conditions(inst_obj)
        self.set_preprocessed_construction_name()
        # only set a construction name if this construction is available
        if not self.construction_name \
                or not (idf.getobject("CONSTRUCTION", self.construction_name)
                        or idf.getobject("CONSTRUCTION:AIRBOUNDARY",
                                         self.construction_name)):
            self.set_construction_name()
        obj = self.set_idfobject_attributes(idf)
        if obj is not None:
            self.set_idfobject_coordinates(obj, idf, inst_obj)
        else:
            pass

    def set_construction_name(self):
        """Set default construction names.

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
        """Set preprocessed constructions.

        This function sets constructions of idf surfaces to preprocessed
        constructions. Virtual space boundaries are set to be an air wall
        (not defined in preprocessing).
        """
        # set air wall for virtual bounds
        if not self.physical:
            if self.out_bound_cond == "Surface":
                self.construction_name = "Air Wall"
        else:
            rel_elem = self.this_bound.bound_element
            if not rel_elem:
                return
            if any([isinstance(rel_elem, window) for window in
                    all_subclasses(Window, include_self=True)]):
                self.construction_name = 'Window_WM_' + \
                                         rel_elem.layerset.layers[
                                             0].material.name \
                                         + '_' + str(
                    rel_elem.layerset.layers[0].thickness.to(ureg.metre).m)
            else:
                self.construction_name = (rel_elem.key.replace(
                    "Disaggregated", "") + '_' + str(len(
                    rel_elem.layerset.layers)) + '_' + '_'.join(
                    [str(l.thickness.to(ureg.metre).m) for l in
                     rel_elem.layerset.layers]))

    def set_idfobject_coordinates(self, obj, idf: IDF,
                                  inst_obj: Union[SpaceBoundary,
                                                  SpaceBoundary2B]):
        """Export surface coordinates.

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
                self.process_circular_shapes(idf, obj_coords, obj, inst_obj)
            else:
                self.process_other_shapes(inst_obj, obj)
        except Exception as ex:
            logger.warning(f"Unexpected {ex=}. Setting coordinates for "
                           f"{inst_obj.guid} failed. This element is not "
                           f"exported."
                           f"{type(ex)=}")

    def set_idfobject_attributes(self, idf: IDF):
        """Writes precomputed surface attributes to idf.

        Args:
            idf: the idf file
        """
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

    def map_surface_types(self, inst_obj: Union[SpaceBoundary,
                                                SpaceBoundary2B]):
        """Map surface types.

        This function maps the attributes of a SpaceBoundary instance to idf
        surface type.

        Args:
            inst_obj: SpaceBoundary instance
        """
        # TODO use bim2sim elements mapping instead of ifc.is_a()
        # TODO update to new disaggregations
        elem = inst_obj.bound_element
        surface_type = None
        if elem is not None:
            if any([isinstance(elem, wall) for wall in all_subclasses(Wall,
                                                                      include_self=True)]):
                surface_type = 'Wall'
            elif any([isinstance(elem, door) for door in all_subclasses(Door,
                                                                        include_self=True)]):
                surface_type = "Door"
            elif any([isinstance(elem, window) for window in all_subclasses(
                    Window, include_self=True)]):
                surface_type = "Window"
            elif any([isinstance(elem, roof) for roof in all_subclasses(Roof,
                                                                        include_self=True)]):
                surface_type = "Roof"
            elif any([isinstance(elem, slab) for slab in all_subclasses(Slab,
                                                                        include_self=True)]):
                if any([isinstance(elem, floor) for floor in all_subclasses(
                        GroundFloor, include_self=True)]):
                    surface_type = "Floor"
                elif any([isinstance(elem, floor) for floor in all_subclasses(
                        InnerFloor, include_self=True)]):
                    if inst_obj.top_bottom == BoundaryOrientation.bottom:
                        surface_type = "Floor"
                    elif inst_obj.top_bottom == BoundaryOrientation.top:
                        surface_type = "Ceiling"
                    elif inst_obj.top_bottom == BoundaryOrientation.vertical:
                        surface_type = "Wall"
                        logger.warning(f"InnerFloor with vertical orientation "
                                       f"found, exported as wall, "
                                       f"GUID: {inst_obj.guid}.")
                    else:
                        logger.warning(f"InnerFloor was not correctly matched "
                                       f"to surface type for GUID: "
                                       f"{inst_obj.guid}.")
                        surface_type = "Floor"
            # elif elem.ifc is not None:
            #     if elem.ifc.is_a("IfcBeam"):
            #         if not PyOCCTools.compare_direction_of_normals(
            #                 inst_obj.bound_normal, gp_XYZ(0, 0, 1)):
            #             surface_type = 'Wall'
            #         else:
            #             surface_type = 'Ceiling'
            #     elif elem.ifc.is_a('IfcColumn'):
            #         surface_type = 'Wall'
            elif inst_obj.top_bottom == BoundaryOrientation.bottom:
                surface_type = "Floor"
            elif inst_obj.top_bottom == BoundaryOrientation.top:
                surface_type = "Ceiling"
                if inst_obj.related_bound is None or inst_obj.is_external:
                    surface_type = "Roof"
            elif inst_obj.top_bottom == BoundaryOrientation.vertical:
                surface_type = "Wall"
            else:
                if not PyOCCTools.compare_direction_of_normals(
                        inst_obj.bound_normal, gp_XYZ(0, 0, 1)):
                    surface_type = 'Wall'
                elif inst_obj.top_bottom == BoundaryOrientation.bottom:
                    surface_type = "Floor"
                elif inst_obj.top_bottom == BoundaryOrientation.top:
                    surface_type = "Ceiling"
                    if inst_obj.related_bound is None or inst_obj.is_external:
                        surface_type = "Roof"
                else:
                    logger.warning(f"No surface type matched for {inst_obj}!")
        elif not inst_obj.physical:
            if not PyOCCTools.compare_direction_of_normals(
                    inst_obj.bound_normal, gp_XYZ(0, 0, 1)):
                surface_type = 'Wall'
            else:
                if inst_obj.top_bottom == BoundaryOrientation.bottom:
                    surface_type = "Floor"
                elif inst_obj.top_bottom == BoundaryOrientation.top:
                    surface_type = "Ceiling"
        else:
            logger.warning(f"No surface type matched for {inst_obj}!")

        self.surface_type = surface_type

    def map_boundary_conditions(self, inst_obj: Union[SpaceBoundary,
                                                      SpaceBoundary2B]):
        """Map boundary conditions.

        This function maps the boundary conditions of a SpaceBoundary instance
        to the idf space boundary conditions.

        Args:
            inst_obj: SpaceBoundary instance
        """
        if inst_obj.level_description == '2b' \
                or inst_obj.related_adb_bound is not None:
            self.out_bound_cond = 'Adiabatic'
            self.sun_exposed = 'NoSun'
            self.wind_exposed = 'NoWind'
        elif (hasattr(inst_obj.ifc, 'CorrespondingBoundary')
              and ((inst_obj.ifc.CorrespondingBoundary is not None) and (
                        inst_obj.ifc.CorrespondingBoundary.InternalOrExternalBoundary.upper()
                        == 'EXTERNAL_EARTH'))
              and (self.key == "BUILDINGSURFACE:DETAILED")
              and not (len(inst_obj.opening_bounds) > 0)):
            self.out_bound_cond = "Ground"
            self.sun_exposed = 'NoSun'
            self.wind_exposed = 'NoWind'
        elif inst_obj.is_external and inst_obj.physical \
                and not self.surface_type == 'Floor':
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
            'IfcExternalSpatialElement'):
            self.out_bound_cond = 'Surface'
            self.out_bound_cond_obj = inst_obj.related_bound.guid
            self.sun_exposed = 'NoSun'
            self.wind_exposed = 'NoWind'
        elif self.key == "FENESTRATIONSURFACE:DETAILED":
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
    def get_circular_shape(obj_pnts: list[tuple]) -> bool:
        """Check if a shape is circular.

        This function checks if a SpaceBoundary has a circular shape.

        Args:
            obj_pnts: SpaceBoundary vertices (list of coordinate tuples)
        Returns:
            True if shape is circular
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

    @staticmethod
    def process_circular_shapes(idf: IDF, obj_coords: list[tuple], obj,
                                inst_obj: Union[SpaceBoundary, SpaceBoundary2B]
                                ):
        """Simplify circular space boundaries.

        This function processes circular boundary shapes. It converts circular
        shapes to triangular shapes.

        Args:
            idf: idf file object
            obj_coords: coordinates of an idf object
            obj: idf object
            inst_obj: SpaceBoundary instance
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
    def process_other_shapes(inst_obj: Union[SpaceBoundary, SpaceBoundary2B],
                             obj):
        """Simplify non-circular shapes.

        This function processes non-circular shapes with too many vertices
        by approximation of the shape utilizing the UV-Bounds from OCC
        (more than 120 vertices for BUILDINGSURFACE:DETAILED
        and more than 4 vertices for FENESTRATIONSURFACE:DETAILED)

        Args:
            inst_obj: SpaceBoundary Instance
            obj: idf object
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
