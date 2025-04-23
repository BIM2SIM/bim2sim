from bim2sim.elements.bps_elements import OuterWall, InnerWall, Roof, \
    InnerFloor, GroundFloor, SpaceBoundaryNoBuildElem
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.types import BoundaryOrientation


class CreateElementsFromSB(ITask):
    reads = ('elements',)
    touches = ('elements',)

    def run(self, elements):
        if not self.playground.sim_settings.create_elements_from_sb:
            self.logger.warning(
                "Skipping task CreateElementsFromSB as sim_setting "
                "'create_elements_from_sb' is set to False."
            )
            return

        sbs_without_element = filter_elements(
            elements, 'SpaceBoundaryNoBuildElem')

        # Container with conditions and for results
        # top_bottom, is_external: resulting cls
        element_lists = {
            (BoundaryOrientation.vertical, True): (OuterWall, []),
            (BoundaryOrientation.vertical, False): (InnerWall, []),
            (BoundaryOrientation.top, True): (Roof, []),
            (BoundaryOrientation.top, False): (InnerFloor, []),
            (BoundaryOrientation.bottom, True): (GroundFloor, []),
            (BoundaryOrientation.bottom, False): (InnerFloor, [])
        }

        for sb_ele in sbs_without_element:
            # TODO for now set all to physical
            sb_ele.physical = True
            key = (sb_ele.top_bottom, sb_ele.is_external)
            cls, lst = element_lists.get(key, (None, None))
            if cls is not None:
                element = cls()
                element.space_boundaries.append(sb_ele)
                sb_ele.bound_element = element
                lst.append(element)
                # add element to elements dict
                elements[element.guid] = element

        inner_floors_from_sb = (
                element_lists[(BoundaryOrientation.top, False)][1] +
                element_lists[(BoundaryOrientation.bottom, False)][1]
        )
        self.logger.info(
            "Created elements from SpaceBoundaries:\n"
            f"  - "
            f"{len(element_lists[(BoundaryOrientation.vertical, True)][1])} "
            f"OuterWalls\n"
            f"  - "
            f"{len(element_lists[(BoundaryOrientation.vertical, False)][1])} "
            f"InnerWalls\n"
            f"  - {len(element_lists[(BoundaryOrientation.top, True)][1])} "
            f"Roofs\n"
            f"  - {len(inner_floors_from_sb)} InnerFloors\n"
            f"  - "
            f"{len(element_lists[(BoundaryOrientation.bottom, True)][1])} "
            f"GroundFloors"
        )
        return elements,
