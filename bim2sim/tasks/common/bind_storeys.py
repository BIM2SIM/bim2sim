from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_instances


class BindStoreys(ITask):
    reads = ('instances', )
    touches = ('instances', )

    def run(self, instances: dict):
        """Bind thermal_zones and instances to each floor/storey and vice
        versa"""
        self.logger.info("Binding bim2sim instances to storeys")
        storeys = filter_instances(instances, 'Storey')
        for storey in storeys:
            storey_instances = []
            for ifc_structure in storey.ifc.ContainsElements:
                for ifc_element in ifc_structure.RelatedElements:
                    instance = instances.get(ifc_element.GlobalId, None)
                    if instance:
                        storey_instances.append(instance)
                        if storey not in instance.storeys:
                            instance.storeys.append(storey)

            storey_spaces = []
            for ifc_aggregates in storey.ifc.IsDecomposedBy:
                for ifc_element in ifc_aggregates.RelatedObjects:
                    instance = instances.get(ifc_element.GlobalId, None)
                    if instance:
                        storey_spaces.append(instance)
                        if storey not in instance.storeys:
                            instance.storeys.append(storey)

            storey.storey_instances = storey_instances
            storey.thermal_zones = storey_spaces
        return instances,
