from collections import OrderedDict

import stl
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.StlAPI import StlAPI_Writer
from OCC.Core.TopOpeBRep import TopOpeBRep_ShapeIntersector
from OCC.Core.gp import gp_Pnt
from stl import mesh

from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.utils.openfoam_utils import \
    OpenFOAMUtils as of_utils
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.pyocc_tools import PyOCCTools
from butterfly.butterfly import blockMeshDict, snappyHexMeshDict, foamfile


class CreateOpenFOAMMeshing(ITask):
    """This ITask initializes the OpenFOAM Meshing.
    """

    reads = ('openfoam_case', 'openfoam_elements')
    touches = ('openfoam_case', 'openfoam_elements')

    def __init__(self, playground):
        super().__init__(playground)

    def run(self, openfoam_case, openfoam_elements):
        # create blockMesh based on surface geometry
        self.create_blockMesh(openfoam_case)
        # create snappyHexMesh based on surface types
        self.create_snappyHexMesh(openfoam_case, openfoam_elements)
        self.update_snappyHexMesh_heating(openfoam_case, openfoam_elements)
        self.add_topoSetDict_for_heating(openfoam_case, openfoam_elements)
        self.modify_topoSet_for_evaluation(openfoam_case, openfoam_elements)
        self.update_blockMeshDict_air(openfoam_case, openfoam_elements)
        self.update_snappyHexMesh_air(openfoam_case, openfoam_elements)
        self.update_snappyHexMesh_furniture(openfoam_case, openfoam_elements)
        self.update_snappyHexMesh_people(openfoam_case, openfoam_elements)
        return openfoam_case, openfoam_elements

    def create_blockMesh(self, openfoam_case, resize_factor=0.1, shape=None):
        mesh_size = self.playground.sim_settings.mesh_size
        if not shape:
            shape = openfoam_case.current_zone.space_shape
        (min_pt, max_pt) = PyOCCTools.simple_bounding_box(shape)
        scaled_min_pt = []
        scaled_max_pt = []
        len_xyz = []
        for p1, p2 in zip(min_pt, max_pt):
            p1 -= resize_factor
            p2 += resize_factor
            len_xyz.append(p2 - p1)
            scaled_min_pt.append(p1)
            scaled_max_pt.append(p2)

        # calculate number of cells per xyz direction
        n_div_xyz = (round(len_xyz[0] / mesh_size),
                     round(len_xyz[1] / mesh_size),
                     round(len_xyz[2] / mesh_size))
        openfoam_case.blockMeshDict = blockMeshDict.BlockMeshDict.from_min_max(
            scaled_min_pt, scaled_max_pt, n_div_xyz=n_div_xyz)
        openfoam_case.blockMeshDict.save(openfoam_case.openfoam_dir)

    def create_snappyHexMesh(self, openfoam_case, openfoam_elements, ):
        stl_name = "space_" + openfoam_case.current_zone.guid
        region_names = []
        regions = {}
        mesh_objects = mesh.Mesh.from_multi_file(
            openfoam_case.openfoam_triSurface_dir /
            str(stl_name + '.stl'),
            mode=stl.Mode.ASCII)
        for obj in mesh_objects:
            region_names.append(str(obj.name, encoding='utf-8'))
        for name in region_names:
            regions.update({name: {'name': name}})
        openfoam_case.snappyHexMeshDict = snappyHexMeshDict.SnappyHexMeshDict()
        openfoam_case.snappyHexMeshDict.add_stl_geometry(
            str("space_" + openfoam_case.current_zone.guid), regions)

        # self.snappyHexMesh.values['geometry']['regions'].update(regions)
        location_in_mesh = (
            str('(' +
                str(
                    openfoam_case.current_zone.space_center.Coord()[
                        0]) + ' ' +
                str(
                    openfoam_case.current_zone.space_center.Coord()[
                        1]) + ' ' +
                str(
                    openfoam_case.current_zone.space_center.Coord()[
                        2]) + ')'
                ))
        openfoam_case.snappyHexMeshDict.values['castellatedMeshControls'][
            'locationInMesh'] = location_in_mesh
        self.set_refinementSurfaces(openfoam_case, openfoam_elements,
                                    region_names)
        openfoam_case.snappyHexMeshDict.values['castellatedMeshControls'][
            'refinementSurfaces'].update(openfoam_case.refinementSurfaces)

        openfoam_case.snappyHexMeshDict.save(openfoam_case.openfoam_dir)

    @staticmethod
    def set_refinementSurfaces(openfoam_case, openfoam_elements,
                               region_names,
                               default_refinement_level=[1, 2]):
        (stl_bounds, heaters, air_terminals,
         furniture, people) = of_utils.split_openfoam_elements(
            openfoam_elements)
        stl_name = "space_" + openfoam_case.current_zone.guid

        refinementSurface_regions = {}

        for obj in stl_bounds:
            refinementSurface_regions.update(
                {obj.solid_name:
                    {
                        'level': '({} {})'.format(
                            int(obj.refinement_level[0]),
                            int(obj.refinement_level[1])),
                        'patchInfo':
                            {'type': obj.patch_info_type}}})

        openfoam_case.refinementSurfaces = {stl_name:
            {
                'level': '({} {})'.format(
                    int(default_refinement_level[0]),
                    int(default_refinement_level[
                            1])),
                'regions': refinementSurface_regions
            }}

        # todo: different approach for air terminals (partially patchInfo
        # wall, partially inlet / outlet.

    def update_snappyHexMesh_heating(self, openfoam_case, openfoam_elements):
        heaters = filter_elements(openfoam_elements, 'Heater')
        for heater in heaters:
            openfoam_case.snappyHexMeshDict.values['geometry'].update(
                {
                    heater.heater_surface.stl_name:
                        {
                            'type': 'triSurfaceMesh',
                            'name': heater.heater_surface.solid_name,
                            'regions':
                                {heater.heater_surface.solid_name:
                                    {
                                        'name': heater.heater_surface.solid_name
                                    }
                                }
                        },
                    heater.porous_media.solid_name:
                        {
                            'type': 'searchableBox',
                            'min': f"({heater.porous_media.bbox_min_max[0][0]} "
                                   f"{heater.porous_media.bbox_min_max[0][1]} "
                                   f"{heater.porous_media.bbox_min_max[0][2]})",
                            'max': f"({heater.porous_media.bbox_min_max[1][0]} "
                                   f"{heater.porous_media.bbox_min_max[1][1]} "
                                   f"{heater.porous_media.bbox_min_max[1][2]})",
                        },
                    heater.solid_name + '_refinement_small':
                        {
                            'type': 'searchableBox',
                            'min': f"({heater.refinement_zone_small[0][0]} "
                                   f"{heater.refinement_zone_small[0][1]} "
                                   f"{heater.refinement_zone_small[0][2]})",
                            'max': f"({heater.refinement_zone_small[1][0]} "
                                   f"{heater.refinement_zone_small[1][1]} "
                                   f"{heater.refinement_zone_small[1][2]})",
                        },
                    heater.solid_name + '_refinement_large':
                        {
                            'type': 'searchableBox',
                            'min': f"({heater.refinement_zone_large[0][0]} "
                                   f"{heater.refinement_zone_large[0][1]} "
                                   f"{heater.refinement_zone_large[0][2]})",
                            'max': f"({heater.refinement_zone_large[1][0]} "
                                   f"{heater.refinement_zone_large[1][1]} "
                                   f"{heater.refinement_zone_large[1][2]})",
                        }
                }
            )
            openfoam_case.snappyHexMeshDict.values['castellatedMeshControls'][
                'refinementSurfaces'].update(
                {
                    heater.heater_surface.solid_name:
                        {
                            'level': '(1 2)',
                            'regions':
                                {
                                    heater.heater_surface.solid_name:
                                        {
                                            'level':
                                                f"({heater.heater_surface.refinement_level[0]} "
                                                f"{heater.heater_surface.refinement_level[1]})",
                                            'patchInfo':
                                                {
                                                    'type':
                                                        heater.heater_surface.patch_info_type
                                                }
                                        }
                                }
                        }
                },
            )
            openfoam_case.snappyHexMeshDict.values['castellatedMeshControls'][
                'refinementRegions'].update(
                {
                    heater.porous_media.solid_name:
                        {
                            'mode': 'inside',
                            'levels':
                                f'(('
                                f'{heater.porous_media.refinement_level[0]} '
                                f'{heater.porous_media.refinement_level[1]-1}))'
                        },
                    heater.solid_name + '_refinement_small':
                        {
                            'mode': 'inside',
                            'levels':
                                f'(('
                                f'{heater.refinement_level[0]} '
                                f'{heater.refinement_level[0]+2}))'
                        },
                    heater.solid_name + '_refinement_large':
                        {
                            'mode': 'inside',
                            'levels':
                                f'(('
                                f'{heater.refinement_level[0]} '
                                f'{heater.refinement_level[0]+1}))'
                        }

                }
            )
            openfoam_case.snappyHexMeshDict.save(openfoam_case.openfoam_dir)

    @staticmethod
    def add_topoSetDict_for_heating(openfoam_case, openfoam_elements):
        heaters = filter_elements(openfoam_elements, 'Heater')
        openfoam_case.topoSetDict = foamfile.FoamFile(
            name='topoSetDict', cls='dictionary', location='system',
            default_values=OrderedDict()
        )
        openfoam_case.topoSetDict.values.update(
            {'actions (': '//'})
        for h in heaters:
            openfoam_case.topoSetDict.values.update(
                {f'//{h.solid_name}': {
                    'name': h.porous_media.solid_name,
                    'action': 'new',
                    'type': 'cellSet',
                    'source': 'surfaceToCell',
                    'sourceInfo':
                        {
                            'file': fr'"constant/triSurface/'
                                    fr'{h.porous_media.stl_name}"',
                            'useSurfaceOrientation': 'true',
                            'outsidePoints': '((0 0 0))',
                            'includeCut': 'false',
                            'includeInside': 'true',
                            'includeOutside': 'false',
                            'nearDistance': '-1',
                            'curvature': '0',
                        }
                },
                }
            )
        openfoam_case.topoSetDict.values.update({');': '//'})  # required to
        # close
        # the
        # round bracket. Replace by better option if you find any.

        openfoam_case.topoSetDict.save(openfoam_case.openfoam_dir)

    @staticmethod
    def modify_topoSet_for_evaluation(openfoam_case, openfoam_elements):
        furniture = filter_elements(openfoam_elements, 'Furniture')
        people = filter_elements(openfoam_elements, 'People')
        heaters = filter_elements(openfoam_elements, 'Heater')
        airterminals = filter_elements(openfoam_elements, 'AirTerminal')
        cut_shapes = []
        for furn in furniture:
            cut_shapes.append(
                PyOCCTools.unify_shape(PyOCCTools.make_solid_from_shape(
                    PyOCCTools, PyOCCTools.simple_bounding_box_shape([
                        furn.tri_geom]))))
        for heater in heaters:
            cut_shapes.append(
                PyOCCTools.unify_shape(PyOCCTools.make_solid_from_shape(
                    PyOCCTools,
                    PyOCCTools.scale_shape(heater.porous_media.tri_geom, 1.1))))
        for person in people:
            cut_shapes.append(
                PyOCCTools.unify_shape(PyOCCTools.make_solid_from_shape(
                    PyOCCTools, PyOCCTools.simple_bounding_box_shape(
                        [person.scaled_surface]))))
        for air in airterminals:
            cut_shapes.append(
                PyOCCTools.unify_shape(PyOCCTools.make_solid_from_shape(
                    PyOCCTools, PyOCCTools.scale_shape(air.bbox_min_max_shape,
                                                       1.1))))
        space_solid_shrinked = (PyOCCTools.make_solid_from_shape(
            PyOCCTools, PyOCCTools.scale_shape(
                openfoam_case.current_zone.space_shape, 0.9)))
        shape = space_solid_shrinked
        for cut_shape in cut_shapes:
            ins = TopOpeBRep_ShapeIntersector()
            ins.InitIntersection(cut_shape, shape)
            if ins.MoreIntersection():
                shape = BRepAlgoAPI_Cut(shape, cut_shape).Shape()
                shape = PyOCCTools.make_solid_from_shape(PyOCCTools, shape)
        tri_eval_shape = PyOCCTools.triangulate_bound_shape(shape)
        stl_writer = StlAPI_Writer()
        stl_writer.SetASCIIMode(True)
        stl_writer.Write(tri_eval_shape,
                         str(openfoam_case.openfoam_triSurface_dir /
                             'evaluate_air_volume.stl'))
        openfoam_case.topoSetDict.values.pop(');')  # required to

        for person in people:
            tri_eval_shape = PyOCCTools.triangulate_bound_shape(
                person.scaled_surface)
            stl_writer = StlAPI_Writer()
            stl_writer.SetASCIIMode(True)
            stl_writer.Write(tri_eval_shape,
                             str(openfoam_case.openfoam_triSurface_dir /
                                 f"evaluate_{person.solid_name}.stl"))
            openfoam_case.topoSetDict.values.update(
                {f'//evaluate_{person.solid_name}': {
                    'name': f"evaluate_{person.solid_name}",
                    'action': 'new',
                    'type': 'cellSet',
                    'source': 'surfaceToCell',
                    'sourceInfo':
                        {
                            'file': fr'"constant/triSurface/'
                                    fr'evaluate_{person.solid_name}.stl"',
                            'useSurfaceOrientation': 'false',
                            'outsidePoints':
                                f'(('
                                f'{openfoam_case.current_zone.space_center.X()} '
                                f'{openfoam_case.current_zone.space_center.Y()} '
                                f'{openfoam_case.current_zone.space_center.Z()}'
                                f' ))',
                            'includeCut': 'true',
                            'includeInside': 'false',
                            'includeOutside': 'false',
                            'nearDistance': '-1',
                            'curvature': '0',
                        }
                },
                }
            )
        openfoam_case.topoSetDict.values.update(
            {f'//evaluate air volume': {
                'name': 'evaluate_air_volume',
                'action': 'new',
                'type': 'cellSet',
                'source': 'surfaceToCell',
                'sourceInfo':
                    {
                        'file': fr'"constant/triSurface/'
                                fr'evaluate_air_volume.stl"',
                        'useSurfaceOrientation': 'true',
                        'outsidePoints': '((0 0 0))',
                        'includeCut': 'false',
                        'includeInside': 'true',
                        'includeOutside': 'false',
                        'nearDistance': '-1',
                        'curvature': '0',
                    }
            },
            }
        )
        openfoam_case.topoSetDict.values.update({');': '//'})  # required to
        # close
        # the
        # round bracket. Replace by better option if you find any.

        openfoam_case.topoSetDict.save(openfoam_case.openfoam_dir)

        # update controlDict for evaluation
        for person in people:
            for operation in ['average', 'min', 'max']:
                evaluate_dict = {
                    f"{person.solid_name}_{operation}": {
                        'type': 'volFieldValue',
                        'libs': '(fieldFunctionObjects)',
                        'log': 'true',
                        'writeFields': 'false',
                        'enabled': 'true',
                        'writeControl': 'timeStep',
                        'writeInterval': '1',
                        'regionType': 'cellZone',
                        'name': f"evaluate_{person.solid_name}",
                        'operation': operation,
                        'fields': '( T U PMV PPD )'
                    }}
                openfoam_case.controlDict.values['functions'].update(
                    evaluate_dict)
        for operation in ['average', 'min', 'max']:
            evaluate_dict = {
                f"evaluate_air_volume_{operation}": {
                    'type': 'volFieldValue',
                    'libs': '(fieldFunctionObjects)',
                    'log': 'true',
                    'writeFields': 'false',
                    'enabled': 'true',
                    'writeControl': 'timeStep',
                    'writeInterval': '1',
                    'regionType': 'cellZone',
                    'name': f"evaluate_air_volume",
                    'operation': operation,
                    'fields': '( T U PMV PPD )'
                }}
            openfoam_case.controlDict.values['functions'].update(
                evaluate_dict)

        openfoam_case.controlDict.save(openfoam_case.openfoam_dir)

    def update_blockMeshDict_air(self, openfoam_case, openfoam_elements):
        air_terminals = filter_elements(openfoam_elements, 'AirTerminal')
        new_min_max = PyOCCTools.simple_bounding_box([
            openfoam_case.current_zone.space_shape,
            *[inlet_outlet.bbox_min_max_shape
              for inlet_outlet in
              air_terminals]])
        new_blockmesh_box = BRepPrimAPI_MakeBox(
            gp_Pnt(*new_min_max[0]),
            gp_Pnt(*new_min_max[1])).Shape()

        self.create_blockMesh(openfoam_case, shape=new_blockmesh_box)

    def update_snappyHexMesh_air(self, openfoam_case, openfoam_elements):
        air_terminals = filter_elements(openfoam_elements, 'AirTerminal')
        for air_terminal in air_terminals:
            for name in [air_terminal.diffuser.solid_name,
                         air_terminal.source_sink.solid_name,
                         air_terminal.box.solid_name]:
                if not name:
                    continue
                openfoam_case.snappyHexMeshDict.values['geometry'].update(
                    {
                        name + '.stl':
                            {
                                'type': 'triSurfaceMesh',
                                'name': name,
                                'regions':
                                    {name:
                                        {
                                            'name': name
                                        }
                                    }
                            }
                    }
                )
            openfoam_case.snappyHexMeshDict.values['geometry'].update({
                air_terminal.air_type + '_refinement_small':
                    {
                        'type': 'searchableBox',
                        'min': f"({air_terminal.refinement_zone_small[0][0]} "
                               f"{air_terminal.refinement_zone_small[0][1]} "
                               f"{air_terminal.refinement_zone_small[0][2]})",
                        'max': f"({air_terminal.refinement_zone_small[1][0]} "
                               f"{air_terminal.refinement_zone_small[1][1]} "
                               f"{air_terminal.refinement_zone_small[1][2]})",
                    },
                air_terminal.air_type + '_refinement_large':
                    {
                        'type': 'searchableBox',
                        'min': f"({air_terminal.refinement_zone_large[0][0]} "
                               f"{air_terminal.refinement_zone_large[0][1]} "
                               f"{air_terminal.refinement_zone_large[0][2]})",
                        'max': f"({air_terminal.refinement_zone_large[1][0]} "
                               f"{air_terminal.refinement_zone_large[1][1]} "
                               f"{air_terminal.refinement_zone_large[1][2]})",
                    }
            }
            )
            if air_terminal.diffuser.solid_name:
                openfoam_case.snappyHexMeshDict.values[
                    'castellatedMeshControls'][
                    'refinementSurfaces'].update(
                    {air_terminal.diffuser.solid_name:
                         {'level':
                              f"({air_terminal.diffuser.refinement_level[0]}"
                              f" {air_terminal.diffuser.refinement_level[1]})",
                          'regions':
                              {air_terminal.diffuser.solid_name:
                                   {'level':
                                        f"({air_terminal.diffuser.refinement_level[0]}"
                                        f" {air_terminal.diffuser.refinement_level[1]})",
                                    'patchInfo': {
                                        'type':
                                            air_terminal.diffuser.patch_info_type}}}}
                     },
                )
            openfoam_case.snappyHexMeshDict.values['castellatedMeshControls'][
                'refinementSurfaces'].update(
                {air_terminal.source_sink.solid_name:
                     {'level': '(1 2)', 'regions':
                         {air_terminal.source_sink.solid_name: {
                             'level': f"({air_terminal.source_sink.refinement_level[0]}"
                                      f" {air_terminal.source_sink.refinement_level[1]})",
                             'patchInfo': {
                                 'type': air_terminal.air_type}}}}
                 },
            )
            openfoam_case.snappyHexMeshDict.values['castellatedMeshControls'][
                'refinementSurfaces'].update(
                {air_terminal.box.solid_name:
                     {'level': '(1 2)',
                      'regions': {
                          air_terminal.box.solid_name: {
                              'level': f"({air_terminal.box.refinement_level[0]}"
                                       f" {air_terminal.box.refinement_level[1]})",
                              'patchInfo': {
                                  'type':
                                      air_terminal.box.patch_info_type}}}}
                 },
            )
            openfoam_case.snappyHexMeshDict.values['castellatedMeshControls'][
                'refinementRegions'].update(
                {air_terminal.air_type + '_refinement_small':
                     {'mode': 'inside',
                      'levels': f"(({air_terminal.refinement_zone_level_small[0]} "
                                f"{air_terminal.refinement_zone_level_small[1]-1}))"},
                 air_terminal.air_type + '_refinement_large':
                     {'mode': 'inside',
                      'levels': f"(({air_terminal.refinement_zone_level_large[0]} "
                                f"{air_terminal.refinement_zone_level_large[1]-2}))"}}
            )
            openfoam_case.snappyHexMeshDict.values[
                # 'castellatedMeshControls'].update({'maxLocalCells':
                # 2000000}) # works
                'castellatedMeshControls'].update({'maxLocalCells': 1000000})
            openfoam_case.snappyHexMeshDict.values[
                # 'castellatedMeshControls'].update({'maxGlobalCells':
                # 6000000}) works
                'castellatedMeshControls'].update({'maxGlobalCells':
                                                       self.playground.sim_settings.mesh_max_global_cells})
            openfoam_case.snappyHexMeshDict.values[
                'meshQualityControls'].update({'maxBoundarySkewness': 20})
            openfoam_case.snappyHexMeshDict.values[
                'meshQualityControls'].update({'maxInternalSkewness': 3})
            openfoam_case.snappyHexMeshDict.values[
                'castellatedMeshControls'].update({'resolveFeatureAngle': 180})
            openfoam_case.snappyHexMeshDict.values[
                'castellatedMeshControls'].update({'minRefinementCells': 5})
            openfoam_case.snappyHexMeshDict.values[
                'snapControls'].update({'nSolveIter': 50})
            openfoam_case.snappyHexMeshDict.values[
                'snapControls'].update({'tolerance': 5})
        openfoam_case.snappyHexMeshDict.save(openfoam_case.openfoam_dir)

    def update_snappyHexMesh_furniture(self, openfoam_case, openfoam_elements):
        furnitures = filter_elements(openfoam_elements, 'Furniture')
        for furniture in furnitures:
            openfoam_case.snappyHexMeshDict.values['geometry'].update(
                {
                    furniture.stl_name:
                        {
                            'type': 'triSurfaceMesh',
                            'name': furniture.solid_name,
                            'regions':
                                {furniture.solid_name:
                                    {
                                        'name': furniture.solid_name
                                    }
                                }
                        },
                    # furniture.solid_name + '_refinement_small':
                    #     {
                    #         'type': 'searchableBox',
                    #         'min': f"({furniture.refinement_zone_small[0][0]} "
                    #                f"{furniture.refinement_zone_small[0][1]} "
                    #                f"{furniture.refinement_zone_small[0][2]})",
                    #         'max': f"({furniture.refinement_zone_small[1][0]} "
                    #                f"{furniture.refinement_zone_small[1][1]} "
                    #                f"{furniture.refinement_zone_small[1][2]})",
                    #     },
                    # furniture.solid_name + '_refinement_large':
                    #     {
                    #         'type': 'searchableBox',
                    #         'min': f"({furniture.refinement_zone_large[0][0]} "
                    #                f"{furniture.refinement_zone_large[0][1]} "
                    #                f"{furniture.refinement_zone_large[0][2]})",
                    #         'max': f"({furniture.refinement_zone_large[1][0]} "
                    #                f"{furniture.refinement_zone_large[1][1]} "
                    #                f"{furniture.refinement_zone_large[1][2]})",
                    #     }
                }
            )
            openfoam_case.snappyHexMeshDict.values['castellatedMeshControls'][
                'refinementSurfaces'].update(
                {
                    furniture.solid_name:
                        {
                            'level': '(1 2)',
                            'regions':
                                {
                                    furniture.solid_name:
                                        {
                                            'level':
                                                f"({furniture.refinement_level[0]} "
                                                f"{furniture.refinement_level[1]})",
                                            'patchInfo':
                                                {
                                                    'type':
                                                        furniture.patch_info_type
                                                }
                                        }
                                }
                        }
                },
            )
            # openfoam_case.snappyHexMeshDict.values['castellatedMeshControls'][
            #     'refinementRegions'].update(
            #     {
            #         furniture.solid_name + '_refinement_small':
            #             {
            #                 'mode': 'inside',
            #                 'levels':
            #                     f'(({furniture.refinement_zone_level_small[0]} '
            #                     f'{furniture.refinement_zone_level_small[1]}))',
            #                 'regions':
            #                     {furniture.stl_name:
            #                          {'mode': 'outside'}},
            #             }
            #     }
            # )
            openfoam_case.snappyHexMeshDict.save(openfoam_case.openfoam_dir)

    def update_snappyHexMesh_people(self, openfoam_case, openfoam_elements):
        people = filter_elements(openfoam_elements, 'People')
        for person in people:
            openfoam_case.snappyHexMeshDict.values['geometry'].update(
                {
                    person.solid_name + "_box":
                        {
                            'type': 'searchableBox',
                            'min': f"({person.bbox_min_max[0][0]} "
                                   f"{person.bbox_min_max[0][1]} "
                                   f"{person.bbox_min_max[0][2]})",
                            'max': f"({person.bbox_min_max[1][0]} "
                                   f"{person.bbox_min_max[1][1]} "
                                   f"{person.bbox_min_max[1][2]})",
                        },
                }
            )
            openfoam_case.snappyHexMeshDict.values['castellatedMeshControls'][
                'refinementRegions'].update(
                {
                    person.solid_name + "_box":
                        {'mode': 'inside',
                         'levels': f"(({person.refinement_level[0]} "
                                   f"{person.refinement_level[1]-1}))"
                         },
                }
            )
            for body_part in person.body_parts_dict.values():
                openfoam_case.snappyHexMeshDict.values['geometry'].update(
                    {
                        body_part.stl_name:
                            {
                                'type': 'triSurfaceMesh',
                                'name': body_part.solid_name,
                                'regions':
                                    {body_part.solid_name:
                                        {
                                            'name': body_part.solid_name
                                        }
                                    }
                            },
                    })

                openfoam_case.snappyHexMeshDict.values[
                    'castellatedMeshControls'][
                    'refinementSurfaces'].update(
                    {
                        body_part.solid_name:
                            {
                                'level': '(1 2)',
                                'regions':
                                    {
                                        body_part.solid_name:
                                            {
                                                'level':
                                                    f"("
                                                    f"{person.refinement_level[0]} "
                                                    f"{person.refinement_level[1]})",
                                                'patchInfo':
                                                    {
                                                        'type':
                                                            body_part.patch_info_type
                                                    }
                                            }
                                    }
                            }
                    },
                )
                openfoam_case.snappyHexMeshDict.save(openfoam_case.openfoam_dir)
