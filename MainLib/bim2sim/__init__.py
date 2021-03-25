"""BIM2SIM library"""

import os
import re
import sys
import importlib
import pkgutil
import logging
import tempfile
from os.path import expanduser
from pathlib import Path
import site

import pkg_resources

from bim2sim.kernel import ifc2python
from bim2sim.manage import BIM2SIMManager
from bim2sim.project import PROJECT, get_config
from bim2sim.workflow import PlantSimulation, BPSMultiZoneSeparated
from bim2sim.decision import Decision

VERSION = '0.1-dev'

# TODO: setup: copy backends to bim2sim/backends
workflow_getter = {'aixlib': PlantSimulation,
                   'teaser': BPSMultiZoneSeparated,
                   'hkesim': PlantSimulation,
                   'energyplus': BPSMultiZoneSeparated}


def get_default_backends():
    path = Path(__file__).parent / 'backends'
    backends = []
    for pkg in [item for item in path.glob('**/*') if item.is_dir()]:
        if pkg.name.startswith('bim2sim_'):
            backends.append(pkg)
    return backends


def get_dev_backends():
    path = Path(__file__).parent.parent.parent
    backends = []
    for plugin in [item for item in path.glob('**/*') if item.is_dir()]:
        if plugin.name.startswith('Plugin'):
            for pkg in [item for item in plugin.glob('**/*') if item.is_dir()]:
                if pkg.name.startswith('bim2sim_'):
                    backends.append(pkg)
    return backends


def get_backends(by_entrypoint=False):
    """load all possible plugins"""
    logger = logging.getLogger(__name__)

    default = get_default_backends()
    dev = get_dev_backends()

    # add all plugins to PATH
    sys.path.extend([str(path.parent) for path in default + dev])

    if by_entrypoint:
        sim = {}
        for entry_point in pkg_resources.iter_entry_points('bim2sim'):
            sim[entry_point.name] = entry_point.load()
    else:
        sim = {}
        for finder, name, ispkg in pkgutil.iter_modules():
            if name.startswith('bim2sim_'):
                module = importlib.import_module(name)
                contend = getattr(module, 'CONTEND', None)
                if not contend:
                    logger.warning("Found potential plugin '%s', but CONTEND is missing", name)
                    continue

                for key, getter in contend.items():
                    sim[key] = getter
                    logger.debug("Found plugin '%s'", name)

    return sim


def finish(success=False):
    """cleanup method"""
    logger = logging.getLogger(__name__)
    if not success:
        pth = PROJECT.root / 'decisions_backup.json'
        Decision.save(pth)
        logger.warning("Decisions are saved in '%s'. Rename file to 'decisions.json' to reuse them.", pth)
    Decision.frontend.shutdown(success)
    logger.info('finished')


def logging_setup():
    """Setup for logging module"""

    formatter = logging.Formatter('[%(levelname)s] %(name)s: %(message)s')
    root_logger = logging.getLogger()

    # Stream
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)
    # File
    file_handler = logging.FileHandler(os.path.join(PROJECT.log, "bim2sim.log"))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    root_logger.setLevel(logging.DEBUG)

    # silence matplotlib
    matlog = logging.getLogger('matplotlib')
    matlog.level = logging.INFO

    logging.debug("Logging setup done.")


