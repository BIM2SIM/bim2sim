from bim2sim.export import modelica
from bim2sim.kernel.elements import bps


class Buildings(modelica.Instance):
    library = "Buildings"


class BuildingThermalZone(Buildings):
    path = "Buildings.ThermalZones.EnergyPlus_9_6_0.ThermalZone"
    represents = bps.ThermalZone


class Floor(Buildings):
    ...
    # TODO
    # Sum all zones and connect with infiltration
    # connect all zones (maybe later)
