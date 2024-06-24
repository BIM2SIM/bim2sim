from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.elements.bps_elements import (InnerWall, Floor, OuterWall,
                                           GroundFloor, Roof)


class ResolveTypeMismatch(ITask):
    """Resolves issues with types, run() method holds detailed information."""
    reads = ('elements', 'space_boundaries', 'disaggregations', 'tz_elements')
    # todo touches

    def run(self, elements, space_boundaries, disaggregations, tz_elements):
        """Resolves issues with types by using SpaceBoundary information.

        ...
        """
        # TODO make filter_elements have a list input as well to simplify and
        #  speed this up after merge
        inner_walls = filter_elements(disaggregations, InnerWall)
        floors = filter_elements(disaggregations, Floor)
        interior_elements = inner_walls + floors
        # TODO as material enrichment is run before, we need to change the
        #  sequence of tasks and the way disaggregation and elements are
        #  handle. Otherwise we still have the wrong material
        for tz in tz_elements.values():
            for bound_ele in tz.bound_elements:
                # check if current element is interior
                if bound_ele in interior_elements:
                    # check whether SB is nevertheless external
                    if any([sb.is_external for sb in
                            bound_ele.space_boundaries]):
                        if hasattr(bound_ele, 'parent'):
                            ifc = bound_ele.parent.ifc
                        else:
                            ifc = bound_ele.ifc
                        if isinstance(bound_ele, InnerWall):
                            self.logger.info(
                                f"Corrected type of IFC entity "
                                f"{ifc} from "
                                f"{bound_ele.__class__.__name__} to "
                                f"{OuterWall.__name__} based on"
                                    f" SpaceBoundary data")
                            bound_ele.__class__ = OuterWall
                        if isinstance(bound_ele, Floor):
                            if all([top_bottom == "TOP" for top_bottom in
                                    bound_ele.top_bottom]):
                                self.logger.info(
                                    f"Corrected type of IFC entity "
                                    f"{ifc} from "
                                    f"{bound_ele.__class__.__name__} to "
                                    f"{Roof.__name__} based on"
                                    f" SpaceBoundary data")
                                bound_ele.__class__ = Roof
                            elif all([top_bottom == "BOTTOM" for top_bottom in
                                      bound_ele.top_bottom]):
                                self.logger.info(
                                    f"Corrected type of IFC entity "
                                    f"{ifc} from "
                                    f"{bound_ele.__class__.__name__} to "
                                    f"{GroundFloor.__name__} based on"
                                    f" SpaceBoundary data")
                                bound_ele.__class__ = GroundFloor
                            else:
                                self.logger.warning(
                                    f"Found mismatching type for {bound_ele}, "
                                    f"but can't correct it due to unclear "
                                    f"information in Space Boundaries. ")
        # ToDo: unify where elements are stored, related to project:
        #  "Refactor element creation task"
