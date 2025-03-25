"""check ifc input file manly based on IDS files"""

import ifcopenshell
import ifctester
import ifctester.ids
import ifctester.reporter
import webbrowser



def run_check_guid(ifc_file: str) -> (bool, dict, dict):
    """check the uniqueness of the guids of the IFC file

    Input:
        ifc_file: path of the IFC file, which is checked

    Returns:
        all_guids_unique: boolean
                      (true: all guids are unique
                       false: one or more guids are not unique)
       double_guid: dict
       guids_none: dict
    """
    model = ifcopenshell.open(ifc_file)

    used_guids: dict[str, ifcopenshell.entity_instance] = dict() # dict of all elements with guids used in the checked ifc model
    double_guids: dict[str, ifcopenshell.entity_instance] = dict() # dict of elements with guids, which are not unique
    all_guids_unique = True
    # TODO entries of the guid_none list should include an attribute value, which helps to identify the element
    guids_none : dict[str, ifcopenshell.entity_instance] = dict() # dict of elements, which have a guid value = None
    guid_none_no = 0
    for inst in model:
       if hasattr(inst, "GlobalId"):
           guid = inst.GlobalId
           name = inst.Name
           # print(guid)
           if guid in used_guids:
               print(guid)
               double_guids[guid] = inst
               all_guids_unique = False
           elif guid in ['', 'None']:
               # TODO if possible to check "guid = None/''" delete this region
               # and adapt whole function
               all_guids_unique = False
               guid_none_no = guid_none_no + 1
               name_dict = name + '--' + str(guid_none_no)
               print("none: {}".format(name))

               guids_none[name_dict] = inst
           else:
               used_guids[guid] = inst
    return (all_guids_unique, double_guids, guids_none)


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
    for spec in my_ids.specifications:
        print("name: {}, passed: {}".format(spec.name, spec.status))
        if not spec.status:
            all_spec_pass = False
    print(">>>>>> ")
    print("all checks of the specifications of this IDS pass: {}".format(all_spec_pass))
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
    guid_check_passed, double_guid = run_check_guid(ifc_file_guid_error)
