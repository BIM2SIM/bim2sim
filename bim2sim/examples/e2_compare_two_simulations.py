import tempfile
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image
from RWTHColors import ColorManager
import pandas as pd
import matplotlib.dates as mdates
from matplotlib import pyplot as plt

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.elements.mapping.units import ureg
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.common_functions import download_test_resources
from bim2sim.utilities.types import IFCDomain, LOD, ZoningCriteria
import bim2sim.plugins.PluginTEASER.bim2sim_teaser.task as teaser_task
from bim2sim.tasks import bps, common


cm = ColorManager()
plt.style.use(['science', 'grid', 'rwth'])
plt.style.use(['science', 'no-latex'])
plt.rcParams.update({'font.size': 14})


def run_ep_simulation():
    default_logging_setup()

    project_path = Path("D:/01_Kurzablage/compare_EP_TEASER_DH/ep_project")

    # download additional test resources for arch domain, you might want to set
    # force_new to True to update your test resources
    download_test_resources(IFCDomain.arch, force_new=False)
    # Set the ifc path to use and define which domain the IFC belongs to
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/FM_ARC_DigitalHub_with_SB89.ifc',
    }

    # Create a project including the folder structure for the project with
    # energyplus as backend
    project = Project.create(project_path, ifc_paths, 'energyplus')
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.epw')
    # Set the install path to your EnergyPlus installation according to your
    # system requirements
    project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'

    # run annual simulation for EnergyPlus
    project.sim_settings.run_full_simulation = True
    project.sim_settings.split_bounds = False
    project.sim_settings.add_shadings = False
    project.sim_settings.split_shadings = False

    project.sim_settings.setpoints_from_template = True
    project.sim_settings.cooling = True

    # overwrite existing layer structures and materials based on templates
    project.sim_settings.layers_and_materials = LOD.low
    # specify templates for the layer and material overwrite

    project.sim_settings.construction_class_walls = 'heavy'
    project.sim_settings.construction_class_windows = \
        'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach'

    project.sim_settings.prj_use_conditions = (Path(
        bim2sim.__file__).parent.parent /
           "test/resources/arch/custom_usages/"
           "UseConditionsFM_ARC_DigitalHub_with_SB89.json")
    project.sim_settings.prj_custom_usages = (Path(
        bim2sim.__file__).parent.parent /
            "test/resources/arch/custom_usages/"
            "customUsagesFM_ARC_DigitalHub_with_SB89.json")
    # Select results to output:
    # TODO dataframe only holds global results but not room based
    project.sim_settings.output_keys = ['output_outdoor_conditions',
                                        'output_zone_temperature',
                                        'output_zone', 'output_infiltration',
                                        'output_meters',
                                        'output_internal_gains']

    space_boundary_genenerator = 'Other'
    handle_proxies = (*(None,) * 12,)
    construction_year = 2015
    answers = (space_boundary_genenerator,
               *handle_proxies,
               construction_year)
    handler = DebugDecisionHandler(answers)
    handler.handle(project.run())

    run_project(project, ConsoleDecisionHandler())
    # Have a look at the elements/elements that were created
    elements = project.playground.state['elements']
    # filter the elements only for outer walls
    df_finals = project.playground.state['df_finals']
    return df_finals


