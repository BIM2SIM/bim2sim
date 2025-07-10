"""
This module contains functions which, given a TopoDS shapes with holes ("inner
loops"), calculate an equivalent shape without holes by adding cuts along
triangulation edges. Using the triangulation as a graph, it finds a spanning
tree between the main polygon and its holes using Kruskal's algorithm
and places the cuts along the edges of this spanning tree.
"""

import logging
import math
from collections import defaultdict
from typing import Tuple, List, Mapping, TypeVar, Generic, Optional

import numpy
# Type aliases that are used throughout this module
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.TopoDS import TopoDS_Iterator, TopoDS_Shape, topods_Face
from OCC.Core.gp import gp_Pnt, gp_XYZ

from bim2sim.utilities.pyocc_tools import PyOCCTools

Vertex = Vector = Tuple[float, float, float]
Edge = Tuple[Vertex, Vertex]
Triangulation = List[List[Vertex]]
Plane = Tuple[Vector, Vector, Vector]
T = TypeVar('T')


class _UnionFind(Generic[T]):
    """
    Implementation of a union-find data structure with union-by-size and path
    compression.
    """

    def __init__(self):
        self._parents = dict()
        self._sizes = dict()

    def union(self, element1: T, element2: T) -> T:
        key1 = self.find(element1)
        key2 = self.find(element2)
        if key1 == key2:
            return
        if self._sizes[key1] < self._sizes[key2]:
            key1, key2 = key2, key1
        self._parents[key2] = key1
        self._sizes[key1] += self._sizes[key2]

    def find(self, element: T) -> T:
        if element not in self._parents:
            self._parents[element] = None
            self._sizes[element] = 1
        root = element
        while self._parents[root] is not None:
            root = self._parents[root]
        while self._parents[element] is not None:
            parent = self._parents[element]
            self._parents[element] = root
            element = parent
        return element


def _gp_pnt_to_coord_tuple(pnt: gp_Pnt) -> Vertex:
    """
    Converts a gp_Pnt instance (3D point class of OCC) to a 3-tuple, because
    we need our vertex type to be comparable and hashable, which gp_Pnt is not.
    """
    return pnt.X(), pnt.Y(), pnt.Z()


def _subshapes(shape):
    it = TopoDS_Iterator(shape)
    clist = []
    while it.More():
        clist.append(_subshapes(it.Value()))
        it.Next()
    return shape if len(clist) == 0 else shape, clist


def _get_triangulation(face: TopoDS_Shape) -> Triangulation:
    """
    Calculates and extracts the triangulation of a TopoDS shape and returns it
    as a list of triangles.
    """
    mesh = BRepMesh_IncrementalMesh(face, 0.01)
    mesh.Perform()
    ex = TopExp_Explorer(mesh.Shape(), TopAbs_FACE)
    bt = BRep_Tool()
    result = []
    while ex.More():
        L = TopLoc_Location()
        triangulation = bt.Triangulation(topods_Face(ex.Current()), L)
        if not triangulation:
            triangulation = bt.Triangulation(PyOCCTools.make_faces_from_pnts(
                PyOCCTools.get_points_of_face(topods_Face(ex.Current()))), L)
            if not triangulation:
                ex.Next()
        triangles = triangulation.Triangles()
        if hasattr(triangulation, 'Nodes'):
            vertices = triangulation.Nodes()
        else:
            vertices = []
            for i in range(1, triangulation.NbNodes() + 1):
                vertices.append(triangulation.Node(i))
        for i in range(1, triangulation.NbTriangles() + 1):
            idx1, idx2, idx3 = triangles.Value(i).Get()
            P1 = vertices[idx1-1].Transformed(L.Transformation())
            P2 = vertices[idx2-1].Transformed(L.Transformation())
            P3 = vertices[idx3-1].Transformed(L.Transformation())
            result.append(
                [_gp_pnt_to_coord_tuple(P1), _gp_pnt_to_coord_tuple(P2),
                 _gp_pnt_to_coord_tuple(P3)])
        ex.Next()
    return result


