import json
from pathlib import Path

from bim2sim.elements.aggregation.bps_aggregations import AggregatedThermalZone
from bim2sim.plugins.PluginTEASER.bim2sim_teaser import export, models
from teaser.logic.buildingobjects.building import Building
from teaser.logic.buildingobjects.buildingphysics.door import Door
from teaser.logic.buildingobjects.buildingphysics.floor import Floor
from teaser.logic.buildingobjects.buildingphysics.groundfloor import GroundFloor
from teaser.logic.buildingobjects.buildingphysics.innerwall import InnerWall
from teaser.logic.buildingobjects.buildingphysics.outerwall import OuterWall
from teaser.logic.buildingobjects.buildingphysics.rooftop import Rooftop
from teaser.logic.buildingobjects.buildingphysics.window import Window
from teaser.project import Project

from bim2sim.elements.base_elements import ProductBased
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements


class CreateTEASER(ITask):
    """Creates a TEASER project by using the found information from IFC"""
    reads = ('libraries', 'elements', 'weather_file')
    touches = ('teaser_prj', 'bldg_names', 'orig_heat_loads',
               'orig_cool_loads')

    def run(self, libraries, elements, weather_file):
        self.logger.info("Start creating the TEASER project from the derived "
                         "building")

        export.TEASERExportInstance.init_factory(libraries)

        teaser_prj = self._create_project()
        bldg_elements = filter_elements(elements, 'Building')
        exported_buildings = []
        for bldg in bldg_elements:
            exported_buildings.append(models.Building(bldg, parent=teaser_prj))

        (r_elements, e_elements) = (export.TEASERExportInstance.requested_elements,
                                      export.TEASERExportInstance.export_elements)

        yield from ProductBased.get_pending_attribute_decisions(r_elements)

        for instance in e_elements:
            instance.collect_params()
        self.prepare_export(exported_buildings)
        orig_heat_loads, orig_cool_loads =\
            self.overwrite_heatloads(exported_buildings)
        teaser_prj.weather_file_path = weather_file

        bldg_names = []
        for bldg in exported_buildings:
            bldg_names.append(bldg.name)

        return teaser_prj, bldg_names, orig_heat_loads, orig_cool_loads

    def _create_project(self):
        """Creates a project in TEASER by a given BIM2SIM instance
        Parent: None"""
        prj = Project(load_data=True)
        prj.name = self.prj_name
        prj.data.load_uc_binding()
        return prj

    @classmethod
    def prepare_export(cls, exported_buildings:list):
        """Export preparations for all thermal zones.

        The preparation includes running the calc_building_parameter function
        of TEASER for all buildings.
        Args:
            exported_buildings: list of all buildings that will be exported
        """

        for bldg in exported_buildings:
            for tz in bldg.thermal_zones:
                cls.min_admissible_elements(tz, bldg)
                t_inside_profile_max = max(tz.use_conditions.heating_profile)
                tz.t_inside = t_inside_profile_max
            bldg.calc_building_parameter()

    @staticmethod
    def overwrite_heatloads(exported_buildings:list):
        """Overwrites the original heating and cooling loads for robustness.

        The original loads are saved and returned.
        """
        orig_heat_loads = {}
        orig_cool_loads = {}
        for bldg in exported_buildings:
            bldg.calc_building_parameter()
            for tz in bldg.thermal_zones:
                orig_heat_loads[tz.name] = tz.model_attr.heat_load
                orig_cool_loads[tz.name] = tz.model_attr.cool_load
                # hardcode to prevent too low heat/cooling loads
                tz.model_attr.heat_load = 100000
                tz.model_attr.cool_load = -100000
        return orig_heat_loads, orig_cool_loads

    @staticmethod
    def min_admissible_elements(tz, bldg):
        # WORKAROUND: Teaser doesn't allow thermal zones without
        # outer elements or without windows, causes singularity problem
        if len(tz.outer_walls + tz.rooftops) == 0:
            ow_min = OuterWall(parent=tz)
            ow_min.area = 0.01
            ow_min.load_type_element(
                year=bldg.year_of_construction,
                construction='heavy',
            )
            ow_min.tilt = 90
            ow_min.orientation = 0
        if len(tz.windows) == 0:
            ow_min = Window(parent=tz)
            ow_min.area = 0.01
            ow_min.load_type_element(
                year=bldg.year_of_construction,
                construction='EnEv',
            )
            ow_min.orientation = 0

    @staticmethod
    def rotate_teaser_building(bldg: Building, true_north: float):
        """rotates entire building and its components for a given true north
        value, only necessary if ifc file true north information its not
        given, but want to rotate before exporting"""
        bldg.rotate_building(true_north)
