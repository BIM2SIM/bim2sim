from bim2sim_teaser import export, models
from teaser.logic.buildingobjects.building import Building
from teaser.logic.buildingobjects.buildingphysics.door import Door
from teaser.logic.buildingobjects.buildingphysics.floor import Floor
from teaser.logic.buildingobjects.buildingphysics.groundfloor import GroundFloor
from teaser.logic.buildingobjects.buildingphysics.innerwall import InnerWall
from teaser.logic.buildingobjects.buildingphysics.outerwall import OuterWall
from teaser.logic.buildingobjects.buildingphysics.rooftop import Rooftop
from teaser.logic.buildingobjects.buildingphysics.window import Window
from teaser.project import Project

from bim2sim.kernel.element import ProductBased
from bim2sim.task.base import ITask
from bim2sim.utilities.common_functions import filter_instances


class ExportTEASER(ITask):
    """Exports a Modelica model with TEASER by using the found information
    from IFC"""
    reads = ('libraries', 'ifc', 'instances', 'weather_file')
    touches = ('bldg_names',)

    instance_switcher = {'OuterWall': OuterWall,
                         'InnerWall': InnerWall,
                         'Floor': Floor,
                         'Window': Window,
                         'GroundFloor': GroundFloor,
                         'Roof': Rooftop,
                         'OuterDoor': Door,
                         'InnerDoor': InnerWall
                         }

    def __init__(self):
        super().__init__()

    def run(self, workflow, libraries, ifc, instances, weather_file):
        #self.logger.info("Export to TEASER")
        export.Instance.init_factory(libraries)

        prj = self._create_project()
        bldg_instances = filter_instances(instances, 'Building')
        exported_buildings = []
        for bldg in bldg_instances:
            exported_buildings.append(models.Building(bldg, parent=prj))

        (r_instances, e_instances) = (export.Instance.requested_instances,
                                      export.Instance.export_instances)

        yield from ProductBased.get_pending_attribute_decisions(r_instances)

        for instance in e_instances:
            instance.collect_params()

        self.prepare_export(exported_buildings)
        prj.weather_file_path = weather_file
        prj.export_aixlib(
            path=self.paths.export / 'TEASER' / 'Model',
            use_postprocessing_calc=True)
        bldg_names = []
        for bldg in exported_buildings:
            bldg_names.append(bldg.name)

        return bldg_names,

    def _create_project(self):
        """Creates a project in TEASER by a given BIM2SIM instance
        Parent: None"""
        prj = Project(load_data=True)
        prj.name = self.prj_name
        prj.data.load_uc_binding()
        return prj

    @classmethod
    def prepare_export(cls, exported_buildings):
        for bldg in exported_buildings:
            for tz in bldg.thermal_zones:
                cls.min_admissible_elements(tz, bldg)
                tz.calc_zone_parameters()
                # hardcode to prevent too low heat/cooling loads
                tz.model_attr.heat_load = 100000
                tz.model_attr.cool_load = -100000
            bldg.calc_building_parameter()

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
