"""BIM2SIM library"""

import os
import re
import sys

import logging
import typing
import importlib
import pkgutil
import tempfile
from os.path import expanduser
from pathlib import Path
import site

import pkg_resources

from bim2sim.kernel import ifc2python
from bim2sim.decision import Decision
from bim2sim.project import Project, FolderStructure
from bim2sim.plugin import Plugin
from bim2sim.plugins import DummyPlugin
from bim2sim.workflow import PlantSimulation, BPSMultiZoneSeparatedLayersLow,\
    BPSMultiZoneSeparatedEP

VERSION = '0.1-dev'

# TODO: setup: copy backends to bim2sim/backends
workflow_getter = {'aixlib': PlantSimulation,
                   'teaser': BPSMultiZoneSeparatedLayersLow,
                   'hkesim': PlantSimulation,
                   'energyplus': BPSMultiZoneSeparatedEP}


def load_plugins(names: typing.Iterable[str] = None) -> typing.Dict[str, Plugin]:
    """Load bim2sim plugins filtered by names if argument names is specified"""
    # TODO: load by names
    # _names = [name for name in names if name.startswith('bim2sim_')]
    logger = logging.getLogger(__name__)
    plugins = {}
    # internal plugins
    plugins[DummyPlugin.name] = DummyPlugin

    # load all
    for finder, name, ispkg in pkgutil.iter_modules():
        if name.startswith('bim2sim_'):
            print(name)
            module = importlib.import_module(name)
            contend = getattr(module, 'CONTEND', None)
            if not contend:
                logger.warning("Found potential plugin '%s', but CONTEND is missing", name)
                continue

            for key, getter in contend.items():
                plugins[key] = getter()
                logger.debug("Found plugin '%s'", name)
    return plugins


def logging_setup():
    """Setup for logging module"""

    formatter = logging.Formatter('[%(levelname)s] %(name)s: %(message)s')
    root_logger = logging.getLogger(__name__)

    # Stream
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)
    # File
    # file_handler = logging.FileHandler(os.path.join(PROJECT.log, "bim2sim.log"))
    # file_handler.setFormatter(formatter)
    # root_logger.addHandler(file_handler)

    root_logger.setLevel(logging.DEBUG)

    # silence matplotlib
    # matlog = logging.getLogger('matplotlib')
    # matlog.level = logging.INFO

    root_logger.debug("Logging setup done.")


def setup_default():
    """Main entry point"""
    logging_setup()
    logger = logging.getLogger(__name__)

    plugins = load_plugins()
    # if not plugins:
    #     raise AssertionError("No plugins found!")

    from bim2sim.decision.console import ConsoleFrontEnd
    Decision.set_frontend(ConsoleFrontEnd())


def setup(frontend_name='default'):
    if frontend_name == 'ExternalFrontEnd':
        from bim2sim.decision.external import ExternalFrontEnd as Frontend
    else:
        from bim2sim.decision.console import ConsoleFrontEnd as Frontend
    Decision.set_frontend(Frontend())


def _debug_run_hvac():
    """Create example project and copy ifc if necessary"""
    path_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..\\.."))
    rel_example = 'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc'
    path_ifc = os.path.normpath(os.path.join(path_base, rel_example))
    path_example = r"C:\temp\bim2sim\testproject"

    if Project.is_project_folder(path_example):
        project = Project(path_example)
    else:
        project = Project.create(path_example, path_ifc, 'hkesim', )

    # setup_defualt(project.config['Frontend']['use'])
    project.run()

def _get_debug_project_path():
    path_file = "debug_dir.user"
    try:
        f = open(path_file)
        path_example = f.read()
        f.close()
    except IOError:
        path_example = str(input("Specify debug root path (Leave blank for '" + expanduser('~')
                                 + "'). This value will be remembered in '" + path_file + "': "))
        if len(path_example) == 0:
            path_example = expanduser('~')
        f = open(path_file, 'a')
        f.write(path_example)
        f.close()

    if not path_example.endswith("/"):
        path_example += "/"

    max_number = 0
    for item in os.listdir(path_example):
        m = re.search('testproject_bps_ep([0-9]+)', item)
        if m:
            max_number = max(int(m.group(1)), max_number)

    return path_example + "testproject_bps_ep" + str(max_number + 1)


