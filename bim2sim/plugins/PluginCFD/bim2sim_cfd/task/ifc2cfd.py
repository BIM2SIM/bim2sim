import os

from bim2sim.decision import ListDecision, DecisionBunch, RealDecision
from bim2sim.kernel.units import ureg
from bim2sim.task.base import ITask
from bim2sim.task.common import LoadIFC


class RunIFC2CFD(ITask):
    '''
    # todo @ eric infos hier ausfüllen
    '''
    final = True

    def run(self, workflow):
        if os.name != 'posix':
            raise OSError("CFD task is only available for Linux systems")
        self.logger.info("Running IFC2CFD")

        process_options = [
            ("--cfd", "STL processing"),
            ("", "IFC processing")
        ]
        process_decision = ListDecision("Which process do you want to use?",
                                        choices=process_options,
                                        key='process_decision',
                                        global_key='process_decision',
                                        allow_skip=False)

        def is_int(val):
            try:
                val = int(val)
            except:
                pass
            if isinstance(val, int):
                return True
            else:
                try:
                    return val.is_integer()
                except AttributeError:
                    return False

        core_decision = RealDecision(
            "How many cores do you want to use?",
            global_key="core_decision",
            allow_skip=True,
            validate_func=is_int
        )

        yield DecisionBunch([process_decision, core_decision])

        args = " --graph " + str(process_decision.value) + " -j" \
                   + str(int(core_decision.value.m))

        if process_decision.value == "":
            translen_decision = RealDecision(
                "What is the maximum transmission length (2a vs. 2b)?",
                global_key="translen_decision",
                unit=ureg.meter,
                allow_skip=False)

            yield DecisionBunch([translen_decision])

            args += " -e" + str(translen_decision.value.m)

        reader = LoadIFC()
        input_file = reader.get_ifc(self.paths.ifc)

        if process_decision.value == '--cfd':
            file_ending = '.stl'
        else:
            file_ending = '.ifc'

        output_file = str(self.paths.export / "result") + str(file_ending)
        ifc2sb_callable = str(
            self.paths.b2sroot / "PluginCFD/bim2sim_cfd/ifc2sb/IFC2SB")

        cmd = ifc2sb_callable + " " + args + ' ' + input_file + ' ' \
              + output_file
        os.system(cmd)
        self.logger.info("Finished IFC2CFD")
