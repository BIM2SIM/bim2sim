from ebcpy import TimeSeriesData
from matplotlib import pyplot as plt, image as mpimg
from pathlib import Path
from PIL import Image
import RWTHColors
import scienceplots
from RWTHColors import ColorManager


import bim2sim
from bim2sim.tasks.base import ITask

cm = ColorManager()


class PlotResults(ITask):
    reads = ('teaser_mat_result_paths',)
    final = True

    def run(self, teaser_mat_result_paths):
        for bldg_name, result_path in teaser_mat_result_paths.items():
            df = TimeSeriesData(result_path).to_df()
            self.plot_total_consumption(df)
            print('test')

    def plot_total_consumption(self, df):
        self.plot_demands(df, "multizonePostProcessing.PHeaterSum", "Heating",
                          Path("D:/01_Kurzablage/test_plots/heating.pdf"))
        self.plot_demands(df, "multizonePostProcessing.PCoolerSum", "Cooling",
                          Path("D:/01_Kurzablage/test_plots/cooling.pdf"))

    @staticmethod
    def plot_demands(df, y_axis_title, demand_type, save_path: Path,
                     logo: bool = True, fig_size=(10, 6), dpi=300):
        """
        Plot demands based on provided data.

        Args:
            df (pandas.DataFrame): The DataFrame containing the data.
            y_axis_title (str): The title of the y-axis.
            demand_type (str): The type of demand.
            save_path (Path): The path to save the plot as a PDF.
            logo (bool, optional): Whether to include a logo. Defaults to True.
            fig_size (tuple, optional): The size of the figure in inches (width, height).
                Defaults to (10, 6).
            dpi (int, optional): Dots per inch (resolution). Defaults to 300.

        Returns:
            None

        Raises:
            Any exceptions raised during plot creation or saving.

        Note:
            - The plot is styled using the 'science', 'grid', and 'rwth' styles.
            - The figure is adjusted with specified spaces around the plot.
            - The y-axis unit and rolling are adjusted for better visibility.
            - The y-axis label is determined based on demand type and converted to kilowatts if necessary.
            - The plot is created with appropriate colors and styles.
            - Limits, labels, titles, and grid are set for the plot.
            - Font sizes and other settings are adjusted.
            - The logo is added to the lower right corner of the plot.

        Example:
            Example usage of the method.

            plot_demands(df=my_dataframe, y_axis_title="Power",
                         demand_type="Cooling", save_path=Path("my_plot.pdf"),
                         logo=True, fig_size=(12, 8), dpi=300)
        """
        # Use rwth color style and science style
        label_pad = 6
        plt.style.use(['science', 'grid', 'rwth'])
        # Create a new figure with specified size
        fig = plt.figure(figsize=fig_size, dpi=dpi)
        # plt.figure(figsize=fig_size, dpi=dpi)  # Adjust size as needed

        # Define spaces next to the real plot with absolute values
        fig.subplots_adjust(left=0.1, right=0.98, top=0.9, bottom=0.1)

        # Create a new variable for x-axis values in hours
        x_values_hours = df.index / 3600  # Convert seconds to hours
        # Create a new variable for y-axis with converted unit and rolling
        # Smooth the data for better visibility
        y_values = df[
            y_axis_title].rolling(
            window=12).mean()  # Adjust window size as needed
        # Determine if y-axis needs to be in kilowatts
        if y_values.max() > 5000:
            # Convert to kilowatts
            plt.ylabel(f"{demand_type} Demand (kW)", labelpad=label_pad)
            y_values = y_values / 1000
        else:
            plt.ylabel(f"{demand_type} Demand (W)", labelpad=label_pad)
        if demand_type == "Heating":
            color = cm.RWTHRot.p(100)
        else:
            color = cm.RWTHBlau.p(100)
            # plot cooling as positive values as well
            y_values = -1 * y_values
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
        plt.title(f"{demand_type} Demand vs. Time")
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

        if logo:
            # Load the logo
            logo_path = Path(bim2sim.__file__).parent.parent \
                        / "docs/source/img/static/b2s_logo_only.png"
            logo = Image.open(logo_path)
            logo.thumbnail((fig_size[0] * dpi / 10, fig_size[0] * dpi / 10))

            if save_path:
                plt.figimage(logo, xo=fig_size[0] * dpi * 0.85,
                             yo=fig_size[1] * 0.005 * dpi, alpha=1)
            else:
                plt.figimage(logo, xo=fig_size[0] * dpi * 0.885,
                             yo=fig_size[1] * 0.01 * dpi, alpha=1)
        # Show the plot
        if save_path is not None:
            plt.ioff()
            plt.savefig(save_path, dpi=dpi, format='pdf')
        else:
            plt.show()