def run_teaser_simulation():
    default_logging_setup()

    project_path = Path("D:/01_Kurzablage/compare_EP_TEASER_DH/teaser_project_zoning_full")

    download_test_resources(IFCDomain.arch, force_new=False)
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/FM_ARC_DigitalHub_with_SB89.ifc',
    }

    # Create a project including the folder structure for the project with
    # teaser as backend and no specified workflow (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'teaser')

    # specify simulation settings (please have a look at the documentation of
    # all under concepts/sim_settings
    # combine spaces to thermal zones based on their usage
    project.sim_settings.zoning_setup = LOD.full
    project.sim_settings.zoning_criteria = ZoningCriteria.usage
    # use cooling

    project.sim_settings.setpoints_from_template = True
    project.sim_settings.cooling = True
    # overwrite existing layer structures and materials based on templates
    project.sim_settings.layers_and_materials = LOD.low
    # specify templates for the layer and material overwrite
    project.sim_settings.construction_class_walls = 'heavy'
    project.sim_settings.construction_class_windows = \
        'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach'

    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')
    # Run a simulation directly with dymola after model creation
    project.sim_settings.dymola_simulation = True
    # Select results to output:
    project.sim_settings.sim_results = [
        "heat_demand_total", "cool_demand_total",
        "heat_demand_rooms", "cool_demand_rooms",
        "heat_energy_total", "cool_energy_total",
        "heat_energy_rooms", "cool_energy_rooms",
        "operative_temp_rooms", "air_temp_rooms", "air_temp_out",
        "internal_gains_machines_rooms", "internal_gains_persons_rooms",
        "internal_gains_lights_rooms",
        # "n_persons_rooms",
        "infiltration_rooms",
        # "mech_ventilation_rooms",
        "heat_set_rooms",
        "cool_set_rooms"
    ]
    project.sim_settings.prj_use_conditions = (Path(
        bim2sim.__file__).parent.parent /
            "test/resources/arch/custom_usages/"
            "UseConditionsFM_ARC_DigitalHub_with_SB89.json")
    project.sim_settings.prj_custom_usages = (Path(
        bim2sim.__file__).parent.parent /
            "test/resources/arch/custom_usages/"
            "customUsagesFM_ARC_DigitalHub_with_SB89.json")
    # Run the project with the ConsoleDecisionHandler. This allows interactive
    space_boundary_genenerator = 'Other'
    handle_proxies = (*(None,) * 12,)
    construction_year = 2015
    answers = (space_boundary_genenerator,
               *handle_proxies,
               construction_year)
    handler = DebugDecisionHandler(answers)
    handler.handle(project.run())

    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, ConsoleDecisionHandler())
    # Have a look at the elements/elements that were created
    elements = project.playground.state['elements']
    # filter the elements only for outer walls
    df_finals = project.playground.state['df_finals']
    return df_finals


def load_teaser_simulation():
    default_logging_setup()
    project_path = Path(
        "D:/01_Kurzablage/compare_EP_TEASER_DH/teaser_project_zoning_full")
    project = Project.create(project_path, plugin='teaser')
    # TODO those 2 are not used but are needed currently as otherwise the
    #  plotting tasks will be executed and weather file is mandatory
    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')
    # Run a simulation directly with dymola after model creation
    project.sim_settings.dymola_simulation = True
    project.sim_settings.sim_results = [
        "heat_demand_total", "cool_demand_total",
        "heat_demand_rooms", "cool_demand_rooms",
        "heat_energy_total", "cool_energy_total",
        "heat_energy_rooms", "cool_energy_rooms",
        "operative_temp_rooms", "air_temp_rooms", "air_temp_out",
        "internal_gains_machines_rooms", "internal_gains_persons_rooms",
        "internal_gains_lights_rooms",
        # "n_persons_rooms",
        "infiltration_rooms",
        # "mech_ventilation_rooms",
        "heat_set_rooms",
        "cool_set_rooms"
    ]
    project.plugin_cls.default_tasks = [
        common.LoadIFC,
        common.DeserializeElements,
        teaser_task.LoadModelicaResults,
        teaser_task.CreateResultDF,
        bps.PlotBEPSResults,
    ]
    space_boundary_genenerator = 'Other'
    handle_proxies = (*(None,) * 12,)
    construction_year = 2015
    answers = (space_boundary_genenerator, space_boundary_genenerator
        )
    handler = DebugDecisionHandler(answers)
    handler.handle(project.run())
    df_finals = project.playground.state['df_finals']
    return df_finals

