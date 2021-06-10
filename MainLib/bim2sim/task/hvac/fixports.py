from itertools import permutations

import numpy as np

from bim2sim.task.base import ITask


class FixPorts(ITask):
    """"""

    reads = ('ifc', )
    touches = ('ifc', )

    def run(self, workflow, ifc):
        self.logger.info("Removing invalid ports from ifc")

        to_remove = set()
        to_remove.update(self.unconnected_ports_on_same_position(ifc))
        to_remove.update(self.ports_with_same_parent_and_same_position(ifc))
        to_remove.update(self.entities_with_unusual_number_of_ports(ifc))

        print(to_remove)
        self.logger.info("Removing %d ports ...", len(to_remove))
        for entity in to_remove:
            ifc.remove(entity)  # this fails on ifcopenshell 0.6
        path = './cleaned.ifc'
        ifc.write(path)
        return (ifc, )

    def unconnected_ports_on_same_position(self, ifc) -> set:
        positions = {}
        for port in ifc.by_type('IfcDistributionPort'):
            position = self._get_position(port)
            positions.setdefault(tuple(np.round(position, 3)), []).append(port)

        to_remove = []
        for pos, ports in positions.items():
            if len(ports) > 2:
                # get unconnected from ports on same position
                for port in positions[pos]:
                    if not self._is_connected(port):
                        to_remove.append(port)
        return set(to_remove)

    def ports_with_same_parent_and_same_position(self, ifc) -> set:
        parents = {}
        for port in self.get_unconnected_ports(ifc):
            parents.setdefault(port.ContainedIn[0].RelatedElement, []).append(port)

        to_remove = set()
        for parent in parents:
            ports = [rel.RelatingPort for rel in parent.HasPorts]  # other options?
            for port1, port2 in permutations(ports, 2):
                unconnected_ports = []
                if np.allclose(
                        self._get_position(port1),
                        self._get_position(port2)):
                    if port1 in parents[parent]:
                        unconnected_ports.append(port1)
                    if port2 in parents[parent]:
                        unconnected_ports.append(port2)
                    # remove only one of them
                    if unconnected_ports:
                        to_remove.add(unconnected_ports[0])
        return to_remove

    def entities_with_unusual_number_of_ports(self, ifc) -> set:
        to_remove = []
        two_port_elements = {'IfcPipeSegment', }
        for item in two_port_elements:
            for entity in ifc.by_type(item):
                if len(entity.HasPorts) > 2:
                    for port in entity.HasPorts:
                        if not self._is_connected(port):
                            to_remove.append(port)
        return set(to_remove)

    def get_unconnected_ports(self, ifc) -> list:
        return [port for port in ifc.by_type('IfcDistributionPort')
                if not self._is_connected(port)]

    @staticmethod
    def _is_connected(port):
        if port.ConnectedTo:
            other = port.ConnectedTo[0].RelatedPort
        elif port.ConnectedFrom:
            other = port.ConnectedFrom[0].RelatingPort
        else:
            return False
        return True

    @staticmethod
    def _get_position(entity) -> np.array:
        port_coordinates_relative = \
            np.array(entity.ObjectPlacement.RelativePlacement.Location.Coordinates)

        parent = entity.ContainedIn[0].RelatedElement
        # parent = entity.ConnectedTo[0].RelatedPort.ContainedIn[0].RelatedElement
        try:
            relative_placement = parent.ObjectPlacement.RelativePlacement
            x_direction = np.array(relative_placement.RefDirection.DirectionRatios)
            z_direction = np.array(relative_placement.Axis.DirectionRatios)
        except AttributeError:
            x_direction = np.array([1, 0, 0])
            z_direction = np.array([0, 0, 1])
        y_direction = np.cross(z_direction, x_direction)
        directions = np.array((x_direction, y_direction, z_direction)).T

        coordinates = FixPorts.get_product_position(parent) \
                      + np.matmul(directions, port_coordinates_relative)
        return coordinates

    @staticmethod
    def get_product_position(product):
        if hasattr(product, 'ObjectPlacement'):
            absolute = np.array(product.ObjectPlacement.RelativePlacement.Location.Coordinates)
            placement_rel = product.ObjectPlacement.PlacementRelTo
            while placement_rel is not None:
                absolute += np.array(placement_rel.RelativePlacement.Location.Coordinates)
                placement_rel = placement_rel.PlacementRelTo
        else:
            absolute = None
        return absolute
