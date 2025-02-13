"""
Common tools for handling OCC Shapes within the bim2sim project.
"""
import math
from typing import List, Tuple, Union

import numpy as np
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_MakeOffsetShape
from OCC.Core.GeomAPI import GeomAPI_IntCS
from OCC.Core.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from scipy.spatial import KDTree
from OCC.Core.BRepBndLib import brepbndlib_Add
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace, \
    BRepBuilderAPI_Transform, BRepBuilderAPI_MakePolygon, \
    BRepBuilderAPI_MakeShell, BRepBuilderAPI_MakeSolid, BRepBuilderAPI_Sewing, \
    BRepBuilderAPI_MakeVertex
from OCC.Core.BRepClass3d import BRepClass3d_SolidClassifier
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.BRepGProp import brepgprop_SurfaceProperties, \
    brepgprop_LinearProperties, brepgprop_VolumeProperties, BRepGProp_Face
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakePrism
from OCC.Core.BRepTools import BRepTools_WireExplorer
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from OCC.Core.GProp import GProp_GProps
from OCC.Core.Geom import Handle_Geom_Plane_DownCast, Geom_Line, \
    Handle_Geom_Curve_DownCast, Handle_Geom_Surface_DownCast
from OCC.Core.ShapeAnalysis import ShapeAnalysis_ShapeContents
from OCC.Core.ShapeFix import ShapeFix_Face, ShapeFix_Shape
from OCC.Core.TopAbs import TopAbs_WIRE, TopAbs_FACE, TopAbs_OUT
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods_Wire, TopoDS_Face, TopoDS_Shape, \
    topods_Face, TopoDS_Edge, TopoDS_Solid, TopoDS_Shell, TopoDS_Builder, \
    TopoDS_Compound
from OCC.Core.gp import gp_XYZ, gp_Pnt, gp_Trsf, gp_Vec, gp_Ax1, gp_Dir, gp_Lin


