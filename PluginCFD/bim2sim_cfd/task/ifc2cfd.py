import os

from bim2sim.decision import ListDecision, DecisionBunch
from bim2sim.task.base import ITask
from bim2sim.task.common import LoadIFC


class RunIFC2CFD(ITask):
    '''
    coole exe
    '''
    final = True

    def run(self, workflow):  #todo eigtl geht hier workflow rein
        self.logger.info("Running IFC2CFD")


        options = [" ", "Arg2"]  # TODO dict anlegen
        decision1 = ListDecision("Multiple possibilities found",
                                 choices=options,
                                 allow_skip=False, allow_load=False, allow_save=False,
                                 collect=False, quick_decide=False)
        yield DecisionBunch([decision1])
        args = decision1.value

        reader = LoadIFC()
        input_file = reader.get_ifc(self.paths.ifc)

        output_file = str(self.paths.export / "result.obj")
        cmd = "/bim2sim/PluginCFD/bim2sim_cfd/assets/IFC2SB" "-j9 --graph --cfd " + input_file
        # cmd += " " + args
        print(cmd)
        os.system(cmd)
        print("Task finished")
