"""check ifc input file manly based on IDS files"""

import ifcopenshell
import ifctester
import ifctester.ids
import ifctester.reporter
import webbrowser

# TODO: Remove, only needed while develope first prototype
ifc_file = '/home/cudok/Documents/10_Git/bim2sim/test/resources/arch/ifc/AC20-FZK-Haus_with_SB55.ifc'
# ids_file = '/home/cudok/Documents/12_ifc_check_ids/ifc_check_spaces(3).ids'

def run_check_guid(ifc_file: str) -> bool:
    """check the uniqueness of the guids of the IFC file

    Input:
        ifc_file: path of the IFC file, which is checked

    Returns:
        all_guids_unique: boolean
                      (true: all guids are unique
                       false: one or more guids are not unique)
    """
    model = ifcopenshell.open(ifc_file)
    return True


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
