"""Check ifc input file mainly based on IDS files."""

import os

from pathlib import Path

from typing import Callable  # , Dict

import ifcopenshell as ifcos # TODO check which modules are used and append them to the line below
from ifcopenshell import entity_instance  # ,file
import ifctester
import ifctester.ids
import ifctester.reporter
import webbrowser


from mako.lookup import TemplateLookup
from mako.template import Template

from bim2sim.elements import bps_elements as bps  # , hvac_elements as hvac
from bim2sim.tasks.base import ITask, Playground

from bim2sim.kernel.ifc_file import IfcFileClass
from bim2sim.utilities.types import IFCDomain

class CheckIfc(ITask):
    """
    Check ifc files for their quality regarding simulation.
    """
    reads = ('ifc_files',)

    # TODO remove self attributes, which not needed
    def __init__(self, playground: Playground):
        super().__init__(playground)
        self.error_summary_sub_inst: dict = {}
        self.error_summary_inst: dict = {}
        self.error_summary_prop: dict = {}
        self.error_version: bool = False
        self.ifc_version: str = None
        self.all_guids_unique: bool = True
        self.double_guids: dict = {}
        self.all_guids_filled: bool = True
        self.empty_guids: dict = {}
        self.sub_inst: list = []
        self.id_list: list = []
        self.elements: list = []
        self.ps_summary: dict = {}
        self.ifc_units: dict = {}
        # TODO maybe not needed her, because set in logic class
        # uses for filerting prepare check
        self.sub_inst_cls = None
        self.plugin = None

    def run(self, ifc_files: [IfcFileClass]):
        """
        Analyzes sub_elements and elements of an IFC file for the validation
        functions and export the errors found as .json and .html files.

        """
        print("Task CheckIfc says Hello")

        self.logger.info(f"Processing IFC Checks with ifcTester")

        base_path = self.paths.ifc_base
        # begin part from load_ifc.py
        # used to get path of the ifc file for ifctester
        if not base_path.is_dir():
            raise AssertionError(f"Given base_path {base_path} is not a"
                                 f" directory. Please provide a directory.")

        ifc_files_paths = list(base_path.glob("**/*.ifc")) + list(
            base_path.glob("**/*.ifcxml")) + list(
            base_path.glob("**/*.ifczip"))
        self.logger.info(f"Found {len(ifc_files_paths)} IFC files in project "
                         f"directory.")
        # end part from load_ifc.py
        log_path = self.paths.log
        ids_file_path = self.playground.sim_settings.ids_file_path
        for ifc_file_path in ifc_files_paths:
            all_spec_pass = self.run_ids_check_on_ifc(
                ifc_file_path, ids_file_path,
                report_html=True, log_path=log_path)

            if all_spec_pass:
                self.logger.info(
                    "all checks of the specifications of this IDS pass: {}".format(all_spec_pass))
            else:
                self.logger.warning(
                    "all checks of the specifications of this IDS pass: {}".format(all_spec_pass))

        self.logger.info(f"Processing IFC Checks without ifcTester")

        paths = self.paths  # TODO needed in if loop, here need better solution
        for ifc_file in ifc_files:
            # checks are domain specific
            # Reset class based on domain to run the right check.
            # Not pretty but works. This might be refactored in #170

            # check uniqueness of GUIDs
            self.all_guids_unique, self.double_guids = CheckLogicBase.run_check_guid_unique(ifc_file)
            list_guids_non_unique = list(self.double_guids.keys())
            self.logger.info("the GUIDs of all elements are unique: {}".format(self.all_guids_unique))
            if self.all_guids_unique is False:
                self.logger.critical("non-unique GUIDs: {}".format(list_guids_non_unique))
            # check emptyness of GUID fields
            self.all_guids_filled, self.empty_guids = CheckLogicBase.run_check_guid_empty(ifc_file)
            list_guids_empty = list(self.empty_guids.keys())
            self.logger.info("the GUIDs of all elements are filled (NOT empty): {}".format(self.all_guids_filled))
            if self.all_guids_filled is False:
                self.logger.critical("empty GUIDs: {}".format(list_guids_empty))
            # check ifc version
            self.version_error, self.ifc_version = CheckLogicBase.run_check_ifc_version(ifc_file)
            # for doc string
            #   Logs:
            #       critical: if loaded IFC is not IFC4
            if self.version_error:
                self.logger.critical(f"ifc Version is not fitting. Should be IFC4, but here: " + self.ifc_version)

            if ifc_file.domain == IFCDomain.hydraulic:
                self.logger.info(f"Processing HVAC-IfcCheck")  # todo
            elif ifc_file.domain == IFCDomain.arch:
                self.logger.info(f"Processing BPS-IfcCheck")  # todo
                # used for preparing data for checking, is filder keyword
                self.sub_inst_cls = 'IfcRelSpaceBoundary'
                self.sub_inst = ifc_file.file.by_type(self.sub_inst_cls)
                # checking itself
                chlb = CheckLogicBase(self.sub_inst)
                self.error_summary_sub_inst = chlb.check_inst_sub()
                self.paths = paths  # TODO needed in if loop, here need better solution
            elif ifc_file.domain == IFCDomain.unknown:
                self.logger.info(f"No domain specified for ifc file "
                                 f"{ifc_file.ifc_file_name}, not processing "
                                 f"any checks")
                return
            else:
                self.logger.info(
                    f"For the Domain {ifc_file.domain} no specific checks are"
                    f" implemented currently. Just running the basic checks."
                    f"")

            ## begin copy form old ifc check (only tempory until new structure is working)



            ## end copy form old ifc check (only tempory until new structure is working)

            # write reportes self made checks
            base_name = f"/{ifc_file.domain.name.upper()}_" \
                        f"{ifc_file.ifc_file_name[:-4]}"
            self._write_errors_to_html_table(base_name, ifc_file.domain)


    def validate_sub_inst(self, sub_inst: list) -> list:
        raise NotImplementedError





    @staticmethod
    def run_ids_check_on_ifc(ifc_file: str, ids_file: str, report_html: bool = False, log_path: str = None) -> bool:
        """run check on IFC file based on IDS

        print the check of specifications pass(true) or fail(false)
        and the name of the specification
        and if all specifications of one IDS pass

        Input:
            ifc_file: path of the IFC file, which is checked
            ids_file: path of the IDS file, which includes the specifications
            log_path: path of the log folder as part of the project structur 
            report_html: generate, save and open the report about checking
                         default = False
        Returns:
            all_spec_pass: boolean
                          (true: all specification passed,
                           false: one or more specification not passed)
        """
        model = ifcos.open(ifc_file)
        my_ids = ifctester.ids.open(ids_file)
        my_ids.validate(model)
        all_spec_pass = True
        for spec in my_ids.specifications:
            if not spec.status:
                all_spec_pass = False

        # generate html report
        if report_html:
            engine = ifctester.reporter.Html(my_ids)
            engine.report()
            output_file = Path(log_path / 'ifc_ids_check.html')
            engine.to_file(output_file)
            # can comment out, if not the browser should show the report
            webbrowser.open(f"file://{output_file}")

        return all_spec_pass

    def get_html_templates(self):
        """
        Gets all stored html templates that will be used to export the errors
        summaries

        Returns:
            templates: dictionary containing all error html templates
        """
        templates = {}
        path_templates = os.path.join(
            self.paths.assets, "templates", "check_ifc")
        lookup = TemplateLookup(directories=[path_templates])
        templates["inst_template"] = Template(
            filename=os.path.join(path_templates, "inst_template"),
            lookup=lookup)
        templates["prop_template"] = Template(
            filename=os.path.join(path_templates, "prop_template"),
            lookup=lookup)
        templates["summary_template"] = Template(
            filename=os.path.join(path_templates, "summary_template_extend"),
            lookup=lookup)
        templates["guid_template"] = Template(
            filename=os.path.join(path_templates, "guid_template"),
            lookup=lookup)
        return templates

    @staticmethod
    def _categorize_errors(error_dict: dict):
        """
        categorizes the resulting errors in a dictionary containing two groups:
            'per_error' where the key is the error name and the value is the
                number of errors with this name
            'per type' where the key is the ifc_type and the values are the
                each element with its respective errors
        Args:
            error_dict: dictionary containing all errors without categorization

        Returns:
            categorized_dict: dictionary containing all errors categorized

        """
        categorized_dict = {'per_error': {}, 'per_type': {}}
        for instance, errors in error_dict.items():
            if ' ' in instance:
                guid, ifc_type = instance.split(' ')
            else:
                guid = '-'
                ifc_type = instance
            if ifc_type not in categorized_dict['per_type']:
                categorized_dict['per_type'][ifc_type] = {}
            categorized_dict['per_type'][ifc_type][guid] = errors
            for error in errors:
                error_com = error.split(' - ')
                if error_com[0] not in categorized_dict['per_error']:
                    categorized_dict['per_error'][error_com[0]] = 0
                categorized_dict['per_error'][error_com[0]] += 1
        return categorized_dict

    def _write_errors_to_html_table(self, base_name: str, domain: IFCDomain):
        """
        Writes all errors in the html templates in a summarized way

        Args:
            base_name: str of file base name for reports
            domain: IFCDomain of the checked IFC
        """
        show_report = True # enable the automatic popup of the reports
        templates = self.get_html_templates()
        summary_inst = self._categorize_errors(self.error_summary_inst)
        summary_sbs = self._categorize_errors(self.error_summary_sub_inst)
        summary_props = self._categorize_errors(self.error_summary_prop)
        all_errors = {**summary_inst['per_type'], **summary_sbs['per_type']}

        with open(str(self.paths.log) +
                  base_name +
                  '_error_summary_inst.html', 'w+') as \
                out_file:
            out_file.write(templates["inst_template"].render_unicode(
                task=self,
                summary_inst=summary_inst,
                summary_sbs=summary_sbs,
                all_errors=all_errors))
            out_file.close()
            if show_report:
                # can comment out, if not the browser should show the report
                webbrowser.open(f"file://{out_file.buffer.name}")
        with open(str(self.paths.log) +
                  base_name +
                  '_error_summary_prop.html', 'w+') as \
                out_file:
            out_file.write(templates["prop_template"].render_unicode(
                task=self,
                summary_props=summary_props))
            out_file.close()
            if show_report:
                # can comment out, if not the browser should show the report
                webbrowser.open(f"file://{out_file.buffer.name}")
        with open(str(self.paths.log) +
                  base_name +
                  '_error_summary.html', 'w+') as out_file:
            out_file.write(templates["summary_template"].render_unicode(
                ifc_version=self.ifc_version,
                version_error = self.version_error,
                all_guids_unique = self.all_guids_unique,
                double_guids = self.double_guids,
                all_guids_filled = self.all_guids_filled,
                empty_guids = self.empty_guids,
                task=self,
                plugin_name=domain.name.upper(),
                base_name=base_name[1:],
                summary_inst=summary_inst,
                summary_sbs=summary_sbs,
                summary_props=summary_props))
            out_file.close()
            if show_report:
                # can comment out, if not the browser should show the report
                webbrowser.open(f"file://{out_file.buffer.name}")

        with open(str(self.paths.log) + base_name + '_error_summary_guid.html',
                  'w+') as \
                out_file:
            out_file.write(templates["guid_template"].render_unicode(
                task=self,
                double_guids = self.double_guids,
                empty_guids = self.empty_guids,
                summary_inst=summary_inst,
                summary_sbs=summary_sbs,
                all_errors=all_errors))
            out_file.close()
            if show_report:
                # can comment out, if not the browser should show the report
                webbrowser.open(f"file://{out_file.buffer.name}")


