import os
import contextlib

from bim2sim.tasks.base import ITask
from bim2sim.plugins.PluginTEASER.bim2sim_teaser.task.create_result_df import \
    bim2sim_teaser_mapping_base, CreateResultDF


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

        self.lock = self.playground.sim_settings.lock

        # Important: if these are adjusted, also adjust sim_setting sim_results
        # and bim2sim_teaser_mapping_base in CreateResultDF
        export_vars = {
            "HeatingDemands": [
                "*multizone.PHeater*",
                "*multizonePostProcessing.PHeater*",
                'multizonePostProcessing.PHeaterSum',
                '*multizonePostProcessing.WHeater*',
                'multizonePostProcessing.WHeaterSum',
                ],
            "CoolingDemands": [
                '*multizone.PCooler*',
                '*multizonePostProcessing.PCooler*',
                '*multizonePostProcessing.PCoolerSum',
                '*multizonePostProcessing.WCooler*',
                'multizonePostProcessing.WCoolerSum',
            ],
            "Temperatures": [
                'weaDat.weaBus.TDryBul',
                '*multizone.TAir*',
                '*multizonePostProcessing.TAir*',
                'multizonePostProcessing.TAirMean',
                'multizonePostProcessing.TOperativeMean',
                '*multizonePostProcessing.TOperativeAverageCalc.u*'
            ],
            'AHU': [
                'multizonePostProcessing.WHeatAHU',
                'multizonePostProcessing.WCoolAHU',
                'multizonePostProcessing.WElAHU',
            ],
            'InternalGains': [
                '*multizonePostProcessing.QIntGains_flow*'
            ],
            'VentilationInfiltration': [
                'multizone.zone*.ventRate',
                'multizone.zone*.ventCont.y'
            ],
            'SetTemperatures': [
                'tableTSet.y*',
                'tableTSetCool.y*',
            ],
            'CPU': [
                'CPUtime'
            ]
        }

        # silence output via redirect_stdout to not mess with bim2sim logs
        with self.lock:
            with open(os.devnull, 'w') as devnull:
                with contextlib.redirect_stdout(devnull):
                    teaser_prj.export_aixlib(
                        path=self.paths.export / 'TEASER' / 'Model',
                        use_postprocessing_calc=True,
                        report=True,
                        export_vars=export_vars
                    )

        self.logger.info("Successfully created simulation model with TEASER.")
