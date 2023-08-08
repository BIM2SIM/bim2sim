"""Create 2b space boundaries to fill gaps in spaces.

This module generates space boundaries of type 2b to fill gaps in the space
surrounding space boundaries. The resulting set of space boundaries should
form a watertight shape.
"""

import logging

import ifcopenshell
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from OCC.Core.TopoDS import TopoDS_Face
from OCC.Core.gp import gp_Pnt

from bim2sim.elements.bps_elements import SpaceBoundary2B, ThermalZone, Door, \
    Window
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import get_spaces_with_bounds
from bim2sim.utilities.pyocc_tools import PyOCCTools
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.task \
    import EPGeomPreprocessing

logger = logging.getLogger(__name__)


class AddSpaceBoundaries2B(ITask):
    """Exports an EnergyPlus model based on IFC information"""

    reads = ('instances',)
    touches = ('instances',)

    def run(self, instances):
        """Run the generation of 2b space boundaries. """
        try:
            inst_2b = self._compute_2b_bound_gaps(instances)
            EPGeomPreprocessing.split_non_convex_bounds(
                EPGeomPreprocessing(self.playground),
                inst_2b,
                self.playground.sim_settings.split_bounds)
        except Exception as ex:
            logger.warning(f"Unexpected {ex=}. No 2b Space Boundaries added."
                           f" {type(ex)=}")
            return instances,
        instances.update(inst_2b)

        return instances,

    def _compute_2b_bound_gaps(self, instances: dict)\
            -> dict[str:SpaceBoundary2B]:
        """Compute 2b space boundaries for gaps between 2a space boundaries.

        This function computes 2b space boundaries for non-watertight sets of
        space boundaries of type 2a. The 2b generation algorithm cuts all
        individual existing space boundary shapes from the space shape. The
        resulting surfaces close the gaps in the space boundary shapes. These
        new shapes are assigned to be shapes of type 2b for simplicity. The
        algorithm could be further improved by a verification of the space
        boundary type (type 2a or 2b).

        Args:
            instances: dict[guid: element]

        Returns:
            dict[guid: SpaceBoundary2B]
        """
        logger.info("Generate space boundaries of type 2B")
        inst_2b = dict()
        spaces = get_spaces_with_bounds(instances)
        for space_obj in spaces:
            # compare surface area of IfcSpace shape with sum of space
            # boundary shapes of this thermal zone.
            space_surf_area = PyOCCTools.get_shape_area(space_obj.space_shape)
            sb_area = 0
            for bound in space_obj.space_boundaries:
                if bound.parent_bound:
                    continue
                sb_area += PyOCCTools.get_shape_area(bound.bound_shape)
            if (space_surf_area - sb_area) < 1e-2:
                continue
            # spaces which reach this point have gaps in their boundaries.
            space_obj.b_bound_shape = space_obj.space_shape
            for bound in space_obj.space_boundaries:
                if bound.bound_area.m == 0:
                    continue
                if PyOCCTools.get_shape_area(space_obj.b_bound_shape) == 0:
                    continue
                # exclude surfaces that are too far from space shape.
                distance = BRepExtrema_DistShapeShape(
                    space_obj.b_bound_shape,
                    bound.bound_shape,
                    Extrema_ExtFlag_MIN).Value()
                if distance > 1e-6:
                    continue
                # cut the current shape from the (leftover) space shape.
                space_obj.b_bound_shape = BRepAlgoAPI_Cut(
                    space_obj.b_bound_shape, bound.bound_shape).Shape()
            # extract faces from the leftover shape.
            faces = PyOCCTools.get_faces_from_shape(space_obj.b_bound_shape)
            if faces:
                # create a new 2b space boundary for each face..
                inst_2b.update(self.create_2b_space_boundaries(faces, space_obj))
        return inst_2b

    @staticmethod
    def create_2b_space_boundaries(faces: list[TopoDS_Face],
                                   space_obj: ThermalZone)\
            -> dict[str: SpaceBoundary2B]:
        """Create new 2b space boundaries.

        Create a new 2b space boundary for each face in the list and
        assign it to the space instance.

        Args:
            faces: list of TopoDS_Face
            space_obj: ThermalZone instance

        Returns:
            dict[guid: SpaceBoundary2B]

        """
        settings = ifcopenshell.geom.main.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings.set(settings.INCLUDE_CURVES, True)
        inst_2b = dict()
        space_obj.space_boundaries_2B = []
        bound_obj = []

        # generate a list of IFCBased instances (e.g. Wall) that are the
        # space surrounding elements. Initialize a shape (geometry) for these
        # instances.
        for bound in space_obj.space_boundaries:
            if bound.bound_instance and bound.bound_instance.ifc.Representation:
                bi = bound.bound_instance.ifc
                bound.bound_instance.shape = ifcopenshell.geom.create_shape(
                    settings, bi).geometry
                bound_obj.append(bound.bound_instance)

        for i, face in enumerate(faces):
            b_bound = SpaceBoundary2B()
            b_bound.bound_shape = face
            if b_bound.bound_area.m < 1e-3:
                continue
            b_bound.guid = ifcopenshell.guid.new()
            b_bound.bound_thermal_zone = space_obj
            # get the building element that is bounded by the current 2b bound
            for instance in bound_obj:
                if isinstance(instance, Door) or isinstance(instance, Window):
                    continue
                center_shape = BRepBuilderAPI_MakeVertex(
                    gp_Pnt(b_bound.bound_center)).Shape()
                distance = BRepExtrema_DistShapeShape(
                    center_shape, instance.shape, Extrema_ExtFlag_MIN).Value()
                if distance < 1e-3:
                    b_bound.bound_instance = instance
                    break
            space_obj.space_boundaries_2B.append(b_bound)
            inst_2b[b_bound.guid] = b_bound
        return inst_2b
