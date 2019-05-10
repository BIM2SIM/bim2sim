import re
from ast import literal_eval

from bim2sim.manage import BIM2SIMManager, PROJECT
from bim2sim.tasks import LOD, PlantSimulation
from bim2sim.workflow import hvac

from bim2sim_hkesim import models

class AixLib(BIM2SIMManager):

    def __init__(self, task):
        super().__init__(task)

        self.relevant_ifc_types = hvac.IFC_TYPES

    def run(self):

        prepare = hvac.Prepare()
        prepare.run(hvac.IFC_TYPES)

        inspect = hvac.Inspect()
        inspect.run(self.ifc, hvac.IFC_TYPES)

        detectcycles = hvac.DetectCycles()
        detectcycles.run(inspect.instances)

        reduce = hvac.Reduce()
        reduce.run(detectcycles.graph)

        #check

        #TODO reduced_instances hold only aggregations, not aggregated are missing
        export = hvac.Export()
        export.run(reduce.reduced_instances)

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
