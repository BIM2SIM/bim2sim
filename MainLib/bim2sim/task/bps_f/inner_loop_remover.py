"""
This module contains functions which, given a TopoDS shapes with holes ("inner loops"), calculate an
equivalent shape without holes by adding cuts along triangulation edges. Using the triangulation as
a graph, it finds a spanning tree between the main polygon and its holes using Kruskal's algorithm
and places the cuts along the edges of this spanning tree.
"""

from typing import Tuple, List, Mapping, TypeVar, Generic, Optional
from collections import defaultdict
import numpy
import math

from OCC.BRep import BRep_Tool
from OCC.BRepMesh import BRepMesh_IncrementalMesh
from OCC.TopAbs import TopAbs_FACE
from OCC.TopExp import TopExp_Explorer
from OCC.TopoDS import TopoDS_Shape, topods_Face
from OCC.TopLoc import TopLoc_Location
from OCC.gp import gp_Pnt

# Type aliases that are used throughout this module
Vertex = Vector = Tuple[float, float, float]
Edge = Tuple[Vertex, Vertex]
Triangulation = List[List[Vertex]]
Plane = Tuple[Vector, Vector, Vector]
T = TypeVar('T')


class _UnionFind(Generic[T]):
    """
    Implementation of a union-find data structure with union-by-size and path compression.
    """
    __parents = dict()
    __sizes = dict()

    def union(self, element1: T, element2: T) -> T:
        key1 = self.find(element1)
        key2 = self.find(element2)
        if key1 == key2: 
            return
        if self.__sizes[key1] < self.__sizes[key2]:
            key1, key2 = key2, key1
        self.__parents[key2] = key1
        self.__sizes[key1] += self.__sizes[key2]
        
    def find(self, element: T) -> T:
        if element not in self.__parents:
            self.__parents[element] = None
            self.__sizes[element] = 1
        root = element
        while self.__parents[root] is not None:
            root = self.__parents[root]
        while self.__parents[element] is not None:
            parent = self.__parents[element]
            self.__parents[element] = root
            element = parent
        return element


def _gp_pnt_to_coord_tuple(pnt: gp_Pnt) -> Vertex:
    """
    Converts a gp_Pnt instance (3D point class of OCC) to a 3-tuple, because we need our vertex
    type to be comparable and hashable, which gp_Pnt is not.
    """
    return pnt.X(), pnt.Y(), pnt.Z()


def _subshapes(shape):
    from OCC.TopoDS import TopoDS_Iterator
    it = TopoDS_Iterator(shape)
    clist = []
    while it.More():
        clist.append(_subshapes(it.Value()))
        it.Next()
    return shape if len(clist) == 0 else shape, clist


def _get_triangulation(face: TopoDS_Shape) -> Triangulation:
    """
    Calculates and extracts the triangulation of a TopoDS shape and returns it as a list of triangles.
    """
    mesh = BRepMesh_IncrementalMesh(face, 0.01)
    mesh.Perform()
    ex = TopExp_Explorer(mesh.Shape(), TopAbs_FACE)
    bt = BRep_Tool()
    result = []
    while ex.More():
        triangulation = bt.Triangulation(topods_Face(ex.Current()), TopLoc_Location()) \
            .GetObject()
        triangles = triangulation.Triangles()
        vertices = triangulation.Nodes()
        for i in range(1, triangulation.NbTriangles() + 1):
            idx1, idx2, idx3 = triangles.Value(i).Get()
            result.append([
                _gp_pnt_to_coord_tuple(vertices.Value(idx1)),
                _gp_pnt_to_coord_tuple(vertices.Value(idx2)),
                _gp_pnt_to_coord_tuple(vertices.Value(idx3))
            ])
        ex.Next()
    return result


def _normalize(edge: Edge) -> Edge:
    """
    Edges are normalized so that (a,b) and (b,a) are both returned as (a,b).
    """
    return (edge[0], edge[1]) if edge[0] < edge[1] else (edge[1], edge[0])


def _iterate_edges(polygon: List[Vertex], directed: bool = False):
    """
    Constructs an iterator for iterating over all edge of the given polygon. If directed is set to false,
    the returned edges are normalized.
    """
    for i in range(len(polygon)):
        v1 = polygon[i]
        v2 = polygon[(i + 1) % len(polygon)]
        yield (v1, v2) if directed else _normalize((v1, v2))


def _get_inside_outside_edges(triangulation: Triangulation) -> Tuple[List[Edge], List[Edge]]:
    """
    Partitions all edges of the triangulation into two lists, edges that lay "outside" and edges that 
    lay "inside". Outside edges are part of the boundaries of either the main polygon or one of its 
    holes, while inside edges were added by the triangulation step.

    Outside edges are returned in their "correct" direction, inside edges are not.
    """
    edge_count = defaultdict(int)
    orientation = dict()
    inside, outside = [], []

    # We count how many times a particular edge is occuring in the triangulation, because every inside
    # edge is part of two triangles, while edges laying on the polygon boundaries are only part of a
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
    return inside, outside


