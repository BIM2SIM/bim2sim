"""Module to export space boundaries as .stl for use in CFD."""

import ast
import logging
import os

import pandas as pd
from OCC.Core.StlAPI import StlAPI_Writer
from OCC.Core.TopoDS import TopoDS_Shape
from stl import mesh, stl

from bim2sim.elements.bps_elements import SpaceBoundary
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements, \
    get_spaces_with_bounds
from bim2sim.utilities.pyocc_tools import PyOCCTools

logger = logging.getLogger(__name__)


class ExportIdfForCfd(ITask):
    """Export Idf shapes as .stl for use in CFD applications."""

    reads = ('elements', 'idf')

    def run(self, elements, idf):
        """Run CFD export depending on settings."""
        if not self.playground.sim_settings.cfd_export:
            return

        logger.info("IDF Postprocessing for CFD started...")
        logger.info("Export STL for CFD")
        stl_name = idf.idfname.replace('.idf', '')
        stl_name = stl_name.replace(str(self.paths.export)+'/', '')
        base_stl_dir = str(self.paths.root) + "/export/STL/"
        os.makedirs(os.path.dirname(base_stl_dir), exist_ok=True)

        self.export_bounds_to_stl(elements, stl_name, base_stl_dir)
        self.export_bounds_per_space_to_stl(elements, stl_name, base_stl_dir)
        self.export_2b_bounds_to_stl(elements, stl_name, base_stl_dir)
        self.combine_stl_files(stl_name, self.paths)
        self.export_space_bound_list(elements, self.paths)
        self.combined_space_stl(stl_name, self.paths)
        logger.info("IDF Postprocessing for CFD finished!")

    def export_2b_bounds_to_stl(self, elements: dict, stl_name: str,
                                stl_dir: str):
        """Export generated 2b space boundaries to stl for CFD purposes.

        Args:
            stl_dir: directory of exported stl files
            elements: dict[guid: element]
            stl_name: name of the stl file.
        """
        spaces = get_spaces_with_bounds(elements)
        for space_obj in spaces:
            if not hasattr(space_obj, "b_bound_shape"):
                continue
            if PyOCCTools.get_shape_area(space_obj.b_bound_shape) > 0:
                name = space_obj.guid + "_2B"
                this_name = \
                    stl_dir + str(stl_name) + "_cfd_" + str(name) + ".stl"
                triang_face = PyOCCTools.triangulate_bound_shape(
                    space_obj.b_bound_shape)
                # Export to STL
                self.write_triang_face(triang_face, this_name)

    def export_bounds_to_stl(self, elements: dict, stl_name: str,
                             stl_dir: str):
        """Export space boundaries to stl file.

        This function exports space boundary geometry to an stl file as
        triangulated surfaces. Only physical (i.e., non-virtual) space
        boundaries are considered here.
        The geometry of opening space boundaries is removed from their
        underlying parent surfaces (e.g., Wall) before exporting to stl,
        so boundaries do not overlap.

        Args:
            stl_dir: directory of exported stl files
            elements: dict[guid: element]
            stl_name: name of the stl file.
        """

        bounds = filter_elements(elements, SpaceBoundary)
        for bound in bounds:
            if not bound.physical:
                continue
            self.export_single_bound_to_stl(bound, stl_dir, stl_name)

    def export_single_bound_to_stl(self, bound: SpaceBoundary, stl_dir: str,
                                   stl_name: str):
        """Export a single bound to stl.

        Args:
            bound: SpaceBoundary instance
            stl_dir: directory of exported stl files
            stl_name: name of the stl file.
        """
        name = bound.guid
        this_name = stl_dir + str(stl_name) + "_cfd_" + str(name) + ".stl"
        bound.cfd_face = bound.bound_shape
        opening_shapes = []
        if bound.opening_bounds:
            opening_shapes = [s.bound_shape for s in bound.opening_bounds]
        triang_face = PyOCCTools.triangulate_bound_shape(bound.cfd_face,
                                                         opening_shapes)
        # Export to STL
        self.write_triang_face(triang_face, this_name)

    @staticmethod
    def write_triang_face(shape: TopoDS_Shape, name):
        """Write triangulated face to stl file.

        Args:
            shape: TopoDS_Shape
            name: path and name of the stl
        """
        stl_writer = StlAPI_Writer()
        stl_writer.SetASCIIMode(True)
        stl_writer.Write(shape, name)

    def export_bounds_per_space_to_stl(self, elements: dict, stl_name: str,
                                       base_stl_dir: str):
        """Export stl bounds per space in individual directories.

        Args:
            elements: dict[guid: element]
            stl_name: name of the stl file.
            base_stl_dir: directory of exported stl files
        """
        spaces = get_spaces_with_bounds(elements)
        for space_obj in spaces:
            space_name = space_obj.guid
            stl_dir = base_stl_dir + space_name + "/"
            os.makedirs(os.path.dirname(stl_dir), exist_ok=True)
            for bound in space_obj.space_boundaries:
                if not bound.physical:
                    continue
                self.export_single_bound_to_stl(bound, stl_dir, stl_name)
            self.combine_space_stl_files(stl_name, space_name, self.paths)

    @staticmethod
    def combined_space_stl(stl_name: str, paths):
        """Combine the stl files per space in stl files.

        Args:
            stl_name: name of the stl file.
            paths: BIM2SIM paths
        """
        sb_dict = pd.read_csv(paths.export / 'space_bound_list.csv').drop(
            'Unnamed: 0', axis=1)
        with open(paths.export / str(
                stl_name + "_combined_STL.stl")) as output_file:
            output_data = output_file.read()
            for index, row in sb_dict.iterrows():
                space_id = row['space_id']
                new_space_id = space_id.replace('$', '___')
                bound_ids = ast.literal_eval(row['bound_ids'])
                for id in bound_ids:
                    id_new = id.replace('$', '___')
                    new_string = 'space_' + new_space_id + '_bound_' + id_new
                    new_string = new_string.upper()
                    output_data = output_data.replace(id_new, new_string)
        with open(paths.export / str(stl_name + "_space_combined_STL.stl"),
                  'w+') as new_file:
            new_file.write(output_data)

    @staticmethod
    def export_space_bound_list(elements: dict, paths: str):
        """Exports a list of spaces and space boundaries.

        Args:
            elements: dict[guid: element]
            paths: BIM2SIM paths
        """
        stl_dir = str(paths.export) + '/'
        space_bound_df = pd.DataFrame(columns=["space_id", "bound_ids"])
        spaces = get_spaces_with_bounds(elements)
        for space in spaces:
            bound_names = []
            for bound in space.space_boundaries:
                bound_names.append(bound.guid)
            space_bound_df = space_bound_df.append({'space_id': space.guid,
                                                    'bound_ids': bound_names},
                                                   ignore_index=True)
        space_bound_df.to_csv(stl_dir + "space_bound_list.csv")

    @staticmethod
    def combine_stl_files(stl_name: str, paths: str):
        """Combine stl files.

        Args:
            stl_name: name of the stl file
            paths: BIM2SIM paths
        """
        stl_dir = str(paths.export) + '/'
        with open(stl_dir + stl_name + "_combined_STL.stl", 'wb+') \
                as output_file:
            for i in os.listdir(stl_dir + 'STL/'):
                if os.path.isfile(os.path.join(stl_dir + 'STL/', i)) \
                        and (stl_name + "_cfd_") in i:
                    sb_mesh = mesh.Mesh.from_file(stl_dir + 'STL/' + i)
                    mesh_name = "cfd_" +i.split("_cfd_", 1)[-1]
                    mesh_name = mesh_name.replace(".stl", "")
                    mesh_name = mesh_name.replace("$", "___")
                    sb_mesh.save(mesh_name, output_file, mode=stl.Mode.ASCII)

    @staticmethod
    def combine_space_stl_files(stl_name: str, space_name: str, paths: str):
        """Combine the stl file of spaces.

        Args:
            stl_name: name of the stl file
            space_name: name of the space
            paths: BIM2SIM paths
        """
        stl_dir = str(paths.export) + '/'
        os.makedirs(os.path.dirname(stl_dir + "space_stl/"), exist_ok=True)

        with open(stl_dir + "space_stl/" + "space_" + space_name + ".stl",
                  'wb+') as output_file:
            for i in os.listdir(stl_dir + 'STL/' + space_name + "/"):
                if os.path.isfile(os.path.join(stl_dir + 'STL/'
                                               + space_name + "/", i)) \
                        and (stl_name + "_cfd_") in i:
                    sb_mesh = mesh.Mesh.from_file(stl_dir + 'STL/'
                                                  + space_name + "/" + i)
                    mesh_name = "cfd_" + i.split("_cfd_", 1)[-1]
                    mesh_name = mesh_name.replace(".stl", "")
                    mesh_name = mesh_name.replace("$", "___")
                    sb_mesh.save(mesh_name, output_file, mode=stl.Mode.ASCII)
