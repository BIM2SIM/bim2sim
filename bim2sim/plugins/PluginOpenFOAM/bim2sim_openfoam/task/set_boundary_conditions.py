import pandas as pd

from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.utils import \
    PostprocessingUtils
from bim2sim.tasks.base import ITask
from butterfly.butterfly import boundaryRadiationProperties, alphat, aoa, \
    g_radiation, idefault, k, nut, omega, p, p_rgh, qr, T, U


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

        return openfoam_case, openfoam_elements

    def read_ep_results(self, openfoam_elements, openfoam_case,
                        year=1900,
                        date='12/21',
                        time=11, add_floor_heating=False):
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
        for bound in openfoam_elements:
            res_key = bound.guid.upper() + ':'
            bound.surf_temp = timestep_df[
                res_key + 'Surface Inside Face Temperature [C](Hourly)']
            if not any(s in bound.bound_element_type for s in ['Window']):
                bound.surf_heat_cond = timestep_df[
                    res_key + ('Surface Inside Face Conduction Heat Transfer '
                               'Rate per Area [W/m2](Hourly)')]
            else:
                bound.surf_heat_cond = (timestep_df[
                                            res_key + (
                                                'Surface Window Net Heat Transfer Rate [W](Hourly)')]
                                        / bound.bound_area)
            openfoam_case.current_zone.zone_heat_conduction += (
                    bound.bound_area * bound.surf_heat_cond)
        if add_floor_heating:
            for bound in openfoam_elements:
                # reduce calculated floor heating by floor heat losses
                # self.current_zone.floor_heating_qr = \
                #     (timestep_df[(f"{self.current_zone.guid.upper()} IDEAL LOADS AIR SYSTEM:Zone "
                #  f"Ideal Loads Zone Total Heating Rate [W](Hourly)")] /
                #      self.current_zone.net_area.m)
                if any(s in bound.bound_element_type for s in ['Floor',
                                                               'GroundFloor']):
                    openfoam_case.current_zone.floor_heating_qr = abs(
                        openfoam_case.current_zone.zone_heat_conduction / bound.bound_area
                        - bound.surf_heat_cond)
                    bound.surf_temp_org = bound.surf_heat_cond
                    bound.surf_heat_cond_org = bound.surf_heat_cond
                    bound.surf_temp = 30
                    bound.surf_heat_cond = openfoam_case.current_zone.floor_heating_qr

    def init_boundary_conditions(self, openfoam_case, openfoam_elements):
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
        openfoam_case.alphat = alphat.Alphat()
        openfoam_case.alphat.values['boundaryField'] = {}
        openfoam_case.alphat.values['dimensions'] = '[1 -1 -1 0 0 0 0]'
        default_name_list = openfoam_case.default_surface_names  # todo: add others here
        for obj in openfoam_elements:
            openfoam_case.alphat.values['boundaryField'].update(
                {obj.solid_name:
                     {'type': 'compressible::alphatJayatillekeWallFunction',
                      'Prt': 0.85,
                      'value': 'uniform 0'}})
        for name in default_name_list:
            openfoam_case.alphat.values['boundaryField'].update(
                {name:
                     {'type': 'compressible::alphatJayatillekeWallFunction',
                      'Prt': 0.85,
                      'value': 'uniform 0'}})
        openfoam_case.alphat.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'compressible::alphatJayatillekeWallFunction',
                  'Prt': 0.85,
                  'value': 'uniform 0'
                  }
             })

        openfoam_case.alphat.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_AoA(openfoam_case, openfoam_elements):
        openfoam_case.aoa = aoa.AoA()
        openfoam_case.aoa.values['boundaryField'] = {}
        default_name_list = openfoam_case.default_surface_names  # todo: add others here

        for obj in openfoam_elements:
            openfoam_case.aoa.values['boundaryField'].update(
                {obj.solid_name:
                     {'type': 'zeroGradient'}})
        for name in default_name_list:
            openfoam_case.aoa.values['boundaryField'].update(
                {name:
                     {'type': 'zeroGradient'}})
        openfoam_case.aoa.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'zeroGradient'}
             }
        )
        openfoam_case.aoa.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_G(openfoam_case, openfoam_elements):
        openfoam_case.g_radiation = g_radiation.G_radiation()
        openfoam_case.g_radiation.values['boundaryField'] = {}
        default_name_list = openfoam_case.default_surface_names  # todo: add others here

        for obj in openfoam_elements:
            openfoam_case.g_radiation.values['boundaryField'].update(
                {obj.solid_name:
                     {'type': 'MarshakRadiation',
                      'T': 'T',
                      'value': 'uniform 0'}})
        for name in default_name_list:
            openfoam_case.g_radiation.values['boundaryField'].update(
                {name:
                     {'type': 'MarshakRadiation',
                      'T': 'T',
                      'value': 'uniform 0'}})
        openfoam_case.g_radiation.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'MarshakRadiation',
                  'T': 'T',
                  'value': 'uniform 0'}})
        openfoam_case.g_radiation.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_IDefault(openfoam_case, openfoam_elements):
        openfoam_case.idefault = idefault.IDefault()
        openfoam_case.idefault.values['boundaryField'] = {}
        default_name_list = openfoam_case.default_surface_names  # todo: add others here

        for obj in openfoam_elements:
            openfoam_case.idefault.values['boundaryField'].update(
                {obj.solid_name:
                     {'type': 'greyDiffusiveRadiation',
                      'T': 'T',
                      'value': 'uniform 0'}})
        for name in default_name_list:
            openfoam_case.idefault.values['boundaryField'].update(
                {name:
                     {'type': 'greyDiffusiveRadiation',
                      'T': 'T',
                      'value': 'uniform 0'}})
        openfoam_case.idefault.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'greyDiffusiveRadiation',
                  'T': 'T',
                  'value': 'uniform 0'}})
        openfoam_case.idefault.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_k(openfoam_case, openfoam_elements):
        openfoam_case.k = k.K()
        openfoam_case.k.values['boundaryField'] = {}
        default_name_list = openfoam_case.default_surface_names  # todo: add others here

        for obj in openfoam_elements:
            openfoam_case.k.values['boundaryField'].update(
                {obj.solid_name:
                     {'type': 'kqRWallFunction',
                      'value': 'uniform 0.1'}})
        for name in default_name_list:
            openfoam_case.k.values['boundaryField'].update(
                {name:
                     {'type': 'kqRWallFunction',
                      'value': 'uniform 0.1'}})
        openfoam_case.k.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'kqRWallFunction',
                  'value': 'uniform 0.1'}})
        openfoam_case.k.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_nut(openfoam_case, openfoam_elements):
        openfoam_case.nut = nut.Nut()
        openfoam_case.nut.values['boundaryField'] = {}
        default_name_list = openfoam_case.default_surface_names  # todo: add others here

        for obj in openfoam_elements:
            openfoam_case.nut.values['boundaryField'].update(
                {obj.solid_name:
                     {'type': 'nutkWallFunction',
                      'value': 'uniform 0'}})
        for name in default_name_list:
            openfoam_case.nut.values['boundaryField'].update(
                {name:
                     {'type': 'nutkWallFunction',
                      'value': 'uniform 0'}})
        openfoam_case.nut.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'nutkWallFunction',
                  'value': 'uniform 0'}})
        openfoam_case.nut.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_omega(openfoam_case, openfoam_elements):
        openfoam_case.omega = omega.Omega()
        openfoam_case.omega.values['boundaryField'] = {}
        default_name_list = openfoam_case.default_surface_names  # todo: add others here

        for obj in openfoam_elements:
            openfoam_case.omega.values['boundaryField'].update(
                {obj.solid_name:
                     {'type': 'omegaWallFunction',
                      'value': 'uniform 0.01'}})
        for name in default_name_list:
            openfoam_case.omega.values['boundaryField'].update(
                {name:
                     {'type': 'omegaWallFunction',
                      'value': 'uniform 0.01'}})
        openfoam_case.omega.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'omegaWallFunction',
                  'value': 'uniform 0.01'}})
        openfoam_case.omega.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_p(openfoam_case, openfoam_elements):
        openfoam_case.p = p.P()
        openfoam_case.p.values['boundaryField'] = {}
        openfoam_case.p.values['internalField'] = 'uniform 101325'
        openfoam_case.p.values['dimensions'] = '[1 -1 -2 0 0 0 0]'
        default_name_list = openfoam_case.default_surface_names  # todo: add others here

        for obj in openfoam_elements:
            openfoam_case.p.values['boundaryField'].update(
                {obj.solid_name:
                     {'type': 'calculated',
                      'value': 'uniform 101325'}})
        for name in default_name_list:
            openfoam_case.p.values['boundaryField'].update(
                {name:
                     {'type': 'calculated',
                      'value': 'uniform 101325'}})
        openfoam_case.p.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'calculated',
                  'value': 'uniform 101325'}})
        openfoam_case.p.save(openfoam_case.openfoam_dir)

    def create_p_rgh(self, openfoam_case, openfoam_elements):
        openfoam_case.p_rgh = p_rgh.P_rgh()
        openfoam_case.p_rgh.values['boundaryField'] = {}
        openfoam_case.p_rgh.values['internalField'] = 'uniform 101325'
        openfoam_case.p_rgh.values['dimensions'] = '[1 -1 -2 0 0 0 0]'
        default_name_list = openfoam_case.default_surface_names  # todo: add others here

        for obj in openfoam_elements:
            openfoam_case.p_rgh.values['boundaryField'].update(
                {obj.solid_name:
                     {'type': 'fixedFluxPressure',
                      'value': 'uniform 101325'}})
        for name in default_name_list:
            openfoam_case.p_rgh.values['boundaryField'].update(
                {name:
                     {'type': 'fixedFluxPressure',
                      'value': 'uniform 101325'}})
        openfoam_case.p_rgh.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'fixedFluxPressure',
                  'value': 'uniform 101325'}})
        openfoam_case.p_rgh.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_qr(openfoam_case, openfoam_elements):
        openfoam_case.qr = qr.Qr()
        openfoam_case.qr.values['boundaryField'] = {}
        default_name_list = openfoam_case.default_surface_names  # todo: add others here

        openfoam_case.qr.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'calculated',
                  'value': 'uniform 0'}})
        openfoam_case.qr.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_T(openfoam_case, openfoam_elements):
        openfoam_case.T = T.T()
        openfoam_case.T.values['boundaryField'] = {}
        openfoam_case.T.values['internalField'] = 'uniform 293.15'
        default_name_list = openfoam_case.default_surface_names  # todo: add others here

        for obj in openfoam_elements:
            openfoam_case.T.values['boundaryField'].update(
                {obj.solid_name:
                     {'type': 'externalWallHeatFluxTemperature',
                      'mode': 'flux',
                      'qr': 'qr',
                      'q': f'uniform {obj.surf_heat_cond}',
                      'qrRelaxation': 0.003,
                      'relaxation': 1.0,
                      'kappaMethod': 'fluidThermo',
                      'kappa': 'fluidThermo',
                      'value': f'uniform {obj.surf_temp + 273.15}'}})
        # for name in default_name_list:
        #     self.T.values['boundaryField'].update(
        #         {name:
        #              {'type': 'externalWallHeatFluxTemperature',
        #               'value': 'uniform 101325'}})

        openfoam_case.T.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'zeroGradient'}})
        openfoam_case.T.save(openfoam_case.openfoam_dir)

        pass

    @staticmethod
    def create_U(openfoam_case, openfoam_elements):
        openfoam_case.U = U.U()
        openfoam_case.U.values['boundaryField'] = {}
        default_name_list = openfoam_case.default_surface_names  # todo: add others here

        openfoam_case.U.values['boundaryField'].update(
            {r'".*"':
                 {'type': 'fixedValue',
                  'value': 'uniform (0.000 0.000 0.000)'}})
        openfoam_case.U.save(openfoam_case.openfoam_dir)

    @staticmethod
    def create_boundaryRadiationProperties(openfoam_case,
                                           openfoam_elements):
        openfoam_case.boundaryRadiationProperties = (
            boundaryRadiationProperties.BoundaryRadiationProperties())
        default_name_list = openfoam_case.default_surface_names  # todo: move
        # to boundary condition setup

        # todo: check if filtering openfoam_elements is required
        for obj in openfoam_elements:
            openfoam_case.boundaryRadiationProperties.values.update(
                {obj.solid_name:
                     {'type': 'lookup',
                      'emissivity': '0.90',
                      'absorptivity': '0.90',
                      'transmissivity': '0'
                      }})
        for name in default_name_list:
            openfoam_case.boundaryRadiationProperties.values.update(
                {name:
                     {'type': 'lookup',
                      'emissivity': '0.90',
                      'absorptivity': '0.90',
                      'transmissivity': '0'
                      }})
        openfoam_case.boundaryRadiationProperties.save(
            openfoam_case.openfoam_dir)
