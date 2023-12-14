from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements


class BindStoreys(ITask):
    reads = ('elements', )
    touches = ('elements', )

    def run(self, elements: dict):
        """Bind thermal_zones and elements to each floor/storey and vice
        versa"""
        self.logger.info("Binding bim2sim elements to storeys")
        storeys = filter_elements(elements, 'Storey')
        for storey in storeys:
            storey_elements = []
            for ifc_structure in storey.ifc.ContainsElements:
                for ifc_element in ifc_structure.RelatedElements:
                    instance = elements.get(ifc_element.GlobalId, None)
                    if instance:
                        storey_elements.append(instance)
                        if storey not in instance.storeys:
                            instance.storeys.append(storey)

            storey_spaces = []
            for ifc_aggregates in storey.ifc.IsDecomposedBy:
                for ifc_element in ifc_aggregates.RelatedObjects:
                    instance = elements.get(ifc_element.GlobalId, None)
                    if instance:
                        storey_spaces.append(instance)
                        if storey not in instance.storeys:
                            instance.storeys.append(storey)

            storey.storey_elements = storey_elements
            storey.thermal_zones = storey_spaces
        return elements,
