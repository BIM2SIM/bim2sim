from pathlib import Path

from bim2sim.tasks.base import ITask
from bim2sim.elements.bps_elements import SpawnBuilding, SpawnMultiZone, FreshAirSource


class CreateSpawnElements(ITask):
    # reads = ('instances',)
    touches = ('instances',)

    def run(self):
    # def run(self, instances):
        # TODO maybe add an option to manual create elements for export without
        #  represents. Because the represents attribute currently makes it
        #  necessary to create those temp objects here and add them to elements
        spawn_building = SpawnBuilding()
        spawn_building.idfName = Path("D:/Test")
        spawn_building.epwName = Path("D:/Test")
        spawn_building.weaName = Path("D:/Test")
        spawn_building.printUnits = True
        fresh_air_source = FreshAirSource()
        spawn_multi = SpawnMultiZone()

        instances = {
            spawn_building.guid: spawn_building,
            fresh_air_source.guid: fresh_air_source,
            spawn_multi.guid: spawn_multi}
        return instances,