def _normalize(edge: Edge) -> Edge:
    """
    Edges are normalized so that (a,b) and (b,a) are both returned as (a,b).
    """
    return (edge[0], edge[1]) if edge[0] < edge[1] else (edge[1], edge[0])


def _iterate_edges(polygon: List[Vertex], directed: bool = False):
    """
    Constructs an iterator for iterating over all edge of the given polygon. If
    directed is set to false, the returned edges are normalized.
    """
    for i in range(len(polygon)):
        v1 = polygon[i]
        v2 = polygon[(i + 1) % len(polygon)]
        yield (v1, v2) if directed else _normalize((v1, v2))


def _get_inside_outside_edges(triangulation: Triangulation, must_equal=False) \
        -> (Tuple)[List[Edge], List[Edge]]:
    """
    Partitions all edges of the triangulation into two lists, edges that lay
    "outside" and edges that lay "inside". Outside edges are part of the
    boundaries of either the main polygon or one of its holes, while inside
    edges were added by the triangulation step.

    Outside edges are returned in their "correct" direction, inside edges are
    not.
    """
    edge_count = defaultdict(int)
    orientation = dict()
    inside, outside = [], []

    # We count how many times a particular edge is occuring in the
    # triangulation, because every inside edge is part of two triangles,
    # while edges laying on the polygon boundaries are only part of a
    # single triangulation.
    for triangle in triangulation:
        for edge in _iterate_edges(triangle, True):
            edge_count[_normalize(edge)] += 1
            orientation[_normalize(edge)] = edge
    for edge, count in edge_count.items():
        if count == 1:
            outside.append(orientation[edge])
        else:
            inside.append(edge)
    if must_equal:
        assert len(inside) == len(outside)
    return inside, outside


def _get_jump_map(cut_edges: List[Edge], out_edges: List[Edge], plane: Plane) \
        -> Mapping[Vertex, List[Vertex]]:
    """
    Constructs a jump map based on a list on cut edges, so that for every edge
    (a,b), map[a] contains b and map[b] contains a.
    
    Things get complicated when we have more than one entry for a vertex, which
    is the case when more than one edge in the spanning tree are incident to a
    vertex. Then we have to order the entries in clockwise order so that the
    polygon reconstruction builds a valid polygon that does not self-intersect.
    This is ALSO complicated by the fact that we are in 3 dimensions (which we
    could ignore until now), but at least we can assume that all input points
    lie in a common plane. Ordering the entries is done in _order_points_cw.
    """
    out_dest = dict()
    for edge in out_edges:
        out_dest[edge[0]] = edge[1]

    jump_map = defaultdict(list)
    for edge in cut_edges:
        jump_map[edge[0]].append(edge[1])
        jump_map[edge[1]].append(edge[0])

    for key, values in jump_map.items():
        if len(values) <= 1:
            continue
        jump_map[key] = _order_points_cw(plane, key, out_dest[key], values)
    return jump_map


def _order_points_cw(plane: Plane, mid: Vector, control: Vector,
                     vertices: List[Vertex]) -> List[Vertex]:
    """
    Based on:
    https://stackoverflow.com/questions/47949485/sorting-a-list-of-3d-points-in-clockwise-order

    To sort points laying in a plane in 3D space in clockwise order around a
    given origin m, we have to

        1. find the normal vector n of this plane
        2. find vectors p, q in our plane such that n, p, q are perpendicular
            to each other and form a right-handed system.
        3. Calculate for every vertex v the triple products u = n * ((v-m) x p)
            and t = n * ((v-m) x q) to obtain a sort key of atan2(u, t).

    We take n, p and q as arguments because we just have to calculate them once.

    We also take a control vector, which is also sorted alongside the other
    vertices. The result is then shifted so that the control vector is the first
    element in the result list. The control vector is not included in the
    returned list.
    """
    n, p, q = plane

    def sort_key(v: Vertex) -> float:
        t = numpy.dot(n, numpy.cross(numpy.subtract(v, mid), p))
        u = numpy.dot(n, numpy.cross(numpy.subtract(v, mid), q))
        return math.atan2(u, t)

    s = sorted([control] + vertices, key=sort_key)
    roll = s.index(control)
    rolled = s[roll:] + s[:roll]
    return rolled[1:]


