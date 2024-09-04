from typing import Optional, Tuple, List

from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, to_hex
from pathlib import Path
from PIL import Image
from RWTHColors import ColorManager
import pandas as pd
# scienceplots is marked as not used but is mandatory
import scienceplots
from matplotlib.dates import DateFormatter

from bim2sim.kernel.ifc_file import IfcFileClass
from bim2sim.tasks.base import ITask
from bim2sim.elements.mapping.units import ureg
from bim2sim.elements.base_elements import SerializedElement
from bim2sim.utilities.svg_utils import create_svg_floor_plan_plot

cm = ColorManager()
plt.style.use(['science', 'grid', 'rwth'])
plt.style.use(['science', 'no-latex'])
plt.rcParams.update({'font.size': 20})
plt.rcParams['legend.frameon'] = True
plt.rcParams['legend.facecolor'] = 'white'
plt.rcParams['legend.framealpha'] = 0.5
plt.rcParams['legend.edgecolor'] = 'black'


class PlotBEPSResults(ITask):
    """Class for plotting results of BEPS.

    This class provides methods to create various plots including time series
    and bar charts for energy consumption and temperatures.
    """

    reads = ('df_finals', 'sim_results_path', 'ifc_files', 'elements')
    final = True

    def run(self, df_finals: dict, sim_results_path: Path,
            ifc_files: List[Path], elements: dict) -> None:
        """
        Run the plotting process for BEPS results.

        Args:
            df_finals (dict): Dictionary of DataFrames containing final
             simulation results.
            sim_results_path (Path): Path to save simulation results.
            ifc_files (List[Path]): List of IFC file paths.
            elements (dict): Dictionary of building elements.
        """
        if not self.playground.sim_settings.create_plots:
            self.logger.warning("Skipping task PlotBEPSResults as sim_setting "
                                "'create_plots' is set to False.")
            return

        plugin_name = self.playground.project.plugin_cls.name
        if (plugin_name == 'TEASER' and not
            self.playground.sim_settings.dymola_simulation):
            self.logger.warning("Skipping task CreateResultDF as sim_setting"
                                " 'dymola_simulation' is set to False and no"
                                " simulation was performed.")
            return

        for bldg_name, df in df_finals.items():
            plot_path = sim_results_path / bldg_name / "plots"
            plot_path.mkdir(exist_ok=True)
            for ifc_file in ifc_files:
                self.plot_floor_plan_with_results(
                    df, elements, 'heat_demand_rooms',
                    ifc_file, plot_path, area_specific=True)
            self.plot_total_consumption(df, plot_path)
            if (any(df.filter(like='surf_inside_temp')) and
                    self.playground.sim_settings.plot_singe_zone_guid):
                self.plot_multiple_temperatures(df.filter(
                    like='surf_inside_temp'), plot_path,logo=False)


    def plot_total_consumption(
            self, df: pd.DataFrame, plot_path: Path) -> None:
        """
        Plot total consumption for heating and cooling.

        Args:
            df (pd.DataFrame): DataFrame containing consumption data.
            plot_path (Path): Path to save the plots.
        """
        self.plot_demands_time_series(df, ["Heating"], plot_path, logo=False,
                                      title=None)
        self.plot_demands_time_series(df, ["Cooling"], plot_path, logo=False,
                                      title=None)
        self.plot_demands_time_series(df, ["Heating", "Cooling"], plot_path,
                                      window=24, logo=False)
        self.plot_temperatures(df, "air_temp_out", plot_path, logo=False)
        self.plot_demands_bar(df, plot_path, logo=False, title=None)

    @staticmethod
    def plot_demands_time_series(df: pd.DataFrame, demand_type: List[str],
                                 save_path: Optional[Path] = None,
                                 logo: bool = True, total_label: bool = True,
                                 window: int = 12,
                                 fig_size: Tuple[int, int] = (10, 6),
                                 dpi: int = 300, title: Optional[str] = None) -> None:
        """
        Plot time series of energy demands.

        Args:
            df (pd.DataFrame): DataFrame containing demand data.
            demand_type (List[str]): List of demand types to plot ("Heating" and/or "Cooling").
            save_path (Optional[Path]): Path to save the plot. If None, the plot will be displayed.
            logo (bool): Whether to add a logo to the plot.
            total_label (bool): Whether to add total energy labels to the legend.
            window (int): Window size for rolling mean calculation.
            fig_size (Tuple[int, int]): Figure size in inches.
            dpi (int): Dots per inch for the figure.
            title (Optional[str]): Title of the plot.
        """
        fig, ax = plt.subplots(figsize=fig_size, dpi=dpi)

        total_energies = {}
        colors = {'heating': cm.RWTHRot.p(100), 'cooling': cm.RWTHBlau.p(100)}

        for dt in demand_type:
            if dt.lower() == "heating":
                y_values = df["heat_demand_total"]
                total_energy_col = "heat_energy_total"
                label = "Heating"
            elif dt.lower() == "cooling":
                y_values = df["cool_demand_total"]
                total_energy_col = "cool_energy_total"
                label = "Cooling"
            else:
                raise ValueError(f"Demand type {dt} is not supported.")

            total_energy = df[total_energy_col].sum()
            total_energies[label] = total_energy

            if y_values.pint.magnitude.max() > 5000:
                y_values = y_values.pint.to(ureg.kilowatt)
            ax.set_ylabel(f"Demand / {format(y_values.pint.units, '~')}", labelpad=5)

            y_values = y_values.rolling(window=window).mean()
            ax.plot(y_values.index, y_values, color=colors[dt.lower()],
                    linewidth=1.5, linestyle='-', label=f"{label} Demand")

        first_day_of_months = (y_values.index.to_period('M').unique().
                               to_timestamp())
        ax.set_xticks(first_day_of_months)
        ax.set_xticklabels([month.strftime('%b')
                            for month in first_day_of_months])
        plt.gcf().autofmt_xdate(rotation=45)

        ax.set_xlim(y_values.index[0], y_values.index[-1])
        if title:
            ax.set_title(title, pad=20)
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        if total_label:
            legend_labels = [f"{label} Total energy: {format(round(total_energies[label].to(ureg.megawatt_hour), 2), '~')}" for label in total_energies]
            handles, labels = ax.get_legend_handles_labels()
            leg = ax.legend(handles, legend_labels + labels,
                            loc='upper right', framealpha=0.9,
                            facecolor='white', edgecolor='black')
            leg.get_frame().set_facecolor('white')
            leg.get_frame().set_alpha(0.9)
            leg.get_frame().set_edgecolor('black')

        if logo:
            raise Warning("Logo option is currently not supported")

        if save_path:
            save_path_demand = save_path / "demands_combined.pdf"
            PlotBEPSResults.save_or_show_plot(
                save_path_demand, dpi, format='pdf')
        else:
            plt.show()

    @staticmethod
    def plot_demands_bar(df: pd.DataFrame,
                         save_path: Optional[Path] = None,
                         logo: bool = True, total_label: bool = True,
                         fig_size: Tuple[int, int] = (10, 6),
                         dpi: int = 300, title: Optional[str] = None) -> None:
        """
        Plot monthly energy consumption as bar chart.

        Args:
            df (pd.DataFrame): DataFrame containing energy consumption data.
            save_path (Optional[Path]): Path to save the plot. If None, the
             plot will be displayed.
            logo (bool): Whether to add a logo to the plot.
            total_label (bool): Whether to add total energy labels to the
             legend.
            fig_size (Tuple[int, int]): Figure size in inches.
            dpi (int): Dots per inch for the figure.
            title (Optional[str]): Title of the plot.
        """
        save_path_monthly = save_path / "monthly_energy_consumption.pdf" if\
            save_path else None
        label_pad = 5
        df_copy = df.copy()
        df_copy.index = pd.to_datetime(df_copy.index, format='%m/%d-%H:%M:%S')

        df_copy['hourly_heat_energy'] = df_copy['heat_energy_total'].pint.to(
            ureg.kilowatthours)
        df_copy['hourly_cool_energy'] = df_copy['cool_energy_total'].pint.to(
            ureg.kilowatthours)

        monthly_sum_heat = df_copy['hourly_heat_energy'].groupby(
            df_copy.index.to_period('M')).sum()
        monthly_sum_cool = df_copy['hourly_cool_energy'].groupby(
            df_copy.index.to_period('M')).sum()

        monthly_labels = monthly_sum_heat.index.strftime('%b').tolist()
        monthly_sum_heat = [q.magnitude for q in monthly_sum_heat]
        monthly_sum_cool = [q.magnitude for q in monthly_sum_cool]

        fig, ax = plt.subplots(figsize=fig_size, dpi=dpi)

        bar_width = 0.4
        index = range(len(monthly_labels))

        ax.bar(index, monthly_sum_heat, color=cm.RWTHRot.p(100),
               width=bar_width, label='Heating')
        ax.bar([p + bar_width for p in index], monthly_sum_cool,
               color=cm.RWTHBlau.p(100), width=bar_width, label='Cooling')

        ax.set_ylabel(f"Energy Consumption / "
                      f"{format(df_copy['hourly_cool_energy'].pint.units,'~')}"
                      f"", labelpad=label_pad)
        if title:
            ax.set_title(title, pad=20)
        ax.set_xticks([p + bar_width / 2 for p in index])
        ax.set_xticklabels(monthly_labels, rotation=45)

        ax.grid(True, linestyle='--', alpha=0.6)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        ax.legend(frameon=True, loc='upper right', edgecolor='black')

        if logo:
            logo_pos = [fig_size[0] * dpi * 0.005, fig_size[1] * 0.95 * dpi]
            PlotBEPSResults.add_logo(dpi, fig_size, logo_pos)

        PlotBEPSResults.save_or_show_plot(save_path_monthly, dpi, format='pdf')

    @staticmethod
    def save_or_show_plot(save_path: Optional[Path], dpi: int,
                          format: str = 'pdf') -> None:
        """
        Save or show the plot depending on whether a save path is provided.

        Args:
            save_path (Optional[Path]): Path to save the plot. If None, the
             plot will be displayed.
            dpi (int): Dots per inch for the saved figure.
            format (str): Format to save the figure in.
        """
        if save_path:
            plt.ioff()
            plt.savefig(save_path, dpi=dpi, format=format)
        else:
            plt.show()

    def plot_floor_plan_with_results(
            self, df: pd.DataFrame,
            elements,
            result_str,
            ifc_file: IfcFileClass,
            plot_path: Path,
            min_space_area: float = 2,
            area_specific: bool = True
    ):
        """Plot a floor plan colorized based on specific heat demand.

        The plot colors each room based on the specific heat demand, while blue
        is the color for minimum heat demand and red for maximum.

        Args:
            df (DataFrame): The DataFrame containing sim result data.
            elements (dict[guid: element]): dict hat holds bim2sim elements
            result_str (str): one of sim_results settings that should be
             plotted. Currently, always max() of this is plotted.
            ifc_file (IfcFileClass): bim2sim IfcFileClass object.
            plot_path (Path): Path to store simulation results.
            min_space_area (float): minimal area in m² of a space that should
             be taken into account for the result calculation in the plot.
            area_specific (bool): True if result_str values should be divided
             by area to get valuer per square meter.

        TODO: this is currently not working for aggregated zones.
        Combined zones, how to proceed:
            - All rooms in the combined zone are given the same color and
                the same value
            - Rooms need names in the plot
            - Legend in the margin showing which room name belongs to which
                zone


            Generally revise:
            - Unit in the color mapping plot and in the plot for numerical
                values
        """
        # check if result_str is valid for floor plan visualization
        if result_str not in self.playground.sim_settings.sim_results:
            raise ValueError(f'Result {result_str} was not requested by '
                             f'sim_setting "sim_results" or is not provided'
                             f'by the simulation. '
                             f'Please Check your "sim_results" settings.')
        if "_rooms" not in result_str:
            raise ValueError(f'Result {result_str} does not provide room level'
                             f'information. Floor plan visualization is  only '
                             f'available for room level results.')
        # create the dict with all space guids and resulting values in the
        # first run
        svg_adjust_dict = {}
        for col_name, col_data in df.items():
            if result_str + '_' in col_name and 'total' not in col_name:
                space_guid = col_name.split(result_str + '_')[-1]
                storey_guid = None
                space_area = None
                for guid, ele in elements.items():
                    if guid == space_guid:
                        # TODO use all storeys for aggregated zones
                        if isinstance(ele, SerializedElement):
                            storey_guid = ele.storeys[0]
                        else:
                            storey_guid = ele.storeys[0].guid
                        space_area = ele.net_area

                if not storey_guid or not space_area:
                    self.logger.warning(
                        f"For space with guid {space_guid} no"
                        f" fitting storey could be found. This space will be "
                        f"ignored for floor plan plots. ")
                    continue
                # Ignore very small areas
                min_area = min_space_area * ureg.m ** 2
                if space_area < min_area:
                    self.logger.warning(
                        f"Space with guid {space_guid} is smaller than "
                        f"the minimal threshold area of {min_area}. The "
                        f"space is ignored for floor plan plotting. ")
                    continue

                svg_adjust_dict.setdefault(storey_guid, {}).setdefault(
                    "space_data", {})
                if area_specific:
                    val = col_data.max() / space_area
                else:
                    val = col_data.max()
                # update minimal and maximal value to get a useful color scale
                svg_adjust_dict[storey_guid]["storey_min_value"] = min(
                    val,  svg_adjust_dict[storey_guid]["storey_min_value"]) \
                    if "storey_min_value" in svg_adjust_dict[storey_guid] \
                    else val
                svg_adjust_dict[storey_guid]["storey_max_value"] = max(
                    val, svg_adjust_dict[storey_guid]["storey_max_value"]) \
                    if "storey_max_value" in svg_adjust_dict[storey_guid] \
                    else val
                svg_adjust_dict[storey_guid]["space_data"][space_guid] = {
                    'text': val}
        # create the color mapping, this needs to be done after the value
        # extraction to have all values for all spaces
        for storey_guid, storey_data in svg_adjust_dict.items():
            storey_min = storey_data["storey_min_value"]
            storey_max = storey_data["storey_max_value"]

            # set common human-readable units
            common_unit = storey_min.to_compact().u
            storey_min = storey_min.to(common_unit)
            storey_max = storey_max.to(common_unit)
            storey_med = round((storey_min + storey_max) / 2, 1).to(
                common_unit)
            if storey_min == storey_max:
                storey_min -= 1 * storey_min.u
                storey_max += 1 * storey_max.u

            cmap = self.create_color_mapping(
                storey_min,
                storey_max,
                storey_med,
                plot_path,
                storey_guid,
            )
            for space_guid, space_data in storey_data["space_data"].items():
                value = space_data["text"].to(common_unit)
                if storey_min == storey_max:
                    storey_min -= 1 * storey_min.u
                    storey_max += 1 * storey_max.u
                    space_data['color'] = "red"
                else:
                    space_data['color'] = (
                        self.get_color_for_value(
                            value.m, storey_min.m, storey_max.m, cmap))
                # store value as text for floor plan plotting
                space_data['text'] = str(value.m.round(1))

        # delete storey_min_value and storey_max_value as no longer needed
        for entry in svg_adjust_dict.values():
            if 'storey_max_value' in entry:
                entry.pop('storey_max_value')
            if 'storey_min_value' in entry:
                entry.pop('storey_min_value')
        # TODO merge the create color_mapping.svg into each of the created
        #  *_modified svg plots.
        # with open("svg_adjust_dict.json", 'w') as file:
        #     json.dump(svg_adjust_dict, file)
        # TODO cleanup temp files of color mapping and so on
        create_svg_floor_plan_plot(ifc_file, plot_path, svg_adjust_dict,
                                   result_str)

    def create_color_mapping(
            self, min_val, max_val, med_val, sim_results_path, storey_guid):
        """Create a colormap from blue to red and save it as an SVG file.

        Args:
          min_val (float): Minimum value for the colormap range.
          max_val (float): Maximum value for the colormap range.

        Returns:
          LinearSegmentedColormap: Created colormap object.
        """
        # if whole storey has only one or the same values color is static
        if min_val == max_val:
            colors = ["red", "red", "red" ]
        else:
            colors = ['blue', 'purple', 'red']
        cmap = LinearSegmentedColormap.from_list(
                'custom', colors)

        # Create a normalization function to map values between 0 and 1
        normalize = plt.Normalize(vmin=min_val.m, vmax=max_val.m)

        # Create a ScalarMappable to use the colormap
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=normalize)
        sm.set_array([])

        # Create a color bar to display the colormap
        fig, ax = plt.subplots(figsize=(0.5, 6))
        fig.subplots_adjust(bottom=0.5)
        cbar = plt.colorbar(sm, orientation='vertical', cax=ax)

        # set ticks and tick labels
        cbar.set_ticks([min_val.m, med_val.m, max_val.m])
        cbar.set_ticklabels(
            [
                f"${min_val.to_compact():.4~L}$",
                f"${med_val.to_compact():.4~L}$",
                f"${max_val.to_compact():.4~L}$",
             ])
        # convert all values to common_unit

        # Save the figure as an SVG file
        plt.savefig(sim_results_path / f'color_mapping_{storey_guid}.svg'
                    , format='svg')
        plt.close(fig)
        return cmap

    @staticmethod
    def get_color_for_value(value, min_val, max_val, cmap):
        """Get the color corresponding to a value within the given colormap.

        Args:
          value (float): Value for which the corresponding color is requested.
          min_val (float): Minimum value of the colormap range.
          max_val (float): Maximum value of the colormap range.
          cmap (LinearSegmentedColormap): Colormap object.

        Returns:
          str: Hexadecimal representation of the color corresponding to the
           value.
        """
        # Normalize the value between 0 and 1
        normalized_value = (value - min_val) / (max_val - min_val)

        # Get the color corresponding to the normalized value
        color = cmap(normalized_value)

        return to_hex(color, keep_alpha=False)


    @staticmethod
    def plot_temperatures(df: pd.DataFrame, data: str,
                     save_path: Optional[Path] = None,
                     logo: bool = True,
                     window: int = 12, fig_size: Tuple[int, int] = (10, 6),
                     dpi: int = 300) -> None:
        """
        Plot temperatures.

        """
        save_path_demand = (save_path /
                            f"{data.lower()}.pdf")
        y_values = df[data]
        color = cm.RWTHBlau.p(100)

        label_pad = 5
        # Create a new figure with specified size
        fig = plt.figure(figsize=fig_size, dpi=dpi)

        # Define spaces next to the real plot with absolute values
        # fig.subplots_adjust(left=0.05, right=0.95, top=1.0, bottom=0.0)

        # Determine if y-axis needs to be in kilowatts
        y_values = y_values.pint.to(ureg.degree_Celsius)

        plt.ylabel(
            f"{data}  / {format(y_values.pint.units, '~')}",
            labelpad=label_pad)
        # Smooth the data for better visibility
        # y_values = y_values.rolling(window=window).mean()
        # take values without units only for plot
        y_values = y_values.pint.magnitude

        # y_values.index = pd.to_datetime(df.index, format='%m/%d-%H:%M:%S')
        # Plotting the data
        plt.plot(y_values.index,
                 y_values, color=color,
                 linewidth=1, linestyle='-')

        first_day_of_months = (y_values.index.to_period('M').unique().
                               to_timestamp())
        plt.xticks(first_day_of_months.strftime('%Y-%m-%d'),
                   [month.strftime('%b') for month in first_day_of_months])

        # Rotate the tick labels for better visibility
        plt.gcf().autofmt_xdate(rotation=45)

        # Limits
        plt.xlim(y_values.index[0], y_values.index[-1])
        plt.ylim(y_values.min()*1.1, y_values.max() * 1.1)
        # Adding x label
        plt.xlabel("Time", labelpad=label_pad)
        # Add title
        plt.title(f"{data}", pad=20)
        # Add grid
        plt.grid(True, linestyle='--', alpha=0.6)

        # add bim2sim logo to plot
        if logo:
            raise Warning("Logo option is currently not supported")
            logo_pos = [fig_size[0] * dpi * 0.005,
                        fig_size[1] * 0.95 * dpi]
            PlotBEPSResults.add_logo(dpi, fig_size, logo_pos)

        # Show or save the plot
        PlotBEPSResults.save_or_show_plot(save_path_demand, dpi, format='pdf')

    @staticmethod
    def plot_multiple_temperatures(
            df: pd.DataFrame, save_path: Optional[Path] = None, logo: bool =
            True, window: int = 12, fig_size: Tuple[int, int] = (10, 6),
            dpi: int = 300) -> None:
        """
        Plot multiple temperature series in one plot.

        Parameters:
            df (pd.DataFrame): DataFrame containing the temperature data to plot.
            save_path (Optional[Path]): Path to save the plot as a PDF file.
            logo (bool): Whether to include a logo in the plot.
            window (int): Rolling window size for smoothing the data.
            fig_size (Tuple[int, int]): Size of the figure.
            dpi (int): Dots per inch for the plot resolution.
        """

        save_path_demand = (
                save_path / "temperatures_plot.pdf") if save_path else None
        label_pad = 5

        # Create a new figure with specified size
        fig = plt.figure(figsize=fig_size, dpi=dpi)

        # Get a colormap with enough colors for all columns
        colormap = plt.get_cmap('tab10')
        colors = [to_hex(colormap(i)) for i in range(len(df.columns))]

        # Iterate over each column in the DataFrame
        for i, column in enumerate(df.columns):
            y_values = df[column]

            # Escape underscores in column names for LaTeX formatting
            safe_column_name = column.replace('_', r'\_')

            # Plot the data
            plt.plot(df.index, y_values, label=safe_column_name,
                     color=colors[i], linewidth=1,
                     linestyle='-')

        # Format the x-axis labels with dd/MM format
        date_format = DateFormatter('%d/%m')
        plt.gca().xaxis.set_major_formatter(date_format)

        # Rotate the tick labels for better visibility
        plt.gcf().autofmt_xdate(rotation=45)

        # Limits
        plt.xlim(df.index[0], df.index[-1])
        plt.ylim(df.min().min() * 0.99, df.max().max() * 1.01)

        # Adding labels and title
        plt.xlabel("Time", labelpad=label_pad)
        plt.ylabel("Temperature (°C)", labelpad=label_pad)
        plt.title("Surface Temperature Data", pad=20)

        # Add grid
        plt.grid(True, linestyle='--', alpha=0.6)

        # Add legend below the x-axis
        plt.legend(title="", loc='upper center',
                   bbox_to_anchor=(0.5, -0.15),
                   ncol=2, fontsize='small', frameon=False)

        # Add bim2sim logo to plot
        if logo:
            logo_pos = [fig_size[0] * dpi * 0.005, fig_size[1] * 0.95 * dpi]
            PlotBEPSResults.add_logo(dpi, fig_size, logo_pos)

        # Save the plot if a path is provided
        PlotBEPSResults.save_or_show_plot(save_path_demand, dpi, format='pdf')


    def plot_thermal_discomfort(self):
        # TODO
        pass

    # @staticmethod
    # def add_logo(dpi, fig_size, logo_pos):
    #     # TODO: this is not completed yet
    #     """Adds the logo to the existing plot."""
    #     # Load the logo
    #     logo_path = Path(bim2sim.__file__).parent.parent \
    #                 / "docs/source/img/static/b2s_logo.png"
    #     # todo get rid of PIL package
    #     logo = Image.open(logo_path)
    #     logo.thumbnail((fig_size[0] * dpi / 10, fig_size[0] * dpi / 10))
    #     plt.figimage(logo, xo=logo_pos[0], yo=logo_pos[1], alpha=1)
    #     # TOdo resizing is not well done yet, this is an option but not
    #     #  finished:
    #     # # Calculate the desired scale factor
    #     # scale_factor = 0.01  # Adjust as needed
    #     #
    #     # # Load the logo
    #     # logo = plt.imread(logo_path)
    #     #
    #     # # Create an OffsetImage
    #     # img = OffsetImage(logo, zoom=scale_factor)
    #     #
    #     # # Set the position of the image
    #     # ab = AnnotationBbox(img, (0.95, -0.1), frameon=False,
    #     #                     xycoords='axes fraction', boxcoords="axes fraction")
    #     # plt.gca().add_artist(ab)