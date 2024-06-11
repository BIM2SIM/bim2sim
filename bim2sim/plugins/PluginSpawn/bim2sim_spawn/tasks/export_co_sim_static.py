import os
from datetime import datetime
from pathlib import Path
import codecs
from mako.template import Template

import bim2sim
from bim2sim.elements.base_elements import ProductBased
from bim2sim.export import modelica
from bim2sim.export.modelica import help_package, help_package_order
from bim2sim.tasks.base import ITask


class ExportModelicaSpawnStatic(ITask):
    """Export to Dymola/Modelica"""

    reads = ('elements',  'weather_file_modelica', 'weather_file_ep')
    # reads = ('libraries', 'elements',)
    final = True

    def run(self, elements: dict, weather_file_modelica: Path,
            weather_file_ep: Path):
        self.logger.info("Export to Modelica code")

        package_path = self.paths.export / 'bim2sim_spawn'
        os.makedirs(package_path, exist_ok=True)

        help_package(path=package_path, name=package_path.stem, within="")
        help_package_order(path=package_path, package_list=[
            'coupled_model',
            'building_model',
            'hvac_model'])

        # EXPORT MULTIZONE MODEL
        # This is a "static" model for now, means no elements are created
        # dynamically but only the parameters are changed based on render
        # function
        templ_path_building = Path(
            bim2sim.__file__).parent / \
                              'assets/templates/modelica/tmplSpawnBuilding.txt'

        with open(templ_path_building) as f:
            template_bldg_str = f.read()
        template_bldg = Template(template_bldg_str)
        weather_path_ep = weather_file_ep
        weather_path_mos = weather_file_modelica
        zone_names = self.get_zone_names()
        idf_path = (self.paths.export / "EnergyPlus/SimResults" /
                    self.prj_name / str(self.prj_name + ".idf"))

        # TODO multithreading lock needed? see modelica/__init__.py for example
        # with lock:
        building_template_data = template_bldg.render(
            within='bim2sim_spawn',
            model_name='building_model',
            model_comment='test2',
            weather_path_ep=self.to_modelica_spawn(weather_path_ep),
            weather_path_mos=self.to_modelica_spawn(weather_path_mos),
            zone_names=self.to_modelica_spawn(zone_names),
            idf_path=self.to_modelica_spawn(idf_path),
            n_zones=len(zone_names)
        )

        # TODO
        # template_total = None
        # total_template_data = template_total.render(
        #     ...
        # )

        export_path = package_path / 'building_model.mo'
        # user_logger.info("Saving '%s' to '%s'", self.name, _path)
        with codecs.open(export_path, "w", "utf-8") as file:
            file.write(building_template_data)

        # TODO
        # EXPORT MAIN MODEL
        # This is the main model that should holds building_simulation and
        # hvac_simulation

    def get_zone_names(self):
        # TODO #1: get names from IDF or EP process for ep zones in
        #  correct order
        if "ep_zone_lists" in self.playground.state:
            zone_list = self.playground.state["ep_zone_lists"]
        else:
            raise ValueError("'ep_zone_list' not found in playground state, "
                             "please make sure that EnergyPlus model creation "
                             "was successful.")
        return zone_list

    # def _help_package(self, name: str, uses: str = None, within: str = None):
    #     """creates a package.mo file
    #
    #     private function, do not call
    #
    #     Parameters
    #     ----------
    #
    #     name : string
    #         name of the Modelica package
    #     within : string
    #         path of Modelica package containing this package
    #
    #     """
    #
    #     template_path_package = Path(bim2sim.__file__).parent / \
    #                             "assets/templates/modelica/package"
    #     package_template = Template(filename=str(template_path_package))
    #     with open(self.paths.export / 'package.mo', 'w') as out_file:
    #         out_file.write(package_template.render_unicode(
    #             name=name,
    #             within=within,
    #             uses=uses))
    #         out_file.close()

    # def _help_package_order(self, package_list, addition=None, extra=None):
    #     """creates a package.order file
    #
    #     private function, do not call
    #
    #     Parameters
    #     ----------
    #
    #     package_list : [string]
    #         name of all models or packages contained in the package
    #     addition : string
    #         if there should be a suffix in front of package_list.string it can
    #         be specified
    #     extra : string
    #         an extra package or model not contained in package_list can be
    #         specified
    #
    #     """
    #
    #     template_package_order_path = Path(bim2sim.__file__).parent / \
    #                                   "assets/templates/modelica/package_order"
    #     package_order_template = Template(filename=str(
    #         template_package_order_path))
    #     with open(self.paths.export / 'package.order', 'w') as out_file:
    #         out_file.write(package_order_template.render_unicode(
    #             list=package_list,
    #             addition=addition,
    #             extra=extra))
    #         out_file.close()

    @staticmethod
    def to_modelica_spawn(parameter):
        """converts parameter to modelica readable string"""
        if parameter is None:
            return parameter
        if isinstance(parameter, bool):
            return 'true' if parameter else 'false'
        if isinstance(parameter, (int, float)):
            return str(parameter)
        if isinstance(parameter, str):
            return '"%s"' % parameter
        if isinstance(parameter, (list, tuple, set)):
            return "{%s}" % (
                ",".join(
                    (ExportModelicaSpawnStatic.to_modelica_spawn(par) for par
                     in parameter)))
        if isinstance(parameter, Path):
            return \
                f"Modelica.Utilities.Files.loadResource(\"" \
                f"{str(parameter)}\")" \
                    .replace("\\", "\\\\")
        return str(parameter)

    #
    # def get_static_connections(self, elements):
    #     connections = []
    #     for inst in elements.values():
    #         if isinstance(inst, SpawnBuilding):
    #             spawn_building = inst
    #         if isinstance(inst, FreshAirSource):
    #             fresh_air = inst
    #         if isinstance(inst, SpawnMultizone):
    #             multi = inst
    #     # TODO remove if as this is only temporary for development
    #     if spawn_building and fresh_air and multi:
    #         connections.append((str(spawn_building.name)+'.weaBus',
    #                         str(fresh_air.name) +'.weaBus'))
    #         # TODO clarify export and arrays in modelica
    #         connections.append((
    #             str(multi.name)+".portsExt[nZones]",
    #             str(fresh_air.name)+".ports[nPorts]"))
    #     return connections
