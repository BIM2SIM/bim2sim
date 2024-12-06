from pathlib import Path
import ast
import time
import psutil
import re

from ebcpy import DymolaAPI

import teaser
from teaser.project import Project

from teaser.data.dataclass import DataClass
from teaser.data.utilities import ConstructionData

from bim2sim_teaser.task import CreateTEASER

import bim2sim
from bim2sim.utilities.common_functions import download_library





def load_serialized_teaser_project(project_path, serialized_teaser_path,
                                   heating_bool, cooling_bool,
                                   ahu_central_bool, ahu_heat_bool, ahu_cool_bool, ahu_hum_bool,
                                   ahu_heat_recovery, ahu_heat_recovery_efficiency,
                                   building_standard, window_standard):

    """This function demonstrates different loading options of TEASER"""
    prj_export_path = Path(project_path, "export", "TEASER")
    prj_model_path = Path(prj_export_path, "Model")

    repo_url = "https://github.com/RWTH-EBC/AixLib.git"
    branch_name = "main"
    repo_name = "AixLib"
    path_aixlib = (Path(bim2sim.__file__).parent.parent / "local" / f"library_{repo_name}")
    #download_library(repo_url, branch_name, path_aixlib)
    path_aixlib = path_aixlib / repo_name / 'package.mo'

    prj = Project()
    prj.load_project(path=serialized_teaser_path)

    prj.data = DataClass(construction_data=ConstructionData.kfw_40)


    # Select results to output:
    sim_results = [
        "heat_demand_total", "cool_demand_total",
        "heat_demand_rooms", "cool_demand_rooms",
        "heat_energy_total", "cool_energy_total",
        "heat_energy_rooms", "cool_energy_rooms",
        "operative_temp_rooms", "air_temp_rooms", "air_temp_out",
        "internal_gains_machines_rooms", "internal_gains_persons_rooms",
        "internal_gains_lights_rooms",
        "heat_set_rooms",
        "cool_set_rooms"
    ]
    prj_custom_usages = (Path(bim2sim.__file__).parent.parent / "test/resources/arch/custom_usages/"
                                              "customUsagesAC20-Institute-Var-2_with_SB-1-0.json")

    # Do some work on the model, e.g. increase total window area of each

    # thermal zone by 10 %
    window_increase_percentage = 0.1

    # specify templates for the layer and material overwrite
    construction_classes = {"year_of_construction": 2016,
                            "year_of_construction_windows": 2015,
                            "construction_class_walls": building_standard,
                            "construction_class_windows": window_standard,
                            "construction_class_doors": building_standard}

    # Specify hvac parameters
    hvac_params = {"heating_bool": heating_bool,
                   "cooling_bool": cooling_bool,
                   "ahu_central_bool": ahu_central_bool,
                   "ahu_heating": ahu_heat_bool,
                   "ahu_cooling": ahu_cool_bool,
                   "ahu_hum_bool": ahu_hum_bool,
                   "ahu_heat_recovery": ahu_heat_recovery,
                   "ahu_heat_recovery_efficiency": ahu_heat_recovery_efficiency,
                  }

    manipulate_teaser_model(teaser_prj=prj,
                            window_increase_percentage=window_increase_percentage,
                            construction_classes=construction_classes,
                            hvac_params=hvac_params)

    # calculate all buildings, this is needed as model_attr and library_attr
    # are not saved via json export.
    prj.calc_all_buildings()

    # As calc_all_buildings() recalculates the heating loads and thus the max
    # ideal heater PI-control values, we might reset those as they can be too
    # low and lead to too low zone temperatures
    orig_heat_loads, orig_cool_loads = CreateTEASER.overwrite_heatloads(prj.buildings)

    prj.export_aixlib(
        path=prj_model_path,
        use_postprocessing_calc=True,
        report=True
    )

    simulate_dymola_ebcpy(teaser_prj=prj,
                          prj_export_path=prj_export_path,
                          path_aixlib=path_aixlib)

