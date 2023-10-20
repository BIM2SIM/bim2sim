import subprocess

from bim2sim.tasks.base import ITask


class RunEnergyPlusSimulation(ITask):
    reads = ('idf', 'weather_file',)

    def run(self, idf, weather_file):
        ep_full = self.playground.sim_settings.run_full_simulation
        output_string = str(self.paths.export / 'EP-results/')
        run_options = []
        run_options.extend([
            self.playground.sim_settings.ep_install_path / 'energyplus.exe',
            '-r',  # run ReadVarsESO after simulation
            '-x',  # expand objects
            '-w', weather_file,  # weather file
            '-d', output_string  # output directory
        ])
        if not ep_full:
            run_options.extend(['-D'])
        else:
            run_options.extend(['-a'])
        subprocess.run([*run_options, idf.idfname])
        self.playground.sim_settings.simulated = True
        self.logger.info(f"Simulation successfully finished.")
        # if ep_full:
        #     PostprocessingUtils._visualize_results(csv_name=self.paths.export / 'EP-results/eplusout.csv')
