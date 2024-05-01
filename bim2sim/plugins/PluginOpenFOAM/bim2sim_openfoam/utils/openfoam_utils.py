import OCC.Core.TopoDS
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape

from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.pyocc_tools import PyOCCTools
import math


class OpenFOAMUtils:
    @staticmethod
    def split_openfoam_elements(openfoam_elements: dict) -> tuple[list, list,
    list]:
        stl_bounds = filter_elements(openfoam_elements, 'StlBound')
        heaters = filter_elements(openfoam_elements, 'Heater')
        air_terminals = filter_elements(openfoam_elements, 'AirTerminal')
        return stl_bounds, heaters, air_terminals

    @staticmethod
    def get_refinement_level(dist: float, bM_size: float) -> list:
        '''
        Computes the refinement level based on the desired
        refined cell size and the blockMesh cell size.
        bM_size/2^X = min_dist
        '''
        ref_level = math.log(bM_size/dist)/math.log(2)
        ref_level = math.ceil(ref_level)
        return [ref_level, ref_level+2]

    @staticmethod
    def get_min_refdist_between_shapes(shape1: OCC.Core.TopoDS.TopoDS_Shape,
                                       shape2: OCC.Core.TopoDS.TopoDS_Shape,
                                       dist_bound=0.01) -> float:
        """
        Computes the minimal distance between two TopoDS Shapes and returns
        the distance divided by 3 such that in the refinement zone,
        there will be 3 cells in between two objects. Optional argument
        dist_bound can specify a maximal minimal distance (default: 1mm).
        """
        extrema = BRepExtrema_DistShapeShape(shape1, shape2)
        extrema.Perform()
        dist = extrema.Value()
        # To ensure correctness of all boundary conditions, there must be at
        # least 3 cells between the object and the wall.
        min_dist = dist / 3
        if min_dist > dist_bound or min_dist == 0:
            min_dist = dist_bound
        return min_dist

    @staticmethod
    def get_min_internal_dist(obj: OCC.Core.TopoDS.TopoDS_Shape) -> float:
        """
        Computes the minimal internal distance of a TopoDS Shape.
        """
        face_list = (PyOCCTools.get_faces_from_shape(obj))
        points = []
        for face in face_list:
            points.extend(PyOCCTools.get_points_of_face(face))
        mindist = 0.05
        for i, p1 in enumerate(points):
            for p2 in points[i:]:
                dist = p1.Distance(p2)
                if mindist > dist > 5e-04:
                    mindist = dist
        return mindist