def _debug_run_bps():
    """Create example project and copy ifc if necessary"""
    path_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

    # rel_example = 'ExampleFiles/AC20-FZK-Haus.ifc'
    # rel_example = 'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Architektur_spaces.ifc'
    rel_example = 'ExampleFiles/AC20-Institute-Var-2.ifc'
    path_ifc = os.path.normpath(os.path.join(path_base, rel_example))
    path_example = r"C:\temp\bim2sim\testproject_bps7"

    if Project.is_project_folder(path_example):
        project = Project(path_example)
    else:
        project = Project.create(path_example, path_ifc, 'teaser', )

    project.run()


def _debug_run_bps_ep():
    """Create example project and copy ifc if necessary"""
    path_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

    # rel_example = 'ExampleFiles/AC20-FZK-Haus.ifc'
    # rel_example = 'ResultFiles/AC20-FZK-Haus_with_SB44.ifc' # aktuell
    # rel_example = 'ResultFiles/Proposal_1_Storey_SpaceBoundaries_with_SB.ifc'
    # rel_example = 'ResultFiles/2020-10-15-KHH-Test_with_SB.ifc'
    rel_example = 'ExampleFiles/AC20-Institute-Var-2.ifc'
    # rel_example = 'ExampleFiles/DigitalHub_Architektur2_2020_Achse_tragend_V2.ifc' # ok
    # rel_example = 'ExampleFiles/AC-20-Smiley-West-10-Bldg.ifc'
    path_ifc = os.path.normpath(os.path.join(path_base, rel_example))

    path_example = _get_debug_project_path()

    if Project.is_project_folder(path_example):
        project = Project(path_example)
    else:
        project = Project.create(path_example, path_ifc, 'energyplus', )

    project.run()


def _test_run_bps_ep(rel_path, temp_project=False):
    """Create example project and copy ifc if necessary. Added for EnergyPlus integration tests"""
    path_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

    path_ifc = os.path.normpath(os.path.join(path_base, rel_path))

    if not temp_project:
        path_example = _get_debug_project_path()
    else:
        path_example = tempfile.mkdtemp()

    old_stderr = sys.stderr
    working_dir = os.getcwd()
    success = False
    if Project.is_project_folder(path_example):
        project = Project(path_example)
    else:
        project = Project.create(path_example, path_ifc, 'energyplus', )

    try:
        print("Project directory: " + path_example)
        os.chdir(path_example)
        if Project.is_project_folder(path_example):
            project = Project(path_example)
        else:
            project = Project.create(path_example, path_ifc, 'energyplus', )

        #HACK: We have to remember stderr because eppy resets it currently.
        success = project.run()
    finally:
        os.chdir(working_dir)
        sys.stderr = old_stderr
        return success


def _debug_run_hvac_aixlib():
    """Create example project and copy ifc if necessary"""
    path_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..\\.."))
    rel_example = 'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc'
    path_ifc = os.path.normpath(os.path.join(path_base, rel_example))
    path_example = r"C:\temp\bim2sim\testproject_aix"

    if Project.is_project_folder(path_example):
        project = Project(path_example)
    else:
        project = Project.create(path_example, path_ifc, 'aixlib', )

    project.run()


def _debug_run_cfd():
    """Create example project and copy ifc if necessary"""

    sys.path.append("/home/fluid/Schreibtisch/B/bim2sim-coding/PluginCFD")
    path_example = r"/home/fluid/Schreibtisch/B/temp"
    # unter ifc muss datei liegen

    if Project.is_project_folder(path_example):
        project = Project(path_example)
    else:
        project = Project.create(path_example, target='cfd', )

    project.run()


setup_default()

if __name__ == '__main__':
    # _debug_run_cfd()
    _debug_run_bps()
    # _debug_run_bps_ep()
    # _debug_run_hvac()

