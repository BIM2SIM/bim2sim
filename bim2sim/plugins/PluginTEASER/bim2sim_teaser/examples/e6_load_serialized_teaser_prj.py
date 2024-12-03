from pathlib import Path
from teaser.project import Project

from bim2sim_teaser.task import CreateTEASER
from e5_serialize_teaser_prj import run_serialize_teaser_project_example


def load_serialized_teaser_project():
    """This function demonstrates different loading options of TEASER"""

    # In example e4_save we saved two TEASER projects using `*.teaserjson` and
    # Python package pickle. This example shows how to import these
    # information into your python environment again.

    prj_export_path, prj_json_path = run_serialize_teaser_project_example()
    prj = Project()

    prj.load_project(path=prj_json_path)
    export_vars = {
        "HeatingDemands": ["*multizone.PHeater*", "*multizone.PHeatAHU"],
        "CoolingDemands": ["*multizone.PCooler*", "*multizone.PCoolAHU"],
        "Temperatures": ["*multizone.TAir*", "*multizone.TRad*"]
    }

    # Do some work on the model, e.g. increase total window area of each
    # thermal zone by 10 %
    window_increase_percentage = 0.1
    for bldg in prj.buildings:
        for tz in bldg.thermal_zones:
            ow_area_old = 0
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
                  f"{tz.name} is {round(win_ratio_res*100,2 )} %.")
    # calculate all buildings, this is needed as model_attr and library_attr
    # are not saved via json export.
    prj.calc_all_buildings()

    # As calc_all_buildings() recalculates the heating loads and thus the max
    # ideal heater PI-control values, we might reset those as they can be too
    # low and lead to too low zone temperatures
    orig_heat_loads, orig_cool_loads = CreateTEASER.overwrite_heatloads(
        prj.buildings)

    prj.export_aixlib(
        path=prj_export_path,
        use_postprocessing_calc=True,
        report=True,
        export_vars=export_vars
    )


if __name__ == "__main__":
    load_serialized_teaser_project()

