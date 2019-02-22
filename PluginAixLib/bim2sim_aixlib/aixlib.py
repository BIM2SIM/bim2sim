import re

from ast import literal_eval

from bim2sim.decorators import log
from bim2sim.manage import BIM2SIMManager, PROJECT
from bim2sim.ifc2python.aggregation import PipeStrand
from bim2sim.filter import TypeFilter
from bim2sim.export import modelica

from bim2sim_hkesim import models

class AixLib(BIM2SIMManager):

    def __init__(self, task):
        super().__init__(task)

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

    @log("preparing")
    def prepare(self):

        # TODO: depending on task ...
        self.filters.append(TypeFilter(self.relevant_ifc_types))

    @log("reducing model")
    def reduce(self):
        reducible_elements = ['IfcPipeSegment', 'IfcPipeFitting']
        for main_pipe in self.raw_instances.values():
            if len(main_pipe.neighbors) == 2 and main_pipe.ifc_type in \
                    reducible_elements:
                for next_pipe in main_pipe.neighbors:
                    if len(next_pipe.neighbors) <= 2 and next_pipe.ifc_type in \
                            reducible_elements:
                        if next_pipe.pipestrand is None and \
                                main_pipe.pipestrand is None:
                            ps = PipeStrand(self)
                            ps.pipes = [main_pipe, next_pipe]
                            next_pipe.pipestrand = ps
                            main_pipe.pipestrand = ps
                        elif next_pipe.pipestrand is None:
                            ps = main_pipe.pipestrand
                            ps.pipes = [next_pipe]
                            next_pipe.pipestrand = ps
                        elif main_pipe.pipestrand is None:
                            ps = next_pipe.pipestrand
                            ps.pipes = [main_pipe]
                            main_pipe.pipestrand = ps
                        elif next_pipe.pipestrand is not None and \
                                main_pipe.pipestrand is not None:
                            ps = next_pipe.pipestrand
                            ps.merge_pipestrands(main_pipe.pipestrand)


    @log("processing")
    def process(self):

        self.instances.extend(self.reduced_instances)

    @log("exporting")
    def export(self):
        for inst in self.instances:
            self.export_instances.append(modelica.Instance.factory(inst))

        modelica_model = modelica.Model(name="Test", comment="testing",
                                        instances=self.export_instances,
                                        connections={})
        print("-" * 80)
        print(modelica_model.code())
        print("-" * 80)
        modelica_model.save(PROJECT.export)

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
