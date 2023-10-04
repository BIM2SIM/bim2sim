import itertools
import os
import re
import sys
from pathlib import Path

import bim2sim
from bim2sim.tasks.base import ITask


class SimulateModel(ITask):
    reads = ('bldg_names',)
    final = True

    def run(self, bldg_names):
        if self.playground.sim_settings.dymola_simulation:
            path = self.get_dymola_path()
            if not path:
                raise Exception('No Dymola Installation found. Program Terminated.')

            self.load_dymola(path)
            from dymola.dymola_interface import DymolaInterface
            dymola = DymolaInterface()

            dir_aixlib = Path(bim2sim.__file__).parent /\
                         'plugins' / 'AixLib' / 'AixLib' / 'package.mo'
            # needed because teaser removes special characters

            regex = re.compile("[^a-zA-z0-9]")
            model_export_name = regex.sub("", self.prj_name)

            dir_model = Path(
                self.paths.export / 'TEASER' / 'Model' / model_export_name /
                'package.mo')
            dir_result = Path(
                self.paths.export / 'TEASER' / 'SimResults' / model_export_name)

            dymola.openModel(str(dir_aixlib))
            dymola.openModel(str(dir_model))

            n_success = 0
            for n_sim, bldg_name in enumerate(bldg_names):
                self.logger.info(f"Starting Simulating Process for model "
                                 f"{bldg_name}. "
                                 f"Simulation {n_sim}/{len(bldg_names)}")
                sim_model = \
                    model_export_name + '.' + bldg_name + '.' + bldg_name
                self.logger.info(f"Translating model {bldg_name}.")
                translate_status = dymola.translateModel(sim_model)
                if translate_status:
                    bldg_result_dir = dir_result / bldg_name
                    bldg_result_dir.mkdir(parents=True, exist_ok=True)
                    output = dymola.simulateExtendedModel(
                        problem=sim_model,
                        startTime=0.0,
                        stopTime=3.1536e+07,
                        outputInterval=3600,
                        method="Dassl",
                        tolerance=0.0001,
                        resultFile=str(bldg_result_dir / bldg_name),
                        # finalNames=['thermalZone.TAir'],
                    )
                    if not output[0]:
                        self.logger.error(
                            f"Simulation of {bldg_name} was not successful")
                    else:
                        n_success += 1
                else:
                    self.logger.error(
                        f"Translation of {bldg_name} was not successful")
            dymola.close()
            self.playground.sim_settings.simulated = True
            self.logger.info(f"Successfully simulated "
                             f"{n_success}/{len(bldg_names)}"
                             f" Simulations.")
            self.logger.info(f"You can find the results under "
                             f"{str(dir_result)}")
            df = self.save_to_dataframe()
            create_plotly_graphs_from_df(df)

    @staticmethod
    def get_dymola_path() -> Path:
        """Function to find local dymola installation path."""
        dymola_versions = [
            'Dymola 2019',
            'Dymola 2019x',
            'Dymola 2020',
            'Dymola 2020x',
            'Dymola 2021',
            'Dymola 2021x',
            'Dymola 2022',
            'Dymola 2022x',
            'Dymola 2023',
            'Dymola 2023x',
            # todo fix newer dymola versions (msl 4.0 error)
        ]

        if os.name == 'nt':  # windows
            prog_paths = [
                'C:/Program Files/',
                'C:/Program Files (x86)/'
            ]
        else:   # linux (os.name == 'posix'):
            prog_paths = [
                '/opt/dymola/'
            ]

        egg_path = '/Modelica/Library/python_interface/dymola.egg'

        dymola_path = None
        for base_path in itertools.product(
                prog_paths, reversed(dymola_versions)):
            dymola_path = Path(''.join(base_path) + egg_path)
            if dymola_path.is_file():
                break
            else:
                dymola_path = None
        return dymola_path

    @staticmethod
    def load_dymola(path: Path):
        sys.path.insert(0, str(path))

    def save_to_dataframe(self):
        # todo #497
        df = None
        pass
        return df
