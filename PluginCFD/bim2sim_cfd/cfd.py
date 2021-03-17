from bim2sim.plugin import Plugin
from bim2sim.task.base import ITask
from bim2sim.decision import ListDecision
from bim2sim.project import PROJECT
from bim2sim.task.common import LoadIFC
import os


class CFDManager(Plugin):

    def __init__(self, task):
        super().__init__(task)

    def run(self):
        print("CFD started")
        self.playground.run_task(Exe)


class Exe(ITask):
    '''
    coole exe
    '''
    final = True

    def run(self, **kwargs): #todo eigtl geht hier workflow rein
        print("Task started")
        print(kwargs)

        options = [" ", "Arg2"]  # TODO dict anlegen
        decision1 = ListDecision("Multiple possibilities found",
                                 choices=options,
                                 allow_skip=False, allow_load=False, allow_save=False,
                                 collect=False, quick_decide=False)
        args = decision1.decide()

        reader = LoadIFC()
        input_file = reader.get_ifc(PROJECT.ifc)

        output_file = str(PROJECT.export / "result.obj")
        cmd = "/home/fluid/Schreibtisch/B/IfcConvert" + " " + input_file + " " + output_file
        cmd += " " + args
        print(cmd)
        os.system(cmd)
        print("Task finished")
