import logging

from bim2sim.elements.base_elements import Element

logger = logging.getLogger(__name__)

class OpenFOAMBaseElement(Element):
    def __init__(self):
        super().__init__()
        self.bound_element_type = None
        self.solid_name = None
        self.stl_name = None
        self.stl_file_path_name = None
        self.tri_geom = None
        self.bound_area = None
        self.patch_info_type = None
        self.refinement_level = None
        self.temperature = None
        self.heat_flux = None
        self.bbox_min_max = None
        self.power = None

    def __repr__(self):
        return "<%s>" % self.__class__.__name__

    def set_boundary_conditions(self):
        raise NotImplementedError(f"set_boundary_conditions not implemented "
                                  f"for {self.__repr__()}")
