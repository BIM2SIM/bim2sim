
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
        self.default_surface_names =['boundingbox']# ['Back', 'Bottom', 'Front', 'Top', 'Left',
                                     # 'Right']
        if playground.sim_settings.simulation_type == 'transient':
            self.transient_simulation = True
        self.internal_gains = None