def plot_demands(ep_results: pd.DataFrame, teaser_results: pd.DataFrame,
                 demand_type: str,
                 save_path: Optional[Path] = None,
                 logo: bool = True, total_label: bool = True,
                 window: int = 12, fig_size: Tuple[int, int] = (10, 6),
                 dpi: int = 300) -> None:
    """
    Plot demands based on provided data.

    Args:
        df (pd.DataFrame): The DataFrame containing the data.
        demand_type (str): The type of demand.
        save_path (Optional[Path], optional): The path to save the plot as
         a PDF. Defaults to None, in which case the plot will be displayed
         but not saved.
        logo (bool, optional): Whether to include a logo. Defaults to True.
        total_label (bool, optional): Whether to include total energy
         label.
         Defaults to True.
        window (int, optional): window for rolling mean value to plot
        fig_size (Tuple[int, int], optional): The size of the figure in
         inches (width, height). Defaults to (10, 6).
        dpi (int, optional): Dots per inch (resolution). Defaults to 300.

    Raises:
        ValueError: If demand_type is not supported.

    Returns:
        None

    Note:
        - The plot is styled using the 'science', 'grid', and 'rwth' styles.
        - The figure is adjusted with specified spaces around the plot.
        - The y-axis unit and rolling are adjusted for better visibility.
        - The y-axis label is determined based on demand type and converted
          to kilowatts if necessary.
        - The plot is created with appropriate colors and styles.
        - Limits, labels, titles, and grid are set for the plot.
        - Font sizes and other settings are adjusted.
        - The total energy label can be displayed in the upper right corner.
        - The logo can be added to the plot.

    Example:
        Example usage of the method.

        plot_demands(df=my_dataframe, demand_type="Cooling",
                     save_path=Path("my_plot.pdf"), logo=True,
                     total_label=True, fig_size=(12, 8), dpi=300)
    """
    if demand_type == "Heating":
        # Create a new variable for y-axis with converted unit and rolling
        # Smooth the data for better visibility
        y_values_teaser = teaser_results["heat_demand_total"]
        y_values_ep = ep_results["heat_demand_total"]
        total_energy_col = "heat_energy_total"
        colors = [cm.RWTHViolett.p(100), cm.RWTHRot.p(100)]
    elif demand_type == "Cooling":
        # Create a new variable for y-axis with converted unit and rolling
        y_values_teaser = teaser_results["cool_demand_total"]
        y_values_ep = ep_results["cool_demand_total"]
        total_energy_col = "cool_energy_total"
        colors = [cm.RWTHTuerkis.p(100), cm.RWTHBlau.p(100)]
    else:
        raise ValueError(f"Demand type {demand_type} is not supported.")

    total_energy_teaser = teaser_results[total_energy_col].sum()
    total_energy_ep = ep_results[total_energy_col].sum()
    label_pad = 5
    # Create a new figure with specified size
    fig = plt.figure(figsize=fig_size, dpi=dpi)

    # Define spaces next to the real plot with absolute values
    fig.subplots_adjust(left=0.05, right=0.95, top=1.0, bottom=0.0)

    # Determine if y-axis needs to be in kilowatts
    for i, y_values in enumerate([y_values_ep, y_values_teaser]):
        if y_values.pint.magnitude.max() > 5000:
            y_values = y_values.pint.to(ureg.kilowatt)

        plt.ylabel(
            f"{demand_type} Demand / {format(y_values.pint.units, '~')}",
            labelpad=label_pad)
        # Smooth the data for better visibility
        y_values = y_values.rolling(window=window).mean()
        # Plotting the data
        # EnergyPlus
        if i == 0:
            y_total = format(round(total_energy_ep.to(ureg.kilowatt_hour), 2),
                             '~')
            plt.plot(y_values.index,
                     y_values, color=colors[i],
                     linewidth=1, linestyle='-',
                     label=f'EnergyPlus Total energy: {y_total}')
        # TEASER
        else:
            y_total = format(round(total_energy_teaser.to(ureg.kilowatt_hour), 2),
                             '~')
            plt.plot(y_values.index,
                     y_values, color=colors[i],
                     linewidth=1, linestyle='-',
                     label=f'TEASER Total energy: {y_total}')
    plt.legend(frameon=True, facecolor='white')
    # Set x-axis ticks for the first day of each month
    first_day_of_months = (y_values.index.to_period('M').unique().
                           to_timestamp())
    plt.xticks(first_day_of_months.strftime('%Y-%m-%d'),
               [month.strftime('%b') for month in first_day_of_months])

    # Rotate the tick labels for better visibility
    plt.gcf().autofmt_xdate(rotation=45)
    # TODO y_values adjust to both result dfs
    # Limits
    plt.xlim(0, y_values.index[-1])
    plt.ylim(0, y_values.max() * 1.1)
    # Adding x label
    plt.xlabel("Time", labelpad=label_pad)
    # Add title
    plt.title(f"{demand_type} Demand", pad=20)
    # Add grid
    plt.grid(True, linestyle='--', alpha=0.6)

    # Adjust further settings
    plt.gca().spines['top'].set_visible(False)
    plt.gca().spines['right'].set_visible(False)
    # Show or save the plot
    if save_path:
        plt.ioff()
        plt.savefig(save_path, dpi=dpi, format="pdf")
    else:
        plt.show()


