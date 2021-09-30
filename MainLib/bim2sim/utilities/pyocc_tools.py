
import numpy as np

from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepBndLib import brepbndlib_Add
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeEdge, \
    BRepBuilderAPI_MakeVertex, BRepBuilderAPI_Transform
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.BRepGProp import brepgprop_SurfaceProperties, brepgprop_LinearProperties
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.BRepTools import BRepTools_WireExplorer
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from OCC.Core.GProp import GProp_GProps
from OCC.Core.GeomAPI import GeomAPI_ProjectPointOnCurve
from OCC.Core.ShapeAnalysis import ShapeAnalysis_ShapeContents
from OCC.Core.ShapeFix import ShapeFix_Face, ShapeFix_Shape
from OCC.Core.TopAbs import TopAbs_WIRE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods_Wire
from OCC.Core.gp import gp_XYZ, gp_Pnt, gp_Trsf, gp_Vec


class PyOCCTools:
    """Class for Tools handling and modifying Python OCC Shapes"""
    @staticmethod
    def remove_vertex_duplicates(vert_list):
        for i, vert in enumerate(vert_list):
            edge_pp_p = BRepBuilderAPI_MakeEdge(vert_list[(i) % (len(vert_list) - 1)],
                                                vert_list[(i + 1) % (len(vert_list) - 1)]).Shape()
            distance = BRepExtrema_DistShapeShape(vert_list[(i + 2) % (len(vert_list) - 1)], edge_pp_p,
                                                  Extrema_ExtFlag_MIN)
            if 0 < distance.Value() < 0.001:
                # first: project close vertex to edge
                edge = BRepBuilderAPI_MakeEdge(vert_list[(i) % (len(vert_list) - 1)],
                                               vert_list[(i + 1) % (len(vert_list) - 1)]).Edge()
                projector = GeomAPI_ProjectPointOnCurve(BRep_Tool.Pnt(vert_list[(i + 2) % (len(vert_list) - 1)]),
                                                        BRep_Tool.Curve(edge)[0])
                np = projector.NearestPoint()
                vert_list[(i + 2) % (len(vert_list) - 1)] = BRepBuilderAPI_MakeVertex(np).Vertex()
                # delete additional vertex
                vert_list.pop((i + 1) % (len(vert_list) - 1))
        return vert_list

    @staticmethod
    def remove_collinear_vertices(vert_list):
        vert_list = vert_list[:-1]
        if len(vert_list) < 5:
            return vert_list
        for i, vert in enumerate(vert_list):
            vert_dist = BRepExtrema_DistShapeShape(vert_list[(i) % (len(vert_list))],
                                                   vert_list[(i + 2) % (len(vert_list))],
                                                   Extrema_ExtFlag_MIN).Value()
            if vert_dist < 1e-3:
                return vert_list
            edge_pp_p = BRepBuilderAPI_MakeEdge(vert_list[(i) % (len(vert_list))],
                                                vert_list[(i + 2) % (len(vert_list))]).Shape()
            distance = BRepExtrema_DistShapeShape(vert_list[(i + 1) % (len(vert_list))], edge_pp_p,
                                                  Extrema_ExtFlag_MIN).Value()
            if distance < 1e-3:
                vert_list.pop((i + 1) % (len(vert_list)))

        vert_list.append(vert_list[0])
        return vert_list

    @staticmethod
    def remove_coincident_vertices(vert_list):
        tol_dist = 1e-2
        new_list = []
        v_b = np.array(vert_list[-1].Coord())
        for i, vert in enumerate(vert_list):
            v = np.array(vert.Coord())
            d_b = np.linalg.norm(v - v_b)
            if d_b > tol_dist:
                new_list.append(vert)
                v_b = v
            # else:
            #     print("Coincident points")
        return new_list

    @staticmethod
    def remove_collinear_vertices2(vert_list):
        tol_cross = 1e-3
        new_list = []

        for i, vert in enumerate(vert_list):
            v = np.array(vert.Coord())
            v_b = np.array(vert_list[(i-1) % (len(vert_list))].Coord())
            v_f = np.array(vert_list[(i+1) % (len(vert_list))].Coord())
            v1 = v-v_b
            v2 = v_f-v_b
            if np.linalg.norm(np.cross(v1, v2)) / np.linalg.norm(v2) > tol_cross:
                new_list.append(vert)
        return new_list

    @staticmethod
    def make_faces_from_pnts(pnt_list):
        """
        This function returns a TopoDS_Face from list of gp_Pnt
        :param pnt_list: list of gp_Pnt or Coordinate-Tuples
        :return: TopoDS_Face
        """
        an_edge = []
        if isinstance(pnt_list[0], tuple):
            new_list = []
            for pnt in pnt_list:
                new_list.append(gp_Pnt(gp_XYZ(pnt[0], pnt[1], pnt[2])))
            pnt_list = new_list
        for i in range(len(pnt_list)):
            edge = BRepBuilderAPI_MakeEdge(pnt_list[i], pnt_list[(i + 1) % len(pnt_list)]).Edge()
            an_edge.append(edge)
        a_wire = BRepBuilderAPI_MakeWire()
        for edge in an_edge:
            a_wire.Add(edge)
        a_wire = a_wire.Wire()
        a_face = BRepBuilderAPI_MakeFace(a_wire).Face()
        return a_face

    @staticmethod
    def make_face_from_vertex_list(vert_list):
        an_edge = []
        for i in range(len(vert_list[:-1])):
            edge = BRepBuilderAPI_MakeEdge(vert_list[i], vert_list[i + 1]).Edge()
            an_edge.append(edge)
        a_wire = BRepBuilderAPI_MakeWire()
        for edge in an_edge:
            a_wire.Add(edge)
        a_wire = a_wire.Wire()
        a_face = BRepBuilderAPI_MakeFace(a_wire).Face()

        return a_face  # .Reversed()

    @staticmethod
    def get_vertex_list_from_face(face):
        an_exp = TopExp_Explorer(face, TopAbs_WIRE)
        vert_list = []
        while an_exp.More():
            wire = topods_Wire(an_exp.Current())
            w_exp = BRepTools_WireExplorer(wire)
            while w_exp.More():
                vert1 = w_exp.CurrentVertex()
                vert_list.append(vert1)
                w_exp.Next()
            an_exp.Next()
        vert_list.append(vert_list[0])

        return vert_list

    @staticmethod
    def get_number_of_vertices(shape):
        shape_analysis = ShapeAnalysis_ShapeContents()
        shape_analysis.Perform(shape)
        nb_vertex = shape_analysis.NbVertices()

        return nb_vertex

    @staticmethod
    def get_points_of_face(shape):
        """
        This function returns a list of gp_Pnt of a Surface
        :param face: TopoDS_Shape (Surface)
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
    def get_center_of_face(face):
        """
        Calculates the center of the given face. The center point is the center of mass.
        """
        prop = GProp_GProps()
        brepgprop_SurfaceProperties(face, prop)
        return prop.CentreOfMass()

    @staticmethod
    def get_center_of_edge(edge):
        """
        Calculates the center of the given edge. The center point is the center of mass.
        """
        prop = GProp_GProps()
        brepgprop_LinearProperties(edge, prop)
        return prop.CentreOfMass()

    @staticmethod
    def scale_face(face, factor):
        """
        Scales the given face by the given factor, using the center of mass of the face as origin of the transformation.
        """
        center = PyOCCTools.get_center_of_face(face)
        trsf = gp_Trsf()
        trsf.SetScale(center, factor)
        return BRepBuilderAPI_Transform(face, trsf).Shape()

    @staticmethod
    def scale_edge(edge, factor):
        """
        Scales the given edge by the given factor, using the center of mass of the edge as origin of the transformation.
        """
        center = PyOCCTools.get_center_of_edge(edge)
        trsf = gp_Trsf()
        trsf.SetScale(center, factor)
        return BRepBuilderAPI_Transform(edge, trsf).Shape()

    @staticmethod
    def make_solid_box_shape(shape):
        box = Bnd_Box()
        brepbndlib_Add(shape, box)
        solid_box = BRepPrimAPI_MakeBox(box.CornerMin(), box.CornerMax()).Solid()
        return solid_box

    @staticmethod
    def fix_face(face, tolerance=1e-3):
        fix = ShapeFix_Face(face)
        fix.SetMaxTolerance(tolerance)
        fix.Perform()
        return fix.Face()

    @staticmethod
    def fix_shape(shape, tolerance=1e-3):
        fix = ShapeFix_Shape(shape)
        fix.SetFixFreeShellMode(True)
        sf = fix.FixShellTool()
        fix.LimitTolerance(tolerance)
        fix.Perform()
        return fix.Shape()

    @staticmethod
    def _move_bound_in_direction_of_normal(bound, move_dist, reversed=False):
        prod_vec = []
        move_dir = bound.bound_normal.Coord()
        if reversed:
            move_dir = bound.bound_normal.Reversed().Coord()
        for i in move_dir:
            prod_vec.append(move_dist * i)
        # move bound in direction of bound normal by move_dist
        trsf = gp_Trsf()
        coord = gp_XYZ(*prod_vec)
        vec = gp_Vec(coord)
        trsf.SetTranslation(vec)
        bound.bound_shape_cl = BRepBuilderAPI_Transform(bound.bound_shape, trsf).Shape()
        return trsf

    @staticmethod
    def _compare_direction_of_normals(normal1, normal2):
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