def _calculate_plane_vectors(vertices: List[Vertex]) -> Plane:
    """
    Calculates n, p and q describing the plane the input values lie in. More
    info see _order_points_cw.
    """
    a, b, c = vertices
    d = numpy.cross(numpy.subtract(b, a), numpy.subtract(c, a))
    n = numpy.divide(d, numpy.linalg.norm(d))

    # We try two different unit vectors for the case that n and the first chosen unit vector are
    # parallel.
    p = (0, 0, 0)
    for uvec in [(1, 0, 0), (0, 1, 0)]:
        np = numpy.cross(uvec, n)
        if numpy.linalg.norm(p) < numpy.linalg.norm(np):
            p = np
    q = numpy.cross(n, p)

    return tuple(n), tuple(p), tuple(q)


def _reconstruct_polygons(edges: List[Edge]) -> List[List[Vertex]]:
    """
    Takes a list of edges in any order and reconstructs the correctly ordered
    vertices of the polygons formed by the given edges. It is assumed that the
    edges in the input are reconstructable to some list of polygons.
    """
    result = []
    chain = dict()
    for edge in edges:
        chain[edge[0]] = edge[1]
    while len(chain) > 0:
        start = next(
            iter(chain))  # use any key in the chain, we don't care which.
        polygon = []
        key = start
        first = True
        while key != start or first:
            first = False
            polygon.append(key)
            next_key = chain[key]
            del chain[key]
            key = next_key
        result.append(polygon)
    return result


def _index_polygon_vertices(polygons: List[List[Vertex]]) -> Mapping[
    Vertex, Tuple[int, int]]:
    """
    Build a index map where  map[v] = (i,j)  <=>  polygons[i][j] = v.
    """
    index = dict()
    for pIdx, polygon in enumerate(polygons):
        for vIdx, vertex in enumerate(polygon):
            index[vertex] = (pIdx, vIdx)
    return index


def _reconstruct_cut_polygon(out_edges: List[Edge], cut_edges: List[Edge],
                             plane: Plane) -> List[Vertex]:
    """
    Takes a list of outside edges and a list of cut edges and reconstructs the
    single polygon they form.
    """
    polygons = _reconstruct_polygons(out_edges)
    jump = dict(_get_jump_map(cut_edges, out_edges, plane))
    poly_index = _index_polygon_vertices(polygons)

    # Finds the index of the first vertex we can start on. We only start on
    # vertices that don't have any jumps to make the exit condition of our main
    # loop simpler. It is guaranteed that such a vertex exists (edges in a
    # spanning tree over all polygons < 3 * vertices in all polygons).
    def find_start_index():
        for i1, polygon in enumerate(polygons):
            for i2, vertex in enumerate(polygon):
                if vertex not in jump:
                    return i1, i2

    cut_polygon = []
    start_index = find_start_index()
    idx = start_index
    last_jump_source: Optional[Vertex] = None

    while True:
        current = polygons[idx[0]][idx[1]]
        cut_polygon.append(current)
        assert len(cut_polygon) <= len(
            out_edges) * 2, "Infinite loop detected. Arguments are not right."

        # We find out if we have to jump to another polygon. If yes, this
        # variable will be set to the index of the jump list of our current
        # vertex to where we have to jump.
        jump_list_index = None
        if current in jump:
            # There are jumps for the current vertex. Check if we already jumped
            # the last time.
            if last_jump_source is None:
                # ... no, so just jump to the last (= first in ccw order) entry
                # in the jump list.
                jump_list_index = -1
            else:
                # ... yes, so we have to jump to the first entry BEFORE the one
                # (= first after in ccw order)
                # we just came from. If we already came from the first entry, we
                # instead start to traverse
                # the current polygon.
                last_jump_index = jump[current].index(last_jump_source)
                if last_jump_index > 0:
                    jump_list_index = last_jump_index - 1

        if jump_list_index is not None:
            jump_vertex = jump[current][jump_list_index]
            idx = poly_index[jump_vertex]
            last_jump_source = current
        else:
            last_jump_source = None
            idx = (idx[0], (idx[1] + 1) % len(polygons[idx[0]]))

        # Because we started on a vertex that has no jumps, the start vertex can
        # only be visited once during polygon reconstruction. Therefore, if we
        # arrive at our start index a second time we are done.
        if idx == start_index:
            break

    return cut_polygon