def plot_time_series_results(
        ep_results: pd.DataFrame,
        teaser_results: pd.DataFrame,
        data_type: str, room_guid: str,
        save_path: Optional[Path] = None,
        first_week: bool = False,
        window: int = 12, fig_size: Tuple[int, int] = (10, 6),
        dpi: int = 300) -> None:
    # if data_type == "t_set_heat":
    #     y_values_teaser = teaser_results[f"heat_set_rooms_{room_guid}"]
    #     # TODO add when EP is implemented
    #     # y_values_ep = teaser_results[f"heat_set_rooms_{room_guid}"]
    #     y_values_ep = ep_results[f"heat_set_rooms_{room_guid}"]
    try:
        teaser_results.index = teaser_results.index.strftime('%m/%d-%H:%M:%S')
    except:
        pass
    try:
        y_values_teaser = teaser_results[data_type + '_' + room_guid]
    except Exception as E:
        raise ValueError(f"data_type {data_type} not found in results for "
                         f"TEASER")
    try:
        y_values_ep = ep_results[data_type + '_' + room_guid]
    except Exception as E:
        raise ValueError(f"data_type {data_type + '_' + room_guid} not found "
                         f"in results for EnergyPlus")
    if "heat" in data_type:
        colors = [cm.RWTHViolett.p(100), cm.RWTHRot.p(100)]
    elif "cool" in data_type:
        colors = [cm.RWTHTuerkis.p(100), cm.RWTHBlau.p(100)]
    else:
        colors = [cm.RWTHViolett.p(100), cm.RWTHRot.p(100)]
