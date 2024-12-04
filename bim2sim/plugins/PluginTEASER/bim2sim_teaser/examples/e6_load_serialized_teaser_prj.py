from pathlib import Path
import ast

import teaser
from teaser.project import Project
from teaser.logic.buildingobjects.thermalzone import ThermalZone
from teaser.logic.buildingobjects.building import Building
from teaser.logic.buildingobjects.buildingphysics.outerwall import OuterWall
from teaser.logic.buildingobjects.buildingphysics.innerwall import InnerWall
from teaser.logic.buildingobjects.buildingphysics.groundfloor import GroundFloor
from teaser.logic.buildingobjects.buildingphysics.window import Window
from teaser.logic.buildingobjects.buildingphysics.rooftop import Rooftop

from teaser.data.dataclass import DataClass
from teaser.data.utilities import ConstructionData

from bim2sim.tasks.bps import EnrichMaterial
from bim2sim_teaser.task import CreateTEASER
from e5_serialize_teaser_prj import run_serialize_teaser_project_example

import bim2sim
from bim2sim.kernel.log import default_logging_setup
from bim2sim.tasks import common, bps
from bim2sim.utilities.common_functions import download_library
from bim2sim.utilities.types import IFCDomain, LOD, ZoningCriteria
from bim2sim.utilities.common_functions import get_type_building_elements
from bim2sim.plugins.PluginTEASER.bim2sim_teaser import PluginTEASER, \
    LoadLibrariesTEASER
import bim2sim.plugins.PluginTEASER.bim2sim_teaser.task as teaser_task


def load_serialized_teaser_project():
    """This function demonstrates different loading options of TEASER"""
    project_path = Path("D:\dja-jho\Testing\Test")
    prj_export_path = Path(project_path, "export")
    prj_json_path = Path(prj_export_path, "TEASER/serialized_teaser/AC20-Institute-Var-2.json")

    prj = Project()
    prj.load_project(path=prj_json_path)

    prj.data = DataClass(construction_data=ConstructionData.kfw_40)

 
    # use cooling
    cooling = False
    setpoints_from_template = True

    overwrite_ahu_by_settings = True
    ahu_heating = True
    ahu_cooling = True
    ahu_heat_recovery = True
    ahu_heat_recovery_efficiency = 0.8

    # overwrite existing layer structures and materials based on templates
    layers_and_materials = LOD.low
    # specify templates for the layer and material overwrite
    construction_class_walls = 'kfw_40'
    construction_class_windows = 'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach'
    construction_class_doors = 'kfw_40'

    year_of_construction = 2015

    # set weather file data
    weather_file_path = fr"D:\dja-jho\Git\Dissertation_coding\outer_optimization\clustering\DEU_NW_Aachen.105010_TMYx.mos"


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
    prj_custom_usages = (Path(
        bim2sim.__file__).parent.parent /
                                              "test/resources/arch/custom_usages/"
                                              "customUsagesAC20-Institute-Var-2_with_SB-1-0.json")

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


            for outer_wall in tz.outer_walls:
                outer_wall.load_type_element(year=bldg.year_of_construction,
                                             construction=construction_class_walls)
            for inner_wall in tz.inner_walls:
                inner_wall.load_type_element(year=bldg.year_of_construction,
                                             construction=construction_class_walls)
            for rooftop in tz.rooftops:
                rooftop.load_type_element(year=bldg.year_of_construction,
                                          construction=construction_class_walls)
            for ground_floor in tz.ground_floors:
                ground_floor.load_type_element(year=bldg.year_of_construction,
                                               construction=construction_class_walls)
            for window in tz.windows:
                window.load_type_element(year=bldg.year_of_construction,
                                         construction=construction_class_windows)
            for door in tz.doors:
                door.load_type_element(year=bldg.year_of_construction,
                                       construction=construction_class_doors)



    # calculate all buildings, this is needed as model_attr and library_attr
    # are not saved via json export.
    prj.calc_all_buildings()

    # As calc_all_buildings() recalculates the heating loads and thus the max
    # ideal heater PI-control values, we might reset those as they can be too
    # low and lead to too low zone temperatures
    orig_heat_loads, orig_cool_loads = CreateTEASER.overwrite_heatloads(prj.buildings)

    prj.export_aixlib(
        path=prj_export_path,
        use_postprocessing_calc=True,
        report=True
    )


if __name__ == "__main__":
    load_serialized_teaser_project()

