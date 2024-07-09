"""Template plugin for bim2sim

Holds a plugin with only base tasks mostly for demonstration.
"""
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam import task as of_tasks
from bim2sim.tasks import common, bps
from bim2sim.sim_settings import OpenFOAMSimSettings
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus import \
    task as ep_tasks


class PluginOpenFOAM(Plugin):
    name = 'openfoam'
    sim_settings = OpenFOAMSimSettings
    default_tasks = [
        common.LoadIFC,
        common.CheckIfc,
        common.CreateElementsOnIfcTypes,
        bps.CreateSpaceBoundaries,
        bps.AddSpaceBoundaries2B,
        bps.CorrectSpaceBoundaries,
        common.BindStoreys,
        bps.DisaggregationCreationAndTypeCheck,
        bps.EnrichMaterial,
        bps.EnrichUseConditions,
        common.Weather,
        ep_tasks.CreateIdf,
        # ep_tasks.ExportIdfForCfd,
        ep_tasks.RunEnergyPlusSimulation,
        of_tasks.InitializeOpenFOAMSetup,
        of_tasks.AddOpenFOAMComfort,
        of_tasks.CreateOpenFOAMGeometry,
        of_tasks.CreateOpenFOAMMeshing,
        of_tasks.SetOpenFOAMBoundaryConditions,
        of_tasks.RunOpenFOAMMeshing,
        of_tasks.RunOpenFOAMSimulation
    ]
