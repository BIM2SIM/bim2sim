from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_instances
from bim2sim.elements.mapping.units import ureg


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
            print(tz)
        output = True
        # TODO use sim_setting instead of output boolean
        if output:
            self.output_to_csv(thermal_zones)

        self.logger.info("Caluclated airflows for spaces succesful")
        return instances,

    def calc_air_flow_zone(self, tz):
        """Function calculates the airflow of one specific zone.

        #TODO
        Args:
            tz: ThermalZone bim2sim element
        Returns:
            airflow: calculated airflow of the specific zone
        """
        nr_persons = tz.persons  # persons/m² (data source is din 18599)
        area = tz.net_area
        # TODO have a look at:
        #  bim2sim/assets/enrichment/usage/UseConditions.json
        factor_usage_dict = {
            "buero": []
        }
        # TODO
        area_air_flow_factor = 0.07 * ureg.meter / ureg.s
        persons_air_flow_factor = 0.07 * ureg.meter ** 3 / ureg.s
        area_airflow = area * area_air_flow_factor
        person_airflow = nr_persons * persons_air_flow_factor
        air_flow = person_airflow + area_airflow
        return air_flow

    def output_to_csv(self, thermal_zones):
        ...
