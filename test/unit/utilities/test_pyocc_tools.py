import unittest

from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.TopoDS import TopoDS_Face
from OCC.Core.gp import gp_Pnt, gp_XYZ

from bim2sim.utilities.pyocc_tools import PyOCCTools


class TestOCCTools(unittest.TestCase):
    """Unittests for bim2sim OCC Tools"""
    def test_face_from_pnts_tuples(self):
        """Test if face can be created from coordinate tuple."""
        pnt_list = [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)]
        face = PyOCCTools.make_faces_from_pnts(pnt_list)
        self.assertIsInstance(face, TopoDS_Face)

    def test_face_from_pnts_gp_pnts(self):
        """Test if face can be created from gp_Pnt."""
        pnt_list = [gp_Pnt(gp_XYZ(0, 0, 0)), gp_Pnt(gp_XYZ(10, 0, 0)),
                    gp_Pnt(gp_XYZ(10, 10, 0)), gp_Pnt(gp_XYZ(0, 10, 0))]
        face = PyOCCTools.make_faces_from_pnts(pnt_list)
        self.assertIsInstance(face, TopoDS_Face)

    def test_get_points_of_face(self):
        """Test if points from face are returned correctly."""
        pnt_list = [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)]
        face = PyOCCTools.make_faces_from_pnts(pnt_list)
        pnts = PyOCCTools.get_points_of_face(face)
        self.assertEqual(4, len(pnts))
        for p in pnts:
            self.assertIsInstance(p, gp_Pnt)

    def test_remove_collinear_vertices(self):
        """Test if collinear points are removed correctly."""
        pnt_list1 = [(0, 0, 0), (5, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)]
        pnt_list2 = [(0, 0, 0), (5, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0),
                     (0, 5, 0)]
        face1 = PyOCCTools.make_faces_from_pnts(pnt_list1)
        face2 = PyOCCTools.make_faces_from_pnts(pnt_list2)
        pnts1 = PyOCCTools.get_points_of_face(face1)
        pnts2 = PyOCCTools.get_points_of_face(face2)

        new_pnts1 = PyOCCTools.remove_collinear_vertices2(pnts1)
        new_pnts2 = PyOCCTools.remove_collinear_vertices2(pnts2)

        self.assertEqual(5, len(pnts1))
        self.assertEqual(6, len(pnts2))
        self.assertEqual(4, len(new_pnts1))
        self.assertEqual(4, len(new_pnts2))
        for p in new_pnts1:
            self.assertIsInstance(p, gp_Pnt)
        for p in new_pnts2:
            self.assertIsInstance(p, gp_Pnt)

    def test_remove_coincident_vertices(self):
        """ test if coincident points are removed correctly """
        pnt_list1 = [(0, 0, 0), (0.001, 0, 0), (10, 0, 0), (10, 10, 0),
                     (0, 10, 0)]
        pnt_list2 = [(-0.01, 0, 0), (0, 0, 0), (10, 0, 0), (10, 10, 0),
                     (0, 10, 0), (0, 10.01, 0)]
        face1 = PyOCCTools.make_faces_from_pnts(pnt_list1)
        face2 = PyOCCTools.make_faces_from_pnts(pnt_list2)
        pnts1 = PyOCCTools.get_points_of_face(face1)
        pnts2 = PyOCCTools.get_points_of_face(face2)

        new_pnts1 = PyOCCTools.remove_coincident_vertices(pnts1)
        new_pnts2 = PyOCCTools.remove_coincident_vertices(pnts2)

        self.assertEqual(5, len(pnts1))
        self.assertEqual(6, len(pnts2))
        self.assertEqual(4, len(new_pnts1))
        self.assertEqual(4, len(new_pnts2))
        for p in new_pnts1:
            self.assertIsInstance(p, gp_Pnt)
        for p in new_pnts2:
            self.assertIsInstance(p, gp_Pnt)

    def test_obj2_in_obj1(self):
        """test if obj2 in obj1 is detected correctly."""
        obj1 = BRepPrimAPI_MakeBox(5., 10., 15.).Shape()
        obj2 = BRepPrimAPI_MakeBox(-5., -10., -15.).Shape()
        obj3 = BRepPrimAPI_MakeBox(1., 1., 1.).Shape()

        obj2_in_obj1 = PyOCCTools.obj2_in_obj1(obj1, obj2)
        obj3_in_obj1 = PyOCCTools.obj2_in_obj1(obj1, obj3)
        obj1_in_obj3 = PyOCCTools.obj2_in_obj1(obj3, obj1)

        self.assertEqual(False, obj2_in_obj1)
        self.assertEqual(True, obj3_in_obj1)
        self.assertEqual(False, obj1_in_obj3)


if __name__ == '__main__':
    unittest.main()
