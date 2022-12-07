from bim2sim.kernel.elements import bps
from bim2sim.kernel.ifc2python import get_layers_ifc
from bim2sim.task.common.common import CheckIfc


class CheckIfcBPS(CheckIfc):
    """
    Check an IFC file, for a number of conditions (missing information,
    incorrect information, etc) that could lead on future tasks to fatal errors.
    """

    def __init__(self):
        super().__init__()
        self.sub_inst_cls = 'IfcRelSpaceBoundary'
        self.plugin = bps

    def validate_sub_inst(self, bound) -> list:
        """
        Validation function for a space boundary that compiles all validation
        functions.

        Args:
            bound: ifc space boundary entity

        Returns:
            error: list of errors found in the ifc space boundaries
        """
        error = []
        self.apply_validation_function(self._check_unique(bound, self.id_list),
                                       'GlobalId - '
                                       'The space boundary GlobalID is not '
                                       'unique',
                                       error)
        self.apply_validation_function(self._check_level(bound),
                                       '2ndLevel - '
                                       'The space boundary is not 2nd level',
                                       error)
        self.apply_validation_function(self._check_description(bound),
                                       'Description - '
                                       'The space boundary description does '
                                       'not provide level information',
                                       error)
        self.apply_validation_function(self._check_rel_space(bound),
                                       'RelatingSpace - '
                                       'The space boundary does not have a '
                                       'relating space associated', error)
        self.apply_validation_function(self._check_rel_building_elem(bound),
                                       'RelatedBuildingElement - '
                                       'The space boundary does not have a '
                                       'related building element associated',
                                       error)
        self.apply_validation_function(self._check_conn_geom(bound),
                                       'ConnectionGeometry - '
                                       'The space boundary does not have a '
                                       'connection geometry', error)
        self.apply_validation_function(self._check_phys_virt_bound(bound),
                                       'PhysicalOrVirtualBoundary - '
                                       'The space boundary is neither '
                                       'physical or virtual', error)
        self.apply_validation_function(self._check_int_ext_bound(bound),
                                       'InternalOrExternalBoundary - '
                                       'The space boundary is neither '
                                       'external or internal', error)
        self.apply_validation_function(self._check_on_relating_elem(bound),
                                       'SurfaceOnRelatingElement - '
                                       'The space boundary does not have a '
                                       'surface on the relating element', error)
        self.apply_validation_function(self._check_on_related_elem(bound),
                                       'SurfaceOnRelatedElement - '
                                       'The space boundary does not have a '
                                       'surface on the related element', error)
        self.apply_validation_function(self._check_basis_surface(bound),
                                       'BasisSurface - '
                                       'The space boundary surface on '
                                       'relating element geometry is missing',
                                       error)
        self.apply_validation_function(self._check_inner_boundaries(bound),
                                       'InnerBoundaries - '
                                       'The space boundary surface on '
                                       'relating element inner boundaries are '
                                       'missing',  error)
        if hasattr(
                bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary,
                'Segments'):
            self.apply_validation_function(
                self._check_outer_boundary_composite(bound),
                'OuterBoundary - '
                'The space boundary surface on relating element outer '
                'boundary is missing', error)
            self.apply_validation_function(self._check_segments(bound),
                                           'OuterBoundary Segments - '
                                           'The space boundary surface on '
                                           'relating element outer boundary '
                                           'geometry is missing', error)
            self.apply_validation_function(self._check_segments_poly(bound),
                                           'OuterBoundary SegmentsPolyline - '
                                           'The space boundary surface on '
                                           'relating element outer boundary '
                                           'geometry is not well structured',
                                           error)
            self.apply_validation_function(
                self._check_segments_poly_coord(bound),
                'OuterBoundary Coordinates - '
                'The space boundary surface on relating element outer boundary '
                'coordinates are missing', error)
        else:
            self.apply_validation_function(
                self._check_outer_boundary_poly(bound),
                'OuterBoundary - '
                'The space boundary surface on relating element outer boundary '
                'is missing', error)
            self.apply_validation_function(
                self._check_outer_boundary_poly_coord(bound),
                'OuterBoundary Coordinates - '
                'The space boundary surface on relating element outer boundary '
                'coordinates are missing', error)

        self.apply_validation_function(self._check_plane_position(bound),
                                       'Position - '
                                       'The space boundary surface on relating '
                                       'element plane position is missing',
                                       error)
        self.apply_validation_function(self._check_location(bound),
                                       'Location - '
                                       'The space boundary surface on relating '
                                       'element location is missing', error)
        self.apply_validation_function(self._check_axis(bound),
                                       'Axis - '
                                       'The space boundary surface on relating '
                                       'element axis are missing',
                                       error)
        self.apply_validation_function(self._check_refdirection(bound),
                                       'RefDirection - '
                                       'The space boundary surface on relating '
                                       'element reference direction is '
                                       'missing', error)
        self.apply_validation_function(self._check_location_coord(bound),
                                       'LocationCoordinates - '
                                       'The space boundary surface on relating '
                                       'element location coordinates are '
                                       'missing', error)
        self.apply_validation_function(self._check_axis_dir_ratios(bound),
                                       'AxisDirectionRatios - '
                                       'The space boundary surface on relating '
                                       'element axis direction ratios are '
                                       'missing', error)
        self.apply_validation_function(
            self._check_refdirection_dir_ratios(bound),
            'RefDirectionDirectionRatios - '
            'The space boundary surface on relating element position '
            'reference direction is missing', error)

        return error

    def validate_instances(self, inst) -> list:
        """
        Validation function for an instance that compiles all instance
        validation functions.

        Args:
            inst:IFC instance being checked

        Returns:
            error: list of instances error

        """
        error = []
        self.apply_validation_function(self._check_unique(inst, self.id_list),
                                       'GlobalId - '
                                       'The instance GlobalID is not unique'
                                       , error)
        self.apply_validation_function(self._check_inst_sb(inst),
                                       'SpaceBoundaries - '
                                       'The instance space boundaries are '
                                       'missing', error)
        self.apply_validation_function(self._check_inst_materials(inst),
                                       'MaterialLayers - '
                                       'The instance materials are missing',
                                       error)
        self.apply_validation_function(self._check_inst_properties(inst),
                                       'Missing Property_Sets - '
                                       'One or more instance\'s necessary '
                                       'property sets are missing', error)
        self.apply_validation_function(self._check_inst_contained_in_structure(inst),
                                       'ContainedInStructure - '
                                       'The instance is not contained in any '
                                       'structure', error)
        self.apply_validation_function(self._check_inst_representation(inst),
                                       'Representation - '
                                       'The instance has no geometric '
                                       'representation', error)
        return error

    @staticmethod
    def _check_level(bound):
        """
        Check that the space boundary is of the second level type

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.Name == "2ndLevel"

    @staticmethod
    def _check_description(bound):
        """
        Check that the space boundary description is 2a or 2b

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.Description in {'2a', '2b'}

    @staticmethod
    def _check_rel_space(bound):
        """
        Check that the space boundary relating space exists and has the
        correct class.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return any(
            [bound.RelatingSpace.is_a('IfcSpace') or
             bound.RelatingSpace.is_a('IfcExternalSpatialElement')])

    @staticmethod
    def _check_rel_building_elem(bound):
        """
        Check that the space boundary related building element exists and has
        the correct class.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        if bound.RelatedBuildingElement is not None:
            return bound.RelatedBuildingElement.is_a('IfcBuildingElement')

    @staticmethod
    def _check_conn_geom(bound):
        """
        Check that the space boundary has a connection geometry and has the
        correct class.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.ConnectionGeometry.is_a('IfcConnectionSurfaceGeometry')

    @staticmethod
    def _check_phys_virt_bound(bound):
        """
        Check that the space boundary is virtual or physical.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.PhysicalOrVirtualBoundary.upper() in \
            {'PHYSICAL', 'VIRTUAL'}

    @staticmethod
    def _check_int_ext_bound(bound):
        """
        Check that the space boundary is internal or external.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.InternalOrExternalBoundary.upper() in {'INTERNAL',
                                                            'EXTERNAL',
                                                            'EXTERNAL_EARTH',
                                                            'EXTERNAL_FIRE',
                                                            'EXTERNAL_WATER'
                                                            }

    @staticmethod
    def _check_on_relating_elem(bound):
        """
        Check that the surface on relating element of a space boundary has
        the geometric information.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.ConnectionGeometry.SurfaceOnRelatingElement.is_a(
            'IfcCurveBoundedPlane')

    @staticmethod
    def _check_on_related_elem(bound):
        """
        Check that the surface on related element of a space boundary has no
        geometric information.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.ConnectionGeometry.SurfaceOnRelatedElement is None

    @staticmethod
    def _check_basis_surface(bound):
        """
        Check that the surface on relating element of a space boundary is
        represented by an IFC Place.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.ConnectionGeometry.SurfaceOnRelatingElement. \
            BasisSurface.is_a('IfcPlane')

    @staticmethod
    def _check_inner_boundaries(bound):
        """
        Check if the surface on relating element of a space boundary inner
        boundaries don't exists or are composite curves.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return (bound.ConnectionGeometry.SurfaceOnRelatingElement.
                InnerBoundaries is None) or \
               (i.is_a('IfcCompositeCurve') for i in bound.ConnectionGeometry.
                   SurfaceOnRelatingElement.InnerBoundaries)

    @staticmethod
    def _check_outer_boundary_composite(bound):
        """
        Check if the surface on relating element of a space boundary outer
        boundaries are composite curves.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.ConnectionGeometry.SurfaceOnRelatingElement. \
            OuterBoundary.is_a('IfcCompositeCurve')

    @staticmethod
    def _check_segments(bound):
        """
        Check if the surface on relating element of a space boundary outer
        boundaries segments are polyline.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return (s.is_a('IfcPolyline') for s in
                bound.ConnectionGeometry.SurfaceOnRelatingElement.
                OuterBoundary.Segments)

    @classmethod
    def _check_segments_poly(cls, bound):
        """
        Check segments of an outer boundary of a surface on relating element.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return all(cls._check_poly_points(s.ParentCurve)
                   for s in
                   bound.ConnectionGeometry.SurfaceOnRelatingElement
                   .OuterBoundary.Segments)

    @classmethod
    def _check_segments_poly_coord(cls, bound):
        """
        Check segments coordinates of an outer boundary of a surface on
        relating element.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return all(cls._check_poly_points_coord(s.ParentCurve)
                   for s in
                   bound.ConnectionGeometry.SurfaceOnRelatingElement.
                   OuterBoundary.Segments)

    @classmethod
    def _check_outer_boundary_poly(cls, bound):
        """
        Check points of outer boundary of a surface on relating element.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return cls._check_poly_points(
            bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary)

    @staticmethod
    def _check_outer_boundary_poly_coord(bound):
        """
        Check outer boundary of a surface on relating element.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return all(
            bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary)

    @staticmethod
    def _check_plane_position(bound):
        """
        Check class of plane position of space boundary.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface. \
            Position.is_a('IfcAxis2Placement3D')

    @staticmethod
    def _check_location(bound):
        """
        Check that location of a space boundary is an IfcCartesianPoint.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface. \
            Position.Location.is_a('IfcCartesianPoint')

    @staticmethod
    def _check_axis(bound):
        """
        Check that axis of space boundary is an IfcDirection.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface. \
            Position.Axis.is_a('IfcDirection')

    @staticmethod
    def _check_refdirection(bound):
        """
        Check that reference direction of space boundary is an IfcDirection.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface. \
            Position.RefDirection.is_a('IfcDirection')

    @classmethod
    def _check_location_coord(cls, bound):
        """
        Check if space boundary surface on relating element coordinates are
        correct.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return cls._check_coords(bound.ConnectionGeometry.
                                 SurfaceOnRelatingElement.BasisSurface.
                                 Position.Location)

    @classmethod
    def _check_axis_dir_ratios(cls, bound):
        """
        Check if space boundary surface on relating element axis are correct.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return cls._check_dir_ratios(
            bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.
            Position.Axis)

    @classmethod
    def _check_refdirection_dir_ratios(cls, bound):
        """
        Check if space boundary surface on relating element reference direction
        are correct.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return cls._check_dir_ratios(
            bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.
            Position.RefDirection)

    @staticmethod
    def _check_poly_points(polyline):
        """
        Check if a polyline has the correct class.

        Args:
            polyline: Polyline IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return polyline.is_a('IfcPolyline')

    @staticmethod
    def _check_coords(points):
        """
        Check coordinates of a group of points (class and length).

        Args:
            points: Points IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return points.is_a('IfcCartesianPoint') and 1 <= len(
            points.Coordinates) <= 4

    @staticmethod
    def _check_dir_ratios(dir_ratios):
        """
        Check length of direction ratios.

        Args:
            dir_ratios: direction ratios IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return 2 <= len(dir_ratios.DirectionRatios) <= 3

    @classmethod
    def _check_poly_points_coord(cls, polyline):
        """
        Check if a polyline has the correct coordinates.

        Args:
            polyline: Polyline IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return all(cls._check_coords(p) for p in polyline.Points)

    @staticmethod
    def _check_inst_sb(inst):
        """
        Check that an instance has associated space boundaries (space or
        building element).

        Args:
            inst: IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        blacklist = ['IfcBuilding', 'IfcSite', 'IfcBuildingStorey',
                     'IfcMaterial', 'IfcMaterialLayer', 'IfcMaterialLayerSet']
        if inst.is_a() in blacklist:
            return True
        elif inst.is_a('IfcSpace'):
            return len(inst.BoundedBy) > 0
        else:
            if len(inst.ProvidesBoundaries) > 0:
                return True
            decompose = []
            if hasattr(inst, 'Decomposes') and len(inst.Decomposes):
                decompose = [decomp.RelatingObject for decomp in
                             inst.Decomposes]
            elif hasattr(inst, 'IsDecomposedBy') and len(inst.IsDecomposedBy):
                decompose = []
                for decomp in inst.IsDecomposedBy:
                    for inst_ifc in decomp.RelatedObjects:
                        decompose.append(inst_ifc)
            for inst_decomp in decompose:
                if len(inst_decomp.ProvidesBoundaries):
                    return True
        return False

    @staticmethod
    def _check_inst_materials(inst):
        """
        Check that an instance has associated materials.

        Args:
            inst: IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        blacklist = ['IfcBuilding', 'IfcSite', 'IfcBuildingStorey', 'IfcSpace']
        if not (inst.is_a() in blacklist):
            return len(get_layers_ifc(inst)) > 0
        return True

    @staticmethod
    def _check_inst_contained_in_structure(inst):
        """
        Check that an instance is contained in an structure.

        Args:
            inst: IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        blacklist = [
            'IfcBuilding', 'IfcSite', 'IfcBuildingStorey', 'IfcSpace',
            'IfcMaterial', 'IfcMaterialLayer', 'IfcMaterialLayerSet'
        ]
        if not (inst.is_a() in blacklist):
            return len(inst.ContainedInStructure) > 0
        if hasattr(inst, 'Decomposes'):
            return len(inst.Decomposes) > 0
        else:
            return True

    @staticmethod
    def _check_inst_representation(inst):
        """
        Check that an instance has a correct geometric representation.

        Args:
            inst: IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        blacklist = [
            'IfcBuilding', 'IfcBuildingStorey', 'IfcMaterial',
            'IfcMaterialLayer', 'IfcMaterialLayerSet'
        ]
        if not (inst.is_a() in blacklist):
            return inst.Representation is not None
        return True
