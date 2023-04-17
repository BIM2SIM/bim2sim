import os
import contextlib

from bim2sim.task.base import ITask


class ExportTEASERModel(ITask):
    """Exports a Modelica model with TEASER by using the found information
    from IFC"""
    reads = ('teaser_prj', 'exported_buildings')
    touches = ('bldg_names',)

    def run(self, workflow, teaser_prj, exported_buildings):
        self.logger.info("Start export of the derived TEASER model to a "
                         "Modelica")
        # silence output via redirect_stdout to not mess with bim2sim logs
        with open(os.devnull, 'w') as devnull:
            with contextlib.redirect_stdout(devnull):
                teaser_prj.export_aixlib(
                    path=self.paths.export / 'TEASER' / 'Model',
                    use_postprocessing_calc=True)

        self.logger.info("Successfully created simulation model with TEASER.")

        bldg_names = []
        for bldg in exported_buildings:
            bldg_names.append(bldg.name)

        return bldg_names,
