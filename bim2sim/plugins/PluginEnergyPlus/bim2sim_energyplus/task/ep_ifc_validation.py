import json

from bim2sim.tasks.base import ITask


class IfcValidation(ITask):
    """
    Validate IFC file, focussing on energy modeling (use of space boundaries).
    """

    reads = ('ifc_files', )

    def __init__(self, playground):
        super().__init__(playground)
        self.error_summary = {}
        self.bounds = []
        self.id_list = []

    def run(self, ifc_files):
        self.bounds = []
        self.id_list = []
        for ifc in ifc_files:

            self.bounds.extend(ifc.by_type('IfcRelSpaceBoundary'))
            self.id_list.extend([e.GlobalId for e in ifc.by_type("IfcRoot")])

        self._check_space_boundaries()
        self._write_errors_to_json()
        self._evaluate_checks()

    def _check_space_boundaries(self):
        """ Perform space boundary validation and add errors to error summary."""
        self.logger.info("Check syntax of IfcRelSpaceBoundary")
        for bound in self.bounds:
            sbv = SpaceBoundaryValidation(bound, self.id_list)
            if len(sbv.error) > 0:
                self.error_summary.update({bound.GlobalId: sbv.error})

    def _write_errors_to_json(self):
        """write error summary to json file for export."""
        with open(str(self.paths.root) + "/export/" + 'ifc_SB_error_summary.json', 'w+') as fp:
            json.dump(self.error_summary, fp, indent="\t")
        self.logger.info("All tests done!")

    def _evaluate_checks(self):
        """Add error summary to logging."""
        if len(self.error_summary) == 0:
            self.logger.info(
                "All %d IfcRelSpaceBoundary entities PASSED the syntax validation process." % len(self.bounds))
        else:
            self.logger.warning("%d out of %d IfcRelSpaceBoundary entities FAILED the syntax validation process. \n"
                                "Occuring sets of errors: %s \n"
                                "See ifc_SB_error_summary.json for further information on the errors."
                                % (len(self.error_summary),
                                   len(self.bounds),
                                   set(tuple(s) for s in [vals for key, vals in self.error_summary.items()])))