def remove_inner_loops(shape: TopoDS_Shape) -> TopoDS_Shape:
    # Build all necessary data structures.
    triangulation = _get_triangulation(shape)
    in_edges, out_edges = _get_inside_outside_edges(triangulation)
    partition = _UnionFind()

    plane = _calculate_plane_vectors(triangulation[0])

    # Build initial partition state. After that, every loop (either the main
    # polygon or a hole)
    # is in its own disjoint set.
    for edge in out_edges:
        partition.union(edge[0], edge[1])

    # We now find a spanning tree by applying Kruskal's algorithm to the
    # triangulation graph. Note that in an unweighted graph, every spanning
    # tree is a minimal spanning tree, so it doesn't actually matter which
    # spanning tree we are calculating here. Edges that are part of the
    # spanning tree are pushed into cut_edges.
    cut_edges = []
    for edge in in_edges:
        if partition.find(edge[0]) != partition.find(edge[1]):
            cut_edges.append(edge)
            partition.union(edge[0], edge[1])

    cut_polygon = _reconstruct_cut_polygon(out_edges, cut_edges, plane)
    new_shape = PyOCCTools.make_faces_from_pnts(cut_polygon)

    # Copy over shape location
    # shape_loc = TopoDS_Iterator(shape).Value().Location()
    # new_shape.Move(shape_loc)

    return new_shape


def _cross(a: Vertex, b: Vertex) -> Vertex:
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - \
           a[1] * b[0]


def _dot(a: Vertex, b: Vertex) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _minus(a: Vertex, b: Vertex) -> Vertex:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def _is_convex_angle(p1: Vertex, p2: Vertex, p3: Vertex,
                     normal: Vertex) -> bool:
    cross = _cross(_minus(p2, p1), _minus(p3, p1))
    return _dot(cross, normal) >= -1e-6