class CheckIfcBPS(CheckIfc):
    """
    Check an IFC file, for a number of conditions (missing information,
    incorrect information, etc.) that could lead on future tasks to
    fatal errors.
    """

    def __init__(self, playground: Playground, ):
        super().__init__(playground)
        # used for preparing data for checking, is filder keyword
        self.sub_inst_cls = 'IfcRelSpaceBoundary'
        self.plugin = bps
        self.space_indicator = True

    @staticmethod
    def _check_rel_space(bound: entity_instance):
        """
        Check that the space boundary relating space exists and has the
        correct class.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return any(
            [bound.RelatingSpace.is_a('IfcSpace') or
             bound.RelatingSpace.is_a('IfcExternalSpatialElement')])

    @staticmethod
    def _check_rel_building_elem(bound: entity_instance):
        """
        Check that the space boundary related building element exists and has
        the correct class.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        if bound.RelatedBuildingElement is not None:
            return bound.RelatedBuildingElement.is_a('IfcElement')

    def validate_sub_inst(self, bound: entity_instance) -> list:
        """
        Validation function for a space boundary that compiles all validation
        functions.

        Args:
            bound: ifc space boundary entity

        Returns:
            error: list of errors found in the ifc space boundaries
        """
        error = []
        self.apply_validation_function(self._check_rel_space(bound),
                                       'RelatingSpace - '
                                       'The space boundary does not have a '
                                       'relating space associated', error)
        self.apply_validation_function(self._check_rel_building_elem(bound),
                                       'RelatedBuildingElement - '
                                       'The space boundary does not have a '
                                       'related building element associated',
                                       error)
        return error


