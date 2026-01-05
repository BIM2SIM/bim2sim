import os
from pathlib import Path

from bim2sim.plugins.PluginTEASER.bim2sim_teaser.examples.e3_complex_project_teaser_ma_jho import \
	run_example_complex_building_teaser
from bim2sim.plugins.PluginHydraulicSystem.bim2sim_hydraulicsystem.examples.e1_project_hydraulic_system_ma_jho import \
	run_example_project_hydraulic_system
from bim2sim.plugins.PluginVentilationSystem.bim2sim_ventilationsystem.examples.e1_create_ventilation_system_ma_jho import \
	run_example_project_ventilation_system

project_path = r"D:\dja-jho\Testing\SystemTest"

heating_bool = True
cooling_bool = True
ahu_bool = True

building_standard = "kfw_40"
window_standard = "Waermeschutzverglasung, dreifach"

heat_delivery_type = "UFH"  # UFH or Radiator

t_forward = 40
t_backward = 30

config_path = Path(project_path, 'config.toml')
if os.path.exists(config_path):
	os.remove(config_path)

run_example_complex_building_teaser(project_path=project_path,
                                    heating_bool=heating_bool,
                                    cooling_bool=cooling_bool,
                                    ahu_bool=ahu_bool,
                                    building_standard=building_standard,
                                    window_standard=window_standard
                                    )

if os.path.exists(config_path):
	os.remove(config_path)

run_example_project_hydraulic_system(project_path=project_path,
                                     heat_delivery_type=heat_delivery_type,
                                     t_forward=t_forward,
                                     t_backward=t_backward)

if os.path.exists(config_path):
	os.remove(config_path)

run_example_project_ventilation_system(project_path=project_path)
