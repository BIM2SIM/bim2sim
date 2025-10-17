
class OpenFOAMCase:
    def __init__(self, playground):
        self.current_zone = None
        self.topoSetDict = None
        self.turbulenceProperties = None
        self.radiationProperties = None
        self.thermophysicalProperties = None
        self.decomposeParDict = None
        self.controlDict = None
        self.fvSchemes = None
        self.fvSolution = None
        self.openfoam_0_dir = None
        self.openfoam_constant_dir = None
        self.openfoam_triSurface_dir = None
        self.openfoam_systems_dir = None
        self.openfoam_dir = None
        self.default_templates_dir = None
        self.transient_simulation = False
        self.required_heating_power = 0
        self.required_cooling_power = 0
        self.furniture_trsfs = []
        self.chair_trsfs = []
        self.default_surface_names =['boundingbox']# ['Back', 'Bottom', 'Front', 'Top', 'Left',
                                     # 'Right']
        if playground.sim_settings.simulation_type == 'transient':
            self.transient_simulation = True
        self.radiation_model = playground.sim_settings.radiation_model
        self.internal_gains = None
        self.n_procs = playground.sim_settings.n_procs
        self.floor_area = None
        self.add_solar_radiation = playground.sim_settings.add_solar_radiation
        self.building_rotation = (
            playground.sim_settings.building_rotation_overwrite)
        self.solar_azimuth_angle = None
        self.solar_altitude_angle = None
        self.solar_hour_angle = None
        self.direct_solar_rad = None
        self.diffuse_solar_rad = None
        self.timestep_df = None