class SpaceBoundaryValidation:
    """
    Validate IFC Space Boundaries for use in EnergyPlus
    """
    def __init__(self, bound, id_list):
        self.error = []
        self.bound = bound
        self.id_list = id_list
        self._validate_space_boundaries()

    def _validate_space_boundaries(self):
        self._apply_validation_function(self._check_unique(), 'GlobalId')
        self._apply_validation_function(self._check_level(), '2ndLevel')
        self._apply_validation_function(self._check_description(), 'Description')
        self._apply_validation_function(self._check_rel_space(), 'RelatingSpace')
        self._apply_validation_function(self._check_rel_building_elem(), 'RelatedBuildingElement')
        self._apply_validation_function(self._check_conn_geom(), 'ConnectionGeometry')
        self._apply_validation_function(self._check_phys_virt_bound(), 'PhysicalOrVirtualBoundary')
        self._apply_validation_function(self._check_int_ext_bound(), 'InternalOrExternalBoundary')
        self._apply_validation_function(self._check_on_relating_elem(), 'SurfaceOnRelatingElement')
        self._apply_validation_function(self._check_on_related_elem(), 'SurfaceOnRelatedElement')
        self._apply_validation_function(self._check_basis_surface(), 'BasisSurface')
        self._apply_validation_function(self._check_inner_boundaries(), 'InnerBoundaries')
        if hasattr(self.bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary, 'Segments'):
            self._apply_validation_function(self._check_outer_boundary_composite(), 'OuterBoundaryCompositeCurve')
            self._apply_validation_function(self._check_segments(), 'Segments')
            self._apply_validation_function(self._check_segments_poly(), 'SegmentsPolyline')
            self._apply_validation_function(self._check_segments_poly_coord(), 'SegmentsPolylineCoordinates')
        else:
            self._apply_validation_function(self._check_outer_boundary_poly(), 'OuterBoundaryPolyline')
            self._apply_validation_function(self._check_outer_boundary_poly_coord(), 'OuterBoundaryPolylineCoordinates')
        self._apply_validation_function(self._check_plane_position(), 'Position')
        self._apply_validation_function(self._check_location(), 'Location')
        self._apply_validation_function(self._check_axis(), 'Axis')
        self._apply_validation_function(self._check_refdirection(), 'RefDirection')
        self._apply_validation_function(self._check_location_coord(), 'LocationCoordinates')
        self._apply_validation_function(self._check_axis_dir_ratios(), 'AxisDirectionRatios')
        self._apply_validation_function(self._check_refdirection_dir_ratios(), 'RefDirectionDirectionRatios')

    def _apply_validation_function(self, fct, err_name):
        if not fct:
            self.error.append(err_name)

    def _check_unique(self):
        return self.id_list.count(self.bound.GlobalId) == 1

    def _check_level(self):
        return self.bound.Name == "2ndLevel"

    def _check_description(self):
        return self.bound.Description in {'2a', '2b'}

    def _check_rel_space(self):
        return any(
            [self.bound.RelatingSpace.is_a('IfcSpace') or self.bound.RelatingSpace.is_a('IfcExternalSpatialElement')])

    def _check_rel_building_elem(self):
        if self.bound.RelatedBuildingElement is not None:
            return self.bound.RelatedBuildingElement.is_a('IfcBuildingElement')

    def _check_conn_geom(self):
        return self.bound.ConnectionGeometry.is_a('IfcConnectionSurfaceGeometry')

    def _check_phys_virt_bound(self):
        return self.bound.PhysicalOrVirtualBoundary.upper() in {'PHYSICAL', 'VIRTUAL'}

    def _check_int_ext_bound(self):
        return self.bound.InternalOrExternalBoundary.upper() in {'INTERNAL',
                                                                 'EXTERNAL',
                                                                 'EXTERNAL_EARTH',
                                                                 'EXTERNAL_FIRE',
                                                                 'EXTERNAL_WATER'
                                                                 }

    def _check_on_relating_elem(self):
        return self.bound.ConnectionGeometry.SurfaceOnRelatingElement.is_a('IfcCurveBoundedPlane')

    def _check_on_related_elem(self):
        return self.bound.ConnectionGeometry.SurfaceOnRelatedElement is None

    def _check_basis_surface(self):
        return self.bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.is_a('IfcPlane')

    def _check_outer_boundary_composite(self):
        return self.bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary.is_a('IfcCompositeCurve')

    def _check_outer_boundary_poly(self):
        return self._check_poly_points(self.bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary)

    def _check_outer_boundary_poly_coord(self):
        return all(self.bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary)

    def _check_inner_boundaries(self):
        return (self.bound.ConnectionGeometry.SurfaceOnRelatingElement.InnerBoundaries is None) or \
               (i.is_a('IfcCompositeCurve')
                for i in self.bound.ConnectionGeometry.SurfaceOnRelatingElement.InnerBoundaries)

    def _check_segments(self):
        return (s.is_a('IfcPolyline')
                for s in self.bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary.Segments)

    def _check_segments_poly(self):
        return all(self._check_poly_points(s.ParentCurve)
                   for s in self.bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary.Segments)

    def _check_segments_poly_coord(self):
        return all(self._check_poly_points_coord(s.ParentCurve)
                   for s in self.bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary.Segments)

    def _check_plane_position(self):
        return self.bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.is_a('IfcAxis2Placement3D')

    def _check_poly_points(self, polyline):
        return polyline.is_a('IfcPolyline')

    def _check_location(self):
        return self.bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.Location.is_a(
            'IfcCartesianPoint')

    def _check_axis(self):
        return self.bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.Axis.is_a('IfcDirection')

    def _check_refdirection(self):
        return self.bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.RefDirection.is_a(
            'IfcDirection')

    def _check_coords(self, points):
        return points.is_a('IfcCartesianPoint') and 1 <= len(points.Coordinates) <= 4

    def _check_dir_ratios(self, dir_ratios):
        return 2 <= len(dir_ratios.DirectionRatios) <= 3

    def _check_poly_points_coord(self, polyline):
        return all(self._check_coords(p) for p in polyline.Points)

    def _check_location_coord(self):
        return self._check_coords(self.bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.Location)

    def _check_axis_dir_ratios(self):
        return self._check_dir_ratios(self.bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.Axis)

    def _check_refdirection_dir_ratios(self):
        return self._check_dir_ratios(
            self.bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.RefDirection)