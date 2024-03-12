from bim2sim.export.modelica import standardlibrary
from bim2sim.tasks.base import ITask


class LoadLibrariesStandardLibrary(ITask):
    """Load AixLib library for export"""
    touches = ('libraries', )

    def run(self, **kwargs):
        return (standardlibrary.StandardLibrary,),
