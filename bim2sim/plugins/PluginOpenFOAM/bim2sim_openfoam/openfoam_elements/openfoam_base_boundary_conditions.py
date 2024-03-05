class OpenFOAMBaseBoundaryFields:
    def __init__(self):
        super().__init__()
        self.aoa = {'type': 'zeroGradient'}
        self.g_radiation = {'type': 'MarshakRadiation',
                            'T': 'T',
                            'value': 'uniform 0'}
        self.idefault = {'type': 'greyDiffusiveRadiation',
                         'T': 'T',
                         'value': 'uniform 0'}
        self.k = {'type': 'kqRWallFunction',
                  'value': 'uniform 0.1'}
        self.nut = {'type': 'nutkWallFunction',
                    'value': 'uniform 0'}
        self.omega = {'type': 'omegaWallFunction',
                      'value': 'uniform 0.01'}
        self.p = {'type': 'calculated',
                  'value': 'uniform 101325'}
        self.p_rgh = {'type': 'fixedFluxPressure',
                      'value': 'uniform 101325'}
        self.qr = {'type': 'calculated',
                   'value': 'uniform 0'}
        self.T = {'type': 'externalWallHeatFluxTemperature',
                  'mode': 'flux',
                  'qr': 'qr',
                  'q': None,
                  # 'q': f'uniform {obj.surf_heat_cond}',
                  'qrRelaxation': 0.003,
                  'relaxation': 1.0,
                  'kappaMethod': 'fluidThermo',
                  'kappa': 'fluidThermo',
                  'value': None
                  # 'value': f'uniform {obj.surf_temp + 273.15}'
                  }
        self.U = {'type': 'fixedValue',
                  'value': 'uniform (0.000 0.000 0.000)'}
