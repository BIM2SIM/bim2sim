import re
from pathlib import Path

from geomeppy import IDF

from bim2sim.tasks.base import ITask
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.utils import \
    PostprocessingUtils


class RunEnergyPlusSimulation(ITask):
    """Run EnergyPlus simulation.

    See run function for more details.
    """
    reads = ('idf', 'sim_results_path')

    def _export_eplusout_html_report(self, csv_path):
        """Create an HTML report for the eplusout.csv file.
        
        This method reads the eplusout.csv file and creates an HTML report
        with the simulation results for better visualization.
        
        Args:
            csv_path (Path): Path to the eplusout.csv file.
        """
        import pandas as pd
        
        # Check if file exists
        if not csv_path.exists():
            self.logger.warning(f"eplusout.csv file not found at {csv_path}")
            return
        
        # Read the CSV file
        try:
            ep_df = pd.read_csv(csv_path)
            
            # Create an HTML file path in the same directory
            html_file = csv_path.parent / "eplusout_energida.htm"
            
            # Create HTML content
            html_content = """<!DOCTYPE html>
    <html>
    <head>
        <title>EnergyPlus Simulation Results</title>
        <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333366; }
        h2 { color: #336699; margin-top: 30px; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 30px; } 
        th { background-color: #336699; color: white; text-align: left; padding: 8px; }
        td { border: 1px solid #ddd; padding: 8px; }
        tr:nth-child(even) { background-color: #f2f2f2; }
        tr:hover { background-color: #e6e6e6; }
        .stats-table { width: auto; margin-bottom: 20px; }
        .summary { margin-bottom: 20px; }
        </style>
    </head>
    <body>
        <h1>EnergyPlus Simulation Results</h1>
        
        <div class="summary">
            <h2>Summary Statistics</h2>
            <table class="stats-table">
                <tr><th>Total Rows</th><td>""" + str(len(ep_df)) + """</td></tr>
                <tr><th>Time Period</th><td>""" + str(ep_df.iloc[0]['Date/Time']) + """ to """ + str(ep_df.iloc[-1]['Date/Time']) + """</td></tr>
                <tr><th>Number of Variables</th><td>""" + str(len(ep_df.columns)) + """</td></tr>
            </table>
        </div>
        
        <h2>Column Statistics</h2>
        <table>
            <tr>
                <th>Column</th>
                <th>Min</th>
                <th>Max</th>
                <th>Mean</th>
                <th>Std Dev</th>
            </tr>
    """
            
            # Add statistics for each numerical column
            for col in ep_df.columns:
                if col != 'Date/Time' and pd.api.types.is_numeric_dtype(ep_df[col]):
                    html_content += f"""
            <tr>
                <td>{col}</td>
                <td>{ep_df[col].min():.4f}</td>
                <td>{ep_df[col].max():.4f}</td>
                <td>{ep_df[col].mean():.4f}</td>
                <td>{ep_df[col].std():.4f}</td>
            </tr>"""
            
            html_content += """
        </table>
        
        <h2>Data Preview (First 20 rows)</h2>
    """ + ep_df.head(20).to_html(index=False) + """
    </body>
    </html>"""
            
            # Save the HTML file
            with open(html_file, 'w') as f:
                f.write(html_content)
            
            self.logger.info(f"Generated HTML report for eplusout.csv at {html_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to create HTML report for eplusout.csv: {e}")


    def run(self, idf: IDF, sim_results_path: Path):
        """Run EneryPlus simulation.

        This function is used to run EnergyPlus. The simulation is performed
        according to the selected simulation settings. The simulation results
        can be found under the simulation result path in the project name
        directory.

        Args:
            idf (IDF): eppy idf, EnergyPlus input file
            sim_results_path (Path): Path to simulation results.

        """
        # subprocess.run(['energyplus', '-x', '-c', '--convert-only', '-d', self.paths.export, idf.idfname])
        export_path = sim_results_path / self.prj_name
        ep_full = self.playground.sim_settings.run_full_simulation
        design_day = False
        if not ep_full and not self.playground.sim_settings.set_run_period:
            design_day = True

        idf.run(output_directory=export_path, readvars=True, annual=ep_full,
                design_day=design_day)
        self.playground.sim_settings.simulated = True
        self.logger.info(f"Simulation successfully finished.")
        if ep_full:
            eplusout_csv_path = export_path / 'eplusout.csv'
            webtool_df_ep = PostprocessingUtils.export_df_for_webtool(
                csv_name=eplusout_csv_path)
            self._export_eplusout_html_report(eplusout_csv_path)
            self.logger.info(f"Exported dataframe for postprocessing.")
        else:
            self.logger.info(f"No dataframe output for postprocessing "
                             "generated. Please set the workflow setting "
                             "'run_full_simulation' to True to enable the "
                             "postprocessing output.")
        self.logger.info(f"You can find the results under "
                         f"{str(export_path)}")