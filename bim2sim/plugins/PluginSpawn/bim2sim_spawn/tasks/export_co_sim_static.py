from datetime import datetime
from pathlib import Path
import codecs
from mako.template import Template

import bim2sim
from bim2sim.elements.base_elements import ProductBased
from bim2sim.export import modelica
from bim2sim.tasks.base import ITask


class ExportModelicaSpawnStatic(ITask):
    """Export to Dymola/Modelica"""

    reads = ('elements',)
    # reads = ('libraries', 'elements',)
    final = True

    def run(self, elements: dict):
        self.logger.info("Export to Modelica code")
        # EXPORT MULTIZONE MODEL
        ## This is a "static" model for now, means no elements are created
        # dynamically but only the parameters are changed based on render function
        templ_path = Path(bim2sim.__file__).parent / \
               'assets/templates/modelica/tmplSpawn.txt'

        with open(templ_path) as f:
            templateStr = f.read()
        template = Template(templateStr)
        weather_path_ep = self.paths.root / 'weatherfiles' / \
            str(self.playground.state["weather_file"].stem + '.epw')
        weather_path_mos = self.paths.root / 'weatherfiles' / \
            str(self.playground.state["weather_file"].stem + '.mos')
        zone_names = self.get_zone_names()
        idf_path = self.paths.export / str(
                self.prj_name + ".idf")
        # TODO multithreading lock needed? see modelica/__init__.py for example
        # with lock:
        data = template.render(
            model_name='building_simulation',
            model_comment='test2',
            weather_path_ep=self.to_modelica_spawn(weather_path_ep),
            weather_path_mos=self.to_modelica_spawn(weather_path_mos),
            zone_names=self.to_modelica_spawn(zone_names),
            idf_path=self.to_modelica_spawn(idf_path),
            n_zones=len(zone_names)
        )



        export_path = self.paths.export / 'testmodel.mo'
        # user_logger.info("Saving '%s' to '%s'", self.name, _path)
        with codecs.open(export_path, "w", "utf-8") as file:
            file.write(data)

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
                ",".join((ExportModelicaSpawnStatic.to_modelica_spawn(par) for par in parameter)))
        if isinstance(parameter, Path):
            return \
                f"Modelica.Utilities.Files.loadResource(\"{str(parameter)}\")"\
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