def main(rootpath=None):
    """Main entry point"""

    _rootpath = rootpath or os.getcwd()
    PROJECT.root = _rootpath
    assert PROJECT.is_project_folder(), \
        "'%s' does not look like a project folder. Create a project folder first." % (_rootpath)

    logging_setup()
    logger = logging.getLogger(__name__)

    plugins = get_backends()

    conf = get_config()
    backend = conf["Backend"].get("use")
    assert backend, "No backend set. Check config.ini"
    backend = backend.lower()

    logger.info("Loading backend '%s' ...", backend)
    print(plugins)
    manager_cls = plugins.get(backend.lower())()

    if manager_cls is None:
        msg = "Simulation '%s' not found in plugins. Available plugins:\n - " % (backend)
        msg += '\n - '.join(list(plugins.keys()) or ['None'])
        raise AttributeError(msg)

    if not BIM2SIMManager in manager_cls.__bases__:
        raise AttributeError("Got invalid manager from %s" % (backend))

    workflow = workflow_getter[backend]()

    # set Frontend for Decisions
    try:
        frontend_name = conf['Frontend']['use']
    except KeyError:
        frontend_name = 'default'

    if frontend_name == 'ExternalFrontEnd':
        from bim2sim.decision.external import ExternalFrontEnd as Frontend
    else:
        from bim2sim.decision.console import ConsoleFrontEnd as Frontend
    Decision.set_frontend(Frontend())

    # prepare simulation
    manager = manager_cls(workflow)

    # run Manager
    success = False
    try:
        manager.run()
        #manager.run_interactive()
        success = True
    except Exception as ex:
        logger.exception("Something went wrong!")
    finally:
        finish(success=success)
        return success

    return 0 if success else -1


def _debug_run_hvac():
    """Create example project and copy ifc if necessary"""
    path_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..\\.."))
    rel_example = 'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc'
    path_ifc = os.path.normpath(os.path.join(path_base, rel_example))
    path_example = r"C:\temp\bim2sim\testproject"

    if not PROJECT.is_project_folder(path_example):
        PROJECT.create(path_example, path_ifc, 'hkesim', )

    return main(path_example)

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
    path_example = r"C:\temp\bim2sim\testproject_bps2"

    if not PROJECT.is_project_folder(path_example):
        PROJECT.create(path_example, path_ifc, 'teaser')

    return main(path_example)


def _debug_run_bps_ep():
    """Create example project and copy ifc if necessary"""
    path_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

    rel_example = 'ExampleFiles/AC20-FZK-Haus.ifc'
    # rel_example = 'ResultFiles/AC20-Institute-Var-2_with_SB11.ifc' # aktuell
    # rel_example = 'ResultFiles/AC20-FZK-Haus_with_SB44.ifc' # aktuell
    # rel_example = 'ResultFiles/FM_ARC_DigitalHub_with_SB11.ifc'
    # rel_example = 'ResultFiles/Proposal_1_Storey_SpaceBoundaries_with_SB.ifc'
    # rel_example = 'ResultFiles/2020-10-15-KHH-Test_with_SB.ifc'
    # rel_example = 'ExampleFiles/AC20-Institute-Var-2.ifc'
    # rel_example = 'ExampleFiles/DigitalHub_Architektur2_2020_Achse_tragend_V2.ifc' # ok
    # rel_example = 'ExampleFiles/AC-20-Smiley-West-10-Bldg.ifc'
    path_ifc = os.path.normpath(os.path.join(path_base, rel_example))

    path_example = _get_debug_project_path()

    if not PROJECT.is_project_folder(path_example):
        PROJECT.create(path_example, path_ifc, 'energyplus')

    main(path_example)


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
    try:
        print("Project directory: " + path_example)
        os.chdir(path_example)
        if not PROJECT.is_project_folder(path_example):
            PROJECT.create(path_example, path_ifc, 'energyplus')

        #HACK: We have to remember stderr because eppy resets it currently.
        success = main(path_example)
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

    if not PROJECT.is_project_folder(path_example):
        PROJECT.create(path_example, path_ifc, 'aixlib',)


def _debug_run_cfd():
    """Create example project and copy ifc if necessary"""

    sys.path.append("/home/fluid/Schreibtisch/B/bim2sim-coding/PluginCFD")
    path_example = r"/home/fluid/Schreibtisch/B/temp"
    # unter ifc muss datei liegen

    if not PROJECT.is_project_folder(path_example):
        PROJECT.create(path_example, target='cfd')
    return main(path_example)


if __name__ == '__main__':
    # _debug_run_cfd()
    _debug_run_bps()
    # _debug_run_bps_ep()
    # _debug_run_hvac()

