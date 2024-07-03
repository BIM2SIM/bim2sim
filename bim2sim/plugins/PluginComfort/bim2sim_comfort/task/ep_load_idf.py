import logging
import os

from geomeppy import IDF

from bim2sim.tasks.base import ITask

logger = logging.getLogger(__name__)


class LoadIdf(ITask):
    """Load the IDF file of an EnergyPlus Simulation.

    Task to Load an IDF file from a previous BIM2SIM execution from project
    directory.
    """

    touches = ('idf',)

    def run(self, workflow):
        """Execute all methods to load an existing IDF file."""
        logger.info("Loading IDF File started ...")
        ep_install_path = workflow.ep_install_path
        IDF.setiddname(ep_install_path + 'Energy+.idd')
        idf_path = self.paths.export
        idf_name = None
        for file in os.listdir(idf_path):
            if file.endswith(".idf"):
                idf_name = os.path.join(idf_path, file)
                break  # todo: handle multiple idfs (choose by name)
        if not idf_name:
            raise AssertionError("No IDF File found for loading!")
        idf = IDF(idf_name)
        logger.info("IDF File successfully loaded")

        return idf,
