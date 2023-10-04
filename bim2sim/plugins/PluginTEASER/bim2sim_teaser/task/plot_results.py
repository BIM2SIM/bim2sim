from typing import Optional, Tuple

from ebcpy import TimeSeriesData
from matplotlib import pyplot as plt, image as mpimg
from pathlib import Path
from PIL import Image
import RWTHColors
import scienceplots
from RWTHColors import ColorManager
import pandas as pd

import bim2sim
from bim2sim.tasks.base import ITask

cm = ColorManager()

modelica_names_mapping = {
    "Heating Power Total": "multizonePostProcessing.PHeaterSum",
    "Cooling Power Total": "multizonePostProcessing.PCoolerSum",
    "Heating Energy Total": "multizonePostProcessing.WHeaterSum",
    "Cooling Energy Total": "multizonePostProcessing.WCoolerSum",
}


class PlotResults(ITask):
    reads = ('teaser_mat_result_paths','dir_teaser_sim_results',)
    final = True

    def run(self, teaser_mat_result_paths, dir_teaser_sim_results):
        for bldg_name, result_path in teaser_mat_result_paths.items():
            df = TimeSeriesData(result_path).to_df()
            self.plot_total_consumption(df, bldg_name, dir_teaser_sim_results)
            print('test')

    def plot_total_consumption(self, df, bldg_name, dir_teaser_sim_results):
        export_path = dir_teaser_sim_results / bldg_name
        self.plot_demands(df, "Heating", export_path)
        self.plot_demands(df, "Cooling", export_path)

    @staticmethod
    def plot_demands(df: pd.DataFrame, demand_type: str,
                     save_path: Optional[Path] = None,
                     logo: bool = True, total_label: bool = True,
                     fig_size: Tuple[int, int] = (10, 6),
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
            total_label (bool, optional): Whether to include total energy label.
             Defaults to True.
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
        save_path = save_path / f"{demand_type}.pdf"
        if demand_type == "Heating":
            # Create a new variable for y-axis with converted unit and rolling
            # Smooth the data for better visibility
            y_values = df[
                modelica_names_mapping["Heating Power Total"]].rolling(
                window=12).mean()
            total_energy = \
                df[modelica_names_mapping["Heating Energy Total"]].iloc[
                    -1] / 3600000
            color = cm.RWTHRot.p(100)
        elif demand_type == "Cooling":
            # Create a new variable for y-axis with converted unit and rolling
            # Smooth the data for better visibility
            y_values = df[
                modelica_names_mapping["Cooling Power Total"]].rolling(
                window=12).mean()
            total_energy = \
                df[modelica_names_mapping["Cooling Energy Total"]].iloc[
                    -1] / 3600000
            color = cm.RWTHBlau.p(100)
            # plot cooling as positive values as well
            y_values = -1 * y_values
        else:
            raise ValueError(f"Demand type {demand_type} is not supported.")
        # Use rwth color style and science style
        label_pad = 6
        plt.style.use(['science', 'grid', 'rwth'])
        # Create a new figure with specified size
        fig = plt.figure(figsize=fig_size, dpi=dpi)

        # Define spaces next to the real plot with absolute values
        fig.subplots_adjust(left=0.1, right=0.98, top=0.9, bottom=0.1)

        # Create a new variable for x-axis values in hours
        x_values_hours = df.index / 3600  # Convert seconds to hours

        # Determine if y-axis needs to be in kilowatts
        if y_values.max() > 5000:
            kw_labels = True
            # Convert to kilowatts
            plt.ylabel(f"{demand_type} Demand (kW)", labelpad=label_pad)
            y_values = y_values / 1000
        else:
            kw_labels = False
            plt.ylabel(f"{demand_type} Demand (W)", labelpad=label_pad)

        # Plotting the data
        plt.plot(x_values_hours,
                 y_values, color=color,
                 linewidth=2, linestyle='-')
        # Limits
        plt.xlim(0, x_values_hours[-1])
        plt.ylim(0, y_values.max() * 1.1)
        # Adding x label
        plt.xlabel("Time (hours)", labelpad=label_pad)
        # Add title
        plt.title(f"{demand_type} Demand")
        # Add grid
        plt.grid(True, linestyle='--', alpha=0.6)
        # Adjust font sizes
        plt.rcParams.update({'font.size': 12})

        # Adjust further settings
        plt.gca().spines['top'].set_visible(False)
        plt.gca().spines['right'].set_visible(False)
        plt.gca().xaxis.set_major_locator(plt.MaxNLocator(prune='both'))
        plt.gca().yaxis.set_major_locator(plt.MaxNLocator(prune='both'))
        # plt.tight_layout()

        if total_label:
            plt.text(0.95, 0.95, f'Total energy: {total_energy:.2f} kWh',
                     horizontalalignment='right',
                     verticalalignment='top',
                     transform=plt.gca().transAxes,  # Use axes coordinates
                     bbox=dict(facecolor='white', alpha=0.5, edgecolor='none'))

        if logo:
            # Load the logo
            logo_path = Path(bim2sim.__file__).parent.parent \
                        / "docs/source/img/static/b2s_logo_only.png"
            # todo get rid of PIL package
            logo = Image.open(logo_path)
            logo.thumbnail((fig_size[0] * dpi / 10, fig_size[0] * dpi / 10))

            if save_path:
                logo_pos = [fig_size[0] * dpi * 0.843,
                            fig_size[1] * 0.005 * dpi]
                if kw_labels:
                    logo_pos = [fig_size[0] * dpi * 0.83,
                                fig_size[1] * 0.005 * dpi]
            else:
                logo_pos = [fig_size[0] * dpi * 0.885, fig_size[1] * 0.01 * dpi]
            plt.figimage(logo, xo=logo_pos[0], yo=logo_pos[1], alpha=1)
        # TOdo resizing is not well done yet, this is an option but not finished:
        # # Calculate the desired scale factor
        # scale_factor = 0.01  # Adjust as needed
        #
        # # Load the logo
        # logo = plt.imread(logo_path)
        #
        # # Create an OffsetImage
        # img = OffsetImage(logo, zoom=scale_factor)
        #
        # # Set the position of the image
        # ab = AnnotationBbox(img, (0.95, -0.1), frameon=False,
        #                     xycoords='axes fraction', boxcoords="axes fraction")
        # plt.gca().add_artist(ab)
        
        # Show the plot
        if save_path:
            plt.ioff()
            plt.savefig(save_path, dpi=dpi, format='pdf')
        else:
            plt.show()
