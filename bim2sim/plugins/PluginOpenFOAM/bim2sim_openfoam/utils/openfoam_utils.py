import OCC.Core.TopoDS
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape

from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.pyocc_tools import PyOCCTools
import math
from stl import mesh
import numpy as np


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
        """
        Computes the refinement level based on the desired
        refined cell size and the blockMesh cell size.
        bM_size/2^X = min_dist
        """
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
