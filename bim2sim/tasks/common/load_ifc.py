from __future__ import annotations

import time
from pathlib import Path

from bim2sim.kernel.ifc_file import IfcFileClass
from bim2sim.tasks.base import ITask
from bim2sim.utilities.types import IFCDomain


class LoadIFC(ITask):
    """Load all IFC files from PROJECT.ifc_base path.

    This tasks reads the IFC files of one or multiple domains inside bim2sim.

    Returns:
        ifc: list of one or multiple IfcFileClass elements
    """
    touches = ('ifc_files', )

    def run(self):
        self.logger.info("Loading IFC files")
        ifc_files = yield from self.load_ifc_files(self.paths.ifc_base)
        return ifc_files,

    def load_ifc_files(self, base_path: Path):
        """Load all ifc files in given base_path or a specific file in this path

        Loads the ifc files inside the different domain folders in the base
         path, and initializes the bim2sim ifc file classes.

         Args:
            base_path: Pathlib path that holds the different domain folders,
              which hold the ifc files.
        """
        if not base_path.is_dir():
            raise AssertionError(f"Given base_path {base_path} is not a"
                                 f" directory. Please provide a directory.")
        ifc_files = []
        ifc_files_paths = list(base_path.glob("**/*.ifc")) + list(
            base_path.glob("**/*.ifcxml")) + list(
            base_path.glob("**/*.ifczip"))
        self.logger.info(f"Found {len(ifc_files_paths)} IFC files in project "
                         f"directory.")
        for i, total_ifc_path in enumerate(ifc_files_paths, start=1):
            self.logger.info(
                f"Loading IFC file {total_ifc_path.name} {i}/{len(ifc_files_paths)}.")
            ifc_domain = total_ifc_path.parent.name
            reset_guids = self.playground.sim_settings.reset_guids
            ifc_domain = IFCDomain[ifc_domain]
            t_load_start = time.time()
            ifc_file_cls = IfcFileClass(
                total_ifc_path,
                ifc_domain=ifc_domain,
                reset_guids=reset_guids)
            yield from ifc_file_cls.initialize_finder(self.paths.finder)
            ifc_files.append(ifc_file_cls)
            t_load_end = time.time()
            t_loading = round(t_load_end - t_load_start, 2)
            self.logger.info(f"Loaded {total_ifc_path.name} for Domain "
                             f"{ifc_domain.name}. "
                             f"This took {t_loading} seconds")
        if not ifc_files:
            self.logger.error("No ifc found in project folder.")
            raise AssertionError("No ifc found. Check '%s'" % base_path)
        self.logger.info(f"Loaded {len(ifc_files)} IFC-files.")
        return ifc_files
