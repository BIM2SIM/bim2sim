"""Check ifc input file mainly based on IDS files."""

import inspect  # used for _get_ifc_type_classes
import types  # used for _get_class_property_sets
import os
import warnings

from pathlib import Path

from typing import Callable, Dict  # Dict used for _get_class_property_sets

import ifcopenshell as ifcos
from bim2sim.utilities.common_functions import all_subclasses  # used in _get_ifc_type_classes
from bim2sim.elements.mapping import attribute  # used in _get_ifc_type_classes
# get_layer_ifc needed for _check_inst_materials
from bim2sim.elements.mapping.ifc2python import get_layers_ifc, \
    get_property_sets, get_ports

import ifctester.ids
import ifctester.reporter
import webbrowser


from mako.lookup import TemplateLookup
from mako.template import Template

from bim2sim.elements import bps_elements as bps, hvac_elements as hvac
from bim2sim.tasks.base import ITask, Playground

from bim2sim.kernel.ifc_file import IfcFileClass
from bim2sim.utilities.types import IFCDomain
from bim2sim import __file__ as bs_file
from bim2sim.tasks.common.load_ifc import extract_ifc_file_names


class CheckIfc(ITask):
    """Check ifc files for their quality regarding simulation."""

    reads = ('ifc_files',)

    def __init__(self, playground: Playground):
        """Initialize CheckIFC."""
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
        self.sub_inst_cls = None
        self.plugin = None

    def run(self, ifc_files: [IfcFileClass]):
        """
        Analyzes sub_elements and elements of an IFC file.

        Therefore validation functions check ifc files and export the errors
        found as .html files.

        It creates following reports:
            error_summary: overview of all errors
            error_summary_inst: summary of errors related to elements
            error_summary_prop: summary of missing properties
            error_summary_guid: summary of GUID errors
            ifc_ids_check: results of checks based on IDS file
        These html files are stored in the log folder of the project folder.

        Args:
            ifc_files: bim2sim IfcFileClass holding the ifcopenshell ifc
                instance
        """
        self.logger.info("Processing IFC Checks with ifcTester")

        base_path = self.paths.ifc_base

        ifc_files_paths = extract_ifc_file_names(base_path)
        self.logger.info(f"Found {len(ifc_files_paths)} IFC files in project "
                         f"directory.")

        log_path = self.paths.log
        # ids check call start
        if self.playground.sim_settings.ids_file_path is None:
            self.logger.critical("Default ids file is used, pls set " +
                                 "project.sim_settings.ids_file_path!")
            self.playground.sim_settings.ids_file_path = (
                Path(bs_file).parent /
                'plugins/PluginIFCCheck/bim2sim_ifccheck/ifc_bps.ids'
            )

        ids_file_path = self.playground.sim_settings.ids_file_path
        for ifc_file_path in ifc_files_paths:
            all_spec_pass = self.run_ids_check_on_ifc(
                ifc_file_path, ids_file_path,
                report_html=True, log_path=log_path)

            if all_spec_pass:
                self.logger.info(
                    "all checks of the specifications of this IDS pass: " +
                    "{}".format(all_spec_pass))
            else:
                self.logger.warning(
                    "all checks of the specifications of this IDS pass: " +
                    "{}".format(all_spec_pass))
        # ids check call end

        self.logger.info("Processing IFC Checks without ifcTester")

        paths = self.paths
        for ifc_file in ifc_files:
            # checks are domain specific
            # Reset class based on domain to run the right check.
            # Not pretty but works. This might be refactored in #170

            # check uniqueness of GUIDs
            self.all_guids_unique, self.double_guids = (
                CheckLogicBase.run_check_guid_unique(ifc_file)
                )
            list_guids_non_unique = list(self.double_guids.keys())
            self.logger.info("the GUIDs of all elements are unique: " +
                             "{}".format(self.all_guids_unique))
            if self.all_guids_unique is False:
                self.logger.critical("non-unique GUIDs: " +
                                     "{}".format(list_guids_non_unique))
            # check emptyness of GUID fields
            self.all_guids_filled, self.empty_guids = (
                CheckLogicBase.run_check_guid_empty(ifc_file)
                )
            list_guids_empty = list(self.empty_guids.keys())
            self.logger.info("the GUIDs of all elements are filled " +
                             "(NOT empty): {}".format(self.all_guids_filled))
            if self.all_guids_filled is False:
                self.logger.critical("empty GUIDs: {}".format(list_guids_empty))
            # check ifc version
            self.version_error, self.ifc_version = (
                CheckLogicBase.run_check_ifc_version(ifc_file)
                )
            # for doc string
            #   Logs:
            #       critical: if loaded IFC is not IFC4
            if self.version_error:
                self.logger.critical("ifc Version is not fitting. " +
                                     "Should be IFC4, but here: " +
                                     self.ifc_version)

            if ifc_file.domain == IFCDomain.hydraulic:
                self.logger.info("Processing HVAC-IfcCheck")
                # used for preparing data for checking, is finder keyword
                self.sub_inst_cls = 'IfcDistributionPort'
                self.plugin = hvac
                self.ps_summary = self._get_class_property_sets(self.plugin)
                self.sub_inst = ifc_file.file.by_type(self.sub_inst_cls)
                self.elements = self.get_relevant_elements(ifc_file.file)
                self.ifc_units = ifc_file.ifc_units
                # checking itself
                chlhvac = CheckLogicHVAC(self.sub_inst, self.elements,
                                         self.ps_summary, self.ifc_units)
                self.error_summary_sub_inst = chlhvac.check_inst_sub()
                self.error_summary_inst = chlhvac.check_elements()

            elif ifc_file.domain == IFCDomain.arch:
                self.logger.info("Processing BPS-IfcCheck")
                # used for preparing data for checking, is finder keyword
                self.sub_inst_cls = 'IfcRelSpaceBoundary'
                self.plugin = bps
                self.ps_summary = self._get_class_property_sets(self.plugin)
                self.sub_inst = ifc_file.file.by_type(self.sub_inst_cls)
                self.elements = self.get_relevant_elements(ifc_file.file)
                self.ifc_units = ifc_file.ifc_units
                # checking itself
                chlbps = CheckLogicBPS(self.sub_inst, self.elements,
                                       self.ps_summary, self.ifc_units)
                self.error_summary_sub_inst = chlbps.check_inst_sub()
                self.error_summary_inst = chlbps.check_elements()
                self.error_summary_prop = chlbps.error_summary_prop
                self.paths = paths
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

            # generating reports (of the additional checks)
            base_name = f"/{ifc_file.domain.name.upper()}_" \
                        f"{ifc_file.ifc_file_name[:-4]}"
            self._write_errors_to_html_table(base_name, ifc_file.domain)

    def get_relevant_elements(self, ifc: ifcos.file):
        """Get all relevant ifc elements.

        This function based on the plugin's classes that
        represent an IFCProduct.

        Args:
            ifc: IFC file translated with ifcopenshell

        Returns:
            ifc_elements: list of IFC instance (Products)
        """
        relevant_ifc_types = list(self.ps_summary.keys())
        ifc_elements = []
        for ifc_type in relevant_ifc_types:
            ifc_elements.extend(ifc.by_type(ifc_type))
        return ifc_elements

    @staticmethod
    def _get_ifc_type_classes(plugin: types.ModuleType):
        """Get all the classes of a plugin that represent an IFCProduct.

        Furthermore, organize them on a dictionary for each ifc_type.
        Args:
            plugin: plugin used in the check tasks (bps or hvac)

        Returns:
            cls_summary: dictionary containing all the ifc_types on the
            plugin with the corresponding class
        """
        plugin_classes = [plugin_class[1] for plugin_class in
                          inspect.getmembers(plugin, inspect.isclass) if
                          inspect.getmro(plugin_class[1])[1].__name__.endswith(
                              'Product')]
        cls_summary = {}

        for plugin_class in plugin_classes:
            # class itself
            if plugin_class.ifc_types:
                for ifc_type in plugin_class.ifc_types.keys():
                    cls_summary[ifc_type] = plugin_class
            # sub classes
            for subclass in all_subclasses(plugin_class):
                for ifc_type in subclass.ifc_types.keys():
                    cls_summary[ifc_type] = subclass
        return cls_summary

    @classmethod
    def _get_class_property_sets(cls, plugin: types.ModuleType) -> Dict:
        """Get all property sets and properties.

        Which are required for bim2sim for all classes of a plugin, that
        represent an IFCProduct, and organize them on a dictionary for each
        ifc_type Args: plugin: plugin used in the check tasks (bps or hvac)

        Returns:
            ps_summary: dictionary containing all the ifc_types on the
            plugin with the corresponding property sets

        """
        ps_summary = {}
        cls_summary = cls._get_ifc_type_classes(plugin)
        for ifc_type, plugin_class in cls_summary.items():
            attributes = inspect.getmembers(
                plugin_class, lambda a: isinstance(a, attribute.Attribute))
            ps_summary[ifc_type] = {}
            for attr in attributes:
                if attr[1].default_ps:
                    ps_summary[ifc_type][attr[0]] = attr[1].default_ps
        return ps_summary

    def validate_sub_inst(self, sub_inst: list) -> list:
        """Raise NotImplemented Error."""
        raise NotImplementedError

    @staticmethod
    def run_ids_check_on_ifc(ifc_file: str, ids_file: str,
                             report_html: bool = False,
                             log_path: str = None) -> bool:
        """Run check on IFC file based on IDS.

        print the check of specifications pass(true) or fail(false)
        and the name of the specification
        and if all specifications of one IDS pass

        Input:
            ifc_file: path of the IFC file, which is checked
            ids_file: path of the IDS file, which includes the specifications
            log_path: path of the log folder as part of the project structure
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
            # webbrowser.open(f"file://{output_file}")

        return all_spec_pass

    def get_html_templates(self):
        """Get all stored html templates.

        Which will be used to export the errors summaries.

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
        """Categorizes the resulting errors in a dictionary.

        This dictionary contains two groups:
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
        """Write all errors in the html templates in a summarized way.

        Args:
            base_name: str of file base name for reports
            domain: IFCDomain of the checked IFC
        """
        show_report = False  # enable the automatic popup of the reports
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
            # opens automatically browser tab showing the generated html report
            if show_report:
                webbrowser.open(f"file://{out_file.buffer.name}")
        with open(str(self.paths.log) +
                  base_name +
                  '_error_summary_prop.html', 'w+') as \
                out_file:
            out_file.write(templates["prop_template"].render_unicode(
                task=self,
                summary_props=summary_props))
            out_file.close()
            # opens automatically browser tab showing the generated html report
            if show_report:
                webbrowser.open(f"file://{out_file.buffer.name}")
        with open(str(self.paths.log) +
                  base_name +
                  '_error_summary.html', 'w+') as out_file:
            out_file.write(templates["summary_template"].render_unicode(
                ifc_version=self.ifc_version,
                version_error=self.version_error,
                all_guids_unique=self.all_guids_unique,
                double_guids=self.double_guids,
                all_guids_filled=self.all_guids_filled,
                empty_guids=self.empty_guids,
                task=self,
                plugin_name=domain.name.upper(),
                base_name=base_name[1:],
                summary_inst=summary_inst,
                summary_sbs=summary_sbs,
                summary_props=summary_props))
            out_file.close()
            # opens automatically browser tab showing the generated html report
            if show_report:
                webbrowser.open(f"file://{out_file.buffer.name}")

        with open(str(self.paths.log) + base_name + '_error_summary_guid.html',
                  'w+') as \
                out_file:
            out_file.write(templates["guid_template"].render_unicode(
                task=self,
                double_guids=self.double_guids,
                empty_guids=self.empty_guids,
                summary_inst=summary_inst,
                summary_sbs=summary_sbs,
                all_errors=all_errors))
            out_file.close()
            # opens automatically browser tab showing the generated html report
            if show_report:
                webbrowser.open(f"file://{out_file.buffer.name}")


class CheckLogicBase():
    """Provides logic for ifc files checking regarding simulation.

    This is a base class. This base class includes all check logic, which is
    useful for all checking use cases.

    Attributes:
        extract_data (list): filtered/extract data from ifc file
    """

    def __init__(self, extract_data, elements, ps_summary, ifc_units):
        """Initialize class."""
        self.space_ndicator = True
        # filtered data, which will be processed
        self.extract_data = extract_data
        self.elements = elements
        self.ps_summary = ps_summary
        self.ifc_units = ifc_units
        self.error_summary_prop: dict = {}

    def run_check_guid_unique(ifc_file) -> (bool, dict):
        """Check the uniqueness of the guids of the IFC file.

        Here the bijective uniqueness is check, but also
        the uniqueness of modified guids by transforming
        the lowercase letters into uppercase letter
        Input:
            ifc_file: path of the IFC file, which is checked

        Returns:
            all_guids_unique: boolean
                          (true: all guids are unique
                           false: one or more guids are not unique)

           double_guid: dict

        """
        # dict of all elements with guids used in the checked ifc model
        used_guids: dict[str, ifcos.entity_instance] = dict()
        # dict of elements with guids, which are not unique
        double_guids: dict[str, ifcos.entity_instance] = dict()
        all_guids_unique = True
        used_guids_upper = []  # to store temporally guid in uppercase letters
        for inst in ifc_file.file:
            if hasattr(inst, "GlobalId"):
                guid = inst.GlobalId
                # print(guid)
                upper_guid = guid.upper()
                # print(upper_guid)
                if (guid in used_guids):
                    double_guids[guid] = inst
                    all_guids_unique = False
                    warnings.warn(
                        "Some GUIDs are not unique! A bijective ifc file have "
                        "to have unique GUIDs. But bim2sim provides a option "
                        "in sim_settings: rest_guids = True"
                    )
                elif (guid.upper() in used_guids_upper):
                    double_guids[guid] = inst
                    all_guids_unique = False
                    warnings.warn(
                        "Some GUIDs are not unique (for transformed GUIDS "
                        "letters low-case into uppercase)! "
                        "A bijective ifc file have "
                        "to have unique GUIDs. But bim2sim provides a option "
                        "in sim_settings: rest_guids = True"
                    )
                else:
                    used_guids[guid] = inst
                    # store temporally guid in uppercase letters
                    used_guids_upper.append(upper_guid)

        return (all_guids_unique, double_guids)

    def run_check_guid_empty(ifc_file) -> (bool, dict):
        """Check it there is/are guid/s, which is/are empty in the IFC file.

        Args:
            ifc_file: path of the IFC file, which is checked

        Returns:
            all_guids_filled: boolean
                          (true: all guids has a value (not empty)
                           false: one or more guids has not value (empty))

           empty_guid: dict
        """
        # dict of all elements with guids used in the checked ifc model
        used_guids: dict[str, ifcos.entity_instance] = dict()
        # dict of elements with guids, which are empty
        empty_guids: dict[str, ifcos.entity_instance] = dict()
        all_guids_filled = True
        # count the number of guids without value (empty), this number is used
        # to make unique identifier
        guid_empty_no = 0
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
        """Check the IFC version.

        Only IFC4 files are valid for bim2sim.

        Attention: no Error is raised anymore.

        Args:
            ifc: ifc file loaded with IfcOpenShell
        Returns:
            version_error: True if version NOT fit
            ifc_version: version of the ifc file
        """
        schema = ifc.schema
        if "IFC4" not in schema:
            version_error = True
        else:
            version_error = False
        return (version_error, schema)

    def check_inst_sub(self):
        """Check sub instances for errors.

        Based on functions in validate_sub_inst via check_inst
        """
        error_summary_sub_inst = self.check_inst(
                    self.validate_sub_inst, self.extract_data)
        return error_summary_sub_inst

    def check_elements(self):
        """Check elements for errors.

        Based on functions in validate_sub_inst via check_inst
        """
        error_summary = self.check_inst(
                    self.validate_elements, self.elements)
        return error_summary

    @staticmethod
    def check_inst(validation_function: Callable, elements: list):
        """Check each element lists.

        Use sb_validation/ports/elements functions to check elements
        adds error to dictionary if object has errors. Combines the
        (error) return of the specific validation function with the
        key (mostly the GlobalID).

        Args:
            validation_function: function that compiles all the validations
                                 to be performed on the object
                                 (sb/port/instance)
            elements: list containing all objects to be evaluates

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
        """Apply a validation to an instance, space boundary or port.

        Function to apply a validation to an instance, space boundary or
        port, it stores the error to the list of errors.

        Args:
            fct: validation function to be applied
            err_name: string that define the error
            error: list of errors

        """
        if not fct:
            error.append(err_name)

    @staticmethod
    def _check_rel_space(bound: ifcos.entity_instance):
        """Check the existence of related space.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return any(
            [bound.RelatingSpace.is_a('IfcSpace') or
             bound.RelatingSpace.is_a('IfcExternalSpatialElement')])

    def validate_sub_inst(self, sub_inst: list) -> list:
        """Raise NotImplemented Error."""
        raise NotImplementedError


class CheckLogicBPS(CheckLogicBase):
    """Provides additional logic for ifc files checking regarding BPS."""

    @staticmethod
    def _check_rel_space(bound: ifcos.entity_instance):
        """Check existence of related space.

        And has the correctness of class type.

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
    def _check_rel_building_elem(bound: ifcos.entity_instance):
        """Check existence of related building element.

        And the correctness of class type.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        if bound.RelatedBuildingElement is not None:
            return bound.RelatedBuildingElement.is_a('IfcElement')

    @staticmethod
    def _check_conn_geom(bound: ifcos.entity_instance):
        """Check that the space boundary has a connection geometry.

        And the correctness of class type.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        if bound.ConnectionGeometry is not None:
            return bound.ConnectionGeometry.is_a('IfcConnectionGeometry')

    @staticmethod
    def _check_on_relating_elem(bound: ifcos.entity_instance):
        """Check geometric information.

        Check that the surface on relating element of a space boundary has the
        geometric information and the correctness of class type.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails

        """
        if bound.ConnectionGeometry is not None:
            return bound.ConnectionGeometry.SurfaceOnRelatingElement.is_a(
                'IfcCurveBoundedPlane')

    @staticmethod
    def _check_on_related_elem(bound: ifcos.entity_instance):
        """Check absence of geometric information.

        Check that the surface on related element of a space boundary has no
        geometric information and the correctness of class type.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        if bound.ConnectionGeometry is not None:
            return (bound.ConnectionGeometry.SurfaceOnRelatedElement is None or
                    bound.ConnectionGeometry.SurfaceOnRelatedElement.is_a(
                        'IfcCurveBoundedPlane'))

    @staticmethod
    def _check_basis_surface(bound: ifcos.entity_instance):
        """Check representation by an IFC Place.

        Check that the surface on relating element of a space boundary is
        represented by an IFC Place and the correctness of class type.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        if bound.ConnectionGeometry is not None:
            return bound.ConnectionGeometry.SurfaceOnRelatingElement. \
                BasisSurface.is_a('IfcPlane')

    @staticmethod
    def _check_inner_boundaries(bound: ifcos.entity_instance):
        """Check absence of the surface and their structure.

        Check if the surface on relating element of a space boundary inner
        boundaries don't exists or are composite curves.
        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        if bound.ConnectionGeometry is not None:
            return (bound.ConnectionGeometry.SurfaceOnRelatingElement.
                    InnerBoundaries is None) or \
                   (i.is_a('IfcCompositeCurve') for i in bound.
                    ConnectionGeometry.SurfaceOnRelatingElement.
                    InnerBoundaries)

    @staticmethod
    def _check_outer_boundary_composite(bound: ifcos.entity_instance):
        """Check if the surface are composite curves.

        Check if the surface on relating element of a space boundary outer
        boundaries are composite curves.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.ConnectionGeometry.SurfaceOnRelatingElement. \
            OuterBoundary.is_a('IfcCompositeCurve')

    @staticmethod
    def _check_segments(bound: ifcos.entity_instance):
        """Check if the surface are poly-line.

        Check if the surface on relating element of a space boundary outer
        boundaries segments are poly-line.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return (s.is_a('IfcCompositeCurveSegment') for s in
                bound.ConnectionGeometry.SurfaceOnRelatingElement.
                OuterBoundary.Segments)

    @staticmethod
    def _check_coords(points: ifcos.entity_instance):
        """Check coordinates of a group of points (class and length).

        Args:
            points: Points IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return points.is_a('IfcCartesianPoint') and 1 <= len(
            points.Coordinates) <= 4

    @staticmethod
    def _check_dir_ratios(dir_ratios: ifcos.entity_instance):
        """Check length of direction ratios.

        Args:
            dir_ratios: direction ratios IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return 2 <= len(dir_ratios.DirectionRatios) <= 3

    @classmethod
    def _check_poly_points_coord(cls, polyline: ifcos.entity_instance):
        """Check if a poly-line has the correct coordinates.

        Args:
            polyline: Poly-line IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return all(cls._check_coords(p) for p in polyline.Points)

    @classmethod
    def _check_segments_poly_coord(cls, bound: ifcos.entity_instance):
        """Check segments coordinates.

        Check segments coordinates of an outer boundary of a surface on
        relating element.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return all(cls._check_poly_points_coord(s.ParentCurve)
                   for s in
                   bound.ConnectionGeometry.SurfaceOnRelatingElement.
                   OuterBoundary.Segments)

    @staticmethod
    def _check_poly_points(polyline: ifcos.entity_instance):
        """Check if a polyline has the correct class.

        Args:
            polyline: Polyline IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return polyline.is_a('IfcPolyline')

    @classmethod
    def _check_outer_boundary_poly(cls, bound: ifcos.entity_instance):
        """Check points of outer boundary of a surface on relating element.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return cls._check_poly_points(
            bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary)

    @staticmethod
    def _check_outer_boundary_poly_coord(bound: ifcos.entity_instance):
        """Check outer boundary of a surface on relating element.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return all(
            bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary)

    @staticmethod
    def _check_plane_position(bound: ifcos.entity_instance):
        """
        Check class of plane position of space boundary.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface. \
            Position.is_a('IfcAxis2Placement3D')

    @staticmethod
    def _check_location(bound: ifcos.entity_instance):
        """
        Check that location of a space boundary is an IfcCartesianPoint.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface. \
            Position.Location.is_a('IfcCartesianPoint')

    @staticmethod
    def _check_axis(bound: ifcos.entity_instance):
        """Check that axis of space boundary is an IfcDirection.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface. \
            Position.Axis.is_a('IfcDirection')

    @staticmethod
    def _check_refdirection(bound: ifcos.entity_instance):
        """Check that reference direction of space boundary is an IfcDirection.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface. \
            Position.RefDirection.is_a('IfcDirection')

    @classmethod
    def _check_location_coord(cls, bound: ifcos.entity_instance):
        """Check the correctness of related coordinates.

        Check if space boundary surface on relating element coordinates are
        correct.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails

        """
        return cls._check_coords(bound.ConnectionGeometry.
                                 SurfaceOnRelatingElement.BasisSurface.
                                 Position.Location)

    @classmethod
    def _check_axis_dir_ratios(cls, bound: ifcos.entity_instance):
        """Check correctness of space boundary surface.

        Check if space boundary surface on relating element axis are correct.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return cls._check_dir_ratios(
            bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.
            Position.Axis)

    @classmethod
    def _check_refdirection_dir_ratios(cls, bound: ifcos.entity_instance):
        """Check correctness of space boundary surface.

        Check if space boundary surface on relating element reference direction
        are correct.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return cls._check_dir_ratios(
            bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.
            Position.RefDirection)

    @staticmethod
    def _check_inst_sb(inst: ifcos.entity_instance):
        """Check association of an instance.

        Check that an instance has associated space boundaries (space or
        building element).

        Args:
            inst: IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        blacklist = ['IfcBuilding', 'IfcSite', 'IfcBuildingStorey',
                     'IfcMaterial', 'IfcMaterialLayer', 'IfcMaterialLayerSet']
        if inst.is_a() in blacklist:
            return True
        elif inst.is_a('IfcSpace') or inst.is_a('IfcExternalSpatialElement'):
            return len(inst.BoundedBy) > 0
        else:
            if len(inst.ProvidesBoundaries) > 0:
                return True
            decompose = []
            if hasattr(inst, 'Decomposes') and len(inst.Decomposes):
                decompose = [decomp.RelatingObject for decomp in
                             inst.Decomposes]
            elif hasattr(inst, 'IsDecomposedBy') and len(inst.IsDecomposedBy):
                decompose = []
                for decomp in inst.IsDecomposedBy:
                    for inst_ifc in decomp.RelatedObjects:
                        decompose.append(inst_ifc)
            for inst_decomp in decompose:
                if len(inst_decomp.ProvidesBoundaries):
                    return True
        return False

    @staticmethod
    def _check_inst_materials(inst: ifcos.entity_instance):
        """Check that an instance has associated materials.

        Args:
            inst: IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        blacklist = [
            'IfcBuilding', 'IfcSite', 'IfcBuildingStorey', 'IfcSpace',
            'IfcExternalSpatialElement']
        if not (inst.is_a() in blacklist):
            return len(get_layers_ifc(inst)) > 0
        return True

    def _check_inst_properties(self, inst: ifcos.entity_instance):
        """Check existence of necessary property sets and properties.

        Check that an instance has the property sets and properties
        necessaries to the plugin.
        Args:
            inst: IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        inst_prop2check = self.ps_summary.get(inst.is_a(), {})
        inst_prop = get_property_sets(inst, self.ifc_units)
        inst_prop_errors = []
        for prop2check, ps2check in inst_prop2check.items():
            ps = inst_prop.get(ps2check[0], None)
            if ps:
                if not ps.get(ps2check[1], None):
                    inst_prop_errors.append(
                        prop2check+' - '+', '.join(ps2check))
            else:
                inst_prop_errors.append(prop2check+' - '+', '.join(ps2check))
        if inst_prop_errors:
            key = inst.GlobalId + ' ' + inst.is_a()
            self.error_summary_prop.update({key: inst_prop_errors})
            return False
        return True

    @staticmethod
    def _check_inst_contained_in_structure(inst: ifcos.entity_instance):
        """Check that an instance is contained in an structure.

        Args:
            inst: IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        blacklist = [
            'IfcBuilding', 'IfcSite', 'IfcBuildingStorey', 'IfcSpace',
            'IfcExternalSpatialElement', 'IfcMaterial', 'IfcMaterialLayer',
            'IfcMaterialLayerSet'
        ]
        if not (inst.is_a() in blacklist):
            return len(inst.ContainedInStructure) > 0
        if hasattr(inst, 'Decomposes'):
            return len(inst.Decomposes) > 0
        else:
            return True

    @staticmethod
    def _check_inst_representation(inst: ifcos.entity_instance):
        """
        Check that an instance has a correct geometric representation.

        Args:
            inst: IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        blacklist = [
            'IfcBuilding', 'IfcBuildingStorey', 'IfcMaterial',
            'IfcMaterialLayer', 'IfcMaterialLayerSet'
        ]
        if not (inst.is_a() in blacklist):
            return inst.Representation is not None
        return True

    def validate_sub_inst(self, bound: ifcos.entity_instance) -> list:
        """Validate space boundary.

        Validation function for a space boundary that compiles all validation
        functions.

        Args:
            bound: ifc space boundary entity

        Returns:
            error: list of errors found in the ifc space boundaries
        """
        error = []
        # print(bound)
        self.apply_validation_function(self._check_rel_space(bound),
                                       'RelatingSpace - '
                                       'The space boundary does not have a '
                                       'relating space associated', error)
        self.apply_validation_function(self._check_rel_building_elem(bound),
                                       'RelatedBuildingElement - '
                                       'The space boundary does not have a '
                                       'related building element associated',
                                       error)
        self.apply_validation_function(self._check_conn_geom(bound),
                                       'ConnectionGeometry - '
                                       'The space boundary does not have a '
                                       'connection geometry', error)
        self.apply_validation_function(self._check_on_relating_elem(bound),
                                       'SurfaceOnRelatingElement - '
                                       'The space boundary does not have a '
                                       'surface on the relating element',
                                       error)
        self.apply_validation_function(self._check_on_related_elem(bound),
                                       'SurfaceOnRelatedElement - '
                                       'The space boundary does not have a '
                                       'surface on the related element', error)
        self.apply_validation_function(self._check_basis_surface(bound),
                                       'BasisSurface - '
                                       'The space boundary surface on '
                                       'relating element geometry is missing',
                                       error)
        self.apply_validation_function(self._check_inner_boundaries(bound),
                                       'InnerBoundaries - '
                                       'The space boundary surface on '
                                       'relating element inner boundaries are '
                                       'missing',  error)
        if bound.ConnectionGeometry is not None:
            if hasattr(
                    bound.ConnectionGeometry.SurfaceOnRelatingElement.
                    OuterBoundary, 'Segments'):
                self.apply_validation_function(
                    self._check_outer_boundary_composite(bound),
                    'OuterBoundary - '
                    'The space boundary surface on relating element outer '
                    'boundary is missing', error)
                self.apply_validation_function(self._check_segments(bound),
                                               'OuterBoundary Segments - '
                                               'The space boundary surface on '
                                               'relating element outer '
                                               'boundary '
                                               'geometry is missing', error)
                self.apply_validation_function(
                    self._check_segments_poly_coord(bound),
                    'OuterBoundary Coordinates - '
                    'The space boundary surface on relating element outer '
                    'boundary coordinates are missing', error)
            else:
                self.apply_validation_function(
                    self._check_outer_boundary_poly(bound),
                    'OuterBoundary - '
                    'The space boundary surface on relating element outer '
                    'boundary is missing', error)
                self.apply_validation_function(
                    self._check_outer_boundary_poly_coord(bound),
                    'OuterBoundary Coordinates - '
                    'The space boundary surface on relating element outer '
                    'boundary coordinates are missing', error)
            self.apply_validation_function(self._check_plane_position(bound),
                                           'Position - '
                                           'The space boundary surface on'
                                           'relating '
                                           'element plane position is missing',
                                           error)
            self.apply_validation_function(self._check_location(bound),
                                           'Location - '
                                           'The space boundary surface on '
                                           'relating element location is '
                                           'missing', error)
            self.apply_validation_function(self._check_axis(bound),
                                           'Axis - '
                                           'The space boundary surface on'
                                           'relating '
                                           'element axis are missing',
                                           error)
            self.apply_validation_function(self._check_refdirection(bound),
                                           'RefDirection - '
                                           'The space boundary surface on '
                                           'relating '
                                           'element reference direction is '
                                           'missing', error)
            self.apply_validation_function(self._check_location_coord(bound),
                                           'LocationCoordinates - '
                                           'The space boundary surface on'
                                           'relating '
                                           'element location coordinates are '
                                           'missing', error)
            self.apply_validation_function(self._check_axis_dir_ratios(bound),
                                           'AxisDirectionRatios - '
                                           'The space boundary surface on '
                                           'relating '
                                           'element axis direction ratios are '
                                           'missing', error)
            self.apply_validation_function(
                self._check_refdirection_dir_ratios(bound),
                'RefDirectionDirectionRatios - '
                'The space boundary surface on relating element position '
                'reference direction is missing', error)
        return error

    def validate_elements(self, inst: ifcos.entity_instance) -> list:
        """Validate elements.

        Validation function for an instance that compiles all instance
        validation functions.
        Args:
            inst:IFC instance being checked

        Returns:
            error: list of elements error

        """
        error = []
        self.apply_validation_function(self._check_inst_sb(inst),
                                       'SpaceBoundaries - '
                                       'The instance space boundaries are '
                                       'missing', error)
        self.apply_validation_function(self._check_inst_materials(inst),
                                       'MaterialLayers - '
                                       'The instance materials are missing',
                                       error)
        self.apply_validation_function(self._check_inst_properties(inst),
                                       'Missing Property_Sets - '
                                       'One or more instance\'s necessary '
                                       'property sets are missing', error)
        self.apply_validation_function(
            self._check_inst_contained_in_structure(inst),
            'ContainedInStructure - '
            'The instance is not contained in any '
            'structure', error)
        self.apply_validation_function(self._check_inst_representation(inst),
                                       'Representation - '
                                       'The instance has no geometric '
                                       'representation', error)
        return error


class CheckLogicHVAC(CheckLogicBase):
    """Provides additional logic for ifc files checking regarding HVAC."""

    @staticmethod
    def _check_assignments(inst: ifcos.entity_instance) -> bool:
        """Check that the inst (also spec. port) has at least one assignment.

        Args:
            port: port ifc entity

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return any(assign.is_a('IfcRelAssignsToGroup') for assign in
                   inst.HasAssignments)

    @staticmethod
    def _check_connection(port: ifcos.entity_instance) -> bool:
        """Check that the port is: "connected_to" or "connected_from".

        Args:
            port: port ifc entity

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return len(port.ConnectedTo) > 0 or len(port.ConnectedFrom) > 0

    @staticmethod
    def _check_contained_in(port: ifcos.entity_instance) -> bool:
        """
        Check that the port is "contained_in".

        Args:
            port: port ifc entity

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return len(port.ContainedIn) > 0

    # elements check
    @staticmethod
    def _check_inst_ports(inst: ifcos.entity_instance) -> bool:
        """Check that an instance has associated ports.

        Args:
            inst: IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        ports = get_ports(inst)
        if ports:
            return True
        else:
            return False

    @staticmethod
    def _check_contained_in_structure(inst: ifcos.entity_instance) -> bool:
        """Check that an instance is contained in an structure.

        Args:
            inst: IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        if hasattr(inst, 'ContainedInStructure'):
            return len(inst.ContainedInStructure) > 0
        else:
            return False

    def _check_inst_properties(self, inst: ifcos.entity_instance):
        """Check necessaries property sets and properties.

        Check that an instance has the property sets and properties
        necessaries to the plugin.
        Args:
            inst: IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        inst_prop2check = self.ps_summary.get(inst.is_a(), {})
        inst_prop = get_property_sets(inst, self.ifc_units)
        inst_prop_errors = []
        for prop2check, ps2check in inst_prop2check.items():
            ps = inst_prop.get(ps2check[0], None)
            if ps:
                if not ps.get(ps2check[1], None):
                    inst_prop_errors.append(
                        prop2check+' - '+', '.join(ps2check))
            else:
                inst_prop_errors.append(prop2check+' - '+', '.join(ps2check))
        if inst_prop_errors:
            key = inst.GlobalId + ' ' + inst.is_a()
            self.error_summary_prop.update({key: inst_prop_errors})
            return False
        return True

    @staticmethod
    def _check_inst_representation(inst: ifcos.entity_instance):
        """Check that an instance has a correct geometric representation.

        Args:
            inst: IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        if hasattr(inst, 'Representation'):
            return inst.Representation is not None
        else:
            return False

    def validate_sub_inst(self, port: ifcos.entity_instance) -> list:
        """Run validation functions for a port.

        Args:
            port: IFC port entity

        Returns:
            error: list of errors found in the IFC port

        """
        error = []
        self.apply_validation_function(self._check_assignments(port),
                                       'Assignments - '
                                       'The port assignments are missing',
                                       error)
        self.apply_validation_function(self._check_connection(port),
                                       'Connections - '
                                       'The port has no connections', error)
        self.apply_validation_function(self._check_contained_in(port),
                                       'ContainedIn - '
                                       'The port is not contained in', error)
        return error

    def validate_elements(self, inst: ifcos.entity_instance) -> list:
        """Validate elements (carrier function).

        Validation function for an instance that compiles all instance
        validation functions.

        Args:
            inst: IFC instance being checked

        Returns:
            error: list of elements error

        """
        error = []

        self.apply_validation_function(self._check_inst_ports(inst),
                                       'Ports - '
                                       'The instance ports are missing', error)
        self.apply_validation_function(
            self._check_contained_in_structure(inst),
            'ContainedInStructure - '
            'The instance is not contained in any '
            'structure', error)
        self.apply_validation_function(self._check_inst_properties(inst),
                                       'Missing Property_Sets - '
                                       'One or more instance\'s necessary '
                                       'property sets are missing', error)
        self.apply_validation_function(self._check_inst_representation(inst),
                                       'Representation - '
                                       'The instance has no geometric '
                                       'representation', error)
        self.apply_validation_function(self._check_assignments(inst),
                                       'Assignments - '
                                       'The instance assignments are missing',
                                       error)
        return error


if __name__ == '__main__':
    pass
