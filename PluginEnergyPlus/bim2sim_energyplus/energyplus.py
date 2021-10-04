from bim2sim.task import bps
from bim2sim.task import common
from bim2sim.plugin import Plugin
from bim2sim.workflow import BPSMultiZoneSeparatedEP
from bim2sim.kernel.elements import bps as bps_elements

from bim2sim_energyplus.weather import Weather


class EnergyPlus(Plugin):
    name = 'EnergyPlus'
    default_workflow = BPSMultiZoneSeparatedEP
    elements = {*bps_elements.items}
    default_tasks = [
        common.LoadIFC,
        common.CreateElements,
        bps.CreateSpaceBoundaries,
        bps.Prepare,
        bps.EnrichUseConditions,
        bps.OrientationGetter,
        bps.MaterialVerification,  # LOD.full
        bps.EnrichMaterial,  # LOD.full
        bps.BuildingVerification,  # all LODs
        bps.EnrichNonValid,  # LOD.full
        bps.EnrichBuildingByTemplates,  # LOD.low
        bps.DisaggregationCreation,
        bps.BindThermalZones,
        Weather,
        bps.ExportEP,
    ]

