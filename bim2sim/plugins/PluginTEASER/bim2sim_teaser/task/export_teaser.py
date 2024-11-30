import os
import contextlib

from bim2sim.tasks.base import ITask


class ExportTEASER(ITask):
    """Export TEASER prj, run() method holds detailed information."""
    reads = ('teaser_prj',)

    def run(self, teaser_prj):
        """Exports the current TEASER project to Modelica.

        This is the final export task that exports the created TEASER project
        into Modelica by using TEASERs inbuilt export functionality. Currently,
        the export will be done to AixLib, potentially the export_ibpsa()
        functionality could be used as well.

        Args:
            teaser_prj: teaser project instance

        """
        self.logger.info("Starting export TEASER model to Modelica")

        export_vars = {
            "PHeater": ["*multizone.PHeater*"],
            "PCooler": ["*multizone.PCooler*"],
            "QIntGains_flow": ["*multizone.QIntGains_flow*"],
            "WHeaterSum": ["multizonePostProcessing.WHeaterSum"],
            "WCoolerSum": ["multizonePostProcessing.WCoolerSum"]
        }

        # silence output via redirect_stdout to not mess with bim2sim logs
        with open(os.devnull, 'w') as devnull:
            with contextlib.redirect_stdout(devnull):
                teaser_prj.export_aixlib(
                    path=self.paths.export / 'TEASER' / 'Model',
                    use_postprocessing_calc=True,
                    report=True,
                    export_vars=export_vars)

        self.logger.info("Successfully created simulation model with TEASER.")
