#import tempfile
#from pathlib import Path

#from bim2sim import Project, run_project, ConsoleDecisionHandler
#from bim2sim.log import default_logging_setup
#from bim2sim.task import common, bps
#from ifcopenshell.file import file
#from bim2sim.kernel.ifc2python import get_property_sets
#from bim2sim.kernel import ifc2python
#import os
#from ifcopenshell import entity_instance, file, open as ifc_open
from pathlib import Path
import ifcopenshell


def run_example_6():
    ifc_path = Path(__file__).parent.parent \
               / 'assets/ifc_example_files/AC20-FZK-Haus.ifc'
    #ifc = ifc2python.load_ifc(os.path.abspath(ifc_path))
    #ifc = ifc2python.reset_guids(ifc)
    #t = ifc_open(f"C:/02_Masterarbeit/09_bim2sim/bim2sim/bim2sim/assets/ifc_example_files/AC20-FZK-Haus.ifc")
    model = ifcopenshell.open(ifc_path)
    print(model.schema)
    print(model.by_id(1))



if __name__ == '__main__':
    run_example_6()
    print("finish")

