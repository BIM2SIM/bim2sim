"""Module to export space boundaries as .stl for use in CFD."""

import ast
import logging
import os

import pandas as pd
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCC.Core.BRepGProp import brepgprop_SurfaceProperties
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.GProp import GProp_GProps
from OCC.Core.StlAPI import StlAPI_Writer
from stl import mesh, stl

from bim2sim.task.base import ITask

logger = logging.getLogger(__name__)


class ExportIdfForCfd(ITask):
    """Export Idf shapes as .stl for use in CFD applications."""

    reads = ('instances', 'idf', 'ifc',)

    def run(self, workflow, instances, idf, ifc):
        if not workflow.cfd_export:
            return

        logger.info("IDF Postprocessing for CFD started...")
        logger.info("Export STL for CFD")
        stl_name = idf.idfname.replace('.idf', '')
        stl_name = stl_name.replace(str(self.paths.export)+'/', '')
        self.export_bounds_to_stl(instances, stl_name)
        self.export_bounds_per_space_to_stl(instances, stl_name)
        self.export_2b_bounds_to_stl(instances, stl_name)
        self.combine_stl_files(stl_name, self.paths)
        self.export_space_bound_list(instances, self.paths)
        self.combined_space_stl(stl_name, self.paths)
        logger.info("IDF Postprocessing for CFD finished!")

    def export_2b_bounds_to_stl(self, instances, stl_name):
        for inst in instances:
            if instances[inst].ifc.is_a("IfcSpace"):
                continue
            space_obj = instances[inst]
            if not hasattr(space_obj, "b_bound_shape"):
                continue
            bound_prop = GProp_GProps()
            brepgprop_SurfaceProperties(space_obj.b_bound_shape, bound_prop)
            area = bound_prop.Mass()
            if area > 0:
                name = space_obj.guid + "_2B"
                stl_dir = str(self.paths.root) + "/export/STL/"
                this_name = stl_dir + str(stl_name) + "_cfd_" + str(name) + ".stl"
                os.makedirs(os.path.dirname(stl_dir), exist_ok=True)
                triang_face = BRepMesh_IncrementalMesh(space_obj.b_bound_shape, 1)
                # Export to STL
                stl_writer = StlAPI_Writer()
                stl_writer.SetASCIIMode(True)
                stl_writer.Write(triang_face.Shape(), this_name)

    def export_bounds_to_stl(self, instances, stl_name):
        """
        This function exports a space to an idf file.
        :param idf: idf file object
        :param space: Space instance
        :param zone: idf zone object
        :return:
        """
        for inst in instances:
            if not instances[inst].ifc.is_a("IfcRelSpaceBoundary"):
                continue
            inst_obj = instances[inst]
            if inst_obj.physical:
                name = inst_obj.guid
                stl_dir = str(self.paths.root) + "/export/STL/"
                this_name = stl_dir + str(stl_name) + "_cfd_" + str(name) + ".stl"
                os.makedirs(os.path.dirname(stl_dir), exist_ok=True)

                inst_obj.cfd_face = inst_obj.bound_shape
                if inst_obj.opening_bounds:
                    for opening in inst_obj.opening_bounds:
                        inst_obj.cfd_face = BRepAlgoAPI_Cut(inst_obj.cfd_face, opening.bound_shape).Shape()
                triang_face = BRepMesh_IncrementalMesh(inst_obj.cfd_face, 1)
                # Export to STL
                stl_writer = StlAPI_Writer()
                stl_writer.SetASCIIMode(True)
                stl_writer.Write(triang_face.Shape(), this_name)

    def export_bounds_per_space_to_stl(self, instances, stl_name):
        """
        This function exports a space to an idf file.
        :param idf: idf file object
        :param space: Space instance
        :param zone: idf zone object
        :return:
        """
        for inst in instances:
            if not instances[inst].ifc.is_a("IfcSpace"):
                continue
            space_obj = instances[inst]
            space_name = space_obj.guid
            stl_dir = str(self.paths.root) + "/export/STL/" + space_name + "/"
            os.makedirs(os.path.dirname(stl_dir), exist_ok=True)
            for inst_obj in space_obj.space_boundaries:
                if not inst_obj.physical:
                    continue
                bound_name = inst_obj.guid
                this_name = stl_dir + str(stl_name) + "_cfd_" + str(bound_name) + ".stl"
                inst_obj.cfd_face = inst_obj.bound_shape
                if inst_obj.opening_bounds:
                    for opening in inst_obj.opening_bounds:
                        inst_obj.cfd_face = BRepAlgoAPI_Cut(inst_obj.cfd_face, opening.bound_shape).Shape()
                triang_face = BRepMesh_IncrementalMesh(inst_obj.cfd_face, 1)
                # Export to STL
                stl_writer = StlAPI_Writer()
                stl_writer.SetASCIIMode(True)
                stl_writer.Write(triang_face.Shape(), this_name)
            self.combine_space_stl_files(stl_name, space_name, self.paths)

    @staticmethod
    def combined_space_stl(stl_name, paths):
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
    def export_space_bound_list(instances, paths):
        stl_dir = str(paths.export) + '/'
        space_bound_df = pd.DataFrame(columns=["space_id", "bound_ids"])
        for inst in instances:
            if not instances[inst].ifc.is_a("IfcSpace"):
                continue
            space = instances[inst]
            bound_names = []
            for bound in space.space_boundaries:
                bound_names.append(bound.guid)
            space_bound_df = space_bound_df.append({'space_id': space.guid, 'bound_ids': bound_names},
                                                   ignore_index=True)
        space_bound_df.to_csv(stl_dir + "space_bound_list.csv")

    @staticmethod
    def combine_stl_files(stl_name, paths):
        stl_dir = str(paths.export) + '/'
        with open(stl_dir + stl_name + "_combined_STL.stl", 'wb+') as output_file:
            for i in os.listdir(stl_dir + 'STL/'):
                if os.path.isfile(os.path.join(stl_dir + 'STL/', i)) and (stl_name + "_cfd_") in i:
                    sb_mesh = mesh.Mesh.from_file(stl_dir + 'STL/' + i)
                    mesh_name = "cfd_" +i.split("_cfd_", 1)[-1]
                    mesh_name = mesh_name.replace(".stl", "")
                    mesh_name = mesh_name.replace("$", "___")
                    sb_mesh.save(mesh_name, output_file, mode=stl.Mode.ASCII)

    @staticmethod
    def combine_space_stl_files(stl_name, space_name, paths):
        stl_dir = str(paths.export) + '/'
        os.makedirs(os.path.dirname(stl_dir + "space_stl/"), exist_ok=True)

        with open(stl_dir + "space_stl/" + "space_" + space_name + ".stl", 'wb+') as output_file:
            for i in os.listdir(stl_dir + 'STL/' + space_name + "/"):
                if os.path.isfile(os.path.join(stl_dir + 'STL/' + space_name + "/", i)) and (stl_name + "_cfd_") in i:
                    sb_mesh = mesh.Mesh.from_file(stl_dir + 'STL/' + space_name + "/" + i)
                    mesh_name = "cfd_" + i.split("_cfd_", 1)[-1]
                    mesh_name = mesh_name.replace(".stl", "")
                    mesh_name = mesh_name.replace("$", "___")
                    sb_mesh.save(mesh_name, output_file, mode=stl.Mode.ASCII)