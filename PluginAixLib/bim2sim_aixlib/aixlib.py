import re

from ast import literal_eval

import bim2sim
from bim2sim.manage import BIM2SIMManager
from bim2sim.ifc2python.hvac import hvacsystem

class AixLib(BIM2SIMManager):

    def __init__(self, task, ifc):
        super().__init__(task, ifc)

        self.relevant_ifc_types = ['IfcAirTerminal',
                                   'IfcAirTerminalBox',
                                   'IfcAirToAirHeatRecovery',
                                   'IfcBoiler',
                                   'IfcBurner',
                                   'IfcChiller',
                                   'IfcCoil',
                                   'IfcCompressor',
                                   'IfcCondenser',
                                   'IfcCooledBeam',
                                   'IfcCoolingTower',
                                   'IfcDamper',
                                   'IfcDuctFitting',
                                   'IfcDuctSegment',
                                   'IfcDuctSilencer',
                                   'IfcEngine',
                                   'IfcEvaporativeCooler',
                                   'IfcEvaporator',
                                   'IfcFan',
                                   'IfcFilter',
                                   'IfcFlowMeter',
                                   'IfcHeatExchanger',
                                   'IfcHumidifier',
                                   'IfcMedicalDevice',
                                   'IfcPipeFitting',
                                   'IfcPipeSegment',
                                   'IfcPump',
                                   'IfcSpaceHeater',
                                   'IfcTank',
                                   'IfcTubeBundle',
                                   'IfcUnitaryEquipment',
                                   'IfcValve',
                                   'IfcVibrationIsolator']

    def prepare(self):
        
        self.logger.info('preparing stuff')

        self.hvac = hvacsystem.HVACSystem(self.ifc)

        return

    def run(self):

        self.logger.info('doing export stuff')

        #self.hvac.draw_hvac_network()
        return

    def create_modelica_table_from_list(self,curve):
        """

        :param curve:
        :return:
        """
        curve = literal_eval(curve)
        for key, value in curve.iteritems():
            # add first and last value to make sure there is a constant
            # behaviour before and after the given heating curve
            value = [value[0] - 5, value[1]] + value + [value[-2] + 5,
                                                        value[-1]]
            # transform to string and replace every second comma with a
            # semicolon to match modelica syntax
            value = str(value)
            value = re.sub('(,[^,]*),', r'\1;', value)
            setattr(self, key, value)
