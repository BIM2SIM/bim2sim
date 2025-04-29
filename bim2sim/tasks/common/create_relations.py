from bim2sim.elements.base_elements import IFCBased
from bim2sim.elements.bps_elements import (
    ThermalZone, Storey, Building, ExternalSpatialElement)
from bim2sim.tasks.base import ITask
from bim2sim.elements.mapping.ifc2python import getBuilding, getStorey, getSite


class CreateRelations(ITask):
    """Relations of elements, run() method holds detailed information."""
    reads = ('elements',)

    def run(self, elements: dict[str, IFCBased]):
        """Bind ThermalZone to ProductBased/Storey/Building and vice versa.

        This is needed as our CreateElements task does not work hierarchic. So
        we need to create the relations after initial creation.
        Problem: Following IFC-schema rules a space that is stretched over
        multiple storeys should only be assigned to one of these storeys. From
        IFC-Schema:
        "NOTE:  Multi storey spaces shall be spatially contained by only a
        single building storey, usually it is the building storey where the
        base of the space lies.
        TODO: this might me solved via PyOCCTools.obj2_in_obj1 but this needs
         all shapes to be existing for ThermalZone instances and Storeys
        "

        Args:
            elements: dict[guid: element]
        """
        self.logger.info("Creating bim2sim elements relations.")
        for element in elements.values():
            # connect element to site and vice versa
            ifc_site = getSite(element.ifc)
            if ifc_site:
                element_site = elements.get(
                    ifc_site.GlobalId, None)
                if isinstance(element, Building):
                    if element not in element_site.buildings:
                        element_site.buildings.append(element)

            # connect element to building and vice versa
            ifc_building = getBuilding(element.ifc)
            if ifc_building:
                element_building = elements.get(
                    ifc_building.GlobalId, None)
                if element_building:
                    if isinstance(element, Storey):
                        if element not in element_building.storeys:
                            element_building.storeys.append(element)
                    if isinstance(element, ThermalZone):
                        if not isinstance(element, ExternalSpatialElement):
                            if element not in element_building.thermal_zones:
                                element_building.thermal_zones.append(element)
                    else:
                        if element not in element_building.elements:
                            element_building.elements.append(element)
                    element.building = element_building

            # connect element to storey and vice versa
            ifc_storey = getStorey(element.ifc)
            if ifc_storey:
                element_storey = elements.get(
                    ifc_storey.GlobalId, None)
                if element_storey:
                    if isinstance(element, ThermalZone):
                        if not isinstance(element, ExternalSpatialElement):
                            if element not in element_storey.thermal_zones:
                                element_storey.thermal_zones.append(element)
                    else:
                        if element not in element_storey.elements:
                            element_storey.elements.append(element)
                    if element not in element.storeys:
                        element.storeys.append(element_storey)
            # relations between element and space are handled in sb_creation
            # as more robust
