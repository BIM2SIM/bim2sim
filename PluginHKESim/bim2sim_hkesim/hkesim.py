
import bim2sim

from bim2sim.decorator import log
from bim2sim.manage import BIM2SIMManager, PROJECT
from bim2sim.ifc2python.element import Element
from bim2sim.ifc2python.aggregation import PipeStrand
from bim2sim.filter import TypeFilter
from bim2sim.tasks import LOD, PlantSimulation
from bim2sim.export import modelica
from bim2sim.decision import Decision

from bim2sim_hkesim import models

class HKESimManager(BIM2SIMManager):

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
        
        #TODO: depending on task ...
        self.filters.append(TypeFilter(self.relevant_ifc_types))

    @log("reducing model")
    def reduce(self):
        # not yet an usefull aggregation. just a showcase ...
        pipes = []
        normal = []
        for m in self.raw_instances.values():
            if m.ifc_type in ["IfcPipeFitting", "IfcPipeSegment"]:
                pipes.append(m)
            else:
                normal.append(m)

        agg_pipe = PipeStrand("Strand 1", pipes) 

        self.reduced_instances.append(agg_pipe)
        self.reduced_instances.extend(normal)

    @log("processing")
    def process(self):
        
        self.instances.extend(self.reduced_instances)

    @log("exporting")
    def export(self):

        Decision.load(PROJECT.decisions)
        for inst in self.instances:
            self.export_instances.append(modelica.Instance.factory(inst))

        self.logger.info(Decision.summary())
        Decision.decide_collected()
        Decision.save(PROJECT.decisions)

        modelica_model = modelica.Model(name="Test", comment="testing", instances=self.export_instances, connections={})
        print("-"*80)
        print(modelica_model.code())
        print("-"*80)
        modelica_model.save(PROJECT.export)
