class OpenFOAMBaseBoundaryFields:
    def __init__(self):
        super().__init__()
        self.alphat = {'type': 'compressible::alphatJayatillekeWallFunction',
                       'Prt': 0.85,
                       'value': 'uniform 0'}
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
        self.T = {'type': 'zeroGradient'}
        self.U = {'type': 'fixedValue',
                  'value': 'uniform (0.000 0.000 0.000)'}
        self.boundaryRadiationProperties = {'type': 'lookup',
                                            'emissivity': '0.90',
                                            'absorptivity': '0.90',
                                            'transmissivity': '0'
                                            }
