"""
Common tools for handling OCC Shapes within the bim2sim project.
"""
from typing import List, Tuple, Union

import numpy as np

from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace, \
    BRepBuilderAPI_Transform, BRepBuilderAPI_MakePolygon
from OCC.Core.BRepGProp import brepgprop_SurfaceProperties, \
    brepgprop_LinearProperties, brepgprop_VolumeProperties
from OCC.Core.BRepTools import BRepTools_WireExplorer
from OCC.Core.GProp import GProp_GProps
from OCC.Core.Geom import Handle_Geom_Plane_DownCast
from OCC.Core.ShapeAnalysis import ShapeAnalysis_ShapeContents
from OCC.Core.ShapeFix import ShapeFix_Face, ShapeFix_Shape
from OCC.Core.TopAbs import TopAbs_WIRE, TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods_Wire, TopoDS_Face, TopoDS_Shape, \
    topods_Face, TopoDS_Edge
from OCC.Core.gp import gp_XYZ, gp_Pnt, gp_Trsf, gp_Vec


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
    def _get_center_of_face(face: TopoDS_Face) -> gp_Pnt:
        """
        Calculates the center of the given face. The center point is the center
        of mass.
        """
        prop = GProp_GProps()
        brepgprop_SurfaceProperties(face, prop)
        return prop.CentreOfMass()

    @staticmethod
    def _get_center_of_edge(edge):
        """
        Calculates the center of the given edge. The center point is the center
        of mass.
        """
        prop = GProp_GProps()
        brepgprop_LinearProperties(edge, prop)
        return prop.CentreOfMass()

    @staticmethod
    def scale_face(face: TopoDS_Face, factor: float) -> TopoDS_Shape:
        """
        Scales the given face by the given factor, using the center of mass of
        the face as origin of the transformation.
        """
        center = PyOCCTools._get_center_of_face(face)
        trsf = gp_Trsf()
        trsf.SetScale(center, factor)
        return BRepBuilderAPI_Transform(face, trsf).Shape()

    @staticmethod
    def scale_edge(edge: TopoDS_Edge, factor: float) -> TopoDS_Shape:
        """
        Scales the given edge by the given factor, using the center of mass of
        the edge as origin of the transformation.
        """
        center = PyOCCTools._get_center_of_edge(edge)
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
                                          reverse=False) -> TopoDS_Shape:
        """Move a BIM2SIM Space Boundary in the direction of its surface
        normal by a given distance."""
        prod_vec = []
        move_dir = bound.bound_normal.Coord()
        if reverse:
            move_dir = bound.bound_normal.Reversed().Coord()
        for i in move_dir:
            prod_vec.append(move_dist * i)
        # move bound in direction of bound normal by move_dist
        trsf = gp_Trsf()
        coord = gp_XYZ(*prod_vec)
        vec = gp_Vec(coord)
        trsf.SetTranslation(vec)
        new_shape = BRepBuilderAPI_Transform(bound.bound_shape, trsf).Shape()
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
    def simple_face_normal(face: TopoDS_Face) -> gp_XYZ:
        """Compute the normal of a TopoDS_Face."""
        face = PyOCCTools.get_face_from_shape(face)
        surf = BRep_Tool.Surface(face)
        obj = surf
        assert obj.DynamicType().Name() == "Geom_Plane"
        plane = Handle_Geom_Plane_DownCast(surf)
        face_prop = GProp_GProps()
        brepgprop_SurfaceProperties(face, face_prop)
        face_normal = plane.Axis().Direction().XYZ()
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
