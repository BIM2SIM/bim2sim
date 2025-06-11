"""check ifc input file manly based on IDS files"""

import ifcopenshell
import ifctester
import ifctester.ids
import ifctester.reporter
import webbrowser

from bim2sim.tasks.base import ITask, Playground

from bim2sim.kernel.ifc_file import IfcFileClass

class CheckIfc(ITask):
    """
    Check ifc file for their quality regarding simulation.
    TODO rename Task CheckIfcNew >> CheckIfc and remove the old CheckIfc
    """
    reads = ('ifc_files',)

    # def __init__(self, playground: Playground):
    #     super().__init__(playground)
    #     self.error_summary_sub_inst: dict = {}
    #     self.error_summary_inst: dict = {}
    #     self.error_summary_prop: dict = {}
    #     self.sub_inst: list = []
    #     self.id_list: list = []
    #     self.elements: list = []
    #     self.ps_summary: dict = {}
    #     self.ifc_units: dict = {}
    #     self.sub_inst_cls = None
    #     self.plugin = None

    def run(self, ifc_files: [IfcFileClass]):
        """
        Analyzes sub_elements and elements of an IFC file for the validation
        functions and export the errors found as .json and .html files.

        """
        print("Task CheckIfc says Hello")
        self.logger.info(f"Processing IFC Check without ifcTester")
        paths = self.paths
        for ifc_file in ifc_files:
            self.run_check_guid_unique(ifc_file)
    

    def run_check_guid_unique(self, ifc_file) -> (bool, dict):
        """check the uniqueness of the guids of the IFC file

        Input:
            ifc_file: path of the IFC file, which is checked

        Returns:
            all_guids_unique: boolean
                          (true: all guids are unique
                           false: one or more guids are not unique)

           double_guid: dict

        """
        # TODO check this function with "false" ifc files
        # TODO and adapt the tests in test folder
        # TODO bring output into the log
        used_guids: dict[str, ifcopenshell.entity_instance] = dict() # dict of all elements with guids used in the checked ifc model
        double_guids: dict[str, ifcopenshell.entity_instance] = dict() # dict of elements with guids, which are not unique
        all_guids_unique = True

        for inst in ifc_file.file:
           if hasattr(inst, "GlobalId"):
               guid = inst.GlobalId
               name = inst.Name
               # print(guid)
               if guid in used_guids:
                   double_guids[guid] = inst
                   all_guids_unique = False
               else:
                   used_guids[guid] = inst

        list_guids_non_unique = list(double_guids.keys())
        print(">>>>>> ")
        print("the GUIDs of all elements are unique: {}".format(all_guids_unique))
        if all_guids_unique is False:
            print("non-unique GUIDs: {}".format(list_guids_non_unique))
        print("<<<<<<")
        return (all_guids_unique, double_guids)

def run_check_guid_empty(ifc_file: str) -> (bool, dict):
    """check it there is/are guid/s, which is/are empty in the IFC file

    Input:
        ifc_file: path of the IFC file, which is checked

    Returns:
        all_guids_filled: boolean
                      (true: all guids has a value (not empty)
                       false: one or more guids has not value (empty))

       empty_guid: dict

    """
    model = ifcopenshell.open(ifc_file)

    used_guids: dict[str, ifcopenshell.entity_instance] = dict() # dict of all elements with guids used in the checked ifc model
    empty_guids: dict[str, ifcopenshell.entity_instance] = dict() # dict of elements with guids, which are empty
    all_guids_filled = True
    guid_empty_no = 0 # count the number of guids without value (empty), this number is used to make unique identifier
    for inst in model:
       if hasattr(inst, "GlobalId"):
           guid = inst.GlobalId
           name = inst.Name
           # print(guid)
           # if guid in used_guids:
           #     double_guids[guid] = inst
           #     all_guids_unique = False
           if guid == '':
               all_guids_filled = False
               guid_empty_no = guid_empty_no + 1
               name_dict = name + '--' + str(guid_empty_no)
               print("none: {}".format(name))

               empty_guids[name_dict] = inst
           else:
               used_guids[guid] = inst

    list_guids_empty = list(empty_guids.keys())
    print(">>>>>> ")
    print("the GUIDs of all elements are filled (NOT empty): {}".format(all_guids_filled))
    if all_guids_filled is False:
        print("empty GUIDs: {}".format(list_guids_empty))
    print("<<<<<<")
    return (all_guids_filled, empty_guids)

def run_ids_check_on_ifc(ifc_file: str, ids_file: str, report_html: bool = False) -> bool:
    """run check on IFC file based on IDS

    print the check of specifications pass(true) or fail(false)
    and the name of the specification
    and if all specifications of one IDS pass

    Input:
        ifc_file: path of the IFC file, which is checked
        ids_file: path of the IDS file, which includes the specifications
        TODO: implete report_html feature, see howto use report down below
        report_html: generate, save and open the report about checking
                     default = False
    Returns:
        all_spec_pass: boolean
                      (true: all specification passed,
                       false: one or more specification not passed)
    """
    model = ifcopenshell.open(ifc_file)
    my_ids = ifctester.ids.open(ids_file)
    my_ids.validate(model)
    all_spec_pass = True
    print(">>>>>> ")
    for spec in my_ids.specifications:
        print("name: {}, passed: {}".format(spec.name, spec.status))
        if not spec.status:
            all_spec_pass = False
    print("---")
    print("all checks of the specifications of this IDS pass: {}".format(all_spec_pass))
    print("---")
    print("<<<<<<")
    return all_spec_pass

# for check the results of return above
# ifctester.reporter.Console(my_ids).report()

# engine = ifctester.reporter.Html(my_ids)
# engine.report()
# output_path = '/home/cudok/Documents/12_ifc_check_ids/02_development/test2.html'
# engine.to_file(output_path)
# webbrowser.open(f"file://{output_path}")
#+end_src

if __name__ == '__main__':

    # TODO: Remove, only needed while develope first prototype
    ifc_file = '/home/cudok/Documents/10_Git/bim2sim/test/resources/arch/ifc/AC20-FZK-Haus_with_SB55.ifc'
    ifc_file_copy = '/home/cudok/Documents/12_ifc_check_ids/AC20-FZK-Haus_with_SB55_copyGUID.ifc'
    ifc_file_guid_error = '/home/cudok/Documents/12_ifc_check_ids/AC20-FZK-Haus_with_SB55_NoneAndDoubleGUID.ifc'
    # ids_file = '/home/cudok/Documents/12_ifc_check_ids/ifc_check_spaces(3).ids'
    guid_check_passed, double_guid = run_check_guid_unique(ifc_file_guid_error)
