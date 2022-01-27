import itertools
import sys
import os

from pathlib import Path
import PluginTEASER

from bim2sim.task.base import ITask


class SimulateModel(ITask):
    final = True

    def run(self, workflow):
        path = self.get_dymola_path()
        self.load_dymola(path)

        from dymola.dymola_interface import DymolaInterface
        dymola = DymolaInterface()
        plugin_path = Path(bim2sim_teaser.__file__).parent

        dir_aixlib = Path(plugin_path/ 'AixLib' / 'AixLib' / 'package.mo')
        dir_model = Path(self.paths.export)
        dymola.openModel(dir_aixlib)
        dymola.openModel()


    def get_dymola_path(self) -> Path:
        """Function to find local dymola installation path."""
        dymola_versions = [
            'Dymola 2019',
            'Dymola 2019x',
            'Dymola 2020',
            'Dymola 2020x',
            'Dymola 2021',
            'Dymola 2021x',
            'Dymola 2022',
            'Dymola 2022x'
        ]

        if os.name == 'nt':  # windows
            prog_paths = [
                'C:/Program Files/',
                'C:/Program Files (x86)/'
            ]
        else:   # linux (os.name == 'posix'):
            prog_paths = [
                '/opt/dymola/'
            ]

        egg_path = '/Modelica/Library/python_interface/dymola.egg'

        dymola_path = None
        for base_path in itertools.product(
                prog_paths, reversed(dymola_versions)):
            dymola_path = Path(''.join(base_path) + egg_path)
            if dymola_path.is_file():
                break
            else:
                dymola_path = None
        return dymola_path

    def load_dymola(self, path: Path):
        sys.path.insert(0, str(path))