def fuse_pieces(pieces: List[List[Vertex]],
                shapes_to_consider: List[TopoDS_Shape] = []) -> List[
    List[Vertex]]:
    normal, _, _ = _calculate_plane_vectors(pieces[0])
    consider_polygons = False

    if len(shapes_to_consider) > 0:
        consider_polygons = True
        edges = []
        for shape in shapes_to_consider:
            list_pnts = PyOCCTools.get_points_of_face(shape)
            for i, p in enumerate(list_pnts[:-1]):
                edges.append(BRepBuilderAPI_MakeEdge(list_pnts[i],
                                                     list_pnts[i + 1]).Shape())
            edges.append(
                BRepBuilderAPI_MakeEdge(list_pnts[-1], list_pnts[0]).Shape())

    i1 = 0
    while i1 < len(pieces) - 1:
        piece_a = pieces[i1]
        i1 += 1
        for piece_a_idx in range(0, len(piece_a)):
            a1 = piece_a[piece_a_idx]
            a2 = piece_a[(piece_a_idx + 1) % len(piece_a)]

            is_inner_edge = False
            piece_b = None
            piece_b_idx = None
            for i2 in range(i1, len(pieces)):
                piece_b = pieces[i2]
                for triangle_b_check_idx in range(0, len(piece_b)):
                    if a2 != piece_b[triangle_b_check_idx]:
                        continue
                    if a1 != piece_b[(triangle_b_check_idx + 1) % len(piece_b)]:
                        continue
                    piece_b_idx = triangle_b_check_idx
                    is_inner_edge = True
                    break
                if is_inner_edge:
                    break
            if not is_inner_edge:
                continue

            # piece_a and piece_b are two triangles with a common edge (piece_a
            # and piece_b)
            # common edge is spanned between a1 and a2
            p1 = piece_a[(piece_a_idx - 1) % len(piece_a)]
            p2 = a1
            p3 = piece_b[(piece_b_idx + 2) % len(piece_b)]

            if not consider_polygons:
                # if no polygons need to be considered, shapes are fused
                # unless resulting shape is non-convex
                if not _is_convex_angle(p1, p2, p3, normal):
                    continue
            else:
                # if an edge from triangulation cuts the edge of a polygon
                # which needs to be considered (e.g. from an opening boundary
                # within a boundary of a wall), then those shapes have to be
                # fused regardless of the resulting angle
                # this may lead to non-convex shapes in some cases
                a1_edge = BRepBuilderAPI_MakeEdge(gp_Pnt(*a1),
                                                  gp_Pnt(*a2)).Shape()
                continue_flag = True
                for edge in edges:
                    if BRepExtrema_DistShapeShape(
                            edge, a1_edge, Extrema_ExtFlag_MIN).Value() < 1e-3:
                        continue_flag = False
                    else:
                        pass
                if continue_flag:
                    continue

            # procedure is repeated for common edge of neighboring shape
            p1 = piece_b[(piece_b_idx - 1) % len(piece_b)]
            p2 = a2
            p3 = piece_a[(piece_a_idx + 2) % len(piece_a)]
            if not consider_polygons:
                if not _is_convex_angle(p1, p2, p3, normal):
                    continue
            else:
                a2_edge = BRepBuilderAPI_MakeEdge(gp_Pnt(*a2),
                                                  gp_Pnt(*a1)).Shape()
                continue_flag = True
                for edge in edges:
                    if BRepExtrema_DistShapeShape(
                            edge, a2_edge, Extrema_ExtFlag_MIN).Value() < 1e-3:
                        continue_flag = False
                    else:
                        pass
                if continue_flag:
                    continue
            # fuse triangles (if angle is convex or opening-polygon is cut by
            # this edge
            fused_piece = []
            i = (piece_a_idx + 1) % len(piece_a)
            while i != piece_a_idx:
                fused_piece.append(piece_a[i])
                i = (i + 1) % len(piece_a)
            i = (piece_b_idx + 1) % len(piece_b)
            while i != piece_b_idx:
                fused_piece.append(piece_b[i])
                i = (i + 1) % len(piece_b)

            i1 -= 1
            pieces.remove(piece_a)
            pieces.remove(piece_b)
            pieces.insert(i1, fused_piece)
            piece_a = fused_piece
            break
    return pieces


def convex_decomposition_base(shape: TopoDS_Shape,
                              opening_shapes: List[TopoDS_Shape] = []) -> List[
    List[Vertex]]:
    """Convex decomposition base: removes common edges of triangles unless a
    non-convex shape is created.
    In case of openings: In a first round, remove all cutting triangle edges
    with the opening polygons regardless of non-convex shapes.
    Then, check for resulting angles. This may lead to non-convex shapes,
    but should work in most cases.
    """
    pieces = _get_triangulation(shape)
    if len(opening_shapes) > 0:
        pieces = fuse_pieces(pieces, opening_shapes)
    pieces = fuse_pieces(pieces)

    return pieces


