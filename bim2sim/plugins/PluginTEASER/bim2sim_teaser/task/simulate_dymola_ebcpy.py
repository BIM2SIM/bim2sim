import re
from pathlib import Path

from ebcpy import DymolaAPI

import bim2sim
from bim2sim.tasks.base import ITask


class SimulateModelEBCPy(ITask):
    reads = ('bldg_names',)
    touches = ('teaser_mat_result_paths', 'sim_results_path')
    final = True

    def run(self, bldg_names):
        teaser_mat_result_paths = {}
        if not self.playground.sim_settings.dymola_simulation:
            self.logger.warning(
                f"{self.name} task was selected to run, but sim_setting for"
                f" dymola_simulation is set to "
                f"{self.playground.sim_settings.dymola_simulation}. "
                f"Please set sim_setting to True or deactivate task.")
            return None, None
        else:
            dir_aixlib = Path(bim2sim.__file__).parent / \
                         'plugins' / 'AixLib' / 'AixLib' / 'package.mo'
            # needed because teaser removes special characters
            regex = re.compile("[^a-zA-z0-9]")
            model_export_name = regex.sub("", self.prj_name)
            dir_model_package = Path(
                self.paths.export / 'TEASER' / 'Model' / model_export_name /
                'package.mo')
            sim_results_path = Path(
                self.paths.export / 'TEASER' / 'SimResults' /
                model_export_name)
            packages = [
                dir_model_package,
                dir_aixlib
            ]

            simulation_setup = {"start_time": 0,
                                "stop_time": 3.1536e+07,
                                "output_interval": 3600}
            n_success = 0
            for n_sim, bldg_name in enumerate(bldg_names):
                self.logger.info(f"Starting simulation for model "
                                 f"{bldg_name}. "
                                 f"Simulation {n_sim}/{len(bldg_names)}")
                sim_model = \
                    model_export_name + '.' + bldg_name + '.' + bldg_name
                bldg_result_dir = sim_results_path / bldg_name
                bldg_result_dir.mkdir(parents=True, exist_ok=True)

                try:
                    dym_api = DymolaAPI(
                        model_name=sim_model,
                        cd=bldg_result_dir,
                        packages=packages,
                        show_window=True,
                        n_restart=-1,
                        equidistant_output=True,
                        debug=True
                    )
                except Exception:
                    raise Exception(
                        "Dymola API could not be initialized, there"
                        "are several possible reasons."
                        " One could be a missing Dymola license.")
                dym_api.set_sim_setup(sim_setup=simulation_setup)

                teaser_mat_result_path = dym_api.simulate(
                    return_option="savepath"
                )
                if teaser_mat_result_path:
                    n_success += 1
                teaser_mat_result_paths[bldg_name] = teaser_mat_result_path
            self.playground.sim_settings.simulated = True
            self.logger.info(f"Successfully simulated "
                             f"{n_success}/{len(bldg_names)}"
                             f" Simulations.")
            self.logger.info(f"You can find the results under "
                             f"{str(sim_results_path)}")
            return teaser_mat_result_paths, sim_results_path
