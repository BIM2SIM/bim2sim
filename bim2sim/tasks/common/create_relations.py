from bim2sim.elements.base_elements import IFCBased
from bim2sim.elements.bps_elements import (
    ThermalZone, Storey, Building, ExternalSpatialElement)
from bim2sim.tasks.base import ITask
from bim2sim.elements.mapping.ifc2python import getBuilding, getStorey, getSite
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.pyocc_tools import PyOCCTools


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

        # calculate neighboring spaces of each space and store them in a
        # dictionary. This pre-computation avoids computational overhead for
        # further geometric calculations in this algorithm
        spaces = filter_elements(elements, 'ThermalZone')
        neighbor_spaces = {space: [] for space in spaces}
        # define the maximum distance to search for neighboring spaces. This
        # should be the maximum occurring wall distance. If selected too
        # large, more neighboring spaces are found, which may result in
        # higher computational cost for further operations, and may lead to
        # an increased number of false-internal surfaces.
        max_space_dist = 0.8  # TODO #31 EDGE bldg
        for space1 in spaces:
            for space2 in spaces:
                if space1 == space2:
                    continue
                if space1 in neighbor_spaces[space2]:
                    continue
                if (PyOCCTools.get_minimum_distance(
                        space1.space_shape, space2.space_shape) <
                        max_space_dist):
                    neighbor_spaces[space1].append(space2)
                    neighbor_spaces[space2].append(space1)
        for space_key, neighbors in neighbor_spaces.items():
            space_key.space_neighbors = neighbors
        self.logger.info('Added pre-computed space neighbors to thermal '
                         'zones. ')