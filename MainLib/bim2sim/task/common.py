import os

from bim2sim.kernel import ifc2python
from bim2sim.manage import PROJECT
from .base import ITask


class Reset(ITask):
    """Reset all progress"""
    touches = '__all__'

    @classmethod
    def requirements_met(cls, state):
        return bool(state)

    def run(self, workflow):
        return {}


class Quit(ITask):
    """Quit interactive tasks"""

    final = True


class LoadIFC(ITask):
    """Load IFC file from PROJECT.ifc path (file or dir)"""
    touches = ('ifc', )

    def run(self, workflow):
        # TODO: use multiple ifs files

        path = PROJECT.ifc  # TODO: extra ITask to load Project settings?

        if os.path.isdir(path):
            ifc_path = self.get_ifc(path)
        elif os.path.isfile(path):
            ifc_path = path
        else:
            raise AssertionError("No ifc found. Check '%s'" % path)

        ifc = ifc2python.load_ifc(os.path.abspath(ifc_path))

        self.logger.info("The exporter version of the IFC file is '%s'",
                         ifc.wrapped_data.header.file_name.originating_system)
        return ifc,

    def get_ifc(self, path):
        """Returns first ifc from ifc folder"""
        lst = []
        for file in os.listdir(path):
            if file.lower().endswith(".ifc"):
                lst.append(file)

        if len(lst) == 1:
            return os.path.join(path, lst[0])
        if len(lst) > 1:
            self.logger.warning("Found multiple ifc files. Selected '%s'.", lst[0])
            return os.path.join(path, lst[0])

        self.logger.error("No ifc found in project folder.")
        return None
