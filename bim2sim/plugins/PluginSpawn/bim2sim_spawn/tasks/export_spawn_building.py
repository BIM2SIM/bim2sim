import codecs
from pathlib import Path

from mako.template import Template

import bim2sim
from bim2sim.plugins.PluginSpawn.bim2sim_spawn.models import to_modelica_spawn
from bim2sim.tasks.base import ITask


class ExportSpawnBuilding(ITask):
    """Export building for SpawnOfEnergyPlus model to Modelica"""

    reads = ('elements',  'weather_file_modelica', 'weather_file_ep')
    touches = ('zone_names', 'model_name_building', 'package_path')

    def run(self, elements: dict, weather_file_modelica: Path,
            weather_file_ep: Path):
        self.logger.info("Export building of Spawn model to Modelica code")
        self.model_name_building = 'BuildingModel'

        # Setup paths
        package_path = self._setup_package_directory()
        template_bldg = self._load_template()

        # Generate data for building template
        zone_names = self._get_zone_names()
        building_template_data = self._render_building_template(
            template_bldg=template_bldg,
            package_path=package_path,
            weather_file_ep=weather_file_ep,
            weather_file_modelica=weather_file_modelica,
            zone_names=zone_names
        )

        # Write the generated Modelica code to file
        export_path = Path(package_path / self.model_name_building)
        self._write_to_file(export_path.with_suffix('.mo'),
                            building_template_data)

        return zone_names, self.model_name_building, package_path

    def _setup_package_directory(self) -> Path:
        """Creates the necessary package directory."""
        package_path = self.paths.export / 'bim2sim_spawn'
        package_path.mkdir(parents=True, exist_ok=True)
        return package_path

    @staticmethod
    def _load_template() -> Template:
        """Loads the building template for rendering."""
        template_path = (Path(bim2sim.__file__).parent /
                         'assets/templates/modelica/tmplSpawnBuilding.txt')
        with open(template_path, 'r', encoding='utf-8') as f:
            template_str = f.read()
        return Template(template_str)

    def _render_building_template(self, template_bldg: Template,
                                  package_path: Path, weather_file_ep: Path,
                                  weather_file_modelica: Path,
                                  zone_names: list) -> str:
        """Renders the building template with the provided data."""
        idf_path = (self.paths.export / "EnergyPlus/SimResults" / self.prj_name
                    / f"{self.prj_name}.idf")
        return template_bldg.render(
            within=package_path.stem,
            model_name=self.model_name_building,
            model_comment='Building model for Spawn of EnergyPlus',
            weather_path_ep=to_modelica_spawn(weather_file_ep),
            weather_path_mos=to_modelica_spawn(weather_file_modelica),
            zone_names=to_modelica_spawn(zone_names),
            idf_path=to_modelica_spawn(idf_path),
            n_zones=len(zone_names)
        )

    def _write_to_file(self, file_path: Path, content: str):
        """Writes the generated content to a file."""
        with codecs.open(file_path, 'w', 'utf-8') as f:
            f.write(content)
        self.logger.info(f"Successfully saved Modelica file to {file_path}")

    def _get_zone_names(self):
        # TODO #1: get names from IDF or EP process for ep zones in
        #  correct order
        if "ep_zone_lists" in self.playground.state:
            zone_list = self.playground.state["ep_zone_lists"]
        else:
            raise ValueError("'ep_zone_list' not found in playground state, "
                             "please make sure that EnergyPlus model creation "
                             "was successful.")
        return zone_list
