import ifcopenshell
import ifcopenshell.geom
import numpy
import math

from bim2sim.workflow import Workflow
from bim2sim.ifc2python.element import Element
from bim2sim.ifc2python import elements



class Recognition (Workflow):
    """Recognition of the space, zone-like instances"""

    def __init__(self):
        super().__init__()
        self.instances_tz = {}

    @Workflow.log
    def run(self, ifc, hvac_instances):
        self.logger.info("Creates python representation of relevant ifc types")

        spaces = ifc.by_type('IfcSpace')
        del spaces[5] #problem mit Flur
        for space in spaces:
            representation = elements.ThermalZone.add_elements_space(space, hvac_instances)
            self.instances_tz[representation.guid] = representation


class Inspect(Workflow):
    """Analyses IFC, creates Element instances and connects them.

    elements are stored in .instances dict with guid as key"""

    def __init__(self):
        super().__init__()
        self.instances_bps = {}

    @Workflow.log
    def run(self, ifc, relevant_ifc_types):
        self.logger.info("Creates python representation of relevant ifc types")

        # # Building and exterior orientations
        # settings = ifcopenshell.geom.settings()
        # walls = ifc.by_type('IfcWall')
        #
        # tolerance = [[0.5, 0.5], [0.5, -0.5], [-0.5, -0.5], [-0.5, 0.5]]
        # storeys_elements = {}
        #
        # storeys = ifc.by_type('IfcBuildingStorey')
        # for storey in storeys:
        #     externals = []
        #     spaces = {}
        #     for ele in storey.ContainsElements[0].RelatedElements:
        #         if 'IfcWall' in str(ele):
        #             representation = Element.factory(ele)
        #             if representation.is_external is True:
        #                 externals.append(ele)
        #             else:
        #                 self.instances_bps[representation.guid] = representation
        #         elif 'IfcWindow' in str(ele):
        #             representation = Element.factory(ele)
        #             if representation.is_external is True:
        #                 externals.append(ele)
        #             else:
        #                 self.instances_bps[representation.guid] = representation
        #     # if len(storey.IsDecomposedBy) != 0:
        #     #     for space in storey.IsDecomposedBy[0].RelatedObjects:
        #     #         space_ = []
        #     #         ps = bps_functions.get_polygon(space)
        #     #         # plt.plot(*ps.exterior.xy)
        #     #         # plt.show()
        #     #         # for ele in externals:
        #     #         #     pw = bps_functions.get_polygon(ele)
        #     #         #     # plt.plot(*pw.xy, 'k')
        #     #         #     if pw.intersects(ps) or ps.contains(pw):
        #     #         #         space_.append(ele)
        #     #         #         # plt.plot(*pw.xy)
        #     #         # # plt.show()
        #     #         # spaces[str(space)] = space_
        #     #
        #     # # storeys_elements[str(storey)] = spaces
        #
        #
        #
        #
        #
        # for space in spaces:
        #     # centroid = Point(representation.position[0:2])
        #     centroid = bps_functions.get_centroid(space)
        #     plt.plot(*centroid.xy, marker='x')
        # # slabs = ifc.by_type('IfcSlab')
        #
        # # p1, p2, p3, p4, cardinal_direction = bps_functions.find_building_polygon(slabs)
        # # building_envelope = bps_functions.find_building_envelope(p1, p2, p3, p4)
        #
        # for wall in walls:
        #     representation = Element.factory(wall)
        #     if representation.is_external is True:
        #         external_walls.append(wall)
        #     else:
        #         self.instances_bps[representation.guid] = representation
        #
        # for wall in external_walls:
        #     representation = Element.factory(wall)
        #     location = Point(representation.position[0:2])
        #     plt.plot(*location.xy, marker='x')
        #     space_elements = []
        #     elemets = wall.ContainedInStructure[0].RelatedElements
        #     for ele in elemets:
        #         if ('IfcWall' in str(ele)) or ('IfcWindow' in str(ele)):
        #             representation = Element.factory(ele)
        #             location = Point(representation.position[0:2])
        #             plt.plot(*location.xy, marker='o')
        #     plt.show()
        #
        #
        #
        #     # centroid = bps_functions.get_centroid(wall)
        #     # plt.plot(*centroid.xy, marker='o')
        #     # wall.Representation.Description = bps_functions.get_orientation\
        #     #     (building_envelope, centroid, cardinal_direction)
        #     self.instances_bps[representation.guid] = representation
        #
        # # plt.plot(*building_envelope[0].exterior.xy)
        # # plt.plot(*building_envelope[1].exterior.xy)
        # # plt.plot(*building_envelope[2].exterior.xy)
        # # plt.plot(*building_envelope[3].exterior.xy)
        #
        #
        # ######
        # external_windows = []
        # windows = ifc.by_type('IfcWindow')
        # for window in windows:
        #     representation = Element.factory(window)
        #     if representation.is_external is True:
        #         external_windows.append(window)
        #     else:
        #         self.instances_bps[representation.guid] = representation
        #
        # for window in external_windows:
        #     representation = Element.factory(window)
        #     centroid = Point(representation.position[0:2])
        #     # plt.plot(*centroid.xy, marker='o')
        #     window.Tag = bps_functions.get_orientation(building_envelope, centroid, cardinal_direction)
        #     self.instances_bps[representation.guid] = representation
        #
        # # plt.plot(*building_envelope[0].exterior.xy)
        # # plt.plot(*building_envelope[1].exterior.xy)
        # # plt.plot(*building_envelope[2].exterior.xy)
        # # plt.plot(*building_envelope[3].exterior.xy)
        # # plt.show()
        #
        # storeys = ifc.by_type('IfcBuildingStorey')
        # for storey in storeys:
        #     slabs = []
        #     exterior_slab = 0
        #     z_coordinate = float('inf')
        #     for element in storey.ContainsElements[0].RelatedElements:
        #         if 'IfcSlab' in str(element):
        #             representation = Element.factory(element)
        #             slabs.append(element)
        #             if representation.position[2] < z_coordinate:
        #                 z_coordinate = representation.position[2]
        #                 exterior_slab = element
        #     slabs[slabs.index(exterior_slab)].Tag = 'True'
        #     for slab in slabs:
        #         representation = Element.factory(slab)
        #         self.instances_bps[representation.guid] = representation
        #
        # plates = ifc.by_type('IfcPlate')
        # for plate in plates:
        #     bps_functions.get_natural_position(plate)
        #
        # # find and fills spaces
        # spaces = ifc.by_type('IfcSpace')
        # for space in spaces:
        #     representation = Element.factory(space)
        #     self.instances_bps[representation.guid] = representation
        #
        # for ifc_type in relevant_ifc_types[4:]:
        #     elements_ = ifc.by_type(ifc_type)
        #     for element in elements_:
        #         representation = Element.factory(element)
        #         self.instances_bps[representation.guid] = representation
        # self.logger.info("Found %d relevant elements", len(self.instances_bps))

