from bim2sim.tasks.base import ITask


class RunOpenFOAMSimulation(ITask):
    """This ITask runs the openfoam simulation.
    """

    reads = ('openfoam_case',)
    touches = ()

    def __init__(self, playground):
        super().__init__(playground)

    def run(self, openfoam_case):
        # todo: add RunOpenFOAM simulation, which should only be executed on
        #  linux (and check for #cores before run and match with
        #  decomposeParDict)
        pass
