import codecs
from pathlib import Path
from typing import List

from mako.template import Template

import bim2sim
from bim2sim.export.modelica import parse_to_modelica
from bim2sim.tasks.base import ITask


class ExportSpawnBuilding(ITask):
    """Export building for SpawnOfEnergyPlus model to Modelica"""

    reads = ('elements', 'weather_file_modelica', 'weather_file_ep',
             'package_name', 'ep_zone_lists')
    touches = ('model_name_building',)

    def run(self, elements: dict, weather_file_modelica: Path,
            weather_file_ep: Path, package_name: str, ep_zone_lists: List):
        """Run the export process for a building Spawn model in Modelica.

        This method prepares the Modelica file for a building model by gathering
        necessary elements, generating the template data, and writing the
        Modelica code to file.

        Args:
            elements: Dictionary containing building elements.
            weather_file_modelica: Path to the Modelica weather file.
            weather_file_ep: Path to the EnergyPlus weather file.
            package_name: Name of the Modelica package for exporting.
            ep_zone_lists: List of thermal zone EP items

        Returns:
            model_name_building: the name of the building model.
        """
        self.logger.info("Export building of Spawn model to Modelica code")
        model_name_building = 'BuildingModel'

        # Setup export paths
        export_package_path = self.paths.export / Path(package_name)

        # Generate building template data
        building_template_data = self._render_building_template(
            package_path=export_package_path,
            model_name=model_name_building,
            weather_file_ep=weather_file_ep,
            weather_file_modelica=weather_file_modelica,
            ep_zone_lists=ep_zone_lists
        )

        # Write the generated Modelica code to file
        self._write_to_file(
            Path(export_package_path / f"{model_name_building}.mo"),
            building_template_data)

        return model_name_building,

    @staticmethod
    def _load_template() -> Template:
        """Loads the building template for rendering.

        Returns:
            Template: Mako template object for the building Modelica file.
        """
        template_path = (Path(bim2sim.__file__).parent /
                         'assets/templates/modelica/tmplSpawnBuilding.txt')
        with open(template_path, 'r', encoding='utf-8') as f:
            template_str = f.read()
        return Template(template_str)

    def _render_building_template(self,
                                  package_path: Path,
                                  model_name: str,
                                  weather_file_ep: Path,
                                  weather_file_modelica: Path,
                                  ep_zone_lists: list) -> str:
        """Render the building Modelica template using provided data.

        Args:
            package_path: The path to the Modelica package.
            model_name: The name of the building model.
            weather_file_ep: The EnergyPlus weather file path.
            weather_file_modelica: The Modelica weather file path.
            ep_zone_lists: List of zone names to be used in the model.

        Returns:
            Rendered Modelica code as a string.
        """
        template_bldg = self._load_template()
        idf_path = (self.paths.export / "EnergyPlus/SimResults" / self.prj_name
                    / f"{self.prj_name}.idf")
        return template_bldg.render(
            within=package_path.stem,
            model_name=model_name,
            model_comment='Building model for Spawn of EnergyPlus',
            weather_path_ep=parse_to_modelica(
                name=None, value=weather_file_ep),
            weather_path_mos=parse_to_modelica(
                name=None, value=weather_file_modelica),
            ep_zone_lists=parse_to_modelica(name=None, value=ep_zone_lists),
            idf_path=parse_to_modelica(name=None, value=idf_path),
            n_zones=len(ep_zone_lists)
        )

    def _write_to_file(self, file_path: Path, content: str):
        """Write the generated content to a Modelica file.

        Args:
            file_path: The path to the output file.
            content: The content to write into the file.
        """
        with codecs.open(file_path, 'w', 'utf-8') as f:
            f.write(content)
        self.logger.info(f"Successfully saved Modelica file to {file_path}")
