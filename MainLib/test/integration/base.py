import logging
import tempfile
from pathlib import Path

import bim2sim


class IntegrationBase:
    """Base class mixin for Integration tests"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='bim2sim_')

    def tearDown(self):
        # manually close file handlers which would block temp dir deletion
        # TODO: this does not always work. log file sometimes still blocked
        # TODO: Projekt not properly reset. Run only one test per Interpreter instance as workaround
        root = logging.getLogger()
        for handler in root.handlers:
            if isinstance(handler, logging.FileHandler):
                handler.stream.flush()
                handler.stream.close()
            root.removeHandler(handler)
        for filt in root.filters:
            root.removeFilter(filt)

        # reset project
        self.reset_project()

        # delete temp dir
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            # sometimes logging still blocks *.log file. We just ignore this and leave some 'garbage'
            pass

    def reset_project(self):
        """clean bim2sim lib"""
        # decisions
        bim2sim.decision.Decision.reset_decisions()
        bim2sim.decision.Decision.stored_decisions.clear()
        # element.objects
        for item in list(bim2sim.kernel.element.Root.objects.values()):
            item.discard()

    def run_project(self, ifc_file: str, backend: str):
        """Create example project and copy ifc if necessary
        :param backend: Project backend e.g. 'hkesim', 'aixlib', ...
        :param ifc_file: name of ifc file located in dir TestModels
        :return: return code of main()
        """

        project_path = Path(self.temp_dir.name)
        path_ifc = Path(__file__).parent.parent / 'TestModels' / ifc_file

        if not bim2sim.PROJECT.is_project_folder(project_path):
            bim2sim.PROJECT.create(project_path, path_ifc, target=backend)
        return_code = bim2sim.main(project_path)
        return return_code
