from __future__ import annotations

import types
import inspect
import json
import logging
import os
import warnings
from typing import Dict, Callable

from ifcopenshell import file, entity_instance
from mako.lookup import TemplateLookup
from mako.template import Template

from bim2sim.elements import hvac_elements as hvac, bps_elements as bps
from bim2sim.elements.mapping import attribute
from bim2sim.elements.mapping.ifc2python import get_property_sets, get_ports, \
    get_layers_ifc
from bim2sim.kernel.ifc_file import IfcFileClass
from bim2sim.tasks.base import ITask, Playground
from bim2sim.utilities.common_functions import all_subclasses
from bim2sim.utilities.types import IFCDomain

class CheckIfc(ITask):
    """
    Check an IFC file, for a number of conditions (missing information,
    incorrect information, etc) that could lead on future tasks to fatal errors.
    """
    reads = ('ifc_files',)

    def __init__(self, playground: Playground):
        super().__init__(playground)
        self.error_summary_sub_inst: dict = {}
        self.error_summary_inst: dict = {}
        self.error_summary_prop: dict = {}
        self.sub_inst: list = []
        self.id_list: list = []
        self.elements: list = []
        self.ps_summary: dict = {}
        self.ifc_units: dict = {}
        self.sub_inst_cls = None
        self.plugin = None

    def run(self, ifc_files: [IfcFileClass]) -> [dict, dict]:
        """
        Analyzes sub_elements and elements of an IFC file for the validation
        functions and export the errors found as .json and .html files.

        Args:
            ifc_files: bim2sim IfcFileClass holding the ifcopenshell ifc
                instance

        Returns:
            error_summary_sub_inst: summary of errors related to sub_elements
            error_summary_inst: summary of errors related to elements
        """
        paths = self.paths
        for ifc_file in ifc_files:
            # Reset class based on domain to run the right check.
            # Not pretty but works. This might be refactored in #170
            if ifc_file.domain == IFCDomain.hydraulic:
                self.logger.info(f"Processing HVAC-IfcCheck")  # todo
                self.__class__ = CheckIfcHVAC
                self.__class__.__init__(self, self.playground)
                self.paths = paths
            elif ifc_file.domain == IFCDomain.arch:
                self.logger.info(f"Processing BPS-IfcCheck")  # todo
                self.__class__ = CheckIfcBPS
                self.__class__.__init__(self, self.playground)
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
                self.__class__ = CheckIfc
            self.ps_summary = self._get_class_property_sets(self.plugin)
            self.ifc_units = ifc_file.ifc_units
            self.sub_inst = ifc_file.file.by_type(self.sub_inst_cls)
            self.elements = self.get_relevant_elements(ifc_file.file)
            self.id_list = [e.GlobalId for e in ifc_file.file.by_type("IfcRoot")]
            self.check_critical_errors(ifc_file.file, self.id_list)
            self.error_summary_sub_inst = self.check_inst(
                self.validate_sub_inst, self.sub_inst)
            self.error_summary_inst = self.check_inst(
                self.validate_elements, self.elements)
            instance_errors = sum(len(errors) for errors in
                                  self.error_summary_inst.values())
            quality_logger = logging.getLogger('bim2sim.QualityReport')
            quality_logger.warning(
                '%d errors were found on %d elements' %
                (instance_errors, len(self.error_summary_inst)))
            sub_inst_errors = sum(len(errors) for errors in list(
                self.error_summary_sub_inst.values()))
            quality_logger.warning(
                '%d errors were found on %d sub_elements' % (
                    sub_inst_errors, len(self.error_summary_sub_inst)))
            base_name = f"/{ifc_file.domain.name.upper()}_" \
                        f"{ifc_file.ifc_file_name[:-4]}"
            self._write_errors_to_json(base_name)
            self._write_errors_to_html_table(base_name, ifc_file.domain)

    def check_critical_errors(self, ifc: file, id_list: list):
        """
        Checks for critical errors in the IFC file.

        Args:
            ifc: ifc file loaded with IfcOpenShell
            id_list: list of all GUID's in IFC File
        Raises:
            TypeError: if a critical error is found
        """
        self.check_ifc_version(ifc)
        self.check_critical_uniqueness(id_list)

    @staticmethod
    def check_ifc_version(ifc: file):
        """
        Checks the IFC version.

        Only IFC4 files are valid for bim2sim.

        Args:
            ifc: ifc file loaded with IfcOpenShell
        Raises:
            TypeError: if loaded IFC is not IFC4
        """
        schema = ifc.schema
        if "IFC4" not in schema:
            raise TypeError(f"Loaded IFC file is of type {schema} but only IFC4"
                            f"is supported. Please ask the creator of the model"
                            f" to provide a valid IFC4 file.")

    @staticmethod
    def _get_ifc_type_classes(plugin):
        """
        Gets all the classes of a plugin, that represent an IFCProduct,
        and organize them on a dictionary for each ifc_type
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
        cls_summary: dict = {}

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
    def _get_class_property_sets(cls, plugin) -> Dict:
        """
        Gets all property sets and properties required for bim2sim for all
        classes of a plugin, that represent an IFCProduct, and organize them on
        a dictionary for each ifc_type
        Args:
            plugin: plugin used in the check tasks (bps or hvac)

        Returns:
            ps_summary: dictionary containing all the ifc_types on the
            plugin with the corresponding property sets
        """
        ps_summary: dict = {}
        cls_summary = cls._get_ifc_type_classes(plugin)
        for ifc_type, plugin_class in cls_summary.items():
            attributes = inspect.getmembers(
                plugin_class, lambda a: isinstance(a, attribute.Attribute))
            ps_summary[ifc_type] = {}
            for attr in attributes:
                if attr[1].default_ps:
                    ps_summary[ifc_type][attr[0]] = attr[1].default_ps
        return ps_summary

    def get_relevant_elements(self, ifc):
        """
        Gets all relevant ifc elements based on the plugin's classes that
        represent an IFCProduct

        Args:
            ifc: IFC file translated with ifcopenshell

        Returns:
            ifc_elements: list of IFC instance (Products)

        """
        relevant_ifc_types = list(self.ps_summary.keys())
        ifc_elements: list = []
        for ifc_type in relevant_ifc_types:
            ifc_elements.extend(ifc.by_type(ifc_type))
        return ifc_elements

    @staticmethod
    def check_inst(validation_function, elements: list):
        """
        Uses sb_validation/ports/elements functions in order to check each
        one and adds error to dictionary if object has errors.
        Args:
            validation_function: function that compiles all the validations
                to be performed on the object (sb/port/instance)
            elements: list containing all objects to be evaluates

        Returns:
            summary: summarized dictionary of errors, where the key is the
                GUID + the ifc_type

        """
        summary: dict = {}
        for inst in elements:
            error = validation_function(inst)
            if len(error) > 0:
                if hasattr(inst, 'GlobalId'):
                    key = inst.GlobalId + ' ' + inst.is_a()
                else:
                    key = inst.is_a()
                summary.update({key: error})
        return summary

    def validate_sub_inst(self, sub_inst: list) -> list:
        raise NotImplementedError

    def validate_elements(self, inst: list) -> list:
        raise NotImplementedError

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

    def _write_errors_to_json(self, base_name: str):
        """
        Function to write the resulting list of errors to a .json file as a
        summary.

        Args:ps
            base_name: str of file base name for reports

        """
        with open(str(self.paths.log) +
                  base_name +
                  f"_sub_inst_error_summary.json",
                  'w+') as fp:
            json.dump(self.error_summary_sub_inst, fp, indent="\t")
        with open(str(self.paths.log) +
                  base_name +
                  f"_inst_error_summary.json",
                  'w+') as fp:
            json.dump(self.error_summary_inst, fp, indent="\t")

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
        categorized_dict: dict = {'per_error': {}, 'per_type': {}}
        for instance, errors in error_dict.items():
            if ' ' in instance:
                guid, ifc_type = instance.split(' ')
            else:
                guid = '-'
                ifc_type = instance
            if ifc_type not in categorized_dict['per_type']:
                categorized_dict['per_type'][ifc_type]: dict = {}
            categorized_dict['per_type'][ifc_type][guid] = errors
            for error in errors:
                error_com = error.split(' - ')
                if error_com[0] not in categorized_dict['per_error']:
                    categorized_dict['per_error'][error_com[0]] = 0
                categorized_dict['per_error'][error_com[0]] += 1
        return categorized_dict

    # general check functions
    @staticmethod
    def _check_unique(inst: entity_instance, id_list: list):
        """
        Check that the global id (GUID) is unique for the analyzed instance

        Args:
            inst: IFC instance
            id_list: list of all GUID's in IFC File
        Returns:
            True: if check succeeds
            False: if check fails
        """
        # Materials have no GlobalId
        blacklist = [
            'IfcMaterialLayer', 'IfcMaterialLayer', 'IfcMaterialLayerSet'
        ]
        if inst.is_a() in blacklist:
            return True
        return id_list.count(inst.GlobalId) == 1

    @staticmethod
    def check_critical_uniqueness(id_list: list):
        """
        Checks if all GlobalIds are unique.

        Only files containing unique GUIDs are valid for bim2sim.

        Args:
            id_list: list of all GUID's in IFC File
        Raises:
            TypeError: if loaded file does not have unique GUIDs
            Warning: if uppercase GUIDs are equal
        """
        if len(id_list) > len(set(id_list)):
            raise TypeError(
                f"The GUIDs of the loaded IFC file are not uniquely defined"
                f" but files containing unique GUIDs can be used. Please ask "
                f"the creator of the model to provide a valid IFC4 "
                f"file.")
        ids_upper = list(map(lambda x: x.upper(), id_list))
        if len(ids_upper) > len(set(ids_upper)):
            warnings.warn(
                "Uppercase GUIDs are not uniquely defined. A restart using the"
                "option of generating new GUIDs should be considered.")

    def _check_inst_properties(self, inst: entity_instance):
        """
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
        inst_prop_errors: list = []
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
    def _check_inst_representation(inst: entity_instance):
        """
        Check that an instance has a correct geometric representation.

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

    def get_html_templates(self):
        """
        Gets all stored html templates that will be used to export the errors
        summaries

        Returns:
            templates: dictionary containing all error html templates
        """
        templates: dict = {}
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
            filename=os.path.join(path_templates, "summary_template"),
            lookup=lookup)
        return templates

    def _write_errors_to_html_table(self, base_name: str, domain: IFCDomain):
        """
        Writes all errors in the html templates in a summarized way

        Args:
            base_name: str of file base name for reports
            domain: IFCDomain of the checked IFC
        """

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
        with open(str(self.paths.log) +
                  base_name +
                  '_error_summary_prop.html', 'w+') as \
                out_file:
            out_file.write(templates["prop_template"].render_unicode(
                task=self,
                summary_props=summary_props))
            out_file.close()
        with open(str(self.paths.log) +
                  base_name +
                  '_error_summary.html', 'w+') as out_file:
            out_file.write(templates["summary_template"].render_unicode(
                task=self,
                plugin_name=domain.name.upper(),
                base_name=base_name[1:],
                summary_inst=summary_inst,
                summary_sbs=summary_sbs,
                summary_props=summary_props))
            out_file.close()


class CheckIfcHVAC(CheckIfc):
    """
    Check an IFC file for a number of conditions (missing information, incorrect information, etc) that could lead on
    future tasks to fatal errors.
    """

    def __init__(self, playground: Playground):
        super().__init__(playground)
        self.sub_inst_cls = 'IfcDistributionPort'
        self.plugin = hvac

    def validate_sub_inst(self, port: entity_instance) -> list:
        """
        Validation function for a port that compiles all validation functions.

        Args:
            port: IFC port entity

        Returns:
            error: list of errors found in the IFC port

        """
        error: list = []
        self.apply_validation_function(self._check_unique(port, self.id_list),
                                       'GlobalId - '
                                       'The space boundary GlobalID is not '
                                       'unique', error)
        self.apply_validation_function(self._check_flow_direction(port),
                                       'FlowDirection - '
                                       'The port flow direction is missing', error)
        self.apply_validation_function(self._check_assignments(port),
                                       'Assignments - '
                                       'The port assignments are missing', error)
        self.apply_validation_function(self._check_connection(port),
                                       'Connections - '
                                       'The port has no connections', error)
        self.apply_validation_function(self._check_contained_in(port),
                                       'ContainedIn - '
                                       'The port is not contained in', error)

        return error

    def validate_elements(self, inst: entity_instance) -> list:
        """
        Validation function for an instance that compiles all instance validation functions.

        Args:
            inst: IFC instance being checked

        Returns:
            error: list of elements error

        """
        error: list = []
        self.apply_validation_function(self._check_unique(inst, self.id_list),
                                       'GlobalId - '
                                       'The instance GlobalID is not unique', error)
        self.apply_validation_function(self._check_inst_ports(inst),
                                       'Ports - '
                                       'The instance ports are missing', error)
        self.apply_validation_function(self._check_contained_in_structure(inst),
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
                                       'The instance assignments are missing', error)

        return error

    @staticmethod
    def _check_flow_direction(port: entity_instance) -> bool:
        """
        Check that the port has a defined flow direction.

        Args:
            port: port IFC entity

        Returns:
            True if check succeeds, False otherwise
        """
        return port.FlowDirection in ['SOURCE', 'SINK', 'SINKANDSOURCE',
                                      'SOURCEANDSINK']

    @staticmethod
    def _check_assignments(port: entity_instance) -> bool:
        """
        Check that the port has at least one assignment.

        Args:
            port: port ifc entity

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return any(assign.is_a('IfcRelAssignsToGroup') for assign in
                   port.HasAssignments)

    @staticmethod
    def _check_connection(port: entity_instance) -> bool:
        """
        Check that the port is: "connected_to" or "connected_from".

        Args:
            port: port ifc entity

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return len(port.ConnectedTo) > 0 or len(port.ConnectedFrom) > 0

    @staticmethod
    def _check_contained_in(port: entity_instance) -> bool:
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
    def _check_inst_ports(inst: entity_instance) -> bool:
        """
        Check that an instance has associated ports.

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
    def _check_contained_in_structure(inst: entity_instance) -> bool:
        """
        Check that an instance is contained in an structure.

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


class CheckIfcBPS(CheckIfc):
    """
    Check an IFC file, for a number of conditions (missing information,
    incorrect information, etc.) that could lead on future tasks to
    fatal errors.
    """

    def __init__(self, playground: Playground, ):
        super().__init__(playground)
        self.sub_inst_cls = 'IfcRelSpaceBoundary'
        self.plugin = bps
        self.space_indicator = True

    def check_critical_errors(self, ifc: file, id_list: list):
        """
        Checks for critical errors in the IFC file.

        Args:
            ifc: ifc file loaded with IfcOpenShell
            id_list: list of all GUID's in IFC File
        Raises:
            TypeError: if a critical error is found
        """
        self.check_ifc_version(ifc)
        self.check_critical_uniqueness(id_list)
        self.check_sub_inst_exist()
        self.check_rel_space_exist()

    def check_sub_inst_exist(self):
        """
        Checks for the existence of IfcRelSpaceBoundaries.

        Only files containing elements of type 'IfcRelSpaceBoundary' are
        valid for bim2sim.

        Raises:
            TypeError: if loaded file does not contain IfcRelSpaceBoundaries
        """
        if len(self.sub_inst) == 0:
            raise TypeError(
                f"Loaded IFC file does not contain elements of type "
                f"'IfcRelSpaceBoundary' but only files containing "
                f"IfcRelSpaceBoundaries can be validated. Please ask the "
                f"creator of the model to provide a valid IFC4 file.")

    def check_rel_space_exist(self):
        """
        Checks for the existence of RelatedSpace attribute of
        IfcRelSpaceBoundaries.

        Only IfcRelSpaceBoundaries with an IfcSpace or
        IfcExternalSpatialElement are valid for bim2sim.

        Raises:
            TypeError: if loaded file only contain IfcRelSpaceBoundaries
            without a valid RelatedSpace.
        """
        indicator = False
        for inst in self.sub_inst:
            if inst.RelatingSpace is not None:
                indicator = True
                break
        if not indicator:
            raise TypeError(
                f"Loaded IFC file does only contain IfcRelSpaceBoundaries "
                f"that do not have an IfcSpace or IfcExternalSpatialElement "
                f"as RelatedSpace but those are necessary for further "
                f"calculations. Please ask the creator of the model to provide"
                f" a valid IFC4 file.")

    def validate_sub_inst(self, bound: entity_instance) -> list:
        """
        Validation function for a space boundary that compiles all validation
        functions.

        Args:
            bound: ifc space boundary entity

        Returns:
            error: list of errors found in the ifc space boundaries
        """
        error: list = []
        self.apply_validation_function(self._check_unique(bound, self.id_list),
                                       'GlobalId - '
                                       'The space boundary GlobalID is not '
                                       'unique',
                                       error)
        self.apply_validation_function(self._check_level(bound),
                                       '2ndLevel - '
                                       'The space boundary is not 2nd level',
                                       error)
        self.apply_validation_function(self._check_description(bound),
                                       'Description - '
                                       'The space boundary description does '
                                       'not provide level information',
                                       error)
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
        self.apply_validation_function(self._check_phys_virt_bound(bound),
                                       'PhysicalOrVirtualBoundary - '
                                       'The space boundary is neither '
                                       'physical or virtual', error)
        self.apply_validation_function(self._check_int_ext_bound(bound),
                                       'InternalOrExternalBoundary - '
                                       'The space boundary is neither '
                                       'external or internal', error)
        self.apply_validation_function(self._check_on_relating_elem(bound),
                                       'SurfaceOnRelatingElement - '
                                       'The space boundary does not have a '
                                       'surface on the relating element', error)
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
        if hasattr(
                bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary,
                'Segments'):
            self.apply_validation_function(
                self._check_outer_boundary_composite(bound),
                'OuterBoundary - '
                'The space boundary surface on relating element outer '
                'boundary is missing', error)
            self.apply_validation_function(self._check_segments(bound),
                                           'OuterBoundary Segments - '
                                           'The space boundary surface on '
                                           'relating element outer boundary '
                                           'geometry is missing', error)
            self.apply_validation_function(self._check_segments_poly(bound),
                                           'OuterBoundary SegmentsPolyline - '
                                           'The space boundary surface on '
                                           'relating element outer boundary '
                                           'geometry is not well structured',
                                           error)
            self.apply_validation_function(
                self._check_segments_poly_coord(bound),
                'OuterBoundary Coordinates - '
                'The space boundary surface on relating element outer boundary '
                'coordinates are missing', error)
        else:
            self.apply_validation_function(
                self._check_outer_boundary_poly(bound),
                'OuterBoundary - '
                'The space boundary surface on relating element outer boundary '
                'is missing', error)
            self.apply_validation_function(
                self._check_outer_boundary_poly_coord(bound),
                'OuterBoundary Coordinates - '
                'The space boundary surface on relating element outer boundary '
                'coordinates are missing', error)

        self.apply_validation_function(self._check_plane_position(bound),
                                       'Position - '
                                       'The space boundary surface on relating '
                                       'element plane position is missing',
                                       error)
        self.apply_validation_function(self._check_location(bound),
                                       'Location - '
                                       'The space boundary surface on relating '
                                       'element location is missing', error)
        self.apply_validation_function(self._check_axis(bound),
                                       'Axis - '
                                       'The space boundary surface on relating '
                                       'element axis are missing',
                                       error)
        self.apply_validation_function(self._check_refdirection(bound),
                                       'RefDirection - '
                                       'The space boundary surface on relating '
                                       'element reference direction is '
                                       'missing', error)
        self.apply_validation_function(self._check_location_coord(bound),
                                       'LocationCoordinates - '
                                       'The space boundary surface on relating '
                                       'element location coordinates are '
                                       'missing', error)
        self.apply_validation_function(self._check_axis_dir_ratios(bound),
                                       'AxisDirectionRatios - '
                                       'The space boundary surface on relating '
                                       'element axis direction ratios are '
                                       'missing', error)
        self.apply_validation_function(
            self._check_refdirection_dir_ratios(bound),
            'RefDirectionDirectionRatios - '
            'The space boundary surface on relating element position '
            'reference direction is missing', error)

        return error

    def validate_elements(self, inst: entity_instance) -> list:
        """
        Validation function for an instance that compiles all instance
        validation functions.

        Args:
            inst:IFC instance being checked

        Returns:
            error: list of elements error

        """
        error: list = []
        self.apply_validation_function(self._check_unique(inst, self.id_list),
                                       'GlobalId - '
                                       'The instance GlobalID is not unique'
                                       , error)
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
        self.apply_validation_function(self._check_inst_contained_in_structure(inst),
                                       'ContainedInStructure - '
                                       'The instance is not contained in any '
                                       'structure', error)
        self.apply_validation_function(self._check_inst_representation(inst),
                                       'Representation - '
                                       'The instance has no geometric '
                                       'representation', error)
        return error

    @staticmethod
    def _check_level(bound: entity_instance):
        """
        Check that the space boundary is of the second level type

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.Name == "2ndLevel"

    @staticmethod
    def _check_description(bound: entity_instance):
        """
        Check that the space boundary description is 2a or 2b

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.Description in {'2a', '2b'}

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

    @staticmethod
    def _check_conn_geom(bound: entity_instance):
        """
        Check that the space boundary has a connection geometry and has the
        correct class.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.ConnectionGeometry.is_a('IfcConnectionGeometry')

    @staticmethod
    def _check_phys_virt_bound(bound: entity_instance):
        """
        Check that the space boundary is virtual or physical.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.PhysicalOrVirtualBoundary.upper() in \
            {'PHYSICAL', 'VIRTUAL', 'NOTDEFINED'}

    @staticmethod
    def _check_int_ext_bound(bound: entity_instance):
        """
        Check that the space boundary is internal or external.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.InternalOrExternalBoundary.upper() in {'INTERNAL',
                                                            'EXTERNAL',
                                                            'EXTERNAL_EARTH',
                                                            'EXTERNAL_FIRE',
                                                            'EXTERNAL_WATER'
                                                            }

    @staticmethod
    def _check_on_relating_elem(bound: entity_instance):
        """
        Check that the surface on relating element of a space boundary has
        the geometric information.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.ConnectionGeometry.SurfaceOnRelatingElement.is_a(
            'IfcCurveBoundedPlane')

    @staticmethod
    def _check_on_related_elem(bound: entity_instance):
        """
        Check that the surface on related element of a space boundary has no
        geometric information.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return (bound.ConnectionGeometry.SurfaceOnRelatedElement is None or
                bound.ConnectionGeometry.SurfaceOnRelatedElement.is_a(
                    'IfcCurveBoundedPlane'))

    @staticmethod
    def _check_basis_surface(bound: entity_instance):
        """
        Check that the surface on relating element of a space boundary is
        represented by an IFC Place.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.ConnectionGeometry.SurfaceOnRelatingElement. \
            BasisSurface.is_a('IfcPlane')

    @staticmethod
    def _check_inner_boundaries(bound: entity_instance):
        """
        Check if the surface on relating element of a space boundary inner
        boundaries don't exists or are composite curves.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return (bound.ConnectionGeometry.SurfaceOnRelatingElement.
                InnerBoundaries is None) or \
               (i.is_a('IfcCompositeCurve') for i in bound.ConnectionGeometry.
                   SurfaceOnRelatingElement.InnerBoundaries)

    @staticmethod
    def _check_outer_boundary_composite(bound: entity_instance):
        """
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
    def _check_segments(bound: entity_instance):
        """
        Check if the surface on relating element of a space boundary outer
        boundaries segments are polyline.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return (s.is_a('IfcCompositeCurveSegment') for s in
                bound.ConnectionGeometry.SurfaceOnRelatingElement.
                OuterBoundary.Segments)

    @classmethod
    def _check_segments_poly(cls, bound: entity_instance):
        """
        Check segments of an outer boundary of a surface on relating element.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return all(cls._check_poly_points(s.ParentCurve)
                   for s in
                   bound.ConnectionGeometry.SurfaceOnRelatingElement
                   .OuterBoundary.Segments)

    @classmethod
    def _check_segments_poly_coord(cls, bound: entity_instance):
        """
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

    @classmethod
    def _check_outer_boundary_poly(cls, bound: entity_instance):
        """
        Check points of outer boundary of a surface on relating element.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return cls._check_poly_points(
            bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary)

    @staticmethod
    def _check_outer_boundary_poly_coord(bound: entity_instance):
        """
        Check outer boundary of a surface on relating element.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return all(
            bound.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary)

    @staticmethod
    def _check_plane_position(bound: entity_instance):
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
    def _check_location(bound: entity_instance):
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
    def _check_axis(bound: entity_instance):
        """
        Check that axis of space boundary is an IfcDirection.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface. \
            Position.Axis.is_a('IfcDirection')

    @staticmethod
    def _check_refdirection(bound: entity_instance):
        """
        Check that reference direction of space boundary is an IfcDirection.

        Args:
            bound: Space boundary IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return bound.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface. \
            Position.RefDirection.is_a('IfcDirection')

    @classmethod
    def _check_location_coord(cls, bound: entity_instance):
        """
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
    def _check_axis_dir_ratios(cls, bound: entity_instance):
        """
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
    def _check_refdirection_dir_ratios(cls, bound: entity_instance):
        """
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
    def _check_poly_points(polyline: entity_instance):
        """
        Check if a polyline has the correct class.

        Args:
            polyline: Polyline IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return polyline.is_a('IfcPolyline')

    @staticmethod
    def _check_coords(points: entity_instance):
        """
        Check coordinates of a group of points (class and length).

        Args:
            points: Points IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return points.is_a('IfcCartesianPoint') and 1 <= len(
            points.Coordinates) <= 4

    @staticmethod
    def _check_dir_ratios(dir_ratios: entity_instance):
        """
        Check length of direction ratios.

        Args:
            dir_ratios: direction ratios IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return 2 <= len(dir_ratios.DirectionRatios) <= 3

    @classmethod
    def _check_poly_points_coord(cls, polyline: entity_instance):
        """
        Check if a polyline has the correct coordinates.

        Args:
            polyline: Polyline IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return all(cls._check_coords(p) for p in polyline.Points)

    @staticmethod
    def _check_inst_sb(inst: entity_instance):
        """
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
            decompose: list = []
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
    def _check_inst_materials(inst: entity_instance):
        """
        Check that an instance has associated materials.

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

    @staticmethod
    def _check_inst_contained_in_structure(inst: entity_instance):
        """
        Check that an instance is contained in an structure.

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
    def _check_inst_representation(inst: entity_instance):
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
