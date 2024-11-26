from bim2sim.elements.graphs.hvac_graph import HvacGraph
from bim2sim.tasks.base import ITask
import logging
from bim2sim.kernel.decision import BoolDecision, DecisionBunch
from bim2sim.utilities.types import FlowSide


logger = logging.getLogger(__name__)


class EnrichFlowDirection(ITask):

    reads = ('graph', )

    def run(self, graph: HvacGraph):
        yield from self.set_flow_sides(graph)
        print('test')

    #Todo Continue here #733
    def set_flow_sides(self, graph: HvacGraph):
        """ Set flow sides for ports in HVAC graph based on known flow sides.

        This function iteratively sets flow sides for ports in the HVAC graph.
        It uses a recursive method (`recurse_set_unknown_sides`) to determine
        the flow side for each unset port. The function may prompt the user
        for decisions in case of conflicts or unknown sides.

        Args:
             graph: The HVAC graph.

        Yields:
            DecisionBunch: A collection of decisions may be yielded during the
                task.
        """
        # TODO: needs testing!
        # TODO: at least one master element required
        print('test')
        accepted = []
        while True:
            unset_port = None
            for port in list(graph.nodes):
                if port.flow_side == FlowSide.unknown and graph.graph[port] \
                        and port not in accepted:
                    unset_port = port
                    break
            if unset_port:
                side, visited, masters = self.recurse_set_unknown_sides(
                    unset_port)
                if side in (-1, 1):
                    # apply suggestions
                    for port in visited:
                        port.flow_side = side
                elif side == 0:
                    # TODO: ask user?
                    accepted.extend(visited)
                elif masters:
                    # ask user to fix conflicts (and retry in next while loop)
                    for port in masters:
                        decision = BoolDecision(
                            "Use %r as VL (y) or RL (n)?" % port,
                            global_key= "Use_port_%s" % port.guid)
                        yield DecisionBunch([decision])
                        use = decision.value
                        if use:
                            port.flow_side = 1
                        else:
                            port.flow_side = -1
                else:
                    # can not be solved (no conflicting masters)
                    # TODO: ask user?
                    accepted.extend(visited)
            else:
                # done
                logging.info("Flow_side set")
                break

    # TODO not used yet
    def recurse_set_side(self, port, side, known: dict = None,
                         raise_error=True):
        """Recursive set flow_side to connected ports"""
        if known is None:
            known = {}

        # set side suggestion
        is_known = port in known
        current_side = known.get(port, port.flow_side)
        if not is_known:
            known[port] = side
        elif is_known and current_side == side:
            return known
        else:
            # conflict
            if raise_error:
                raise AssertionError("Conflicting flow_side in %r" % port)
            else:
                logger.error("Conflicting flow_side in %r", port)
                known[port] = None
                return known

        # call neighbours
        for neigh in self.neighbors(port):
            if (neigh.parent.is_consumer() or neigh.parent.is_generator()) \
                    and port.parent is neigh.parent:
                # switch flag over consumers / generators
                self.recurse_set_side(neigh, -side, known, raise_error)
            else:
                self.recurse_set_side(neigh, side, known, raise_error)

        return known

    def recurse_set_unknown_sides(self, port, visited: list = None,
                                  masters: list = None):
        """Recursive checks neighbours flow_side.
        :returns tuple of
            common flow_side (None if conflict)
            list of checked ports
            list of ports on which flow_side s are determined"""

        if visited is None:
            visited = []
        if masters is None:
            masters = []

        # mark as visited to prevent deadloops
        visited.append(port)

        if port.flow_side in (-1, 1):
            # use port with known flow_side as master
            masters.append(port)
            return port.flow_side, visited, masters

        # call neighbours
        neighbour_sides = {}
        for neigh in self.neighbors(port):
            if neigh not in visited:
                if (neigh.parent.is_consumer() or neigh.parent.is_generator()) \
                        and port.parent is neigh.parent:
                    # switch flag over consumers / generators
                    side, _, _ = self.recurse_set_unknown_sides(
                        neigh, visited, masters)
                    side = -side
                else:
                    side, _, _ = self.recurse_set_unknown_sides(
                        neigh, visited, masters)
                neighbour_sides[neigh] = side

        sides = set(neighbour_sides.values())
        if not sides:
            return port.flow_side, visited, masters
        elif len(sides) == 1:
            # all neighbours have same site
            side = sides.pop()
            return side, visited, masters
        elif len(sides) == 2 and 0 in sides:
            side = (sides - {0}).pop()
            return side, visited, masters
        else:
            # conflict
            return None, visited, masters



