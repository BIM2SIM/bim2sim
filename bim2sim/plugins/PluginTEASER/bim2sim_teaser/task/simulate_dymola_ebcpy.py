import re
from pathlib import Path
import subprocess
import time
import psutil

from ebcpy import DymolaAPI

import bim2sim
from bim2sim.tasks.base import ITask


class SimulateModelEBCPy(ITask):
    """Simulate TEASER model, run() method holds detailed information."""
    reads = ('bldg_names', 'teaser_prj')
    touches = ('sim_results_path',)
    final = True

    def run(self, bldg_names, teaser_prj):
        """Simulates the exported TEASER model by using ebcpy.

        The Modelica model that is created through TEASER is simulated by using
        ebcpy and its DymolaAPI. Modelica/Dymola stores simulation results
        in .mat files which are stored in the export folder of the `bim2sim`
        project.

        Args:
            bldg_names: bldg_names: list of names of all buildings in project

        Returns:
            teaser_mat_result_paths: dict[bldg_name: mat result path] where for
                each building the corresponding result is stored
            sim_results_path: path where the sim results are stored, including
                the subdirectory with the model name
        """
        if not self.playground.sim_settings.dymola_simulation:
            self.logger.warning(
                f"{self.name} task was selected to run, but sim_setting for"
                f" dymola_simulation is set to "
                f"{self.playground.sim_settings.dymola_simulation}. "
                f"Please set sim_setting to True or deactivate task.")
            return None,
        else:
            if self.playground.sim_settings.path_aixlib:
                dir_aixlib = self.playground.sim_settings.path_aixlib
            else:
                # if aixlib not provided by setting, try using the path from
                # regression testing
                self.logger.warning(
                    f'The sim_setting "path_aixlib" is not set, trying to use'
                    f'the regression test path for AixLib library.')
                dir_aixlib = (
                        Path(bim2sim.__file__).parent / 'plugins' /
                        f'Plugin{self.playground.project.plugin_cls.name}'
                        / 'test' / 'regression' / 'library' /
                        'library_AixLib' / 'AixLib' / 'package.mo')
            if not dir_aixlib.exists():
                raise FileNotFoundError(
                    f'AixLib directory not found. The sim_setting '
                    f'"path_aixlib" is not set and library for regression '
                    f'testing was not downloaded yet. Please either set the '
                    f'"path_aixlib" sim_setting or run '
                    f'prepare_regression_tests.py for '
                    f'Plugin{self.playground.project.plugin_cls.name}.')
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
                                "output_interval": 3600,
                                "solver": "Cvode",
                                "tolerance": 0.001}
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
                        working_directory=bldg_result_dir,
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
                # activate spare solver as TEASER models are mostly sparse
                dym_api.dymola.ExecuteCommand(
                    "Advanced.SparseActivate=true")
                teaser_mat_result_path = dym_api.simulate(
                    return_option="savepath",
                    savepath=str(sim_results_path / bldg_name),
                    result_file_name="teaser_results"
                )
                if teaser_mat_result_path:
                    n_success += 1
            self.playground.sim_settings.simulated = True
            self.logger.info(f"Successfully simulated "
                             f"{n_success}/{len(bldg_names)}"
                             f" Simulations.")
            self.logger.info(f"You can find the results under "
                             f"{str(sim_results_path)}")

            if self.playground.sim_settings.edit_mat_result_file_flag:
                self.edit_mat_result_file(teaser_prj, bldg_name, bldg_result_dir)

            return sim_results_path,


    def edit_mat_result_file(self, teaser_prj, bldg_name, bldg_result_dir):
        """Creates .mos script to extract specific data out of dymola mat result file
            and safe it to a new .mat file

        Args:
            teaser_prj: teaser project instance (to extract number of thermal zones in building)
            bldg_result_dir: Path to dymola result directory
        Returns:
            mos_script_post_path: Path to created .mos script
        """
        #TODO Make generic with input simsettings.var_names

        var_names_heating = [
            "multizonePostProcessing.PHeater",
            "multizonePostProcessing.WHeaterSum"
        ]
        var_names_cooling = [
            "multizonePostProcessing.PCooler",
            "multizonePostProcessing.WCoolerSum"
        ]
        var_names_ahu = [
            "multizonePostProcessing.PelAHU",
            "multizonePostProcessing.PHeatAHU",
            "multizonePostProcessing.PCoolAHU"
        ]

        zone_var = [
            "multizonePostProcessing.PHeater",
            "multizonePostProcessing.PCooler"
        ]

        var_names = var_names_heating
        if self.playground.sim_settings.cooling:
            var_names += var_names_cooling
        if self.playground.sim_settings.overwrite_ahu_by_settings:
            var_names += var_names_ahu


        for building in teaser_prj.buildings:
            if bldg_name == building.name:
                n = len(building.thermal_zones) # number of thermal zones

        script = f'cd("{str(bldg_result_dir)}");\n'
        script += f'resultFile = "teaser_results.mat";\n'
        script += f'outName = "teaser_results_edited.mat";\n\n'
        script += 'varNames = {"Time",\n'

        # Internal gains
        for i in range(1, n + 1):
            script += f'"multizonePostProcessing.QIntGains_flow[{i}, 1]",\n'
            script += f'"multizonePostProcessing.QIntGains_flow[{i}, 2]",\n'
            script += f'"multizonePostProcessing.QIntGains_flow[{i}, 3]",\n'
        for var in var_names:
            if var in zone_var:
                for i in range(1, n + 1):
                    script += f'"{var}[{i}]",\n'
            else:
                if var != var_names[-1]:
                    script += f'"{var}",\n'
                else:
                    script += f'"{var}"\n'

        script += '};\n\n'
        script += f'n = readTrajectorySize(resultFile);\n'
        script += f'writeTrajectory(outName, varNames, transpose(readTrajectory(resultFile, varNames, n)));'

        mos_file_path = bldg_result_dir / "edit_result_file.mos"
        with open(mos_file_path, 'w') as file:
            file.write(script)

        dymola_executable = r"C:\Program Files\Dymola 2023\bin64\dymola.exe"
        subprocess.Popen([dymola_executable, mos_file_path], shell=True)
        time.sleep(10)
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] == 'Dymola.exe':
                    psutil.Process(proc.info['pid']).terminate()
                    print('Dymola.exe wurde beendet')
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass