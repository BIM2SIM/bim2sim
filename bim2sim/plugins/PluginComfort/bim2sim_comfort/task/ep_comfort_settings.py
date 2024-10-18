"""Export EnergyPlus Comfort Settings.

This module includes all functions for exporting Comfort Settings as EnergyPlus
Input files (idf). Geometric preprocessing (includes EnergyPlus
specific space boundary enrichment) and EnergyPlus Input File export must be
executed before this module.
"""
import json
import logging
import os
from pathlib import Path

import bim2sim
from bim2sim.elements.bps_elements import ThermalZone
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.task import \
    IdfPostprocessing
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
from geomeppy import IDF

logger = logging.getLogger(__name__)


class ComfortSettings(ITask):
    """
    Create Comfort Settings for an EnergyPlus Input file.

    Task to create Comfort Settings for an EnergyPlus Input file.
    """

    reads = ('elements', 'idf', 'sim_results_path')
    touches = ('idf',)

    def __init__(self, playground):
        super().__init__(playground)
        self.idf = None

    def run(self, elements: dict, idf: IDF, sim_results_path: Path):
        """Execute all methods to export comfort parameters to idf.

        Execute all methods to export comfort parameters to idf.
        Args:
            elements: bim2sim elements
            idf: eppy idf
            sim_results_path (Path): path to simulation results.
        """
        logger.info("IDF extension in PluginComfort started ...")
        self.add_comfort_to_people_enrichment(
            idf, elements, self.playground.sim_settings.use_dynamic_clothing)
        self.add_comfort_variables(idf)
        # self.remove_empty_zones(idf)
        self.remove_duplicate_names(idf)
        self.remove_empty_zones(idf)
        zone_dict_path = sim_results_path / self.prj_name / 'zone_dict.json'
        if not zone_dict_path.exists():
            IdfPostprocessing.write_zone_names(idf, elements, sim_results_path /
                                               self.prj_name)
        idf.save(idf.idfname)

        return idf,

    @staticmethod
    def define_comfort_usage_dict():
        """Define a new set of comfort parameters per use condition.

        This method defines hardcoded schedules for clothing, air velocity
        and work efficiency. Check values for applicability of these
        parameters. The resulting json file is written to
        bim2sim_comfort/assets/comfort_usage.json.

        """
        usage_path = Path(os.path.dirname(bim2sim.assets.__file__) +
                          '/enrichment/usage/UseConditions.json')
        with open(usage_path, 'r+', encoding='utf-8') as file:
            usage_dict = json.load(file)

        comfort_usage_dict = {
            'Default': {
                'Clothing Insulation Schedule':
                # ASHRAE 55, Trousers, long-sleeve shirt, suit jacket,
                # vest, T-Shirt
                    [1.14] * 24,
                'Air Velocity Schedule':
                    [0.0] * 24,
                'Work Efficiency Schedule':
                    [0.00] * 24,
            },
            'Single office': {
                'Clothing Insulation Schedule':
                # ASHRAE 55, Trousers, long-sleeve Shirt + suit jacket
                    [0.96] * 24,
                'Air Velocity Schedule':
                    [0.1] * 24,
                'Work Efficiency Schedule':
                    [0.1] * 24,
            },
            'Living': {
                'Clothing Insulation Schedule':
                # ASHRAE 55, Sweat pants, long-sleeve sweatshirt
                    [0.74] * 24,
                'Air Velocity Schedule':
                    [0.1] * 24,
                'Work Efficiency Schedule':
                    [0.05] * 24,
            },
            'Bed room': {
                'Clothing Insulation Schedule':
                # ASHRAE 55, Sleepwear
                    [0.96] * 24,
                'Air Velocity Schedule':
                    [0.1] * 24,
                'Work Efficiency Schedule':
                    [0.0] * 24,
            },
            'WC and sanitary rooms in non-residential buildings': {
                'Clothing Insulation Schedule':
                # ASHRAE 55, Trousers, short-sleeve shirt
                    [0.57] * 24,
                'Air Velocity Schedule':
                    [0.1] * 24,
                'Work Efficiency Schedule':
                    [0.05] * 24,
            },
            'Kitchen in non-residential buildings': {
                'Clothing Insulation Schedule':
                # ASHRAE 55, Knee-length skirt, long-sleeve shirt, full slip
                    [0.67] * 24,
                'Air Velocity Schedule':
                    [0.2] * 24,
                'Work Efficiency Schedule':
                    [0.1] * 24,
            },
            'Traffic area': {
                'Clothing Insulation Schedule':
                # ASHRAE 55, Trousers, long-sleeve shirt + sweater + T-Shirt
                    [1.01] * 24,
                'Air Velocity Schedule':
                    [0.2] * 24,
                'Work Efficiency Schedule':
                    [0.1] * 24,
            }
        }
        if not os.path.exists(Path(__file__).parent.parent / 'assets/'):
            os.mkdir(Path(__file__).parent.parent / 'assets/')
        with open(Path(__file__).parent.parent / 'assets/comfort_usage.json', 'w'
                  ) as cu:
            json.dump(comfort_usage_dict, cu, indent=4)
        cu.close()

    def add_comfort_to_people_enrichment(self, idf: IDF, elements,
                                         use_dynamic_clothing=False):
        """Add comfort parameters to people objects in CreateIdf.

        This method adds comfort parameters to people objects to the
        input eppy idf.
        Args:
            idf: eppy idf
            elements: bim2sim elements
            use_dynamic_clothing: True if dynamic clothing (ASHRAE 55)
                should be activated

        """
        spaces = filter_elements(elements, ThermalZone)
        people_objs = idf.idfobjects['PEOPLE']

        # load comfort schedules for individual usage definitions
        with open(Path(__file__).parent.parent / 'assets/comfort_usage.json'
                  ) as cu:
            plugin_comfort_dict = json.load(cu)
        # define default schedules
        self.set_day_week_year_limit_schedule(
            idf, plugin_comfort_dict['Default']['Clothing Insulation Schedule'],
            'Default_Clothing_Insulation_Schedule')
        self.set_day_week_year_limit_schedule(
            idf, plugin_comfort_dict['Default']['Air Velocity Schedule'],
            'Default_Air_Velocity_Schedule')
        self.set_day_week_year_limit_schedule(
            idf, plugin_comfort_dict['Default']['Work Efficiency Schedule'],
            'Default_Work_Efficiency_Schedule')

        for space in spaces:
            # get people_obj that has been defined in CreateIdf (internal loads)
            people_obj = [p for p in people_objs if p.Name == space.guid][0]
            if space.clothing_persons:
                space_clothing = space.clothing_persons
                if space.surround_clo_persons:
                    space_clothing += space.surround_clo_persons
                clo_sched_name = ('Clothing_Insulation_Schedule_' +
                                  space.usage.replace(',', ''))
                if idf.getobject("SCHEDULE:YEAR", name=clo_sched_name) is None:
                    clothing = [space_clothing]*24
                    self.set_day_week_year_limit_schedule(
                        idf, clothing,
                        clo_sched_name)
            else:
                clo_sched_name = 'Default_Clothing_Insulation_Schedule'

            if space.usage in plugin_comfort_dict.keys():
                air_sched_name = ('Air_Velocity_Schedule_' +
                                  space.usage.replace(',', ''))
                work_eff_sched_name = ('Work_Efficiency_Schedule_' +
                                       space.usage.replace(',', ''))
                if idf.getobject("SCHEDULE:YEAR", name=air_sched_name) is None:
                    this_usage_dict = plugin_comfort_dict[space.usage]
                    self.set_day_week_year_limit_schedule(
                        idf, this_usage_dict['Air Velocity Schedule'],
                        air_sched_name)
                    self.set_day_week_year_limit_schedule(
                        idf, this_usage_dict['Work Efficiency Schedule'],
                        work_eff_sched_name)
            else:
                air_sched_name = 'Default_Air_Velocity_Schedule'
                work_eff_sched_name = 'Default_Work_Efficiency_Schedule'
            if use_dynamic_clothing:
                people_obj.Clothing_Insulation_Calculation_Method = \
                    'DynamicClothingModelASHRAE55'
                people_obj.\
                    Clothing_Insulation_Calculation_Method_Schedule_Name \
                    = 'DynamicClothingModelASHRAE55'
            else:
                people_obj.Clothing_Insulation_Schedule_Name = clo_sched_name
            people_obj.Air_Velocity_Schedule_Name = air_sched_name
            people_obj.Work_Efficiency_Schedule_Name = work_eff_sched_name
            people_obj.Thermal_Comfort_Model_1_Type = 'Fanger'
            people_obj.Thermal_Comfort_Model_2_Type = 'Pierce'
            people_obj.Thermal_Comfort_Model_3_Type = 'AdaptiveASH55'
            people_obj.Thermal_Comfort_Model_4_Type = 'AdaptiveCEN15251'

    def add_comfort_to_people_manual(self, idf: IDF, elements,
                                     use_dynamic_clothing=False):
        """Manually add comfort parameters to people objects in CreateIdf.

        This method manually adds comfort parameters to people objects to the
        input eppy idf.
        Args:
            idf: eppy idf
            elements: bim2sim elements
            use_dynamic_clothing: True if dynamic clothing (ASHRAE 55)
                should be activated
        """
        spaces = filter_elements(elements, ThermalZone)
        people_objs = idf.idfobjects['PEOPLE']

        # load comfort schedules for individual usage definitions
        with open(Path(__file__).parent.parent / 'assets/comfort_usage.json'
                  ) as cu:
            comfort_dict = json.load(cu)
        # define default schedules
        self.set_day_week_year_limit_schedule(
            idf, comfort_dict['Default']['Clothing Insulation Schedule'],
            'Default_Clothing_Insulation_Schedule')
        self.set_day_week_year_limit_schedule(
            idf, comfort_dict['Default']['Air Velocity Schedule'],
            'Default_Air_Velocity_Schedule')
        self.set_day_week_year_limit_schedule(
            idf, comfort_dict['Default']['Work Efficiency Schedule'],
            'Default_Work_Efficiency_Schedule')

        for space in spaces:
            # get people_obj that has been defined in CreateIdf(internal loads)
            people_obj = [p for p in people_objs if p.Name == space.guid][0]
            if space.usage in comfort_dict.keys():
                clo_sched_name = ('Clothing_Insulation_Schedule_' +
                                  space.usage.replace(',', ''))
                air_sched_name = ('Air_Velocity_Schedule_' +
                                  space.usage.replace(',', ''))
                work_eff_sched_name = ('Work_Efficiency_Schedule_' +
                                       space.usage.replace(',', ''))
                if (idf.getobject("SCHEDULE:YEAR", name=clo_sched_name) is
                        None):
                    this_usage_dict = comfort_dict[space.usage]
                    self.set_day_week_year_limit_schedule(
                        idf, this_usage_dict['Clothing Insulation Schedule'],
                        clo_sched_name)
                    self.set_day_week_year_limit_schedule(
                        idf, this_usage_dict['Air Velocity Schedule'],
                        air_sched_name)
                    self.set_day_week_year_limit_schedule(
                        idf, this_usage_dict['Work Efficiency Schedule'],
                        work_eff_sched_name)
            else:
                clo_sched_name = 'Default_Clothing_Insulation_Schedule'
                air_sched_name = 'Default_Air_Velocity_Schedule'
                work_eff_sched_name = 'Default_Work_Efficiency_Schedule'
            if use_dynamic_clothing:
                people_obj.Clothing_Insulation_Calculation_Method = \
                    'DynamicClothingModelASHRAE55'
                people_obj. \
                    Clothing_Insulation_Calculation_Method_Schedule_Name \
                    = 'DynamicClothingModelASHRAE55'
            else:
                people_obj.Clothing_Insulation_Schedule_Name = clo_sched_name
            people_obj.Air_Velocity_Schedule_Name = air_sched_name
            people_obj.Work_Efficiency_Schedule_Name = work_eff_sched_name
            people_obj.Thermal_Comfort_Model_1_Type = 'Fanger'
            people_obj.Thermal_Comfort_Model_2_Type = 'Pierce'
            people_obj.Thermal_Comfort_Model_3_Type = 'AdaptiveASH55'

    @staticmethod
    def add_comfort_variables(idf: IDF):
        """Add output variables for comfort measures to the input IDF file.

        Args:
            idf: eppy idf

        """
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Thermal Comfort Fanger Model PMV",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Thermal Comfort Fanger Model PPD",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Thermal Comfort Pierce Model Effective "
                          "Temperature PMV",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Thermal Comfort Pierce Model Discomfort Index",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Thermal Comfort ASHRAE 55 Adaptive Model 80% "
                          "Acceptability Status",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Thermal Comfort ASHRAE 55 Adaptive Model 90% "
                          "Acceptability Status",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Thermal Comfort ASHRAE 55 Adaptive Model "
                          "Running Average Outdoor Air Temperature",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Thermal Comfort CEN 15251 Adaptive Model "
                          "Category I Status",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Thermal Comfort CEN 15251 Adaptive Model "
                          "Category II Status",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Thermal Comfort CEN 15251 Adaptive Model "
                          "Category III Status",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Thermal Comfort CEN 15251 Adaptive Model "
                          "Running Average Outdoor Air Temperature",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Thermal Comfort CEN 15251 Adaptive Model "
                          "Temperature",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Thermal Comfort Clothing Value",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone People Occupant Count",
            Reporting_Frequency="Hourly",
        )

        if not "Zone Mean Air Temperature" in \
               [v.Variable_Name for v in idf.idfobjects['OUTPUT:VARIABLE']]:
            idf.newidfobject(
                "OUTPUT:VARIABLE",
                Variable_Name="Zone Mean Air Temperature",
                Reporting_Frequency="Hourly",
            )

    @staticmethod
    def set_day_week_year_limit_schedule(idf: IDF, schedule: list[float],
                                         schedule_name: str,
                                         limits_name: str = 'Any Number'):
        """Set day, week and year schedule (hourly).

        This function sets an hourly day, week and year schedule.

        Args:
            idf: idf file object
            schedule: list of float values for the schedule (e.g.,
                temperatures, loads)
            schedule_name: str
            limits_name: str, defaults set to 'Any Number'
        """
        if idf.getobject("SCHEDULETYPELIMITS", limits_name) is None:
            idf.newidfobject("SCHEDULETYPELIMITS", Name=limits_name)
        if idf.getobject("SCHEDULE:DAY:HOURLY", name=schedule_name) is None:
            hours = {}
            for i, l in enumerate(schedule[:24]):
                hours.update({'Hour_' + str(i + 1): schedule[i]})
            idf.newidfobject("SCHEDULE:DAY:HOURLY", Name=schedule_name,
                             Schedule_Type_Limits_Name=limits_name, **hours)
        if idf.getobject("SCHEDULE:WEEK:COMPACT",
                         name=schedule_name) is None:
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

    @staticmethod
    def remove_empty_zones(idf: IDF):
        """Remove empty zones and zonegroups from idf.

        Depending on the quality of the input ifc and their space
        boundaries, empty thermal zones may be created (or be left after
        corrections) in the resulting idf. This raises errors in thermal
        comfort simulation. This method evaluates if a thermal zone has
        surfaces in idf, and removes the zone from zonelists and zonegroups.

        Args:
            idf: eppy idf

        """
        zones = idf.idfobjects['ZONE']
        surfaces = idf.getsurfaces()
        zonelists = idf.idfobjects['ZONELIST']
        zonegroups = idf.idfobjects['ZONEGROUP']
        removed_zones = 0
        for z in zones:
            zone_has_surface = False
            for s in surfaces:
                if z.Name.upper() == s.Zone_Name.upper():
                    zone_has_surface = True
                    break
            if not zone_has_surface:
                idf.removeidfobject(z)
                removed_zones +=1
        if removed_zones > 0:
            while zonelists:
                for l in zonelists:
                    idf.removeidfobject(l)
            while zonegroups:
                for g in zonegroups:
                    idf.removeidfobject(g)
        logger.warning('Removed %d empty zones from IDF', removed_zones)

    @staticmethod
    def remove_duplicate_names(idf: IDF):
        """Test for duplicate idfobject names and remove objects.

        EnergyPlus requires unique naming for IdfObjects, otherwise,
        the simulation crashes. To increase the robustness of the
        implementation, the idf is tested for duplicate names and duplicate
        objects are removed. This decreases the accuracy of the model,
        so the logging should be evaluated carefully for duplicate objects.
        With a suitable IFC input model quality, no duplicate names should
        be found.

        Args:
            idf: eppy idf

        """
        object_keys = [o for o in idf.idfobjects]
        for key in object_keys:
            names = []
            objects = idf.idfobjects[key]
            for o in objects:
                if hasattr(o, 'Name'):
                    if o.Name.upper() in names:
                        logger.warning('DUPLICATE OBJECT: %s %s', key, o.Name)
                        idf.removeidfobject(o)
                    else:
                        names.append(o.Name.upper())
                elif hasattr(o, 'Zone_Name'):
                    if o.Zone_Name.upper() in names:
                        logger.warning('DUPLICATE OBJECT: %s %s', key,
                                       o.Zone_Name)
                        idf.removeidfobject(o)
                    else:
                        names.append(o.Zone_Name.upper())
                else:
                    continue
