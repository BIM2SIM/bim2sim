from bim2sim.utilities.pyocc_tools import PyOCCTools


class StlBound:
    def __init__(self, bound, idf):
        self.bound = bound
        self.guid = bound.guid
        self.bound_element_type = bound.bound_element.__class__.__name__
        # hotfix for incorrectly assigned floors and roofs in bim2sim elements
        if self.bound_element_type in ['Floor', 'GroundFloor', 'Roof']:
            self.bound_element_type = idf.getobject('BUILDINGSURFACE:DETAILED',
                                                    self.guid.upper()).Surface_Type
        self.solid_name = self.bound_element_type + '_' + bound.guid.replace(
            '$', '___')
        if not hasattr(bound, 'cfd_face'):
            bound.cfd_face = bound.bound_shape
        opening_shapes = []
        if bound.opening_bounds:
            opening_shapes = [s.bound_shape for s in bound.opening_bounds]
        self.tri_geom = PyOCCTools.triangulate_bound_shape(bound.cfd_face,
                                                           opening_shapes)
        self.temperature = 293.15
        self.heat_flux = 0
        self.bound_area = PyOCCTools.get_shape_area(self.tri_geom)
        self.set_default_refinement_level()
        self.set_patch_info_type()

    def set_default_refinement_level(self):
        self.refinement_level = [1, 2]
        if self.bound_element_type in ['OuterWall', 'Window', 'Door',
                                       'Floor', 'Roof', 'GroundFloor',
                                       'OuterDoor', 'Ceiling']:
            self.refinement_level = [2, 3]
        elif self.bound_element_type in ['InnerWall', 'Wall', 'InnerDoor']:
            self.refinement_level = [2, 2]
        else:
            print(f"{self.bound_element_type} bound_element_type is unknown")

    def set_patch_info_type(self):
        # AirTerminal, SpaceHeater
        self.patch_info_type = 'wall'
        if self.bound_element_type == 'SpaceHeater':
            self.patch_info_type = 'wall'
        elif self.bound_element_type == 'AirTerminal':
            # todo: implement distinction for inlet (Zuluft) and outlet (
            #  Abluft), for the surface itself and the surrounding boxes.
            pass
        else:
            pass