def _get_jump_map(cut_edges: List[Edge], out_edges: List[Edge], plane: Plane) \
        -> Mapping[Vertex, List[Vertex]]:
    """
    Constructs a jump map based on a list on cut edges, so that for every edge (a,b), map[a] contains
    b and map[b] contains a.
    
    Things get complicated when we have more than one entry for a vertex, which is the case when more
    than one edge in the spanning tree are incident to a vertex. Then we have to order the entries in
    clockwise order so that the polygon reconstruction builds a valid polygon that does not self-intersect.
    This is ALSO complicated by the fact that we are in 3 dimensions (which we could ignore until now), but
    at least we can assume that all input points lie in a common plane. Ordering the entries is done in
    _order_points_cw.
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


def _order_points_cw(plane: Plane, mid: Vector, control: Vector, vertices: List[Vertex]) -> List[Vertex]:
    """
    Based on: https://stackoverflow.com/questions/47949485/sorting-a-list-of-3d-points-in-clockwise-order

    To sort points laying in a plane in 3D space in clockwise order around a given origin m, we have to

        1. find the normal vector n of this plane
        2. find vectors p, q in our plane such that n, p, q are perpendicular to each other and form a
           right-handed system.
        3. Calculate for every vertex v the triple products u = n * ((v-m) x p) and t = n * ((v-m) x q)
           to obtain a sort key of atan2(u, t).

    We take n, p and q as arguments because we just have to calculate them once.

    We also take a control vector, which is also sorted alongside the other vertices. The result is then
    shifted so that the control vector is the first element in the result list. The control vector is not
    included in the returned list.
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
    Calculates n, p and q describing the plane the input values lie in. More info see _order_points_cw.
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
    Takes a list of edges in any order and reconstructs the correctly ordered vertices of the polygons
    formed by the given edges. It is assumed that the edges in the input are reconstructable to some
    list of polygons.
    """
    result = []
    chain = dict()
    for edge in edges:
        chain[edge[0]] = edge[1]
    while len(chain) > 0:
        start = next(iter(chain))  # use any key in the chain, we don't care which.
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


def _index_polygon_vertices(polygons: List[List[Vertex]]) -> Mapping[Vertex, Tuple[int, int]]:
    """
    Build a index map where  map[v] = (i,j)  <=>  polygons[i][j] = v.
    """
    index = dict()
    for pIdx, polygon in enumerate(polygons):
        for vIdx, vertex in enumerate(polygon):
            index[vertex] = (pIdx, vIdx)
    return index


def _reconstruct_cut_polygon(out_edges: List[Edge], cut_edges: List[Edge], plane: Plane) -> List[Vertex]:
    """
    Takes a list of outside edges and a list of cut edges and reconstructs the single polygon they form.
    """
    polygons = _reconstruct_polygons(out_edges)
    jump = dict(_get_jump_map(cut_edges, out_edges, plane))
    poly_index = _index_polygon_vertices(polygons)

    # Finds the index of the first vertex we can start on. We only start on vertices that don't have any
    # jumps to make the exit condition of our main loop simpler. It is guaranteed that such a vertex
    # exists (edges in a spanning tree over all polygons < 3 * vertices in all polygons).
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
        assert len(cut_polygon) <= len(out_edges) * 2, "Infinite loop detected. Arguments are not right."

        # We find out if we have to jump to another polygon. If yes, this variable will be set to the index
        # of the jump list of our current vertex to where we have to jump.
        jump_list_index = None
        if current in jump:
            # There are jumps for the current vertex. Check if we already jumped the last time.
            if last_jump_source is None:
                # ... no, so just jump to the last (= first in ccw order) entry in the jump list.
                jump_list_index = -1
            else:
                # ... yes, so we have to jump to the first entry BEFORE the one (= first after in ccw order)
                # we just came from. If we already came from the first entry, we instead start to traverse
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

        # Because we started on a vertex that has no jumps, the start vertex can only be visited once during
        # polygon reconstruction. Therefore, if we arrive at our start index a second time we are done.
        if idx == start_index:
            break

    return cut_polygon


def remove_inner_loops(shape: TopoDS_Shape) -> TopoDS_Shape:
    from kernel.elements import SpaceBoundary
    # if not shape:
    #     _big_rect = SpaceBoundary._make_faces_from_pnts([(1, 1, 0), (5, 1, 0), (5, 5, 0), (1, 5, 0)])
    #     _small_rect = SpaceBoundary._make_faces_from_pnts([(2, 2, 0), (3, 2, 0), (3, 3, 0), (2, 3, 0)])
    #     _extra_small_rect = SpaceBoundary._make_faces_from_pnts([(2, 4, 0), (2, 3.5, 0), (2.5, 3.5, 0), (2.5, 4, 0)])
    #     _small_trig = SpaceBoundary._make_faces_from_pnts([(4, 3, 0), (4, 4, 0), (3, 4, 0)])
    #     from OCC.BRepAlgoAPI import BRepAlgoAPI_Cut
    #     shape = _big_rect
    #     shape = BRepAlgoAPI_Cut(shape, _small_rect).Shape()
    #     shape = BRepAlgoAPI_Cut(shape, _extra_small_rect).Shape()
    #     shape = BRepAlgoAPI_Cut(shape, _small_trig).Shape()

    # Build all necessary data structures.
    triangulation = _get_triangulation(shape)
    in_edges, out_edges = _get_inside_outside_edges(triangulation)
    partition = _UnionFind()

    # Build initial partition state. After that, every loop (either the main polygon or a hole)
    # is in its own disjoint set.
    for edge in out_edges:
        partition.union(edge[0], edge[1])
        
    # We now find a spanning tree by applying Kruskal's algorithm to the triangulation graph. Note
    # that in an unweighted graph, every spanning tree is a minimal spanning tree, so it doesn't
    # actually matter which spanning tree we are calculating here. Edges that are part of the
    # spanning tree are pushed into cut_edges.
    cut_edges = []
    for edge in in_edges:
        if partition.find(edge[0]) != partition.find(edge[1]):Q
            cut_edges.append(edge)
            partition.union(edge[0], edge[1])

    plane = _calculate_plane_vectors(triangulation[0])
    cut_polygon = _reconstruct_cut_polygon(out_edges, cut_edges, plane)

    return SpaceBoundary._make_faces_from_pnts(cut_polygon)
