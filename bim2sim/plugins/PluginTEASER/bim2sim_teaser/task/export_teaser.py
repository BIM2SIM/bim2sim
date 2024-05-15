import os
import contextlib
from ebcpy import TimeSeriesData

from bim2sim.tasks.base import ITask


class ExportTEASER(ITask):
    """Exports the previous created TEASER project to Modelica."""
    reads = ('teaser_prj',)
    touches = ('teaser_prj',)

    def run(self, teaser_prj):
        self.logger.info("Starting export TEASER model to Modelica")
        """
        export_vars = {
            "PHeater": ["*multizone.PHeater*"],
            "PCooler": ["*multizone.PCooler*"],
            "QIntGains_flow": ["*multizone.QIntGains_flow*"],
            "WHeaterSum": "multizonePostProcessing.WHeaterSum",
            "WCoolerSum": "multizonePostProcessing.WCoolerSum"
        }
        """
        # silence output via redirect_stdout to not mess with bim2sim logs
        with open(os.devnull, 'w') as devnull:
            with contextlib.redirect_stdout(devnull):
                teaser_prj.export_aixlib(
                    path=self.paths.export / 'TEASER' / 'Model',
                    use_postprocessing_calc=True,
                    report=True)
                    #export_vars=export_vars)

        self.logger.info("Successfully created simulation model with TEASER.")

        return teaser_prj,