#     elif data_type == "t_set_cool":
#         # Create a new variable for y-axis with converted unit and rolling
#         y_values_teaser = teaser_results[f"cool_set_rooms_{room_guid}"]
#         # y_values_ep = teaser_results[f"cool_set_rooms_{room_guid}"]
#         # TODO add when EP is implemented
#         y_values_ep = ep_results[f"cool_set_rooms_{room_guid}"]
#         colors = [cm.RWTHTuerkis.p(100), cm.RWTHBlau.p(100)]
#     else:
#         raise ValueError(f"Demand type {data_type} is not supported.")

    label_pad = 5
    # Create a new figure with specified size
    fig = plt.figure(figsize=fig_size, dpi=dpi)

    # Define spaces next to the real plot with absolute values
    fig.subplots_adjust(left=0.05, right=0.95, top=1.0, bottom=0.0)

    # Determine if y-axis needs to be in kilowatts
    y_lim_min = None
    y_lim_max = None
    for i, y_values in enumerate([y_values_ep, y_values_teaser]):

        if any(i in data_type for i in ["set", "temp"]):
            y_values = y_values.pint.to(ureg.degree_Celsius)
        if any(i in data_type for i in ["demand", 'internal_gains']):
            if y_values.pint.magnitude.max() > 5000:
                y_values = y_values.pint.to(ureg.kilowatt)
            else:
                y_values = y_values.pint.to(ureg.watt)
        plt.ylabel(
            f"{data_type} / {format(y_values.pint.units, '~')}",
            labelpad=label_pad)
        # Smooth the data for better visibili
        y_values = y_values.rolling(window=window).mean()
        # Plotting the data
        # EnergyPlus
        if i == 0:
            pass
            plt.plot(y_values.index,
                     y_values, color=colors[i],
                     linewidth=1, linestyle='-',
                     label=f'EnergyPlus')
        # TEASER
        else:
            plt.plot(y_values.index,
                     y_values, color=colors[i],
                     linewidth=1, linestyle='-',
                     label=f'TEASER')
        # set y limits
        if y_lim_min:
            y_lim_min = min(y_lim_min, y_values.min())
        else:
            y_lim_min = y_values.max()
        if y_lim_max:
            y_lim_max = max(y_lim_max, y_values.max())
        else:
            y_lim_max = y_values.max()
    plt.ylim(y_lim_min*0.9, y_lim_max*1.1)
    plt.legend(frameon=True, facecolor='white')
    plt.xticks(
        teaser_results.index,
        teaser_results.index.str[0:2] + '-' + teaser_results.index.str[3:5],
        rotation=45)
    # TODO y_values adjust to both result dfs
    # Limits
    if first_week:
        plt.xlim(0, y_values.index[168])
    else:
        plt.xlim(0, y_values.index[-1])
    # Add grid
    plt.grid(True, linestyle='--', alpha=0.6)

    # Adjust further settings
    plt.gca().spines['top'].set_visible(False)
    plt.gca().spines['right'].set_visible(False)
    plt.gca().xaxis.set_major_locator(plt.MaxNLocator(prune='both'))
    plt.gca().yaxis.set_major_locator(plt.MaxNLocator(prune='both'))
    # Show or save the plot
    if save_path:
        filename = data_type + '_' + room_guid + '.pdf'
        save_path = save_path / filename
        plt.ioff()
        plt.savefig(save_path, dpi=dpi, format="pdf")
    else:
        plt.show()


