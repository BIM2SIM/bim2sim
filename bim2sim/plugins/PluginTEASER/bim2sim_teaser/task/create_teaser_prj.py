from teaser.data.dataclass import DataClass
from teaser.data.utilities import ConstructionData
from teaser.logic.buildingobjects.building import Building
from teaser.logic.buildingobjects.buildingphysics.outerwall import OuterWall
from teaser.logic.buildingobjects.buildingphysics.window import Window
from teaser.project import Project

from bim2sim.plugins.PluginTEASER.bim2sim_teaser import export, models
from bim2sim.elements.base_elements import ProductBased
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements


class CreateTEASER(ITask):
    """Creates the TEASER project, run() method holds detailed information."""
    reads = ('libraries', 'elements', 'weather_file_modelica')
    touches = ('teaser_prj', 'bldg_names', 'orig_heat_loads',
               'orig_cool_loads')

    def run(self, libraries, elements, weather_file_modelica):
        """Creates the TEASER project based on `bim2sim` elements.

        The previous created and enriched `bim2sim` elements are used to
        parametrize a TEASER project instance. Therefore we map each `bim2sim`
        element to it's corresponding TEASER element.

        Args:
            libraries: previous loaded libraries. In the case this is the
                TEASER library
            elements: dict[guid: element] with `bim2sim` elements
            weather_file_modelica: path to weather file

        Returns:
            teaser_prj: teaser project instance
            bldg_names: list of names of all buildings in project, needed to
                maintain the information for later tasks
            orig_heat_loads: dict[tz.name: heat_load] with original heat loads
                as they get overwritten
            orig_cool_loads: dict[tz.name: cool_load] with original cool loads
                as they get overwritten
            tz_mapping: dict that holds mapping between thermal zones in TEASER
                and thermal zones in IFC for later post-processing
        """
        self.logger.info("Start creating the TEASER project from the derived "
                         "building")

        export.TEASERExportInstance.init_factory(libraries)

        teaser_prj = self._create_project()
        bldg_elements = filter_elements(elements, 'Building')
        exported_buildings = []

        # Create the building and adds thermal zones and building elements
        #  This is performed recursively through starting with the Building
        #  instance which holds the zones which again hold the single elements
        for bldg in bldg_elements:
            exported_buildings.append(models.Building(bldg, parent=teaser_prj))

        (r_elements, e_elements) = (export.TEASERExportInstance.requested_elements,
                                      export.TEASERExportInstance.export_elements)

        # Perform decisions for requested but not existing attributes
        yield from ProductBased.get_pending_attribute_decisions(r_elements)

        # All parameters are checked against the specified check function and
        #  exported with the correct unit
        for instance in e_elements:
            instance.collect_params()

        self.prepare_export(exported_buildings)
        teaser_prj.calc_all_buildings()
        orig_heat_loads, orig_cool_loads =\
            self.overwrite_heatloads(exported_buildings)
        teaser_prj.weather_file_path = weather_file_modelica

        bldg_names = []
        for bldg in exported_buildings:
            bldg_names.append(bldg.name)

        return teaser_prj, bldg_names, orig_heat_loads, orig_cool_loads

    def _create_project(self):
        """Creates a project in TEASER by a given `bim2sim` instance
        Parent: None"""
        prj = Project()
        prj.name = self.prj_name
        # iwu_heavy is not used later and just a dummy as material information
        # are generated in bim2sim already and parsed into TEASER
        prj.data = DataClass(construction_data=ConstructionData.iwu_heavy)
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
            ow_min.name = 'min_outer_wall'
            ow_min.area = 0.01
            ow_min.load_type_element(
                year=2000,
                construction='iwu_heavy',
            )
            ow_min.tilt = 90
            ow_min.orientation = 0
        if len(tz.windows) == 0:
            win_min = Window(parent=tz)
            win_min.name = 'min_window'
            win_min.area = 0.01
            win_min.load_type_element(
                year=2000,
                construction='EnEv',
            )
            win_min.orientation = 0

    @staticmethod
    def rotate_teaser_building(bldg: Building, true_north: float):
        """rotates entire building and its components for a given true north
        value, only necessary if ifc file true north information its not
        given, but want to rotate before exporting"""
        bldg.rotate_building(true_north)