class CheckLogicBase():
    """Provides logic for ifc files checking regarding simulation.

    This is a base class. This base class includes all check logic, which is
    useful for all checking use cases.
    """

    def __init__(self, sub_inst):
        # # used for preparing data for checking, is filder keyword
        # self.sub_inst_cls = 'IfcRelSpaceBoundary'
        self.plugin = bps
        self.space_ndicator = True
        # prepare data for checking (filering)
        self.sub_inst = sub_inst

    def run_check_guid_unique(ifc_file) -> (bool, dict):
        """check the uniqueness of the guids of the IFC file

        Input:
            ifc_file: path of the IFC file, which is checked

        Returns:
            all_guids_unique: boolean
                          (true: all guids are unique
                           false: one or more guids are not unique)

           double_guid: dict

        """
        # TODO bring output into the log
        used_guids: dict[str, ifcos.entity_instance] = dict() # dict of all elements with guids used in the checked ifc model
        double_guids: dict[str, ifcos.entity_instance] = dict() # dict of elements with guids, which are not unique
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

        return (all_guids_unique, double_guids)

    def run_check_guid_empty(ifc_file) -> (bool, dict):
        """check it there is/are guid/s, which is/are empty in the IFC file

        Input:
            ifc_file: path of the IFC file, which is checked

        Returns:
            all_guids_filled: boolean
                          (true: all guids has a value (not empty)
                           false: one or more guids has not value (empty))

           empty_guid: dict

        """

        used_guids: dict[str, ifcos.entity_instance] = dict() # dict of all elements with guids used in the checked ifc model
        empty_guids: dict[str, ifcos.entity_instance] = dict() # dict of elements with guids, which are empty
        all_guids_filled = True
        guid_empty_no = 0 # count the number of guids without value (empty), this number is used to make unique identifier
        for inst in ifc_file.file:
           if hasattr(inst, "GlobalId"):
               guid = inst.GlobalId
               name = inst.Name
               if guid == '':
                   all_guids_filled = False
                   guid_empty_no = guid_empty_no + 1
                   name_dict = name + '--' + str(guid_empty_no)
                   empty_guids[name_dict] = inst
               else:
                   used_guids[guid] = inst

        return (all_guids_filled, empty_guids)


    @staticmethod
    def run_check_ifc_version(ifc: ifcos.file) -> (bool, str):
        """
        Checks the IFC version.

        Only IFC4 files are valid for bim2sim.

        Attention: no Error is raised anymore.

        Args:
            ifc: ifc file loaded with IfcOpenShell
        Return:
            version_error: True if version NOT fit
            ifc_version: version of the ifc file
        """
        schema = ifc.schema
        if "IFC4" not in schema:
            version_error = True
            # raise TypeError(f"Loaded IFC file is of type {schema} but only IFC4"
            #                 f"is supported. Please ask the creator of the model"
            #                 f" to provide a valid IFC4 file.")
        else:
            version_error = False
        return (version_error, schema)


    ###### old ifc check, maybe stay here

    def check_inst_sub(self):
        """Proide the data to check_inst function related to sub inst.
        """
        error_summary_sub_inst = self.check_inst(
                    self.validate_sub_inst, self.sub_inst)
        return error_summary_sub_inst

    @staticmethod
    def check_inst(validation_function: Callable, elements: list):
        """Uses sb_validation/ports/elements functions in order to check each
        one and adds error to dictionary if object has errors. Combines the
        (error) return of the specific validation function with the key (mostly
        the GlobalID).

        Args: validation_function: function that compiles all the
        validations to be performed on the object (sb/port/instance) elements:
        list containing all objects to be evaluates

        Returns:
            summary: summarized dictionary of errors, where the key is the
                GUID + the ifc_type

        """
        summary = {}
        for inst in elements:
            error = validation_function(inst)
            if len(error) > 0:
                if hasattr(inst, 'GlobalId'):
                    key = inst.GlobalId + ' ' + inst.is_a()
                else:
                    key = inst.is_a()
                summary.update({key: error})
        return summary

    @staticmethod
    def apply_validation_function(fct: bool, err_name: str, error: list):
        """
        Function to apply a validation to an instance, space boundary or
        port, it stores the error to the list of errors.

        Args:
            fct: validation function to be applied
            err_name: string that define the error
            error: list of errors

        """
        if not fct:
            error.append(err_name)

    ###### old ifc check, maybe stay here

    @staticmethod
    def _check_rel_space(bound: entity_instance):
        """
        Check that the space boundary relating space exists and has the
        correct class.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return any(
            [bound.RelatingSpace.is_a('IfcSpace') or
             bound.RelatingSpace.is_a('IfcExternalSpatialElement')])

    @staticmethod
    def _check_rel_building_elem(bound: entity_instance):
        """
        Check that the space boundary related building element exists and has
        the correct class.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        if bound.RelatedBuildingElement is not None:
            return bound.RelatedBuildingElement.is_a('IfcElement')

    def validate_sub_inst(self, bound: entity_instance) -> list:
        """
        Validation function for a space boundary that compiles all validation
        functions.

        Args:
            bound: ifc space boundary entity

        Returns:
            error: list of errors found in the ifc space boundaries
        """
        error = []
        self.apply_validation_function(self._check_rel_space(bound),
                                       'RelatingSpace - '
                                       'The space boundary does not have a '
                                       'relating space associated', error)
        self.apply_validation_function(self._check_rel_building_elem(bound),
                                       'RelatedBuildingElement - '
                                       'The space boundary does not have a '
                                       'related building element associated',
                                       error)
        return error


class CheckLogicBPS(CheckLogicBase):
    """Provides additional logic for ifc files checking regarding BPS."""




if __name__ == '__main__':
    pass