class PyOCCTools:
    """Class for Tools handling and modifying Python OCC Shapes"""

    @staticmethod
    def remove_coincident_vertices(vert_list: List[gp_Pnt]) -> List[gp_Pnt]:
        """ remove coincident vertices from list of gp_Pnt.
        Vertices are coincident if closer than tolerance."""
        tol_dist = 1e-2
        new_list = []
        v_b = np.array(vert_list[-1].Coord())
        for vert in vert_list:
            v = np.array(vert.Coord())
            d_b = np.linalg.norm(v - v_b)
            if d_b > tol_dist:
                new_list.append(vert)
                v_b = v
        return new_list

    @staticmethod
    def remove_collinear_vertices2(vert_list: List[gp_Pnt]) -> List[gp_Pnt]:
        """ remove collinear vertices from list of gp_Pnt.
        Vertices are collinear if cross product less tolerance."""
        tol_cross = 1e-3
        new_list = []

        for i, vert in enumerate(vert_list):
            v = np.array(vert.Coord())
            v_b = np.array(vert_list[(i - 1) % (len(vert_list))].Coord())
            v_f = np.array(vert_list[(i + 1) % (len(vert_list))].Coord())
            v1 = v - v_b
            v2 = v_f - v_b
            if np.linalg.norm(np.cross(v1, v2)) / np.linalg.norm(
                    v2) > tol_cross:
                new_list.append(vert)
        return new_list

    @staticmethod
    def make_faces_from_pnts(
            pnt_list: Union[List[Tuple[float]], List[gp_Pnt]]) -> TopoDS_Face:
        """
        This function returns a TopoDS_Face from list of gp_Pnt
        :param pnt_list: list of gp_Pnt or Coordinate-Tuples
        :return: TopoDS_Face
        """
        if isinstance(pnt_list[0], tuple):
            new_list = []
            for pnt in pnt_list:
                new_list.append(gp_Pnt(gp_XYZ(pnt[0], pnt[1], pnt[2])))
            pnt_list = new_list
        poly = BRepBuilderAPI_MakePolygon()
        for coord in pnt_list:
            poly.Add(coord)
        poly.Close()
        a_wire = poly.Wire()
        a_face = BRepBuilderAPI_MakeFace(a_wire).Face()
        return a_face

    @staticmethod
    def get_number_of_vertices(shape: TopoDS_Shape) -> int:
        """ get number of vertices of a shape"""
        shape_analysis = ShapeAnalysis_ShapeContents()
        shape_analysis.Perform(shape)
        nb_vertex = shape_analysis.NbVertices()

        return nb_vertex

    @staticmethod
    def get_number_of_faces(shape: TopoDS_Shape) -> int:
        """ get number of faces of a shape"""
        shape_analysis = ShapeAnalysis_ShapeContents()
        shape_analysis.Perform(shape)
        nb_faces = shape_analysis.NbFaces()

        return nb_faces

    @staticmethod
    def get_points_of_face(shape: TopoDS_Shape) -> List[gp_Pnt]:
        """
        This function returns a list of gp_Pnt of a Surface
        :param shape: TopoDS_Shape (Surface)
        :return: pnt_list (list of gp_Pnt)
        """
        an_exp = TopExp_Explorer(shape, TopAbs_WIRE)
        pnt_list = []
        while an_exp.More():
            wire = topods_Wire(an_exp.Current())
            w_exp = BRepTools_WireExplorer(wire)
            while w_exp.More():
                pnt1 = BRep_Tool.Pnt(w_exp.CurrentVertex())
                pnt_list.append(pnt1)
                w_exp.Next()
            an_exp.Next()
        return pnt_list

    @staticmethod
    def get_center_of_face(face: TopoDS_Face) -> gp_Pnt:
        """
        Calculates the center of the given face. The center point is the center
        of mass.
        """
        prop = GProp_GProps()
        brepgprop_SurfaceProperties(face, prop)
        return prop.CentreOfMass()

    @staticmethod
    def get_center_of_shape(shape: TopoDS_Shape) -> gp_Pnt:
        """
        Calculates the center of the given shape. The center point is the
        center of mass.
        """
        prop = GProp_GProps()
        brepgprop_VolumeProperties(shape, prop)
        return prop.CentreOfMass()

    @staticmethod
    def get_center_of_edge(edge):
        """
        Calculates the center of the given edge. The center point is the center
        of mass.
        """
        prop = GProp_GProps()
        brepgprop_LinearProperties(edge, prop)
        return prop.CentreOfMass()

    @staticmethod
    def get_center_of_volume(volume: TopoDS_Shape) -> gp_Pnt:
        """Compute the center of mass of a TopoDS_Shape volume.

        Args:
            volume: TopoDS_Shape

        Returns: gp_Pnt of the center of mass
        """
        prop = GProp_GProps()
        brepgprop_VolumeProperties(volume, prop)
        return prop.CentreOfMass()

    @staticmethod
    def scale_face(face: TopoDS_Face, factor: float,
                   predefined_center: gp_Pnt = None) -> TopoDS_Shape:
        """
        Scales the given face by the given factor, using the center of mass of
        the face as origin of the transformation. If another center than the
        center of mass should be used for the origin of the transformation,
        set the predefined_center.
        """
        if not predefined_center:
            center = PyOCCTools.get_center_of_face(face)
        else:
            center = predefined_center
        trsf = gp_Trsf()
        trsf.SetScale(center, factor)
        return BRepBuilderAPI_Transform(face, trsf).Shape()

    @staticmethod
    def scale_shape(shape: TopoDS_Shape, factor: float,
                    predefined_center: gp_Pnt = None) -> TopoDS_Shape:
        """
        Scales the given shape by the given factor, using the center of mass of
        the shape as origin of the transformation. If another center than the
        center of mass should be used for the origin of the transformation,
        set the predefined_center.
        """
        if not predefined_center:
            center = PyOCCTools.get_center_of_volume(shape)
        else:
            center = predefined_center
        trsf = gp_Trsf()
        trsf.SetScale(center, factor)
        return BRepBuilderAPI_Transform(shape, trsf).Shape()

    @staticmethod
    def scale_shape_absolute(shape: TopoDS_Shape, scale_in_meters: float,
                             predefined_center: gp_Pnt = None):
        """
        Scales the given shape by the given distance in all directions.
        Using the center of mass of the shape as origin of the
        transformation. If another center than the center of mass should be
        used for the origin of the transformation,
        set the predefined_center.
        Args:
            shape:
            scale_in_meters: scale in meters, scaling is applied in each
            direction.
            predefined_center:

        Returns:

        """
        (min_x, min_y, min_z), (max_x, max_y, max_z) = (
            PyOCCTools.simple_bounding_box(shape))
        original_size = min(max_x - min_x, max_y - min_y, max_z - min_z)
        new_size = original_size + scale_in_meters * 2
        scaling_factor = new_size / original_size
        return PyOCCTools.scale_shape(shape, scaling_factor)

    @staticmethod
    def scale_edge(edge: TopoDS_Edge, factor: float) -> TopoDS_Shape:
        """
        Scales the given edge by the given factor, using the center of mass of
        the edge as origin of the transformation.
        """
        center = PyOCCTools.get_center_of_edge(edge)
        trsf = gp_Trsf()
        trsf.SetScale(center, factor)
        return BRepBuilderAPI_Transform(edge, trsf).Shape()

    @staticmethod
    def fix_face(face: TopoDS_Face, tolerance=1e-3) -> TopoDS_Face:
        """Apply shape healing on a face."""
        fix = ShapeFix_Face(face)
        fix.SetMaxTolerance(tolerance)
        fix.Perform()
        return fix.Face()

    @staticmethod
    def fix_shape(shape: TopoDS_Shape, tolerance=1e-3) -> TopoDS_Shape:
        """Apply shape healing on a shape."""
        fix = ShapeFix_Shape(shape)
        fix.SetFixFreeShellMode(True)
        fix.LimitTolerance(tolerance)
        fix.Perform()
        return fix.Shape()

    @staticmethod
    def move_bound_in_direction_of_normal(bound, move_dist: float,
                                          reverse=False, move_dir:
            gp_Dir=None) -> (TopoDS_Shape):
        """Move a BIM2SIM Space Boundary in the direction of its surface
        normal by a given distance."""
        if not move_dir:
            if isinstance(bound, TopoDS_Shape):
                bound_normal = PyOCCTools.simple_face_normal(bound)
                bound_shape = bound
            else:
                bound_normal = bound.bound_normal
                bound_shape = bound.bound_shape
            move_dir = bound_normal.Coord()
        else:
            move_dir = move_dir.Coord()
            bound_shape=bound
        prod_vec = []
        if reverse:
            move_dir = gp_Vec(*move_dir).Reversed().Coord()
        for i in move_dir:
            prod_vec.append(move_dist * i)
        # move bound in direction of bound normal by move_dist
        trsf = gp_Trsf()
        coord = gp_XYZ(*prod_vec)
        vec = gp_Vec(coord)
        trsf.SetTranslation(vec)
        new_shape = BRepBuilderAPI_Transform(bound_shape, trsf).Shape()
        return new_shape

    @staticmethod
    def compare_direction_of_normals(normal1: gp_XYZ, normal2: gp_XYZ) -> bool:
        """
        Compare the direction of two surface normals (vectors).
        True, if direction is same or reversed
        :param normal1: first normal (gp_Pnt)
        :param normal2: second normal (gp_Pnt)
        :return: True/False
        """
        dotp = normal1.Dot(normal2)
        check = False
        if 1 - 1e-2 < dotp ** 2 < 1 + 1e-2:
            check = True
        return check

    @staticmethod
    def _a2p(o, z, x):
        """Compute Axis of Local Placement of an IfcProducts Objectplacement"""
        y = np.cross(z, x)
        r = np.eye(4)
        r[:-1, :-1] = x, y, z
        r[-1, :-1] = o
        return r.T

    @staticmethod
    def _axis2placement(plc):
        """Get Axis of Local Placement of an IfcProducts Objectplacement"""
        z = np.array(plc.Axis.DirectionRatios if plc.Axis else (0, 0, 1))
        x = np.array(
            plc.RefDirection.DirectionRatios if plc.RefDirection else (1, 0, 0))
        o = plc.Location.Coordinates
        return PyOCCTools._a2p(o, z, x)

    @staticmethod
    def local_placement(plc):
        """Get Local Placement of an IfcProducts Objectplacement"""
        if plc.PlacementRelTo is None:
            parent = np.eye(4)
        else:
            parent = PyOCCTools.local_placement(plc.PlacementRelTo)
        return np.dot(PyOCCTools._axis2placement(plc.RelativePlacement), parent)

    @staticmethod
    def simple_face_normal(face: TopoDS_Face, check_orientation: bool = True) \
            -> gp_XYZ:
        """Compute the normal of a TopoDS_Face."""
        face = PyOCCTools.get_face_from_shape(face)
        surf = BRep_Tool.Surface(face)
        obj = surf
        assert obj.DynamicType().Name() == "Geom_Plane"
        plane = Handle_Geom_Plane_DownCast(surf)
        face_normal = plane.Axis().Direction().XYZ()
        if check_orientation:
            if face.Orientation() == 1:
                face_normal = face_normal.Reversed()
        return face_normal

    @staticmethod
    def flip_orientation_of_face(face: TopoDS_Face) -> TopoDS_Face:
        """Flip the orientation of a TopoDS_Face."""
        face = face.Reversed()
        return face

    @staticmethod
    def get_face_from_shape(shape: TopoDS_Shape) -> TopoDS_Face:
        """Return first face of a TopoDS_Shape."""
        exp = TopExp_Explorer(shape, TopAbs_FACE)
        face = exp.Current()
        try:
            face = topods_Face(face)
        except:
            exp1 = TopExp_Explorer(shape, TopAbs_WIRE)
            wire = exp1.Current()
            face = BRepBuilderAPI_MakeFace(wire).Face()
        return face

    @staticmethod
    def get_faces_from_shape(shape: TopoDS_Shape) -> List[TopoDS_Face]:
        """Return all faces from a shape."""
        faces = []
        an_exp = TopExp_Explorer(shape, TopAbs_FACE)
        while an_exp.More():
            face = topods_Face(an_exp.Current())
            faces.append(face)
            an_exp.Next()
        return faces

    @staticmethod
    def get_shape_area(shape: TopoDS_Shape) -> float:
        """compute area of a space boundary"""
        bound_prop = GProp_GProps()
        brepgprop_SurfaceProperties(shape, bound_prop)
        area = bound_prop.Mass()
        return area

    @staticmethod
    def remove_coincident_and_collinear_points_from_face(
            face: TopoDS_Face) -> TopoDS_Face:
        """
        removes collinear and coincident vertices iff resulting number of
        vertices is > 3, so a valid face can be build.
        """
        org_area = PyOCCTools.get_shape_area(face)
        pnt_list = PyOCCTools.get_points_of_face(face)
        pnt_list_new = PyOCCTools.remove_coincident_vertices(pnt_list)
        pnt_list_new = PyOCCTools.remove_collinear_vertices2(pnt_list_new)
        if pnt_list_new != pnt_list:
            if len(pnt_list_new) < 3:
                pnt_list_new = pnt_list
            new_face = PyOCCTools.make_faces_from_pnts(pnt_list_new)
            new_area = (PyOCCTools.get_shape_area(new_face))
            if abs(new_area - org_area) < 5e-3:
                face = new_face
        return face

    @staticmethod
    def get_shape_volume(shape: TopoDS_Shape) -> float:
        """
        This function computes the volume of a shape and returns the value as a
        float.
        Args:
            shape: TopoDS_Shape
        Returns:
            volume: float
        """
        props = GProp_GProps()
        brepgprop_VolumeProperties(shape, props)
        volume = props.Mass()
        return volume

    @staticmethod
    def sew_shapes(shape_list: list[TopoDS_Shape], tolerance=0.0001) -> (
            TopoDS_Shape):
        sew = BRepBuilderAPI_Sewing(tolerance)
        for shp in shape_list:
            sew.Add(shp)
        sew.Perform()
        return sew.SewedShape()

    @staticmethod
    def get_points_of_minimum_shape_distance(
            shape1: TopoDS_Shape, shape2: TopoDS_Shape) -> list[list[gp_Pnt,
    gp_Pnt, float]]:
        """
        Compute points of minimum distance.

        Returns list of [point on first shape, point on second shape,
        distance between these points].
        """
        minimum_point_pairs = []
        extrema = BRepExtrema_DistShapeShape(shape1, shape2,
                                             Extrema_ExtFlag_MIN)
        # Perform the computation
        extrema.Perform()
        # Check if the computation was successful
        if extrema.IsDone():
            # Get the number of solution pairs (usually 1 for minimum distance)
            nb_extrema = extrema.NbSolution()
            # print(f"Number of minimum distance solutions: {nb_extrema}")
            for i in range(1,
                           nb_extrema + 1):  # OpenCASCADE is 1-based indexing
                # Retrieve the points on each shape
                p1 = extrema.PointOnShape1(i)
                p2 = extrema.PointOnShape2(i)
                minimum_point_pairs.append([p1, p2, extrema.Value()])
        return minimum_point_pairs

    @staticmethod
    def get_points_of_minimum_point_shape_distance(
            point: gp_Pnt, shape: TopoDS_Shape) -> list[list[gp_Pnt, gp_Pnt,
    float]]:

        vertex = BRepBuilderAPI_MakeVertex(point).Vertex()
        minimum_point_pairs = PyOCCTools.get_points_of_minimum_shape_distance(
            vertex, shape)
        return minimum_point_pairs

    @staticmethod
    def move_bounds_to_vertical_pos(bound_list: list(),
                                    base_face: TopoDS_Face) -> list[
        TopoDS_Shape]:
        new_shape_list = []
        for bound in bound_list:
            if not isinstance(bound, TopoDS_Shape):
                bound_shape = bound.bound_shape
            else:
                bound_shape = bound
            distance = BRepExtrema_DistShapeShape(base_face,
                                                  bound_shape,
                                                  Extrema_ExtFlag_MIN).Value()
            if abs(distance) > 1e-4:
                new_shape = PyOCCTools.move_bound_in_direction_of_normal(
                    bound, distance)
                if abs(BRepExtrema_DistShapeShape(
                        base_face, new_shape, Extrema_ExtFlag_MIN).Value()) \
                        > 1e-4:
                    new_shape = PyOCCTools.move_bound_in_direction_of_normal(
                        bound, distance, reverse=True)
            else:
                new_shape = bound_shape
            new_shape_list.append(new_shape)
        return new_shape_list

    @staticmethod
    def get_footprint_of_shape(shape: TopoDS_Shape) -> TopoDS_Face:
        """
        Calculate the footprint of a TopoDS_Shape.
        """
        footprint_shapes = []
        return_shape = None
        faces = PyOCCTools.get_faces_from_shape(shape)
        for face in faces:
            prop = BRepGProp_Face(face)
            p = gp_Pnt()
            normal_direction = gp_Vec()
            prop.Normal(0., 0., p, normal_direction)
            if abs(1 - normal_direction.Z()) < 1e-4:
                footprint_shapes.append(face)
        if len(footprint_shapes) == 0:
            for face in faces:
                prop = BRepGProp_Face(face)
                p = gp_Pnt()
                normal_direction = gp_Vec()
                prop.Normal(0., 0., p, normal_direction)
                if abs(1 - abs(normal_direction.Z())) < 1e-4:
                    footprint_shapes.append(face)
        if len(footprint_shapes) == 1:
            return_shape = footprint_shapes[0]
        elif len(footprint_shapes) > 1:
            bbox = Bnd_Box()
            brepbndlib_Add(shape, bbox)
            xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
            bbox_ground_face = PyOCCTools.make_faces_from_pnts(
                [(xmin, ymin, zmin),
                 (xmin, ymax, zmin),
                 (xmax, ymax, zmin),
                 (xmax, ymin, zmin)]
            )
            footprint_shapes = PyOCCTools.move_bounds_to_vertical_pos(
                footprint_shapes, bbox_ground_face)

            return_shape = PyOCCTools.sew_shapes(footprint_shapes)
        return return_shape

    @staticmethod
    def triangulate_bound_shape(shape: TopoDS_Shape,
                                cut_shapes: list[TopoDS_Shape] = []) \
            -> TopoDS_Shape:
        """Triangulate bound shape.

        Args:
            shape: TopoDS_Shape
            cut_shapes: list of TopoDS_Shape
        Returns:
            Triangulated TopoDS_Shape

        """
        if cut_shapes:
            for cut_shape in cut_shapes:
                shape = BRepAlgoAPI_Cut(
                    shape, cut_shape).Shape()
        triang_face = BRepMesh_IncrementalMesh(shape, 1)
        return triang_face.Shape()

    @staticmethod
    def check_pnt_in_solid(solid: TopoDS_Solid, pnt: gp_Pnt, tol=1.0e-6) \
            -> bool:
        """Check if a gp_Pnt is inside a TopoDS_Solid.

        This method checks if a gp_Pnt is included in a TopoDS_Solid. Returns
        True if gp_Pnt is included, else False.

        Args:
            solid: TopoDS_Solid where the gp_Pnt should be included
            pnt: gp_Pnt that is tested
            tol: tolerance, default is set to 1e-6

        Returns: True if gp_Pnt is included in TopoDS_Solid, else False
        """
        pnt_in_solid = False
        classifier = BRepClass3d_SolidClassifier()
        classifier.Load(solid)
        classifier.Perform(pnt, tol)

        if not classifier.State() == TopAbs_OUT:  # check if center is in solid
            pnt_in_solid = True
        return pnt_in_solid

    @staticmethod
    def make_shell_from_faces(faces: list[TopoDS_Face]) -> TopoDS_Shell:
        """Creates a TopoDS_Shell from a list of TopoDS_Face.

        Args:
            faces: list of TopoDS_Face

        Returns: TopoDS_Shell
        """
        shell = BRepBuilderAPI_MakeShell()
        shell = shell.Shell()
        builder = TopoDS_Builder()
        builder.MakeShell(shell)

        for face in faces:
            builder.Add(shell, face)
        return shell

    @staticmethod
    def make_solid_from_shell(shell: TopoDS_Shell) -> TopoDS_Solid:
        """Create a TopoDS_Solid from a given TopoDS_Shell.

        Args:
            shell: TopoDS_Shell

        Returns: TopoDS_Solid
        """
        solid = BRepBuilderAPI_MakeSolid()
        solid.Add(shell)
        return solid.Solid()

    def make_solid_from_shape(self, base_shape: TopoDS_Shape) -> TopoDS_Solid:
        """Make a TopoDS_Solid from a TopoDS_Shape.

        Args:
            base_shape: TopoDS_Shape

        Returns: TopoDS_Solid

        """
        faces = self.get_faces_from_shape(base_shape)
        shell = self.make_shell_from_faces(faces)
        return self.make_solid_from_shell(shell)

    @staticmethod
    def obj2_in_obj1(obj1: TopoDS_Shape, obj2: TopoDS_Shape) -> bool:
        """ Checks if the center of obj2 is actually in the shape of obj1.

        This method is used to compute if the center of mass of a TopoDS_Shape
        is included in another TopoDS_Shape. This can be used to determine,
        if a HVAC element (e.g., IfcSpaceHeater) is included in the
        TopoDS_Shape of an IfcSpace.

        Args:
            obj1: TopoDS_Shape of the larger element (e.g., IfcSpace)
            obj2: TopoDS_Shape of the smaller element (e.g., IfcSpaceHeater,
                IfcAirTerminal)

        Returns: True if obj2 is in obj1, else False
        """
        faces = PyOCCTools.get_faces_from_shape(obj1)
        shell = PyOCCTools.make_shell_from_faces(faces)
        obj1_solid = PyOCCTools.make_solid_from_shell(shell)
        obj2_center = PyOCCTools.get_center_of_volume(obj2)

        return PyOCCTools.check_pnt_in_solid(obj1_solid, obj2_center)

    @staticmethod
    def get_minimal_bounding_box(shape):
        # Create an empty bounding box
        bbox = Bnd_Box()

        an_exp = TopExp_Explorer(shape, TopAbs_FACE)
        while an_exp.More():
            face = topods_Face(an_exp.Current())
            brepbndlib_Add(face, bbox)
            an_exp.Next()

        # Get the minimal bounding box
        min_x, min_y, min_z, max_x, max_y, max_z = bbox.Get()

        return (min_x, min_y, min_z), (max_x, max_y, max_z)

    @staticmethod
    def simple_bounding_box(shapes: Union[TopoDS_Shape, List[TopoDS_Shape]]) \
            -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """Simple Bounding box.

         Return min_max_coordinates of a simple Bounding box, either from a
         single TopoDS_Shape or a list of TopoDS_Shapes
         """
        bbox = Bnd_Box()
        if isinstance(shapes, TopoDS_Shape):
            brepbndlib_Add(shapes, bbox)
        else:
            for shape in shapes:
                brepbndlib_Add(shape, bbox)
        min_x, min_y, min_z, max_x, max_y, max_z = bbox.Get()

        return (min_x, min_y, min_z), (max_x, max_y, max_z)

    @staticmethod
    def simple_bounding_box_shape(
            shapes: Union[TopoDS_Shape, List[TopoDS_Shape]]):
        min_box, max_box = PyOCCTools.simple_bounding_box(shapes)
        return BRepPrimAPI_MakeBox(gp_Pnt(*min_box), gp_Pnt(*max_box)).Shape()

    @staticmethod
    def get_unique_vertices(edges: list) -> list:
        """Get unique vertices from a list of edges."""
        unique_vertices = []
        for edge in edges:
            for vertex in edge:
                if vertex not in unique_vertices:
                    unique_vertices.append(vertex)
        unique_vertices = [gp_Pnt(v[0], v[1], v[2]) for v in unique_vertices]
        return unique_vertices

    @staticmethod
    def remove_sides_of_bounding_box(shape, cut_top=False, cut_bottom=True,
                                     cut_left=False, cut_right=False,
                                     cut_back=False, cut_front=False):
        shape_list = []
        removed_list = []
        bbox_shape = PyOCCTools.simple_bounding_box(shape)
        top_surface_min_max = ((bbox_shape[0][0],
                                bbox_shape[0][1],
                                bbox_shape[1][2]),
                               (bbox_shape[1][0],
                                bbox_shape[1][1],
                                bbox_shape[1][2]))
        top_surface = PyOCCTools.make_faces_from_pnts([
            gp_Pnt(*top_surface_min_max[0]),
            gp_Pnt(top_surface_min_max[1][0],
                   top_surface_min_max[0][1],
                   top_surface_min_max[0][2]),
            gp_Pnt(*top_surface_min_max[1]),
            gp_Pnt(top_surface_min_max[0][0],
                   top_surface_min_max[1][1],
                   top_surface_min_max[1][2])])
        if not cut_top:
            shape_list.append(top_surface)
        else:
            removed_list.append(top_surface)
        bottom_surface_min_max = ((bbox_shape[0][0],
                                   bbox_shape[0][1],
                                   bbox_shape[0][2]),
                                  (bbox_shape[1][0],
                                   bbox_shape[1][1],
                                   bbox_shape[0][2]))
        bottom_surface = PyOCCTools.make_faces_from_pnts([
            gp_Pnt(*bottom_surface_min_max[0]),
            gp_Pnt(bottom_surface_min_max[1][0],
                   bottom_surface_min_max[0][1],
                   bottom_surface_min_max[0][2]),
            gp_Pnt(*bottom_surface_min_max[1]),
            gp_Pnt(bottom_surface_min_max[0][0],
                   bottom_surface_min_max[1][1],
                   bottom_surface_min_max[1][2])])
        if not cut_bottom:
            shape_list.append(bottom_surface)
        else:
            removed_list.append(bottom_surface)
        front_surface_min_max = (
            bbox_shape[0],
            (bbox_shape[1][0],
             bbox_shape[0][1],
             bbox_shape[1][2]))
        front_surface = PyOCCTools.make_faces_from_pnts([
            gp_Pnt(*front_surface_min_max[0]),
            gp_Pnt(front_surface_min_max[1][0],
                   front_surface_min_max[0][1],
                   front_surface_min_max[0][2]),
            gp_Pnt(*front_surface_min_max[1]),
            gp_Pnt(front_surface_min_max[0][0],
                   front_surface_min_max[0][1],
                   front_surface_min_max[1][2])])
        if not cut_front:
            shape_list.append(front_surface)
        else:
            removed_list.append(front_surface)
        back_surface_min_max = ((bbox_shape[0][0],
                                 bbox_shape[1][1],
                                 bbox_shape[0][2]),
                                bbox_shape[1])
        back_surface = PyOCCTools.make_faces_from_pnts([
            gp_Pnt(*back_surface_min_max[0]),
            gp_Pnt(back_surface_min_max[1][0],
                   back_surface_min_max[0][1],
                   back_surface_min_max[0][2]),
            gp_Pnt(*back_surface_min_max[1]),
            gp_Pnt(back_surface_min_max[0][0],
                   back_surface_min_max[0][1],
                   back_surface_min_max[1][2])])

        if not cut_back:
            shape_list.append(back_surface)
        else:
            removed_list.append(back_surface)
        side_surface_left = PyOCCTools.make_faces_from_pnts([
            gp_Pnt(*back_surface_min_max[0]),
            gp_Pnt(*front_surface_min_max[0]),
            gp_Pnt(front_surface_min_max[0][0],
                   front_surface_min_max[0][1],
                   front_surface_min_max[1][2]),
            gp_Pnt(back_surface_min_max[0][0],
                   back_surface_min_max[0][1],
                   back_surface_min_max[1][2])]
        )
        if not cut_left:
            shape_list.append(side_surface_left)
        else:
            removed_list.append(side_surface_left)
        side_surface_right = PyOCCTools.make_faces_from_pnts([
            gp_Pnt(back_surface_min_max[1][0],
                   back_surface_min_max[1][1],
                   back_surface_min_max[0][2]),
            gp_Pnt(front_surface_min_max[1][0],
                   front_surface_min_max[1][1],
                   front_surface_min_max[0][2]),
            gp_Pnt(*front_surface_min_max[1]),
            gp_Pnt(*back_surface_min_max[1])]
        )
        if not cut_right:
            shape_list.append(side_surface_right)
        else:
            removed_list.append(side_surface_right)
        compound = TopoDS_Compound()
        builder = TopoDS_Builder()
        builder.MakeCompound(compound)
        for shp in shape_list:
            builder.Add(compound, shp)
        return compound, shape_list, removed_list

    @staticmethod
    def rotate_by_deg(shape, axis='z', rotation=90):
        """

        Args:
            shape:
            axis:
            rotation:

        Returns:

        """
        rot_center = PyOCCTools.get_center_of_face(shape)
        rot_ax = None
        if axis == 'x':
            rot_ax = gp_Ax1(rot_center, gp_Dir(1, 0, 0))
        if axis == 'y':
            rot_ax = gp_Ax1(rot_center, gp_Dir(0, 1, 0))
        if axis == 'z':
            rot_ax = gp_Ax1(rot_center, gp_Dir(0, 0, 1))

        trsf = gp_Trsf()
        trsf.SetRotation(rot_ax, rotation * math.pi / 180)
        new_shape = BRepBuilderAPI_Transform(shape, trsf).Shape()
        return new_shape

    @staticmethod
    def sample_points_on_faces(shape, u_samples=10, v_samples=10):
        """
        Generate a grid of points on the surfaces of a shape.
        Parameters:
            - shape: TopoDS_Shape
            - u_samples: Number of samples along the U direction
            - v_samples: Number of samples along the V direction
        Returns:
            A list of (x, y, z) points.
        """
        points = []
        explorer = TopExp_Explorer(shape, TopAbs_FACE)
        while explorer.More():
            face = topods_Face(explorer.Current())
            surface = BRepAdaptor_Surface(face)
            # Get the parameter range of the surface
            u_min, u_max = surface.FirstUParameter(), surface.LastUParameter()
            v_min, v_max = surface.FirstVParameter(), surface.LastVParameter()
            # Generate a grid of parameters
            u_values = np.linspace(u_min, u_max, u_samples)
            v_values = np.linspace(v_min, v_max, v_samples)
            # Evaluate the surface at each grid point
            for u in u_values:
                for v in v_values:
                    pnt = surface.Value(u, v)
                    points.append((pnt.X(), pnt.Y(), pnt.Z()))
            explorer.Next()
        return points

    @staticmethod
    def calculate_point_based_distance(shape1, shape2, final_num_points=1e5):
        num_verts_1 = PyOCCTools.get_number_of_vertices(shape1)
        if num_verts_1 < 5e4:
            num_faces_1 = PyOCCTools.get_number_of_faces(shape1)
            sample_points_per_face = math.floor(math.sqrt((
                                                                  final_num_points - num_verts_1)
                                                          / num_faces_1))
            points_on_shape1 = PyOCCTools.sample_points_on_faces(
                shape1, u_samples=sample_points_per_face,
                v_samples=sample_points_per_face)
        else:
            points_on_shape1 = PyOCCTools.get_points_of_face(shape1)
            points_on_shape1 = [(p.X(), p.Y(), p.Z()) for p in points_on_shape1]

        num_verts_2 = PyOCCTools.get_number_of_vertices(shape2)
        if num_verts_2 < 5e4:
            num_faces_2 = PyOCCTools.get_number_of_faces(shape2)
            sample_points_per_face = math.floor(math.sqrt(
                (final_num_points - num_verts_2) / num_faces_2))
            points_on_shape2 = PyOCCTools.sample_points_on_faces(
                shape2, u_samples=sample_points_per_face,
                v_samples=sample_points_per_face)
        else:
            points_on_shape2 = PyOCCTools.get_points_of_face(shape2)
            points_on_shape2 = [(p.X(), p.Y(), p.Z()) for p in points_on_shape2]

        tree1 = KDTree(points_on_shape1)
        distances, _ = tree1.query(points_on_shape2)
        # print(f"Minimum distance: {min(distances)}")
        return min(distances)

    @staticmethod
    def create_offset_shape(shape, offset, tolerance=0.0001):
        sewing = BRepBuilderAPI_Sewing()
        sewing.SetTolerance(tolerance)
        sewing.Add(shape)
        sewing.Perform()
        sewed_shell = sewing.SewedShape()
        offset_builder = BRepOffsetAPI_MakeOffsetShape()
        offset_builder.PerformBySimple(sewed_shell, offset)
        return offset_builder.Shape()

    @staticmethod
    def unify_shape(shape):
        unify = ShapeUpgrade_UnifySameDomain()
        unify.Initialize(shape)
        unify.Build()
        return unify.Shape()

    @staticmethod
    def enlarge_bounding_box_shape_in_dir(shape, distance=0.05,
                                         direction=gp_Dir(0, 0, 1)):
        (min_box, max_box) = PyOCCTools.simple_bounding_box([shape])
        p1 = BRepBuilderAPI_MakeVertex(gp_Pnt(*min_box)).Vertex()
        moved_p1 = BRep_Tool.Pnt(PyOCCTools.move_bound_in_direction_of_normal(
            p1, distance, move_dir=direction, reverse=True))
        p2 = BRepBuilderAPI_MakeVertex(gp_Pnt(*max_box)).Vertex()
        moved_p2 = BRep_Tool.Pnt(PyOCCTools.move_bound_in_direction_of_normal(
            p2, distance, move_dir=direction, reverse=False))
        new_shape = BRepPrimAPI_MakeBox(moved_p1, moved_p2).Shape()
        return new_shape

    @staticmethod
    def fuse_shapes(shapes:List[TopoDS_Shape]):
        if not shapes:
            return None
        if len(shapes) < 2:
            return shapes[0]
        fuse_shape = shapes[0]
        for shape in shapes[1:]:
            fuse_shape = BRepAlgoAPI_Fuse(fuse_shape, shape).Shape()
        return fuse_shape

    @staticmethod
    def get_projection_of_bounding_box(shapes: list[TopoDS_Shape],
                                       proj_type: Union['x','y','z'],
                                       value:float=None,
                                       ) -> TopoDS_Shape:
        ((x1, y1, z1), (x2, y2, z2)) = PyOCCTools.simple_bounding_box(shapes)
        if proj_type == 'x':
            if not value:
                value = x1
            pnt_list = [(value, y1, z1), (value, y2, z1), (value, y2, z2),
                        (value, y1, z2)]
        elif proj_type == 'y':
            if not value:
                value = y1
            pnt_list = [(x1, value, z1), (x2, value, z1), (x2, value, z2),
                        (x1, value, z2)]
        else:
            if not value:
                value = z1
            pnt_list = [(x1, y1, value), (x2, y1, value), (x2, y2, value),
                        (x1, y2, value)]
        return PyOCCTools.make_faces_from_pnts(pnt_list)

    @staticmethod
    def find_min_distance_along_direction(start_point, direction, shape,
                                          max_distance=1e6):
        """Finds the minimum distance from a start point to a shape along a
        given direction.

        Args:
            start_point (gp_Pnt): The starting point.
            direction (gp_Dir): The direction vector.
            shape (TopoDS_Shape): The target shape.
            max_distance (float, optional): The maximum search distance.
            Defaults to 1e6.

        Returns:
            tuple or (None, None): A tuple containing the distance and
            intersection point, or (None, None) if no intersection is found.
        """
        # Create a Geom_Line (infinite, but we limit it to the maximum distance)
        line = Geom_Line(gp_Lin(start_point, direction))
        # assert line.DynamicType().Name() == "Geom_Curve"
        line_handle = Handle_Geom_Curve_DownCast(line)

        # Explore the faces of the shape
        explorer = TopExp_Explorer(shape, TopAbs_FACE)
        intersections = []

        while explorer.More():
            face = explorer.Current()
            # Get the geometry of the face
            geom_face = BRep_Tool.Surface(face)
            # assert geom_face.DynamicType().Name() == "Geom_Surface"
            surf_handle = Handle_Geom_Surface_DownCast(geom_face)

            # Calculate the intersection between the line and the face
            intersector = GeomAPI_IntCS(line_handle, surf_handle)
            intersector.Perform(line_handle, surf_handle)

            if intersector.IsDone():
                for i in range(1, intersector.NbPoints() + 1):
                    pnt = intersector.Point(i)
                    # Vector from the start point to the intersection point
                    vec = gp_Pnt(start_point.X(), start_point.Y(),
                                 start_point.Z()).Distance(pnt)

                    # Alternatively: Determine if the point lies in the desired direction
                    # Calculate the dot product between (pnt - start_point) and direction
                    delta = gp_Pnt(pnt.X() - start_point.X(),
                                   pnt.Y() - start_point.Y(),
                                   pnt.Z() - start_point.Z())

                    dot = delta.X() * direction.X() + delta.Y() * direction.Y() + delta.Z() * direction.Z()
                    if dot > 0:  # Only points in the direction of the ray
                        intersections.append((start_point.Distance(pnt), pnt))

            explorer.Next()

        if not intersections:
            return None, None  # No intersection found

        # Find the intersection point with the smallest positive distance (dot)
        intersections.sort(key=lambda x: x[0])
        min_distance = intersections[0][0]# / gp_Vec(direction).Magnitude()
        intersection_point = intersections[0][1]

        # Optionally: Limit the search to max_distance
        if min_distance > max_distance:
            return None, None

        return min_distance, intersection_point

    @staticmethod
    def extrude_face_in_direction(shape:TopoDS_Shape, distance:float=0.1,
                                  direction:gp_Dir=gp_Dir(0,0,1),
                                  bidirectional=True):
        extrusion_vec = gp_Vec(
            direction.X()*distance, direction.Y()*distance, direction.Z()*distance
        )
        extrusion = BRepPrimAPI_MakePrism(shape, extrusion_vec).Shape()
        if bidirectional:
            extrusion_vec1 = gp_Vec(
                direction.X() * -distance, direction.Y() * -distance,
                direction.Z() * -distance
            )
            extrusion1 = BRepPrimAPI_MakePrism(shape, extrusion_vec1).Shape()
            extrusion = PyOCCTools.fuse_shapes([extrusion, extrusion1])
        return extrusion