if __name__ == "__main__":
    simulate_EP = True
    simulate_TEASER = False
    load_TEASER = True
    base_path = Path(
            "D:/01_Kurzablage/compare_EP_TEASER_DH/")

    if simulate_TEASER:
        teaser_results = run_teaser_simulation()["Building"]
        teaser_results.name = 'TEASER'
        teaser_results.to_pickle(
            base_path / "teaser_results")
    elif load_TEASER:
        teaser_results = load_teaser_simulation()["Building"]
        teaser_results.name = 'TEASER'
        teaser_results.to_pickle(
            base_path / "teaser_results")
    else:
        teaser_results = pd.read_pickle(base_path/'teaser_results')
    if simulate_EP:
        ep_results = run_ep_simulation()["FM_ARC_DigitalHub_with_SB89"]
        ep_results.name = 'EnergyPlus'
        ep_results.to_pickle(
            base_path / "ep_results")
    else:
        ep_results = pd.read_pickle(base_path / 'ep_results')
    # plot_demands(ep_results, teaser_results, demand_type='Heating',
    #              save_path=Path(
    #                  "D:/01_Kurzablage/compare_EP_TEASER_DH/heating.pdf"),
    #              )
    # plot_demands(ep_results, teaser_results, demand_type='Cooling',
    #              save_path=Path(
    #                  "D:/01_Kurzablage/compare_EP_TEASER_DH/cooling.pdf"),
    #              )
    # plot_time_series_results(
    #     ep_results, teaser_results,data_type='heat_demand_rooms',
    #     room_guid='1$3U$o1ZbAmgqaIrn6$oDh', first_week=False, window=1,
    #     save_path=Path("D:/01_Kurzablage/compare_EP_TEASER_DH/")
    #     )
    # plot_time_series_results(
    #     ep_results, teaser_results,data_type='heat_demand_rooms',
    #     room_guid='1Pa4Dm1xXFOuQ42mT39OUf', first_week=False, window=1,
    #     save_path=Path("D:/01_Kurzablage/compare_EP_TEASER_DH/")
    #     )
    # plot_time_series_results(
    #     ep_results, teaser_results,data_type='heat_demand_rooms',
    #     room_guid='3FbynaDAnDlvm_UyBTNi42', first_week=False, window=1,
    #     save_path=Path("D:/01_Kurzablage/compare_EP_TEASER_DH/")
    #     )
    # plot_time_series_results(
    #     ep_results, teaser_results,data_type='infiltration_rooms',
    #     room_guid='1$3U$o1ZbAmgqaIrn6$oDh', first_week=False, window=1,
    #     save_path=Path("D:/01_Kurzablage/compare_EP_TEASER_DH/")
    #     )
    # plot_time_series_results(
    #     ep_results, teaser_results,data_type='infiltration_rooms',
    #     room_guid='1Pa4Dm1xXFOuQ42mT39OUf', first_week=False, window=1,
    #     save_path=Path("D:/01_Kurzablage/compare_EP_TEASER_DH/")
    #     )
    # plot_time_series_results(
    #     ep_results, teaser_results,data_type='infiltration_rooms',
    #     room_guid='3FbynaDAnDlvm_UyBTNi42', first_week=False, window=1,
    #     save_path=Path("D:/01_Kurzablage/compare_EP_TEASER_DH/")
    #     )

    # plot_time_series_results(
    #     ep_results, teaser_results,data_type='heat_set_rooms',
    #     room_guid='3FbynaDAnDlvm_UyBTNi42', first_week=True, window=1,
    #     save_path=Path("D:/01_Kurzablage/compare_EP_TEASER_DH/")
    #     )
    # plot_time_series_results(
    #     ep_results, teaser_results,data_type='cool_set_rooms',
    #     room_guid='3FbynaDAnDlvm_UyBTNi42', first_week=True, window=1,
    #     save_path=Path("D:/01_Kurzablage/compare_EP_TEASER_DH/")
    #     )
    # plot_time_series_results(
    #     ep_results, teaser_results,data_type='air_temp_rooms',
    #     room_guid='3FbynaDAnDlvm_UyBTNi42', first_week=True, window=1,
    #     save_path=Path("D:/01_Kurzablage/compare_EP_TEASER_DH/")
    #     )
    # plot_time_series_results(
    #     ep_results, teaser_results,data_type='heat_demand_rooms',
    #     room_guid='3FbynaDAnDlvm_UyBTNi42', first_week=True, window=1,
    #     save_path=Path("D:/01_Kurzablage/compare_EP_TEASER_DH/")
    #     )
    #
    # plot_time_series_results(
    #     ep_results, teaser_results,data_type='cool_demand_rooms',
    #     room_guid='3FbynaDAnDlvm_UyBTNi42', first_week=True, window=1,
    #     save_path=Path("D:/01_Kurzablage/compare_EP_TEASER_DH/")
    #     )
    # plot_time_series_results(
    #     ep_results, teaser_results,data_type='internal_gains_machines_rooms',
    #     room_guid='3FbynaDAnDlvm_UyBTNi42', first_week=True, window=1,
    #     save_path=Path("D:/01_Kurzablage/compare_EP_TEASER_DH/")
    #     )
    # plot_time_series_results(
    #     ep_results, teaser_results,data_type='internal_gains_persons_rooms',
    #     room_guid='3FbynaDAnDlvm_UyBTNi42', first_week=True, window=1,
    #     save_path=Path("D:/01_Kurzablage/compare_EP_TEASER_DH/")
    #     )
    # plot_time_series_results(
    #     ep_results, teaser_results,data_type='internal_gains_lights_rooms',
    #     room_guid='3FbynaDAnDlvm_UyBTNi42', first_week=True, window=1,
    #     save_path=Path("D:/01_Kurzablage/compare_EP_TEASER_DH/")
    #     )
