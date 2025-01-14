
class OpenFOAMCase:
    def __init__(self, playground):
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
        self.default_surface_names =['boundingbox']# ['Back', 'Bottom', 'Front', 'Top', 'Left',
                                     # 'Right']
        if playground.sim_settings.simulation_type == 'transient':
            self.transient_simulation = True
        self.radiation_model = playground.sim_settings.radiation_model
        self.internal_gains = None
        self.n_procs = playground.sim_settings.n_procs
        self.floor_area = None
