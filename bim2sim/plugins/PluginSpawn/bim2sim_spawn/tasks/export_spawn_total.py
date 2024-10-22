import codecs
from collections import defaultdict
from pathlib import Path
from threading import Lock
from typing import List, Tuple, Optional, Dict

from mako.template import Template

import bim2sim
from bim2sim.elements.base_elements import ProductBased
from bim2sim.elements.hvac_elements import HVACProduct
from bim2sim.export.modelica import help_package, help_package_order, \
    ModelicaElement
from bim2sim.plugins.PluginSpawn.bim2sim_spawn.models import to_modelica_spawn
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.pyocc_tools import PyOCCTools

TEMPLATE_PATH_TOTAL = Path(bim2sim.__file__).parent / \
                      'assets/templates/modelica/tmplSpawnTotalModel.txt'
TEMPLATE_TOTAL_STR = TEMPLATE_PATH_TOTAL.read_text()
TEMPLATE_TOTAL = Template(TEMPLATE_TOTAL_STR)
LOCK = Lock()


class ExportSpawnTotal(ITask):
    """Export total model for SpawnOfEnergyPlus model to Modelica"""

    reads = (
        'elements', 'weather_file_modelica', 'weather_file_ep',
        'zone_names', 'model_name_hydraulic', 'model_name_building',
        'export_elements', 'connections', 'cons_heat_ports_conv',
        'cons_heat_ports_rad', 'package_name'
    )
    final = True

    def run(self,
            elements: Dict[str, ProductBased],
            weather_file_modelica: Path,
            weather_file_ep: Path,
            zone_names: List[str],
            model_name_hydraulic: str,
            model_name_building: str,
            export_elements: Dict[HVACProduct, ModelicaElement],
            connections: List[Tuple[str, str]],
            cons_heat_ports_conv: List[Tuple[str, str]],
            cons_heat_ports_rad: List[Tuple[str, str]],
            package_name: str):
        """Run the export process to generate the Modelica code.

        Args:
            elements: The elements' data.
            weather_file_modelica: Path to the Modelica weather file.
            weather_file_ep: Path to the EnergyPlus weather file.
            zone_names: List of zone names.
            model_name_hydraulic: The name of the hydraulic model.
            model_name_building: The name of the building model.
            export_elements: HVAC elements to export.
            connections: List of fluid port connections.
            cons_heat_ports_conv: List of convective heat port connections.
            cons_heat_ports_rad: List of radiative heat port connections.
            package_name: The package name of the modelica package.
        """

        # Exports the total model
        self.logger.info("Export total Spawn model to Modelica code")
        model_name_total = 'TotalModel'

        # Filter elements by type
        tz_elements = filter_elements(elements, 'ThermalZone')
        space_heater_elements = filter_elements(elements, 'SpaceHeater')

        # Group heaters by their corresponding zones
        zone_to_heaters = self._group_space_heaters_by_zone(
            tz_elements, space_heater_elements
        )

        # Map heat ports between building and HVAC models
        cons_heat_ports_conv_building_hvac = self.get_port_mapping(
            cons_heat_ports_conv, "Con", model_name_building,
            model_name_hydraulic, zone_to_heaters
        )
        cons_heat_ports_rad_building_hvac = self.get_port_mapping(
            cons_heat_ports_rad, "Rad", model_name_building,
            model_name_hydraulic, zone_to_heaters
        )

        # Define package path
        package_path = self.paths.export / Path(package_name)
        # Save the rendered Modelica total model
        self._save_total_modelica_model(
            model_name_total, model_name_building, model_name_hydraulic,
            cons_heat_ports_conv_building_hvac,
            cons_heat_ports_rad_building_hvac,
            weather_file_modelica, package_path
        )

        # Creates the package help files
        self._create_modelica_help_package(
            package_path, model_name_total, model_name_building,
            model_name_hydraulic
        )

    @staticmethod
    def _create_modelica_help_package(
            package_path: Path, model_name_total: str,
            model_name_building: str, model_name_hydraulic: str):
        """Create the Modelica help package files.

        Args:
            package_path: The path to the package directory.
            model_name_total: The name of the total model.
            model_name_building: The name of the building model.
            model_name_hydraulic: The name of the hydraulic model.
        """
        help_package(path=package_path, name=package_path.stem, within="")
        help_package_order(path=package_path, package_list=[
            model_name_total, model_name_building, model_name_hydraulic])

    @staticmethod
    def _group_space_heaters_by_zone(tz_elements: List,
                                     space_heater_elements: List) \
            -> Dict[str, List[str]]:
        """Group space heaters by their respective zones.

        Args:
            tz_elements: List of thermal zone elements.
            space_heater_elements: List of space heater elements.

        Returns:
             A dictionary mapping zone GUIDs to lists of heater GUIDs.
        """
        zone_to_heaters = defaultdict(list)
        for tz in tz_elements:
            for space_heater in space_heater_elements:
                if PyOCCTools.obj2_in_obj1(
                        obj1=tz.space_shape, obj2=space_heater.shape):
                    zone_to_heaters[tz.guid].append(space_heater.guid)
        return zone_to_heaters

    def _save_total_modelica_model(
            self, model_name_total: str, model_name_building: str,
            model_name_hydraulic: str,
            cons_heat_ports_conv_building_hvac: List[Tuple[str, str]],
            cons_heat_ports_rad_building_hvac: List[Tuple[str, str]],
            weather_path_mos: Path, package_path: Path):
        """Render and save the total Modelica model file using a template.

        Args:
            model_name_total: The name of the total model.
            model_name_building: The name of the building model.
            model_name_hydraulic: The name of the hydraulic model.
            cons_heat_ports_conv_building_hvac: List of convective heat port
                mappings.
            cons_heat_ports_rad_building_hvac: List of radiative heat port
                mappings.
            weather_path_mos: Path to the Modelica weather file.
            package_path: The path to the package directory.
        """
        with LOCK:
            total_template_data = TEMPLATE_TOTAL.render(
                within=package_path.stem,
                model_name=model_name_total,
                model_comment='test2',
                weather_path_mos=to_modelica_spawn(weather_path_mos),
                model_name_building=model_name_building,
                model_name_hydraulic=model_name_hydraulic,
                cons_heat_ports_conv_building_hvac=
                cons_heat_ports_conv_building_hvac,
                cons_heat_ports_rad_building_hvac=
                cons_heat_ports_rad_building_hvac
            )

        export_path = package_path / f"{model_name_total}.mo"
        self.logger.info(f"Saving {model_name_total} Modelica model to "
                         f"{export_path}")
        with codecs.open(export_path, "w", "utf-8") as file:
            file.write(total_template_data)

    @classmethod
    def get_port_mapping(
            cls, cons_heat_ports: List[Tuple[str, str]], port_type: str,
            model_name_building: str, model_name_hydraulic: str,
            zone_to_heaters: Dict[str, List[str]]) -> List[Tuple[str, str]]:
        """Mapping between building heat ports and HVAC heat ports.

        Args:
            cons_heat_ports: A list of tuples where each tuple contains the HVAC
                outer port name and the corresponding space heater name.
            port_type: The type of port to map, e.g., "Con" for convective or
                "Rad" for radiative.
            model_name_building: The name of the building model.
            model_name_hydraulic: The name of the hydraulic model.
            zone_to_heaters: A dictionary mapping zone GUIDs to lists of heater
                GUIDs.

        Returns:
             A list of tuples where each tuple contains the mapped building port
                and the corresponding hydraulic port in the HVAC model.
        """
        mapping = []
        for hvac_outer_port, space_heater_name in cons_heat_ports:
            heater_guid = space_heater_name.split('.')[0].replace(
                'spaceheater_', '').replace('_', '$')
            building_index = cls.get_building_index(
                zone_to_heaters, heater_guid)
            building_port = (f"{model_name_building.lower()}."
                             f"heaPor{port_type}[{building_index}]")
            hydraulic_port = (f"{model_name_hydraulic.lower()}."
                              f"{hvac_outer_port}")
            mapping.append((building_port, hydraulic_port))
        return mapping

    @staticmethod
    def get_building_index(
            zone_to_heaters: Dict[str, List[str]],
            heater_guid: str) -> Optional[int]:
        """Get the index of the building in the zone_to_heaters dictionary.

        Args:
            zone_to_heaters: A dictionary mapping zone GUIDs to lists of heater
                GUIDs.
            heater_guid: The GUID of the heater to search for.

        Returns:
            Optional: The index (1-based) of the zone that contains the heater
                with the specified GUID. Returns None if the heater GUID is not
                found in any zone.
        """
        for index, (zone_guid, heater_list) in enumerate(
                zone_to_heaters.items(), start=1):
            if heater_guid in heater_list:
                return index
        return None
