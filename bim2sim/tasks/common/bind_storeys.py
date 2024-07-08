from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.elements.mapping.ifc2python import (getSpatialChildren,
                                                 getHierarchicalChildren)
# from bim2sim.utilities.pyocc_tools import PyOCCTools


class BindStoreys(ITask):
    """Bind storeys to elements, run() method holds detailed information."""
    reads = ('elements', )

    def run(self, elements: dict):
        """Bind thermal_zones and elements to each floor/storey and vice
        versa.

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
        self.logger.info("Binding bim2sim elements to storeys")
        storeys = filter_elements(elements, 'Storey')
        for storey in storeys:
            storey_elements = []
            for ifc_element in getSpatialChildren(storey.ifc):
                instance = elements.get(ifc_element.GlobalId, None)
                if instance:
                    storey_elements.append(instance)
                    if storey not in instance.storeys:
                        instance.storeys.append(storey)

            storey_spaces = []
            for ifc_element in getHierarchicalChildren(storey.ifc):
                instance = elements.get(ifc_element.GlobalId, None)
                if instance:
                    storey_spaces.append(instance)
                    if storey not in instance.storeys:
                        instance.storeys.append(storey)

            storey.storey_elements = storey_elements
            storey.thermal_zones = storey_spaces
        self.add_storeys_to_buildings(elements)

    @classmethod
    def add_storeys_to_buildings(cls, elements):
        """adds storeys to building"""
        bldg_elements = filter_elements(elements, 'Building')
        for bldg in bldg_elements:
            for decomposed in bldg.ifc.IsDecomposedBy:
                for rel_object in decomposed.RelatedObjects:
                  if rel_object.is_a("IfcBuildingStorey"):
                    storey = elements.get(rel_object.GlobalId, None)
                    if storey and storey not in bldg.storeys:
                        bldg.storeys.append(storey)
            cls.add_thermal_zones_to_building(bldg)

    @staticmethod
    def add_thermal_zones_to_building(bldg):
        """adds thermal zones to building"""
        for storey in bldg.storeys:
            for tz in storey.thermal_zones:
                if tz not in bldg.thermal_zones:
                    bldg.thermal_zones.append(tz)
