import logging

from bim2sim.elements.base_elements import Element
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.openfoam_base_boundary_conditions import \
    OpenFOAMBaseBoundaryFields
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.openfoam_base_element import \
    OpenFOAMBaseElement
from bim2sim.utilities.pyocc_tools import PyOCCTools
from bim2sim.utilities.types import BoundaryOrientation

logger = logging.getLogger(__name__)


class StlBound(OpenFOAMBaseBoundaryFields, OpenFOAMBaseElement):
    def __init__(self, bound, radiation_model):
        super().__init__()
        self.radiation_model = radiation_model
        self.bound = bound
        self.guid = bound.guid
        self.bound_element_type = (
            bound.bound_element.__class__.__name__.replace('Disaggregated', ''))
        if (self.bound_element_type in ['Floor', 'InnerFloor'] and
                bound.top_bottom == 'TOP'):
            self.bound_element_type = 'Ceiling'
        # hotfix for incorrectly assigned floors and roofs in bim2sim elements
        # todo: test and remove?
        if self.bound_element_type in ['InnerFloor']:
            if bound.top_bottom == BoundaryOrientation.top:
                self.bound_element_type = 'Ceiling'
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
        self.power = 0
        self.bound_area = PyOCCTools.get_shape_area(self.tri_geom)
        self.set_default_refinement_level()
        self.set_patch_info_type()

    def set_default_refinement_level(self):
        self.refinement_level = [2, 3]
        if self.bound_element_type in ['OuterWall', 'Window', 'Door',
                                       'InnerFloor', 'Floor', 'Roof',
                                       'GroundFloor', 'OuterDoor', 'Ceiling']:
            self.refinement_level = [2, 3]
        elif self.bound_element_type in ['InnerWall', 'Wall', 'InnerDoor']:
            self.refinement_level = [2, 3]
        else:
            logger.warning(f"{self.bound_element_type} bound_element_type is "
                           f"unknown")

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

    def read_boundary_conditions(self, timestep_df, default_temp):
        res_key = self.guid.upper() + ':'
        if not self.bound.physical:
            self.heat_flux = 0
            self.power = 0
            self.temperature = default_temp - 273.15
        try:
            self.temperature = timestep_df[
                res_key + 'Surface Inside Face Temperature [C](Hourly)']
        except KeyError:
            logger.warning(f"the boundary with guid %s does not provide a "
                  f"surface inside face temperature and is set to adiabatic.", self.guid)
            self.heat_flux = 0
            self.power = 0
            self.temperature = default_temp - 273.15
            return
        if not self.bound_element_type == 'Window':
            self.power = timestep_df[res_key + ('Surface Inside Face '
                                                    'Conduction Heat Transfer '
                                                    'Rate [W](Hourly)')]
            prev_heat_flux = timestep_df[res_key + ('Surface Inside Face '
                                                     'Conduction Heat Transfer '
                                                     'Rate per Area [W/m2]('
                                                     'Hourly)')]
            self.heat_flux = prev_heat_flux
        else:
            self.heat_flux = (timestep_df[res_key + (
                'Surface Window Net Heat Transfer '
                'Rate [W](Hourly)')] /
                              self.bound_area)
            self.power = timestep_df[res_key + (
                'Surface Window Net Heat Transfer '
                'Rate [W](Hourly)')]

    def set_boundary_conditions(self, no_heatloss=False):
        if self.radiation_model == 'none':
            qr = 'none'
        else:
            qr = 'qr'
        if no_heatloss:
            pass
        elif any(i for i in ["INNER", "FLOOR"] if i in self.solid_name.upper()):
        # else: #
            self.T = {
                'type': 'fixedValue',
                'value': f'uniform {self.temperature + 273.15}'
            }
        else:
            self.T = {'type': 'externalWallHeatFluxTemperature',
                      'mode': 'power',
                      'qr': f"{qr}",
                      'Q': f'uniform {self.power}',
                      'qrRelaxation': 0.003,
                      'relaxation': 1.0,
                      'kappaMethod': 'fluidThermo',
                      'kappa': 'fluidThermo',
                      'value': f'uniform {self.temperature + 273.15}'
                      }
