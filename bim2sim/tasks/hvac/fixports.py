import json
from itertools import permutations
from pathlib import Path

import ifcopenshell
import numpy as np
from ifcopenshell.entity_instance import entity_instance

import bim2sim
from bim2sim.tasks.base import ITask
from bim2sim.sim_settings import BaseSimSettings


class FixPorts(ITask):
    """Remove invalid ports from ifc."""

    reads = ('ifc',)
    touches = ('ifc',)

    def run(self, ifc: ifcopenshell.file) -> tuple:
        self.logger.info("Removing invalid ports from ifc")

        to_remove = set()
        to_remove.update(self.unconnected_ports_on_same_position(ifc))
        to_remove.update(self.ports_with_same_parent_and_same_position(ifc))
        to_remove.update(self.entities_with_unusual_number_of_ports(ifc))

        print(to_remove)
        self.logger.info("Removing %d ports ...", len(to_remove))
        with open('./port_blacklist.json', 'w') as file:
            json.dump([entity.GlobalId for entity in to_remove], file)
        raise NotImplementedError("This tasks is only a temporary fix.")
        for entity in to_remove:
            # this fails on ifcopenshell 0.6
            # https://github.com/IfcOpenShell/IfcOpenShell/issues/275
            ifc.remove(entity)
        path = './cleaned.ifc'
        ifc.write(path)
        return ifc,

    def unconnected_ports_on_same_position(self, ifc: ifcopenshell.file) -> set:
        """Analyse IFC file for unconnected ports on the same position.

        Args:
            ifc: the IFC file that is inspected

        Returns:
            to_remove: set of ports to be removed
        """
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

    def ports_with_same_parent_and_same_position(self, ifc: ifcopenshell.file) -> set:
        parents = {}
        for port in self.get_unconnected_ports(ifc):
            parents.setdefault(port.ContainedIn[0].RelatedElement, []).append(port)

        to_remove = set()
        for parent in parents:
            ports = [rel.RelatingPort for rel in parent.HasPorts]
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

    def entities_with_unusual_number_of_ports(self, ifc: ifcopenshell.file) -> set:
        to_remove = []
        two_port_elements = {'IfcPipeSegment', }
        for item in two_port_elements:
            for entity in ifc.by_type(item):
                if len(entity.HasPorts) > 2:
                    for port in entity.HasPorts:
                        if not self._is_connected(port):
                            to_remove.append(port)
        return set(to_remove)

    def get_unconnected_ports(self, ifc: ifcopenshell.file) -> list:
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
    def _get_position(entity: entity_instance) -> np.array:
        port_coordinates_relative = np.array(entity.ObjectPlacement.RelativePlacement.Location.Coordinates)

        parent = entity.ContainedIn[0].RelatedElement
        try:
            relative_placement = parent.ObjectPlacement.RelativePlacement
            x_direction = np.array(relative_placement.RefDirection.DirectionRatios)
            z_direction = np.array(relative_placement.Axis.DirectionRatios)
        except AttributeError:
            x_direction = np.array([1, 0, 0])
            z_direction = np.array([0, 0, 1])
        y_direction = np.cross(z_direction, x_direction)
        directions = np.array((x_direction, y_direction, z_direction)).T

        coordinates = FixPorts.get_product_position(parent) + np.matmul(directions, port_coordinates_relative)
        return coordinates

    @staticmethod
    def get_product_position(entity: entity_instance):
        if hasattr(entity, 'ObjectPlacement'):
            absolute = np.array(entity.ObjectPlacement.RelativePlacement.Location.Coordinates)
            placement_rel = entity.ObjectPlacement.PlacementRelTo
            while placement_rel is not None:
                absolute += np.array(placement_rel.RelativePlacement.Location.Coordinates)
                placement_rel = placement_rel.PlacementRelTo
        else:
            absolute = None
        return absolute


if __name__ == '__main__':
    folder = Path(bim2sim.__file__).parent.parent /\
             'test/resources/hydraulic/ifc'
    path = folder / 'B03_Heating.ifc'
    ifc = ifcopenshell.open(path)
    FixPorts().run(None, ifc)
