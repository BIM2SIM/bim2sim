import OCC.Core.TopoDS
from OCC.Core.gp import gp_Pnt
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
import bim2sim.tasks.common.inner_loop_remover as ilr
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.pyocc_tools import PyOCCTools
import math
from stl import mesh
import numpy as np
import re


class OpenFOAMUtils:
    @staticmethod
    def split_openfoam_elements(openfoam_elements: dict) -> tuple[list, list,
    list, list, list]:
        stl_bounds = filter_elements(openfoam_elements, 'StlBound')
        heaters = filter_elements(openfoam_elements, 'Heater')
        air_terminals = filter_elements(openfoam_elements, 'AirTerminal')
        furniture = filter_elements(openfoam_elements, 'Furniture')
        people = filter_elements(openfoam_elements, 'People')
        return stl_bounds, heaters, air_terminals, furniture, people

    @staticmethod
    def get_refinement_level(dist: float, bM_size: float, mean_dist:
            float=None) -> list:
        """
        Computes the refinement level based on the desired
        refined cell size and the blockMesh cell size.
        bM_size/2^X = min_dist
        """
        ref_level = math.log(bM_size / dist) / math.log(2)
        ref_level = math.ceil(ref_level)
        if mean_dist:
            min_level = math.log(bM_size / mean_dist) / math.log(2)
            min_level = int(round(min_level,0))
            if min_level < 0:
                min_level = 0
            if min_level > ref_level:
                min_level = ref_level
        else:
            min_level = ref_level
        return [min_level, ref_level + 2]

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
    def get_min_internal_dist(points: list[gp_Pnt]) -> float:
        """
        Computes the minimal internal distance of a TopoDS Shape.
        """
        mindist = 0.05
        for i, p1 in enumerate(points):
            for p2 in points[i:]:
                dist = p1.Distance(p2)
                if mindist > dist > 5e-04:
                    mindist = dist
        return mindist

    def validate_volumes_cells(self, case: str, inlet_type: str,
                               outlet_type: str) -> bool:
        """
        Compute the absolute difference in the volumes of the geometry of
        the room and the volume of the discretized domain.
        If the V directory was not created in the controlDict, it can be
        created after meshing using (Linux):
            postProcess -func writeCellVolumes -time 0
            gzip -d V.gz
        The total discretized volume can also be obtained from the checkMesh
        functionality.

        case must be the path to the corresponding OpenFOAM case directory.
        inlet_type and outlet_type must be equal to the
        corresponding sim_setting options.
        """
        base_dir = case + '/' + 'constant' + '/' + 'triSurface' + '/'
        vol_geom = self.get_vol_from_geometry(base_dir, inlet_type, outlet_type)
        vol_cells = self.get_vol_from_cells(case)
        abs_diff = abs(vol_geom - vol_cells)
        if abs_diff < 0.05:
            mesh_valid = True
        else:
            mesh_valid = False
        return mesh_valid

    @staticmethod
    def get_vol_from_geometry(base_dir: str, inlet_type: str,
                              outlet_type: str) -> float:
        """
        Compute the volume of the simulated room based on the STL files.

        base_dir must be the path to the triSurface directory of the
        corresponding OpenFOAM case.
        inlet_type and outlet_type must be equal to the
        corresponding sim_setting options.
        """
        partMesh = []
        with open(base_dir + 'space_2RSCzLOBz4FAK$_wE8VckM.stl', 'r') as \
                multimesh:
            mesh_lines = multimesh.readlines()
            start_ind = end_ind = -1
            for line in mesh_lines:
                if 'endsolid' in line:
                    start_ind = end_ind + 1
                    end_ind = mesh_lines.index(line)
                    with open('temp_mesh.stl', 'w') as temp_mesh:
                        temp_mesh.writelines(mesh_lines[start_ind:end_ind + 1])
                        temp_mesh.close()
                    partMesh.append(mesh.Mesh.from_file('temp_mesh.stl'))
        partMesh.append(mesh.Mesh.from_file(base_dir + 'inlet_diffuser.stl'))
        partMesh.append(mesh.Mesh.from_file(base_dir + 'outlet_diffuser.stl'))
        if not inlet_type == 'SimpleStlDiffusor':
            partMesh.append(mesh.Mesh.from_file(base_dir + 'inlet_box.stl'))
            partMesh.append(mesh.Mesh.from_file(base_dir +
                                                'inlet_source_sink.stl'))
        if not outlet_type == 'SimpleStlDiffusor':
            partMesh.append(mesh.Mesh.from_file(base_dir + 'outlet_box.stl'))
            partMesh.append(mesh.Mesh.from_file(base_dir +
                                                'outlet_source_sink.stl'))
        combined = partMesh[0]
        for part in partMesh[1:]:
            combined = mesh.Mesh(np.concatenate((combined.data, part.data)))
        vol_geom = float(combined.get_mass_properties()[0])
        return vol_geom

    @staticmethod
    def get_vol_from_cells(case) -> float:
        """
        Compute the volume of the simulated room based on the FVM cells.

        case must be the path to the corresponding OpenFOAM case directory.
        """
        with open(case + '/' + '0' + '/' + 'V') as f:
            lines = f.readlines()
            n_cells = int(lines[21])
            total_vol = 0
            for line in lines[23:n_cells + 23]:
                total_vol += float(line)
        return total_vol

    def detriangulize(self, obj):
        """2-step algorithm for removing triangularizaton from an obj as
        TopoDS_Compound. 1. remove inner edges. 2. remove collinear and
        coincident points."""
        triang = ilr._get_triangulation(obj)
        inner_edges, outer_edges = ilr._get_inside_outside_edges(triang,
                                                                 must_equal=False)
        edges = inner_edges + outer_edges
        vertices = PyOCCTools.get_unique_vertices(outer_edges)
        vertices = self.remove_coincident_vertices(vertices)
        vertices = PyOCCTools.remove_collinear_vertices2(vertices)
        return vertices, edges

    @staticmethod
    def get_edge_lengths(edges):
        """
        Calculate the lengths of edges in 3D space.

        Parameters:
            edges (list of tuples): A list where each element is a tuple
            containing two 3D coordinates
            (e.g., [((x1, y1, z1), (x2, y2, z2)), ...]).

        Returns:
            list: A list of lengths corresponding to the edges.
        """
        lengths = []
        for (x1, y1, z1), (x2, y2, z2) in edges:
            length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)
            lengths.append(length)
        return lengths

    @staticmethod
    def remove_coincident_vertices(vert_list: list) -> list:
        """Slightly modified version of the method in PyOCCTools. Remove
        coincident vertices from list of gp_Pnt. Vertices are coincident if
        closer than tolerance. Does not assume vertices to be sorted."""
        tol_dist = 1e-3
        remove_list = []
        for i, vert in enumerate(vert_list):
            for vert2 in vert_list[i + 1:]:
                v = np.array(vert.Coord())
                v2 = np.array(vert2.Coord())
                d_b = np.linalg.norm(v - v2)
                if d_b < tol_dist:
                    remove_list.append(vert2)
        for v in remove_list:
            if v in vert_list:
                vert_list.remove(v)
        return vert_list

    @staticmethod
    def string_to_dict(s):
        # Extract the tuples from the string using regular expressions
        matches = re.findall(r"\((\d+)\s([\d.]+)\)", s)
        # Convert the matches to a dictionary
        return {int(k): float(v) for k, v in matches}

    @staticmethod
    def dict_to_string(d):
        # Format the dictionary back into the original string format
        sorted_items = sorted(d.items())
        tuples_str = " ".join(f"({k} {v})" for k, v in sorted_items)
        return f"table ( {tuples_str} )"

    @staticmethod
    def duplicate_table_for_restart(dict_with_string_tables: dict,
                                    add_number_to_keys: int) -> dict:
        new_dict = {}
        for key, eq_val in dict_with_string_tables.items():
            d = OpenFOAMUtils.string_to_dict(eq_val)
            if d:
                d_updated = {}
                for d_key, d_val in d.items():
                    d_updated.update({d_key: d_val})
                    d_updated.update({d_key + add_number_to_keys: d_val})
                s_updated = OpenFOAMUtils.dict_to_string(d_updated)
                new_dict.update({key: s_updated})
            else:
                new_dict.update({key: eq_val})
        return new_dict

    @staticmethod
    def prime_factors(n):
        factors = []
        divisor = 2
        while n > 1:
            while n % divisor == 0:
                factors.append(divisor)
                n //= divisor
            divisor += 1
        return factors

    @staticmethod
    def split_into_three_factors(n):
        factors = OpenFOAMUtils.prime_factors(n)
        factors.sort()
        groups = []
        for i, factor in enumerate(factors):
            groups.append(factor)
        while len(groups) < 3:
            groups.append(1)
        res = len(groups) - 3
        for i in range(res):
            groups[i] = groups[i] * groups[-1]
            groups.pop()
        return groups
