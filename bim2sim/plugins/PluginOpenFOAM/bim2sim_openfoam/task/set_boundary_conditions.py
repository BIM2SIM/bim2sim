from collections import OrderedDict

import pandas as pd

from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.utils import \
    PostprocessingUtils
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.openfoam_base_boundary_conditions import \
    OpenFOAMBaseBoundaryFields
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.utils.openfoam_utils import \
    OpenFOAMUtils as of_utils
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
from butterfly.butterfly import boundaryRadiationProperties, alphat, aoa, \
    g_radiation, idefault, k, nut, omega, p, p_rgh, qr, T, U, foamfile


class SetOpenFOAMBoundaryConditions(ITask):
    """This ITask initializes the OpenFOAM Setup.
    """

    reads = ('openfoam_elements', 'openfoam_case')
    touches = ('openfoam_case', 'openfoam_elements')

    def __init__(self, playground):
        super().__init__(playground)
        self.default_surface_names = ['Back', 'Bottom', 'Front', 'Top', 'Left',
                                      'Right']

    def run(self, openfoam_elements, openfoam_case):
        self.read_ep_results(
            openfoam_elements, openfoam_case,
            date=self.playground.sim_settings.simulation_date,
            time=self.playground.sim_settings.simulation_time,
            add_floor_heating=self.playground.sim_settings.add_floorheating)
        self.init_boundary_conditions(openfoam_case, openfoam_elements)
        self.add_fvOptions_for_heating(openfoam_case, openfoam_elements)

        return openfoam_case, openfoam_elements

    def read_ep_results(self, openfoam_elements, openfoam_case,
                        year=1900,
                        date='12/21',
                        time=11, add_floor_heating=False):
        stl_bounds = filter_elements(openfoam_elements, 'StlBound')
        full_results_df = pd.read_csv(
            self.paths.export / 'EnergyPlus' / 'SimResults' /
            self.playground.project.name
            / 'eplusout.csv')  # , index_col='Date/Time')
        # full_results_df.index.str.strip()
        full_results_df['Date/Time'] = full_results_df['Date/Time'].apply(
            PostprocessingUtils._string_to_datetime)
        full_results_df = full_results_df.set_index('Date/Time')
        timestep_df = full_results_df.loc[
            f"{year}-{date} {time:02}:00:00"]
        openfoam_case.current_zone.zone_heat_conduction = 0
        openfoam_case.current_zone.air_temp = timestep_df[
                                                  openfoam_case.current_zone.guid.upper() +
                                                  ':' + (
                                                      'Zone Mean Air Temperature [C]('
                                                      'Hourly)')] + 273.15
        for bound in stl_bounds:
            bound.read_boundary_conditions(timestep_df, openfoam_case.current_zone.air_temp)
            openfoam_case.current_zone.zone_heat_conduction += (
                    bound.bound_area * bound.heat_flux)
        if add_floor_heating:
            total_floor_area = 0
            for bound in stl_bounds:
                # reduce calculated floor heating by floor heat losses
                # self.current_zone.floor_heating_qr = \
                #     (timestep_df[(f"{self.current_zone.guid.upper()} IDEAL LOADS AIR SYSTEM:Zone "
                #  f"Ideal Loads Zone Total Heating Rate [W](Hourly)")] /
                #      self.current_zone.net_area.m)
                # todo: only works for spaces with a single floor surface
                if any(s in bound.bound_element_type for s in ['Floor',
                                                               'GroundFloor']):
                    total_floor_area += bound.bound_area
            openfoam_case.current_zone.abs_floor_heating_qr = \
                abs(openfoam_case.current_zone.zone_heat_conduction /
                    total_floor_area)
            for bound in stl_bounds:
                if any(s in bound.bound_element_type for s in ['Floor',
                                                               'GroundFloor']):
                    bound.temperature_org = bound.temperature
                    bound.heat_flux_org = bound.heat_flux
                    bound.temperature = 30
                    # previous heat flux of the boundary has to be neglegted.
                    # the previous bound heat flux needs to be added to the
                    # total floor heating heat flux.
                    bound.heat_flux = abs(
                        openfoam_case.current_zone.abs_floor_heating_qr +
                        bound.heat_flux)

    def init_boundary_conditions(self, openfoam_case, openfoam_elements):
        stl_bounds, heaters, air_terminals = \
            of_utils.split_openfoam_elements(openfoam_elements)
        for bound in stl_bounds:
            bound.set_boundary_conditions()
        for heater in heaters:
            heater.set_boundary_conditions(abs(
                openfoam_case.current_zone.zone_heat_conduction))

        for air_terminal in air_terminals:
            air_terminal.set_boundary_conditions(
                openfoam_case.current_zone.air_temp)
        # todo: move initial boundary condition settings to OpenFOAM element
        #  classes.
        self.create_alphat(openfoam_case, openfoam_elements)
        self.create_AoA(openfoam_case, openfoam_elements)
        self.create_G(openfoam_case, openfoam_elements)
        self.create_IDefault(openfoam_case, openfoam_elements)
        self.create_k(openfoam_case, openfoam_elements)
        self.create_nut(openfoam_case, openfoam_elements)
        self.create_omega(openfoam_case, openfoam_elements)
        self.create_p(openfoam_case, openfoam_elements)
        self.create_p_rgh(openfoam_case, openfoam_elements)
        self.create_qr(openfoam_case, openfoam_elements)
        self.create_T(openfoam_case, openfoam_elements)
        self.create_U(openfoam_case, openfoam_elements)
        self.create_boundaryRadiationProperties(openfoam_case,
                                                openfoam_elements)

    @staticmethod
    def create_alphat(openfoam_case, openfoam_elements):
        stl_bounds, heaters, air_terminals = \
            of_utils.split_openfoam_elements(openfoam_elements)
        openfoam_case.alphat = alphat.Alphat()
        openfoam_case.alphat.values['boundaryField'] = {}
        openfoam_case.alphat.values['dimensions'] = '[1 -1 -1 0 0 0 0]'
        for bound in stl_bounds:
            openfoam_case.alphat.values['boundaryField'].update(
                {bound.solid_name: bound.alphat})

        for heater in heaters:
            openfoam_case.alphat.values['boundaryField'].update(
                {heater.porous_media.solid_name: heater.porous_media.alphat})
            openfoam_case.alphat.values['boundaryField'].update(
                {
                    heater.heater_surface.solid_name: heater.heater_surface.alphat})
        for air_terminal in air_terminals:
            openfoam_case.alphat.values['boundaryField'].update(
                {air_terminal.diffuser.solid_name: air_terminal.diffuser.alphat,
                 air_terminal.source_sink.solid_name:
                     air_terminal.source_sink.alphat,
                 air_terminal.box.solid_name: air_terminal.box.alphat
                 })

        openfoam_case.alphat.values['boundaryField'].update(
            {r'".*"': OpenFOAMBaseBoundaryFields().alphat
             })

        openfoam_case.alphat.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_AoA(openfoam_case, openfoam_elements):
        stl_bounds, heaters, air_terminals = \
            of_utils.split_openfoam_elements(openfoam_elements)
        openfoam_case.aoa = aoa.AoA()
        openfoam_case.aoa.values['boundaryField'] = {}
        for bound in stl_bounds:
            openfoam_case.aoa.values['boundaryField'].update(
                {bound.solid_name: bound.aoa})
        for heater in heaters:
            openfoam_case.aoa.values['boundaryField'].update(
                {heater.porous_media.solid_name: heater.porous_media.aoa})
            openfoam_case.aoa.values['boundaryField'].update(
                {heater.heater_surface.solid_name: heater.heater_surface.aoa})
        for air_terminal in air_terminals:
            openfoam_case.aoa.values['boundaryField'].update(
                {air_terminal.diffuser.solid_name: air_terminal.diffuser.aoa,
                 air_terminal.source_sink.solid_name:
                     air_terminal.source_sink.aoa,
                 air_terminal.box.solid_name: air_terminal.box.aoa
                 })

        openfoam_case.aoa.values['boundaryField'].update(
            {r'".*"': OpenFOAMBaseBoundaryFields().aoa}
        )
        openfoam_case.aoa.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_G(openfoam_case, openfoam_elements):
        stl_bounds, heaters, air_terminals = \
            of_utils.split_openfoam_elements(openfoam_elements)
        openfoam_case.g_radiation = g_radiation.G_radiation()
        openfoam_case.g_radiation.values['boundaryField'] = {}

        for bound in stl_bounds:
            openfoam_case.g_radiation.values['boundaryField'].update(
                {bound.solid_name: bound.g_radiation})
        for heater in heaters:
            openfoam_case.g_radiation.values['boundaryField'].update(
                {heater.porous_media.solid_name:
                     heater.porous_media.g_radiation})
            openfoam_case.g_radiation.values['boundaryField'].update(
                {heater.heater_surface.solid_name:
                     heater.heater_surface.g_radiation})
        for air_terminal in air_terminals:
            openfoam_case.g_radiation.values['boundaryField'].update(
                {
                    air_terminal.diffuser.solid_name: air_terminal.diffuser.g_radiation,
                    air_terminal.source_sink.solid_name:
                        air_terminal.source_sink.g_radiation,
                    air_terminal.box.solid_name: air_terminal.box.g_radiation
                })
        openfoam_case.g_radiation.values['boundaryField'].update(
            {r'".*"': OpenFOAMBaseBoundaryFields().g_radiation})
        openfoam_case.g_radiation.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_IDefault(openfoam_case, openfoam_elements):
        stl_bounds, heaters, air_terminals = \
            of_utils.split_openfoam_elements(openfoam_elements)
        openfoam_case.idefault = idefault.IDefault()
        openfoam_case.idefault.values['boundaryField'] = {}

        for bound in stl_bounds:
            openfoam_case.idefault.values['boundaryField'].update(
                {bound.solid_name: bound.idefault})
        for heater in heaters:
            openfoam_case.idefault.values['boundaryField'].update(
                {heater.porous_media.solid_name:
                     heater.porous_media.idefault})
            openfoam_case.idefault.values['boundaryField'].update(
                {heater.heater_surface.solid_name:
                     heater.heater_surface.idefault})
        for air_terminal in air_terminals:
            openfoam_case.idefault.values['boundaryField'].update(
                {
                    air_terminal.diffuser.solid_name: air_terminal.diffuser.idefault,
                    air_terminal.source_sink.solid_name:
                        air_terminal.source_sink.idefault,
                    air_terminal.box.solid_name: air_terminal.box.idefault
                })
        openfoam_case.idefault.values['boundaryField'].update(
            {r'".*"': OpenFOAMBaseBoundaryFields().idefault})
        openfoam_case.idefault.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_k(openfoam_case, openfoam_elements):
        stl_bounds, heaters, air_terminals = \
            of_utils.split_openfoam_elements(openfoam_elements)
        openfoam_case.k = k.K()
        openfoam_case.k.values['boundaryField'] = {}

        for bound in stl_bounds:
            openfoam_case.k.values['boundaryField'].update(
                {bound.solid_name: bound.k})
        for heater in heaters:
            openfoam_case.k.values['boundaryField'].update(
                {heater.porous_media.solid_name:
                     heater.porous_media.k})
            openfoam_case.k.values['boundaryField'].update(
                {heater.heater_surface.solid_name:
                     heater.heater_surface.k})
        for air_terminal in air_terminals:
            openfoam_case.k.values['boundaryField'].update(
                {air_terminal.diffuser.solid_name: air_terminal.diffuser.k,
                 air_terminal.source_sink.solid_name:
                     air_terminal.source_sink.k,
                 air_terminal.box.solid_name: air_terminal.box.k
                 })
        openfoam_case.k.values['boundaryField'].update(
            {r'".*"': OpenFOAMBaseBoundaryFields().k})
        openfoam_case.k.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_nut(openfoam_case, openfoam_elements):
        stl_bounds, heaters, air_terminals = \
            of_utils.split_openfoam_elements(openfoam_elements)
        openfoam_case.nut = nut.Nut()
        openfoam_case.nut.values['boundaryField'] = {}

        for bound in stl_bounds:
            openfoam_case.nut.values['boundaryField'].update(
                {bound.solid_name: bound.nut})
        for heater in heaters:
            openfoam_case.nut.values['boundaryField'].update(
                {heater.porous_media.solid_name:
                     heater.porous_media.nut})
            openfoam_case.nut.values['boundaryField'].update(
                {heater.heater_surface.solid_name:
                     heater.heater_surface.nut})
        for air_terminal in air_terminals:
            openfoam_case.nut.values['boundaryField'].update(
                {air_terminal.diffuser.solid_name: air_terminal.diffuser.nut,
                 air_terminal.source_sink.solid_name:
                     air_terminal.source_sink.nut,
                 air_terminal.box.solid_name: air_terminal.box.nut
                 })
        openfoam_case.nut.values['boundaryField'].update(
            {r'".*"': OpenFOAMBaseBoundaryFields().nut})
        openfoam_case.nut.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_omega(openfoam_case, openfoam_elements):
        stl_bounds, heaters, air_terminals = \
            of_utils.split_openfoam_elements(openfoam_elements)
        openfoam_case.omega = omega.Omega()
        openfoam_case.omega.values['boundaryField'] = {}

        for bound in stl_bounds:
            openfoam_case.omega.values['boundaryField'].update(
                {bound.solid_name: bound.omega})
        for heater in heaters:
            openfoam_case.omega.values['boundaryField'].update(
                {heater.porous_media.solid_name:
                     heater.porous_media.omega})
            openfoam_case.omega.values['boundaryField'].update(
                {heater.heater_surface.solid_name:
                     heater.heater_surface.omega})
        for air_terminal in air_terminals:
            openfoam_case.omega.values['boundaryField'].update(
                {air_terminal.diffuser.solid_name: air_terminal.diffuser.omega,
                 air_terminal.source_sink.solid_name:
                     air_terminal.source_sink.omega,
                 air_terminal.box.solid_name: air_terminal.box.omega
                 })
        openfoam_case.omega.values['boundaryField'].update(
            {r'".*"': OpenFOAMBaseBoundaryFields().omega})
        openfoam_case.omega.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_p(openfoam_case, openfoam_elements):
        stl_bounds, heaters, air_terminals = \
            of_utils.split_openfoam_elements(openfoam_elements)
        openfoam_case.p = p.P()
        openfoam_case.p.values['boundaryField'] = {}
        openfoam_case.p.values['internalField'] = 'uniform 101325'
        openfoam_case.p.values['dimensions'] = '[1 -1 -2 0 0 0 0]'

        for bound in stl_bounds:
            openfoam_case.p.values['boundaryField'].update(
                {bound.solid_name: bound.p})
        for heater in heaters:
            openfoam_case.p.values['boundaryField'].update(
                {heater.porous_media.solid_name:
                     heater.porous_media.p})
            openfoam_case.p.values['boundaryField'].update(
                {heater.heater_surface.solid_name:
                     heater.heater_surface.p})
        for air_terminal in air_terminals:
            openfoam_case.p.values['boundaryField'].update(
                {air_terminal.diffuser.solid_name: air_terminal.diffuser.p,
                 air_terminal.source_sink.solid_name:
                     air_terminal.source_sink.p,
                 air_terminal.box.solid_name: air_terminal.box.p
                 })
        openfoam_case.p.values['boundaryField'].update(
            {r'".*"': OpenFOAMBaseBoundaryFields().p})
        openfoam_case.p.save(openfoam_case.openfoam_dir)

    def create_p_rgh(self, openfoam_case, openfoam_elements):
        stl_bounds, heaters, air_terminals = \
            of_utils.split_openfoam_elements(openfoam_elements)
        openfoam_case.p_rgh = p_rgh.P_rgh()
        openfoam_case.p_rgh.values['boundaryField'] = {}
        openfoam_case.p_rgh.values['internalField'] = 'uniform 101325'
        openfoam_case.p_rgh.values['dimensions'] = '[1 -1 -2 0 0 0 0]'

        for bound in stl_bounds:
            openfoam_case.p_rgh.values['boundaryField'].update(
                {bound.solid_name: bound.p_rgh})
        for heater in heaters:
            openfoam_case.p_rgh.values['boundaryField'].update(
                {heater.porous_media.solid_name:
                     heater.porous_media.p_rgh})
            openfoam_case.p_rgh.values['boundaryField'].update(
                {heater.heater_surface.solid_name:
                     heater.heater_surface.p_rgh})
        for air_terminal in air_terminals:
            openfoam_case.p_rgh.values['boundaryField'].update(
                {air_terminal.diffuser.solid_name: air_terminal.diffuser.p_rgh,
                 air_terminal.source_sink.solid_name:
                     air_terminal.source_sink.p_rgh,
                 air_terminal.box.solid_name: air_terminal.box.p_rgh
                 })
        openfoam_case.p_rgh.values['boundaryField'].update(
            {r'".*"': OpenFOAMBaseBoundaryFields().p_rgh})
        openfoam_case.p_rgh.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_qr(openfoam_case, openfoam_elements):
        stl_bounds, heaters, air_terminals = \
            of_utils.split_openfoam_elements(openfoam_elements)
        openfoam_case.qr = qr.Qr()
        openfoam_case.qr.values['boundaryField'] = {}

        for bound in stl_bounds:
            openfoam_case.qr.values['boundaryField'].update(
                {bound.solid_name: bound.qr})
        for heater in heaters:
            openfoam_case.qr.values['boundaryField'].update(
                {heater.porous_media.solid_name:
                     heater.porous_media.qr})
            openfoam_case.qr.values['boundaryField'].update(
                {heater.heater_surface.solid_name:
                     heater.heater_surface.qr})
        for air_terminal in air_terminals:
            openfoam_case.qr.values['boundaryField'].update(
                {air_terminal.diffuser.solid_name: air_terminal.diffuser.qr,
                 air_terminal.source_sink.solid_name:
                     air_terminal.source_sink.qr,
                 air_terminal.box.solid_name: air_terminal.box.qr
                 })
        openfoam_case.qr.values['boundaryField'].update(
            {r'".*"': OpenFOAMBaseBoundaryFields().qr})
        openfoam_case.qr.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_T(openfoam_case, openfoam_elements):
        stl_bounds, heaters, air_terminals = \
            of_utils.split_openfoam_elements(openfoam_elements)
        openfoam_case.T = T.T()
        openfoam_case.T.values['boundaryField'] = {}
        openfoam_case.T.values['internalField'] = 'uniform 293.15'

        for bound in stl_bounds:
            openfoam_case.T.values['boundaryField'].update(
                {bound.solid_name: bound.T})
        for heater in heaters:
            openfoam_case.T.values['boundaryField'].update(
                {heater.porous_media.solid_name:
                     heater.porous_media.T})
            openfoam_case.T.values['boundaryField'].update(
                {heater.heater_surface.solid_name:
                     heater.heater_surface.T})
        for air_terminal in air_terminals:
            openfoam_case.T.values['boundaryField'].update(
                {air_terminal.diffuser.solid_name: air_terminal.diffuser.T,
                 air_terminal.source_sink.solid_name:
                     air_terminal.source_sink.T,
                 air_terminal.box.solid_name: air_terminal.box.T
                 })
        openfoam_case.T.values['boundaryField'].update(
            {r'".*"': OpenFOAMBaseBoundaryFields().T})
        openfoam_case.T.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_U(openfoam_case, openfoam_elements):
        stl_bounds, heaters, air_terminals = \
            of_utils.split_openfoam_elements(openfoam_elements)
        openfoam_case.U = U.U()
        openfoam_case.U.values['boundaryField'] = {}

        for bound in stl_bounds:
            openfoam_case.U.values['boundaryField'].update(
                {bound.solid_name: bound.U})
        for heater in heaters:
            openfoam_case.U.values['boundaryField'].update(
                {heater.porous_media.solid_name:
                     heater.porous_media.U})
            openfoam_case.U.values['boundaryField'].update(
                {heater.heater_surface.solid_name:
                     heater.heater_surface.U})
        for air_terminal in air_terminals:
            openfoam_case.U.values['boundaryField'].update(
                {air_terminal.diffuser.solid_name: air_terminal.diffuser.U,
                 air_terminal.source_sink.solid_name:
                     air_terminal.source_sink.U,
                 air_terminal.box.solid_name: air_terminal.box.U
                 })
        openfoam_case.U.values['boundaryField'].update(
            {r'".*"': OpenFOAMBaseBoundaryFields().U})
        openfoam_case.U.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_boundaryRadiationProperties(openfoam_case,
                                           openfoam_elements):
        stl_bounds, heaters, air_terminals = \
            of_utils.split_openfoam_elements(openfoam_elements)
        openfoam_case.boundaryRadiationProperties = (
            boundaryRadiationProperties.BoundaryRadiationProperties())
        default_name_list = openfoam_case.default_surface_names

        for bound in stl_bounds:
            openfoam_case.boundaryRadiationProperties.values.update(
                {bound.solid_name: bound.boundaryRadiationProperties})
        for heater in heaters:
            openfoam_case.boundaryRadiationProperties.values.update(
                {heater.porous_media.solid_name:
                     heater.porous_media.boundaryRadiationProperties})
            openfoam_case.boundaryRadiationProperties.values.update(
                {heater.heater_surface.solid_name:
                     heater.heater_surface.boundaryRadiationProperties})
        for air_terminal in air_terminals:
            openfoam_case.boundaryRadiationProperties.values.update(
                {air_terminal.diffuser.solid_name:
                     air_terminal.diffuser.boundaryRadiationProperties,
                 air_terminal.source_sink.solid_name:
                     air_terminal.source_sink.boundaryRadiationProperties,
                 air_terminal.box.solid_name:
                     air_terminal.box.boundaryRadiationProperties,
                 })
        for name in default_name_list:
            openfoam_case.boundaryRadiationProperties.values.update(
                {
                    name: OpenFOAMBaseBoundaryFields().boundaryRadiationProperties})
        openfoam_case.boundaryRadiationProperties.save(
            openfoam_case.openfoam_dir)

    @staticmethod
    def add_fvOptions_for_heating(openfoam_case, openfoam_elements):
        heaters = filter_elements(openfoam_elements, 'Heater')
        openfoam_case.fvOptions = foamfile.FoamFile(
            name='fvOptions', cls='dictionary', location='system',
            default_values=OrderedDict()
        )
        for heater in heaters:
            openfoam_case.fvOptions.values.update(
                {heater.porous_media.solid_name + '_ScalarSemiImplicitSource':
                     {'type': 'scalarSemiImplicitSource',
                      'scalarSemiImplicitSourceCoeffs':
                          {'mode': 'uniform',
                           'selectionMode': 'cellZone',
                           'volumeMode': 'absolute',
                           'cellZone':
                               heater.porous_media.solid_name,
                           'injectionRateSuSp':
                               {'h':
                                    f"({heater.porous_media.power} 0)"
                                }
                           }
                      }
                 }
            )
        openfoam_case.fvOptions.save(openfoam_case.openfoam_dir)
