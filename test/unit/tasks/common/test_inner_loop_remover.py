import unittest

from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut

from bim2sim.tasks.common.inner_loop_remover import convex_decomposition_base
from bim2sim.utilities.pyocc_tools import PyOCCTools


class TestInnerLoopRemover(unittest.TestCase):
    def test_simple_convex_polygon(self):
        points = [(1.0, 1.0, 0.0), (5.0, 1.0, 0.0), (5.0, 5.0, 0.0), (1.0, 5.0, 0.0)]
        shape = PyOCCTools.make_faces_from_pnts(points)

        result = convex_decomposition_base(shape)
        self.assertEqual(result, [points])

    def test_polygon_with_single_reflex(self):
        shape = PyOCCTools.make_faces_from_pnts([(1.0, 1.0, 0.0), (5.0, 1.0, 0.0), (2.0, 2.0, 0.0), (1.0, 5.0, 0.0)])

        result = convex_decomposition_base(shape)
        self.assertEqual(result, [
            [(5.0, 1.0, 0.0), (2.0, 2.0, 0.0), (1.0, 1.0, 0.0)],
            [(1.0, 5.0, 0.0), (1.0, 1.0, 0.0), (2.0, 2.0, 0.0)]
        ])

    def test_bigger_polygon_with_single_reflex(self):
        points = [(1.0, 1.0, 0.0), (3.0, 0.0, 0.0), (5.0, 1.0, 0.0), (2.0, 2.0, 0.0), (1.0, 5.0, 0.0)]
        shape = PyOCCTools.make_faces_from_pnts(points)

        result = convex_decomposition_base(shape)
        self.assertEqual(result, [
            [(2.0, 2.0, 0.0), (1.0, 1.0, 0.0), (3.0, 0.0, 0.0), (5.0, 1.0, 0.0)],
            [(1.0, 5.0, 0.0), (1.0, 1.0, 0.0), (2.0, 2.0, 0.0)]
        ])

    def test_convex_polygon_with_single_hole(self):
        big_rect = PyOCCTools.make_faces_from_pnts([(1, 1, 0), (5, 1, 0), (5, 5, 0), (1, 5, 0)])
        small_rect = PyOCCTools.make_faces_from_pnts([(2, 2, 0), (3, 2, 0), (3, 3, 0), (2, 3, 0)])
        shape = BRepAlgoAPI_Cut(big_rect, small_rect).Shape()

        result = convex_decomposition_base(shape)
        self.assertEqual(result, [
            [(3.0, 2.0, 0.0), (2.0, 2.0, 0.0), (1.0, 1.0, 0.0), (5.0, 1.0, 0.0)],
            [(1.0, 1.0, 0.0), (2.0, 2.0, 0.0), (2.0, 3.0, 0.0), (1.0, 5.0, 0.0)],
            [(3.0, 3.0, 0.0), (3.0, 2.0, 0.0), (5.0, 1.0, 0.0), (5.0, 5.0, 0.0)],
            [(1.0, 5.0, 0.0), (2.0, 3.0, 0.0), (3.0, 3.0, 0.0), (5.0, 5.0, 0.0)]
        ])

    def test_polygon_with_reflex_and_single_hole(self):
        big_shape = PyOCCTools.make_faces_from_pnts([(1, 1, 0), (5, 1, 0), (5, 5, 0), (3, 4, 0), (1, 5, 0)])
        small_rect = PyOCCTools.make_faces_from_pnts([(2, 2, 0), (3, 2, 0), (3, 3, 0), (2, 3, 0)])
        shape = BRepAlgoAPI_Cut(big_shape, small_rect).Shape()

        result = convex_decomposition_base(shape)
        self.assertEqual(result, [
            [(1.0, 1.0, 0.0), (2.0, 2.0, 0.0), (2.0, 3.0, 0.0), (1.0, 5.0, 0.0)],
            [(3.0, 2.0, 0.0), (2.0, 2.0, 0.0), (1.0, 1.0, 0.0), (5.0, 1.0, 0.0)],
            [(3.0, 3.0, 0.0), (3.0, 2.0, 0.0), (5.0, 1.0, 0.0), (5.0, 5.0, 0.0), (3.0, 4.0, 0.0)],
            [(2.0, 3.0, 0.0), (3.0, 3.0, 0.0), (3.0, 4.0, 0.0), (1.0, 5.0, 0.0)]
        ])

    def test_polygon_with_reflexes_and_multiple_holes(self):
        big_shape = PyOCCTools.make_faces_from_pnts([(1, 1, 0), (2, 1.5, 0), (5, 1, 0), (5, 5, 0), (1, 5, 0), (1.5, 4, 0)])
        small_rect = PyOCCTools.make_faces_from_pnts([(2, 2, 0), (3, 2, 0), (3, 3, 0), (2, 3, 0)])
        extra_small_rect = PyOCCTools.make_faces_from_pnts([(2, 4, 0), (2, 3.5, 0), (2.5, 3.5, 0), (2.5, 4, 0)])
        small_trig = PyOCCTools.make_faces_from_pnts([(4, 3, 0), (4, 4, 0), (3, 4, 0)])
        shape = BRepAlgoAPI_Cut(big_shape, small_rect).Shape()
        shape = BRepAlgoAPI_Cut(shape, extra_small_rect).Shape()
        shape = BRepAlgoAPI_Cut(shape, small_trig).Shape()

        result = convex_decomposition_base(shape)
        self.assertEqual(result, [
            [(1.5, 4.0, 0.0), (1.0, 1.0, 0.0), (2.0, 1.5, 0.0), (2.0, 2.0, 0.0), (2.0, 3.0, 0.0), (2.0, 3.5, 0.0), (2.0, 4.0, 0.0)],
            [(3.0, 2.0, 0.0), (2.0, 2.0, 0.0), (2.0, 1.5, 0.0), (5.0, 1.0, 0.0)],
            [(5.0, 5.0, 0.0), (1.0, 5.0, 0.0), (1.5, 4.0, 0.0), (2.0, 4.0, 0.0), (2.5, 4.0, 0.0), (3.0, 4.0, 0.0), (4.0, 4.0, 0.0)],
            [(2.0, 3.0, 0.0), (3.0, 3.0, 0.0), (2.5, 3.5, 0.0), (2.0, 3.5, 0.0)],
            [(3.0, 4.0, 0.0), (2.5, 4.0, 0.0), (2.5, 3.5, 0.0), (3.0, 3.0, 0.0), (4.0, 3.0, 0.0)],
            [(4.0, 3.0, 0.0), (3.0, 3.0, 0.0), (3.0, 2.0, 0.0), (5.0, 1.0, 0.0)],
            [(5.0, 5.0, 0.0), (4.0, 4.0, 0.0), (4.0, 3.0, 0.0), (5.0, 1.0, 0.0)]
        ])