def convex_decomposition(shape: TopoDS_Shape,
                         opening_shapes: List[TopoDS_Shape] = []) -> List[
    TopoDS_Shape]:
    pieces = convex_decomposition_base(shape, opening_shapes)
    pieces_area = 0
    new_area = 0
    new_pieces = []
    for p in pieces:
        pieces_area += PyOCCTools.get_shape_area(
            PyOCCTools.make_faces_from_pnts(p))
        pnt_list_new = PyOCCTools.remove_coincident_vertices(
            [gp_XYZ(pnt[0], pnt[1], pnt[2]) for pnt in p])
        pnt_list_new = PyOCCTools.remove_collinear_vertices2(pnt_list_new)
        if pnt_list_new != p and len(pnt_list_new) > 3:
            pnt_list_new = [n.Coord() for n in pnt_list_new]
            p = pnt_list_new
        new_pieces.append(p)
        new_area += PyOCCTools.get_shape_area(
            PyOCCTools.make_faces_from_pnts(p))
    if abs(pieces_area - new_area) > 1e-3:
        new_pieces = pieces
    new_shapes = list(
        map(lambda p: PyOCCTools.make_faces_from_pnts(p), new_pieces))
    oriented_shapes = []
    org_normal = PyOCCTools.simple_face_normal(shape)
    for new_shape in new_shapes:
        new_normal = PyOCCTools.simple_face_normal(new_shape)
        if all([abs(i) < 1e-3 for i in ((new_normal - org_normal).Coord())]):
            oriented_shapes.append(new_shape)
        else:
            new_shape = PyOCCTools.flip_orientation_of_face(new_shape)
            new_normal = PyOCCTools.simple_face_normal(new_shape)
            if all([abs(i) < 1e-3 for i in
                    ((new_normal - org_normal).Coord())]):
                oriented_shapes.append(new_shape)
            else:
                logger = logging.getLogger(__name__)
                logger.error(
                    "Convex decomposition produces a gap in new space boundary")
    # check if decomposed shape has same area as original shape
    oriented_area = 0
    org_area = PyOCCTools.get_shape_area(shape)
    for face in oriented_shapes:
        oriented_area += PyOCCTools.get_shape_area(face)
    cut_count = 0
    while abs(org_area - oriented_area) > 5e-3:
        cut_count += 1
        cut_shape = shape
        for bound in oriented_shapes:
            cut_shape = BRepAlgoAPI_Cut(cut_shape, bound).Shape()
        list_cut_shapes = PyOCCTools.get_faces_from_shape(cut_shape)
        add_cut_shapes = []
        for cs in list_cut_shapes:
            new_normal = PyOCCTools.simple_face_normal(cs)
            if not all([abs(i) < 1e-3 for i in
                        ((new_normal - org_normal).Coord())]):
                cs = PyOCCTools.flip_orientation_of_face(cs)
            cut_area = PyOCCTools.get_shape_area(cs)
            if cut_area < 5e-4:
                continue
            cs = PyOCCTools.remove_coincident_and_collinear_points_from_face(cs)
            oriented_area += cut_area
            add_cut_shapes.append(cs)
        if cut_count > 3:
            logger = logging.getLogger(__name__)
            logger.error(
                "Convex decomposition produces a gap in new space boundary")
            break
        else:
            oriented_shapes.extend(add_cut_shapes)
    return oriented_shapes


def is_convex_slow(shape: TopoDS_Shape) -> bool:
    """
    Computational expensive check if a TopoDS_Shape is convex.
    Args:
        shape: TopoDS_Shape

    Returns:
        bool, True if shape is convex.
    """
    return len(convex_decomposition_base(shape)) == 1


def is_convex_no_holes(shape: TopoDS_Shape) -> bool:
    """check if TopoDS_Shape is convex. Returns False if shape is non-convex"""
    gp_pnts = PyOCCTools.get_points_of_face(shape)
    pnts = list(map(lambda p: _gp_pnt_to_coord_tuple(p), gp_pnts))
    z = 0
    for i in range(0, len(pnts)):
        p0 = pnts[i]
        p1 = pnts[(i + 1) % len(pnts)]
        p2 = pnts[(i + 2) % len(pnts)]
        cross = _cross(_minus(p1, p0), _minus(p2, p1))[2]
        if z != 0 and abs(cross) >= 1e-6 and numpy.sign(cross) != numpy.sign(z):
            return False
        else:
            z = cross
    return True


def is_polygon_convex_no_holes(pnts: List[Tuple[float, float, float]]) -> bool:
    """check if polygon made from tuples of floats is convex.
    Returns False if shape is non-convex"""
    z = 0
    for i in range(0, len(pnts)):
        p0 = pnts[i]
        p1 = pnts[(i + 1) % len(pnts)]
        p2 = pnts[(i + 2) % len(pnts)]
        cross = _cross(_minus(p1, p0), _minus(p2, p1))[2]
        if z != 0 and abs(cross) >= 1e-6 and numpy.sign(cross) != numpy.sign(z):
            return False
        else:
            z = cross
    return True
