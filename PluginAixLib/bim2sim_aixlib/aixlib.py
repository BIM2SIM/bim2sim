import re
from ast import literal_eval

from bim2sim.manage import BIM2SIMManager, PROJECT
from bim2sim.workflow import hvac, bps, thermalzones
from bim2sim.export.modelica import standardlibrary

class AixLib(BIM2SIMManager):

    def __init__(self, task):
        super().__init__(task)

        self.relevant_ifc_types = hvac.IFC_TYPES

    def run(self):
        ###

        recognition = thermalzones.Recognition()
        recognition.run(self.ifc, thermalzones.IFC_TYPES)

        ###
        prepare = hvac.Prepare()
        prepare.run(self.task, hvac.IFC_TYPES)

        inspect = hvac.Inspect()
        if not inspect.load(PROJECT.workflow):
            inspect.run(self.task, self.ifc, hvac.IFC_TYPES)
            inspect.save(PROJECT.workflow)

        enrich = hvac.Enrich()
        enrich.run(inspect.instances)

        makegraph = hvac.MakeGraph()
        if not makegraph.load(PROJECT.workflow):
            makegraph.run(self.task, list(inspect.instances.values()))
            makegraph.save(PROJECT.workflow)

        reduce = hvac.Reduce()
        reduce.run(self.task, makegraph.graph)

        libraries = (standardlibrary.StandardLibrary, )
        export = hvac.Export()
        export.run(self.task, libraries, reduce.reduced_instances, reduce.connections)

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
