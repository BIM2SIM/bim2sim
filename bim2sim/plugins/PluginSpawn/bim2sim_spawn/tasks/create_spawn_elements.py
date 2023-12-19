from pathlib import Path

from bim2sim.tasks.base import ITask
from bim2sim.elements.bps_elements import SpawnBuilding, SpawnMultiZone, FreshAirSource


class CreateSpawnElements(ITask):
    # reads = ('instances',)
    touches = ('elements',)

    def run(self):
    # def run(self, elements):
        # TODO maybe add an option to manual create elements for export without
        #  represents. Because the represents attribute currently makes it
        #  necessary to create those temp objects here and add them to elements
        spawn_building = SpawnBuilding()
        spawn_building.idfName = self.paths.export / str(
                self.prj_name + ".idf")
        # todo use loadresource maybe after prototype ready
        spawn_building.epwName = self.paths.root / 'weatherfiles' / \
            str(self.playground.state["weather_file"].stem + '.epw')
        spawn_building.weaName = self.paths.root / 'weatherfiles' / \
            str(self.playground.state["weather_file"].stem + '.mos')
        spawn_building.printUnits = True
        fresh_air_source = FreshAirSource()
        spawn_multi = SpawnMultiZone()
        spawn_multi.zone_names = self.get_zone_names()

        elements = {
            spawn_building.guid: spawn_building,
            fresh_air_source.guid: fresh_air_source,
            spawn_multi.guid: spawn_multi}
        return elements,

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