def manipulate_teaser_model(teaser_prj,
                            window_increase_percentage,
                            construction_classes,
                            hvac_params):

    for bldg in teaser_prj.buildings:

        for tz in bldg.thermal_zones:

            # Increase window-wall ratio
            """ow_area_old = 0
            for ow in tz.outer_walls:
                ow_area_old += ow.area
            win_area_old = 0
            for win in tz.windows:
                win_area_old += win.area
            win_ratio = win_area_old / ow_area_old
            print(f"Current window to wall ratio of thermal zone "
                  f"{tz.name} is {round(win_ratio*100,2 )} %. "
                  f"Increasing total window "
                  f"area by {window_increase_percentage*100} %.")
            # calculate the total new window area
            win_area_new = (1 + window_increase_percentage) * win_area_old
            win_area_increase = win_area_new-win_area_old
            ow_area_new = ow_area_old - win_area_increase
            ow_area_decrease = ow_area_old - ow_area_new
            # distribute the changes on the different windows and outer walls
            # based on their percentage ratio
            for win in tz.windows:
                win.area += win_area_increase * win.area/win_area_old
            for ow in tz.outer_walls:
                ow.area -= ow_area_decrease * ow.area/ow_area_old
            # check new areas
            ow_area_res = 0
            for ow in tz.outer_walls:
                ow_area_res += ow.area
            win_area_res = 0
            for win in tz.windows:
                win_area_res += win.area
            win_ratio_res = win_area_res/ow_area_res
            print(f"New window to wall ratio of thermal zone "
                  f"{tz.name} is {round(win_ratio_res*100,2 )} %.")"""

            # element and material types
            for outer_wall in tz.outer_walls:
                outer_wall.load_type_element(year=construction_classes["year_of_construction"],
                                             construction=construction_classes["construction_class_walls"])
            for inner_wall in tz.inner_walls:
                inner_wall.load_type_element(year=construction_classes["year_of_construction"],
                                             construction=construction_classes["construction_class_walls"])
            for rooftop in tz.rooftops:
                rooftop.load_type_element(year=construction_classes["year_of_construction"],
                                          construction=construction_classes["construction_class_walls"])
            for ground_floor in tz.ground_floors:
                ground_floor.load_type_element(year=construction_classes["year_of_construction"],
                                               construction=construction_classes["construction_class_walls"])
            for window in tz.windows:
                window.load_type_element(year=construction_classes["year_of_construction_windows"],
                                         construction=construction_classes["construction_class_windows"],
                                         data_class=DataClass(construction_data=ConstructionData.iwu_heavy))
            for door in tz.doors:
                door.load_type_element(year=construction_classes["year_of_construction"],
                                       construction=construction_classes["construction_class_doors"])

def simulate_dymola_ebcpy(teaser_prj, prj_export_path, path_aixlib):
    """Simulates the exported TEASER model by using ebcpy.

    The Modelica model that is created through TEASER is simulated by using
    ebcpy and its DymolaAPI. Modelica/Dymola stores simulation results
    in .mat files which are stored in the export folder of the `bim2sim`
    project.

    Args:


    Returns:

    """

    # Function for extracting relevant information out of simulation result file
    def edit_mat_result_file(self, teaser_prj, bldg_result_dir, bldg_name):
        """Creates .mos script to extract specific data out of dymola mat result file
            and safe it to a new .mat file

        Args:
            teaser_prj: teaser project instance (to extract number of thermal zones in building)
            bldg_result_dir: Path to dymola result directory
        Returns:
            mos_script_post_path: Path to created .mos script
        """
        # TODO Make generic with input simsettings.var_names

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
                n = len(building.thermal_zones)  # number of thermal zones

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

        if isinstance(mos_file_path, Path):
            mos_file_path = str(mos_file_path)

        mos_file_path = mos_file_path.replace("\\", "/")
        # Search for e.g. "D:testzone" and replace it with D:/testzone
        loc = mos_file_path.find(":")
        if mos_file_path[loc + 1] != "/" and loc != -1:
            path = mos_file_path.replace(":", ":/")

        return mos_file_path

    for bldg in teaser_prj.buildings:
        # needed because teaser removes special characters
        model_export_name = teaser_prj.name
        dir_model_package = Path(prj_export_path, "Model", model_export_name, "package.mo")
        sim_results_path = Path(prj_export_path / "SimResults" / model_export_name)
        packages = [
            dir_model_package,
            path_aixlib
        ]

        simulation_setup = {"start_time": 0,
                            "stop_time": 3.1536e+07,
                            "output_interval": 3600,
                            "solver": "Cvode",
                            "tolerance": 0.001}
        n_success = 0

        print(f"Starting simulation for model {model_export_name}.")

        sim_model = \
            model_export_name + '.' + bldg.name + '.' + bldg.name
        bldg_result_dir = sim_results_path / bldg.name
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
            savepath=str(sim_results_path / bldg.name),
            result_file_name="teaser_results"
        )


        mos_file_path = edit_mat_result_file(teaser_prj, bldg.name, bldg_result_dir)
        dym_api.dymola.RunScript(mos_file_path)
        time.sleep(10)

        dym_api.close()

        print(f"Successfully simulated building")
        print(f"You can find the results under {str(sim_results_path)}")




if __name__ == "__main__":
    load_serialized_teaser_project()

