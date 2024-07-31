import os
from datetime import datetime
from pathlib import Path
import codecs
from mako.template import Template

import bim2sim
from bim2sim.elements.base_elements import ProductBased
from bim2sim.export import modelica
from bim2sim.export.modelica import help_package, help_package_order
from bim2sim.plugins.PluginSpawn.bim2sim_spawn.models import to_modelica_spawn
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.pyocc_tools import PyOCCTools


class ExportSpawnTotal(ITask):
    """Export total model for SpawnOfEnergyPlus model to Modelica"""

    reads = ('elements', 'weather_file_modelica', 'weather_file_ep',
             'zone_names')
    final = True

    def run(self, elements: dict, weather_file_modelica: Path,
            weather_file_ep: Path, zone_names):
        self.logger.info("Export total Spawn model to Modelica code")

        package_path = self.paths.export / 'bim2sim_spawn'
        os.makedirs(package_path, exist_ok=True)

        help_package(path=package_path, name=package_path.stem, within="")
        help_package_order(path=package_path, package_list=[
            'total_model',
            'building_model',
            'hvac_model'])

        # EXPORT MULTIZONE MODEL
        # This is a "static" model for now, means no elements are created
        # dynamically but only the parameters are changed based on render
        # function
        templ_path_total = Path(
            bim2sim.__file__).parent / \
                              ('assets/templates/modelica/tmplSpawnTotalModel'
                               '.txt')

        with open(templ_path_total) as f:
            template_total_str = f.read()
        template_total = Template(template_total_str)
        weather_path_mos = weather_file_modelica
        tz_elements = filter_elements(elements, 'ThermalZone')
        space_heater_elements = filter_elements(elements,
                                               'SpaceHeater')
        # ToDO Missing: list with space heater guids for array indexing
        tz_space_heater_mapping = []
        for tz in tz_elements:
            for space_heater in space_heater_elements:
                # TODO check SpaceHeater is some how semantically connected
                #  to the Space in the IFC, is this correct?
                if PyOCCTools.obj2_in_obj1(
                        obj1=tz.space_shape, obj2=space_heater.shape):
                    tz_space_heater_mapping.append(
                        (tz.guid, space_heater.guid))
        # ToDo radiator_names_list is missing
    #
        # TODO multithreading lock needed? see modelica/__init__.py for example
        # with lock:
        total_template_data = template_total.render(
            within='bim2sim_spawn',
            model_name='total_model',
            model_comment='test2',
            weather_path_mos=to_modelica_spawn(weather_path_mos),
            bldg_to_hvac_heat_ports_connections=...
            # n_zones=len(zone_names)
        )

        export_path = package_path / 'total_model.mo'
        # user_logger.info("Saving '%s' to '%s'", self.name, _path)
        with codecs.open(export_path, "w", "utf-8") as file:
            file.write(total_template_data)

