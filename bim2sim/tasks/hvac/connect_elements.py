import itertools
import logging
from typing import Tuple, Generator, Iterable

import networkx as nx
import numpy as np

from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.base_elements import Port, ProductBased
from bim2sim.kernel.decision import DecisionBunch
from bim2sim.tasks.base import ITask, Playground


quality_logger = logging.getLogger('bim2sim.QualityReport')


class ConnectElements(ITask):
    """Analyses IFC, creates element elements and connects them. Elements are
    stored in elements dict with GUID as key."""

    reads = ('elements',)
    touches = ('elements',)

    def __init__(self, playground: Playground):
        super().__init__(playground)
        self.elements = {}
        pass

    def run(self, elements: dict) -> dict:
        """Connect elements based on port information and geometric relations.

        This method performs the following steps:
        1. Checks the ports of elements.
        2. Connects the relevant elements based on relations.
        3. Checks the positions of connections and connects ports based on
            geometric distance.
        4. Connects remaining unconnected ports by position.
        5. Logs information about the number of connected and unconnected ports.

        Args:
            elements: dictionary of elements with GUID as key.

        Returns:
            elements: dictionary of elements with GUID as key, with updated
                connections.
        """
        self.logger.info("Connect elements")

        # Check ports
        self.logger.info("Checking ports of elements ...")
        self.remove_duplicate_ports(elements)
        # Make connections by relations
        self.logger.info("Connecting the relevant elements")
        self.logger.info(" - Connecting by relations ...")
        all_ports = [port for item in elements.values() for port in item.ports]
        rel_connections = self.connections_by_relation(all_ports)
        self.logger.info(" - Found %d potential connections.",
                         len(rel_connections))
        # Check connections
        self.logger.info(" - Checking positions of connections ...")
        confirmed, unconfirmed, rejected = self.confirm_connections_position(
            rel_connections)
        self.logger.info(
            " - %d connections are confirmed and %d rejected. %d can't be "
            "confirmed.",
            len(confirmed), len(rejected), len(unconfirmed))
        for port1, port2 in confirmed + unconfirmed:
            # Unconfirmed ports have no position data and can not be
            # connected by position
            port1.connect(port2)
        # Connect unconnected ports by position
        unconnected_ports = (port for port in all_ports if
                             not port.is_connected())
        self.logger.info(" - Connecting remaining ports by position ...")
        pos_connect_tol = (self.playground.sim_settings.
                           tolerance_connect_by_position)
        pos_connections = self.connections_by_position(
            unconnected_ports, eps=pos_connect_tol)
        self.logger.info(" - Found %d additional connections.",
                         len(pos_connections))
        for port1, port2 in pos_connections:
            port1.connect(port2)
        # Get number of connected and unconnected ports
        nr_total = len(all_ports)
        unconnected = [port for port in all_ports if not port.is_connected()]
        nr_unconnected = len(unconnected)
        nr_connected = nr_total - nr_unconnected
        self.logger.info("In total %d of %d ports are connected.", nr_connected,
                         nr_total)
        if nr_total > nr_connected:
            self.logger.warning("%d ports are not connected!", nr_unconnected)
        # Connect by bounding box TODO: implement
        unconnected_elements = {uc.parent for uc in unconnected}
        if unconnected_elements:
            bb_connections = self.connections_by_boundingbox(
                unconnected,
                unconnected_elements
            )
            self.logger.warning(
                "Connecting by bounding box is not implemented.")
        # Check inner connections
        yield from self.check_inner_connections(elements.values())

        # TODO: manually add / modify connections
        return elements,

    @staticmethod
    def remove_duplicate_ports(elements: dict):
        """Checks position of all ports for each element and handles
        overlapping ports.

        This method analyzes port positions within building elements
        (e.g. pipes, fittings) and identifies overlapping ports that may
        indicate data quality issues. When two ports of the same element
        overlap and both connect to the same third port, they are merged into
        a single bidirectional port.

        Args:
            elements: Dictionary mapping GUIDs to element objects that should
            be checked.
                     Each element must have a 'ports' attribute containing its
                     ports.

        Quality Checks:
            - Warns if ports of the same element are closer than 1 unit
            (atol=1)
            - Identifies overlapping ports using numpy.allclose with rtol=1e-7

        Port Merging:
            If overlapping ports A and B are found that both connect to the
             same port C:
            - Port B is removed from the element
            - Port A is set as bidirectional (SINKANDSOURCE)
            - Port A becomes the flow master
            - The change is logged for documentation

            WARNING: Poor quality of elements <IFC>: Overlapping ports (port1
            and port2 @[x,y,z])
            INFO: Removing <IFC port2> and set <IFC port1> as SINKANDSOURCE.
        """
        for ele in elements.values():
            for port_a, port_b in itertools.combinations(ele.ports, 2):
                if np.allclose(port_a.position, port_b.position, rtol=1e-7,
                               atol=1):
                    quality_logger.warning("Poor quality of elements %s: "
                                           "Overlapping ports (%s and %s @%s)",
                                           ele.ifc, port_a.guid, port_b.guid,
                                           port_a.position)
                    connections = ConnectElements.connections_by_relation(
                        [port_a, port_b], include_conflicts=True)
                    all_ports = [port for connection in connections for port in
                                 connection]
                    other_ports = [port for port in all_ports if
                                   port not in [port_a, port_b]]
                    if port_a in all_ports and port_b in all_ports and len(
                            set(other_ports)) == 1:
                        # Both ports connected to same other port ->
                        # merge ports
                        quality_logger.info(
                            "Removing %s and set %s as SINKANDSOURCE.",
                            port_b.ifc, port_a.ifc)
                        ele.ports.remove(port_b)
                        port_b.parent = None
                        port_a.flow_direction.value = 0
                        port_a.flow_master = True

    @staticmethod
    def connections_by_relation(ports: list, include_conflicts: bool = False) \
            -> list:
        """Connect ports of elements by IFC relations.

        This method uses IfcRelConnects relations to establish connections
        between ports. It can include conflicting connections in the output
        if specified.

        Args:
            ports: list of ports to be connected
            include_conflicts: if true, conflicts are included. Defaults to
                false.

        Returns:
            connections: list of tuples of ports that are connected.
        """
        connections = []
        port_mapping = {port.guid: port for port in ports}
        for port in ports:
            if not port.ifc:
                continue
            connected_ports = [conn.RelatingPort for conn in
                               port.ifc.ConnectedFrom] + [conn.RelatedPort for
                                                          conn in
                                                          port.ifc.ConnectedTo]
            if connected_ports:
                other_port = None
                if len(connected_ports) > 1:
                    # conflicts
                    quality_logger.warning("%s has multiple connections",
                                           port.ifc)
                    possibilities = []
                    for connected_port in connected_ports:
                        possible_port = port_mapping.get(
                            connected_port.GlobalId)

                        if possible_port.parent is not None:
                            possibilities.append(possible_port)

                    # solving conflicts
                    if include_conflicts:
                        for poss in possibilities:
                            connections.append((port, poss))
                    else:
                        if len(possibilities) == 1:
                            other_port = possibilities[0]
                            quality_logger.info(
                                "Solved by ignoring deleted connection.")
                        else:
                            quality_logger.error(
                                "Unable to solve conflicting connections. "
                                "Continue without connecting %s", port.ifc)
                else:
                    # explicit
                    other_port = port_mapping.get(connected_ports[0].GlobalId)
                if other_port:
                    if port.parent and other_port.parent:
                        connections.append((port, other_port))
                    else:
                        quality_logger.debug(
                            "Not connecting ports without parent (%s, %s)",
                            port,
                            other_port
                        )
        return connections

    @staticmethod
    def confirm_connections_position(connections: list, eps: float = 1)\
            -> Tuple[list, list, list]:
        """Checks distance between port positions.

        The method uses the 'port_distance' function from 'ConnectElements'
        to calculate distances. If distance < eps, the connection is
        confirmed otherwise rejected.

        Args:
            connections: list of connections to be checked.
            eps: distance tolerance for which connections are either confirmed
                or rejected. Defaults to 1.

        Returns:
            tuple of lists of connections (confirmed, unconfirmed, rejected)
        """
        confirmed = []
        unconfirmed = []
        rejected = []
        for port1, port2 in connections:
            delta = ConnectElements.port_distance(port1, port2)
            if delta is None:
                unconfirmed.append((port1, port2))
            elif max(abs(delta)) < eps:
                confirmed.append((port1, port2))
            else:
                rejected.append((port1, port2))
        return confirmed, unconfirmed, rejected

    @staticmethod
    def port_distance(port1: Port, port2: Port) -> np.array:
        """Calculates distance (delta in x, y, z) of ports.

        Args:
            port1: the first port.
            port2: the seconds port.

        Returns:
            delta: distance between port1 and port2 in x, y, z coordinates.
        """
        try:
            delta = port1.position - port2.position
        except AttributeError:
            delta = None
        return delta

    @staticmethod
    def connections_by_position(ports: Generator, eps: float = 10) -> list:
        """Connect ports of elements by computing geometric distance.

        The method uses geometric distance between ports to establish
        connections. If multiple candidates are found for a port, the method
        prioritizes the closest one.

        Args:
            ports: A generator of ports to be connected.
            eps: distance tolerance for which ports are connected. Defaults
                to 10.

        Returns:
            list of tuples of ports that are connected.
        """
        graph = nx.Graph()
        for port1, port2 in itertools.combinations(ports, 2):
            if port1.parent == port2.parent:
                continue
            delta = ConnectElements.port_distance(port1, port2)
            if delta is None:
                continue
            abs_delta = max(abs(delta))
            if abs_delta < eps:
                graph.add_edge(port1, port2, delta=abs_delta)

        # verify
        conflicts = [port for port, deg in graph.degree() if deg > 1]
        for port in conflicts:
            candidates = sorted(graph.edges(port, data=True),
                                key=lambda t: t[2].get('delta', eps)
                                )
            # initially there are at least two candidates, but there will be
            # less, if previous conflicts belong to them
            if len(candidates) <= 1:
                # no action required
                continue
            quality_logger.warning(
                "Found %d geometrically close ports around %s. Details: %s",
                len(candidates), port, candidates)
            if candidates[0][2]['delta'] < candidates[1][2]['delta']:
                # keep first
                first = 1
                quality_logger.info(
                    "Accept closest ports with delta %d as connection "
                    "(%s - %s)",
                    candidates[0][2]['delta'],
                    candidates[0][0],
                    candidates[0][1]
                )
            else:
                # remove all
                first = 0
                quality_logger.warning(
                    "No connection determined, because there are no two "
                    "closest ports.")
            for cand in candidates[first:]:
                graph.remove_edge(cand[0], cand[1])

        return list(graph.edges())

    @staticmethod
    def check_inner_connections(elements: Iterable[ProductBased]) -> \
            Generator[DecisionBunch, None, None]:
        """Check inner connections of HVACProducts.

        Args:
            elements: An iterable of elements, where each element is a subclass
                of ProductBased.

        Yields:
            Yields decisions to set inner connections.

        """
        # TODO: if a lot of decisions occur, it would help to merge
        #  DecisionBunches before yielding them
        for element in elements:
            if isinstance(element, hvac.HVACProduct) \
                    and not element.inner_connections:
                yield from element.decide_inner_connections()

    @staticmethod
    def connections_by_boundingbox(open_ports, elements):
        """Search for open ports in elements bounding boxes.

        This is especially useful for vessel like elements with variable
        number of ports (and bad ifc export) or proxy elements.
        Missing ports on element side are created on demand."""

        # TODO: implement
        connections = []
        return connections
