from bim2sim.sim_settings import BuildingSimSettings, ChoiceSetting, \
    PathSetting
from bim2sim.utilities.types import LOD, ZoningCriteria


class TEASERSimSettings(BuildingSimSettings):
    """Defines simulation settings for TEASER Plugin.

    This class defines the simulation settings for the TEASER Plugin. It
    inherits all choices from the BuildingSimulation settings. TEASER
    specific settings are added here.
    """
    sim_results = ChoiceSetting(
        default=[
            "heat_demand_total", "cool_demand_total",
            "heat_demand_rooms", "cool_demand_rooms",
            "heat_energy_total", "cool_energy_total",
            "heat_energy_rooms", "cool_energy_rooms",
            "air_temp_out", "operative_temp_rooms", "air_temp_rooms",
            "internal_gains_machines_rooms", "internal_gains_persons_rooms",
            "internal_gains_lights_rooms", "n_persons_rooms",
            "infiltration_rooms", "mech_ventilation_rooms",
            "heat_set_rooms", "cool_set_rooms", "cpu_time"

                 ],
        choices={
            "heat_demand_total":
                "Total heating demand (power) as time series data",
            "cool_demand_total":
                "Total cooling demand (power) as time series data",
            "heat_demand_rooms":
                "Zone based heating demand (power) as time series data",
            "cool_demand_rooms":
                "Zone based cooling demand (power) as time series data",
            "heat_energy_total":
                "Total heating energy as time series data",
            "cool_energy_total":
                "Total cooling energy as time series data",
            "heat_energy_rooms":
                "Zone based heating energy as time series data",
            "cool_energy_rooms":
                "Zone cooling heating energy as time series data",
            "air_temp_out":
                "Outdoor air temperature as time series data",
            "operative_temp_rooms":
                "Zone based operative temperature as time series data",
            "air_temp_rooms":
                "Zone based indoor air temperature as time series data",
            "internal_gains_machines_rooms":
                "Internal gains through machines in W as time series data",
            "internal_gains_persons_rooms":
                "Internal gains through persons in W as time series data",
            "internal_gains_lights_rooms":
                "Internal gains through lights in W as time series data",
            "n_persons_rooms":
                "Total amount of occupying persons as time series data",
            "infiltration_rooms":
                "Infiltration into room in 1/h as time series data",
            "mech_ventilation_rooms":
                "Mechanical ventilation flow in m³/h as time series data",
            "heat_set_rooms":
                "Heating set point in °C time series data",
            "cool_set_rooms":
                "Cooling set point in °C time series data",
            "cpu_time": "Computational time taken for simulation."
        },
        multiple_choice=True,
    )

    zoning_criteria = ChoiceSetting(
        default=ZoningCriteria.usage,
        choices={
            ZoningCriteria.external:
                'Group all thermal zones that have contact to the exterior'
                ' together and all thermal zones that do not have contact to'
                ' exterior.',
            ZoningCriteria.external_orientation:
                'Like external, but takes orientation '
                '(North, East, South, West)'
                ' into account as well',
            ZoningCriteria.usage:
                'Group all thermal zones that have the same usage.',
            ZoningCriteria.external_orientation_usage:
                'Combines grouping based on exterior contact, '
                'orientation, and usage.',
            ZoningCriteria.all_criteria:
                'Uses all criteria including exterior contact, orientation, '
                'usage, glass percentage, and only groups physically adjacent '
                'rooms.',
            ZoningCriteria.individual_spaces:
                'Creates individual thermal zones for each space.',
            ZoningCriteria.combined_single_zone:
                'Combines all spaces into a single thermal zone.'
        },
        for_frontend=True
    )

    path_aixlib = PathSetting(
        default=None,
        description='Path to the local AixLib`s repository. This needs to '
                    'point to the root level package.mo file. If not'
                    ' provided, the version for regression testing will be '
                    'used if it was already downloaded using the '
                    'prepare_regression_tests.py script.',
        for_frontend=False,
        mandatory=False
    )