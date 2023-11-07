from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_instances


class CalcAirFlow(ITask):
    """Calculate the needed airflow for all rooms/spaces in the building.

    - welche annahmen (Normen/Richtlinien)
    - welche inputs etc.

    Args:
        instances: bim2sim elements
    Returns:
        instances: bim2sim elements enriched with needed air flows
    """
    reads = ('instances', )
    touches = ('instances', )

    def run(self, instances):
        self.logger.info("Start calculating the needed air flows for each zone"
                         )
        thermal_zones = filter_instances(instances, 'ThermalZone')
        for tz in thermal_zones:
            tz.air_flow = self.calc_air_flow_zone(tz)
        output = True
        # TODO use sim_setting instead of output boolean
        if output:
            self.output_to_csv(thermal_zones)

        self.logger.info("Caluclated airflows for spaces succesful")
        return instances,

    def calc_air_flow_zone(self, tz):
        """Function calculates the airflow of one specific zone.

        Args:
            tz: ThermalZone bim2sim element
        Returns:
            airflow: calculated airflow of the specific zone
        """
        nr_persons = tz.persons  # persons/m² (data source is din 18599)
        area = tz.net_area

        area_airflow = ...
        person_airflow = ...
        air_flow = person_airflow + area_airflow
        return air_flow

    def output_to_csv(self, thermal_zones):
        ...
