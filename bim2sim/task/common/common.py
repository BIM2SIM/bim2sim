import logging
import os
import json
import inspect

from typing import Tuple, List, Any, Type, Set, Dict, Generator
from bim2sim.decision import Decision, ListDecision, DecisionBunch
from bim2sim.filter import TypeFilter, TextFilter
from bim2sim.kernel import ifc2python
from bim2sim.kernel.element import Factory, ProductBased
from bim2sim.kernel.units import parse_ifc
from ifcopenshell.file import file
from bim2sim.task.base import ITask
from bim2sim.kernel.ifc2python import get_property_sets
from bim2sim.kernel import attribute
from mako.template import Template
from mako.lookup import TemplateLookup
from bim2sim.workflow import Workflow


class Reset(ITask):
    """Reset all progress"""

    touches = '__reset__'
    single_use = False

    @classmethod
    def requirements_met(cls, state, history):
        return bool(state)

    def run(self, workflow):
        return {}


class Quit(ITask):
    """Quit interactive tasks"""

    final = True
    single_use = False


class LoadIFC(ITask):
    """Load IFC file from PROJECT.ifc path (file or dir)"""
    touches = ('ifc', )

    def run(self, workflow):
        # TODO: use multiple ifs files

        path = self.paths.ifc

        if os.path.isdir(path):
            ifc_path = self.get_ifc(path)
        elif os.path.isfile(path):
            ifc_path = path
        else:
            raise AssertionError("No ifc found. Check '%s'" % path)
        ifc = ifc2python.load_ifc(os.path.abspath(ifc_path))
        workflow.ifc_units.update(**self.get_ifcunits(ifc))

        # Schema2Python.get_ifc_structure(ifc)

        self.logger.info("The exporter version of the IFC file is '%s'",
                         ifc.wrapped_data.header.file_name.originating_system)
        return ifc,

    def get_ifc(self, path):
        """Returns first ifc from ifc folder"""
        lst = []
        for file in os.listdir(path):
            if file.lower().endswith(".ifc"):
                lst.append(file)

        if len(lst) == 1:
            return os.path.join(path, lst[0])
        if len(lst) > 1:
            self.logger.warning("Found multiple ifc files. Selected '%s'.", lst[0])
            return os.path.join(path, lst[0])

        self.logger.error("No ifc found in project folder.")
        return None

    @staticmethod
    def get_ifcunits(ifc: file):
        """Returns dict with units available on ifc file"""

        unit_assignment = ifc.by_type('IfcUnitAssignment')

        results = {}

        for unit_entity in unit_assignment[0].Units:
            try:
                key = 'Ifc{}'.format(unit_entity.UnitType.capitalize().replace('unit', 'Measure'))
                pos_key = 'IfcPositive{}'.format(unit_entity.UnitType.capitalize().replace('unit', 'Measure'))
                unit = parse_ifc(unit_entity)
                results[key] = unit
                results[pos_key] = unit

                # unit_type = unit_entity.is_a()
                # if unit_type == 'IfcDerivedUnit':
                #     pass  # TODO: Implement
                # elif unit_type == 'IfcSIUnit':
                #     key = 'Ifc{}'.format(unit_entity.UnitType.capitalize().replace('unit', 'Measure'))
                #     prefix_string = unit_entity.Prefix.lower() if unit_entity.Prefix else ''
                #     unit = ureg.parse_units('{}{}'.format(prefix_string, ifc_pint_unitmap[unit_entity.Name]))
                #     if unit_entity.Dimensions:
                #         unit = unit**unit_entity.Dimensions
                #     results[key] = unit
                # elif unit_type == 'IfcConversionBasedUnit':
                #     pass  # TODO: Implement
                # elif unit_type == 'IfcMonetaryUnit':
                #     pass  # TODO: Implement
                # else:
                #     pass  # TODO: Implement
            except:
                print("Failed to parse %s" % unit_entity)

        return results


class CreateElements(ITask):
    """Create internal elements from IFC."""

    reads = ('ifc',)
    touches = ('instances', 'finder')

    def run(self, workflow, ifc):
        self.logger.info("Creates elements of relevant ifc types")
        default_ifc_types = {'IfcBuildingElementProxy', 'IfcUnitaryEquipment'}
        relevant_ifc_types = self.get_ifc_types(workflow.relevant_elements)
        relevant_ifc_types.update(default_ifc_types)

        self.factory = Factory(
            workflow.relevant_elements,
            workflow.ifc_units,
            self.paths.finder)
        # use finder to get correct export tool
        for app in ifc.by_type('IfcApplication'):
            for decision in self.factory.finder.check_tool_template(
                    app.ApplicationFullName):
                yield DecisionBunch([decision])
        # Filtering:
        #  filter returns dict of entities: suggested class and list of unknown
        #  accept_valids returns created elements and lst of invalids

        instance_lst = []
        entity_best_guess_dict = {}
        # filter by type
        type_filter = TypeFilter(relevant_ifc_types)
        entity_type_dict, unknown_entities = type_filter.run(ifc)

        # create valid elements
        valids, invalids = self.accept_valids(entity_type_dict)
        instance_lst.extend(valids)
        unknown_entities.extend(invalids)

        # filter by text
        text_filter = TextFilter(
            workflow.relevant_elements,
            workflow.ifc_units,
            ['Description'])
        entity_class_dict, unknown_entities = yield from self.filter_by_text(
            text_filter, unknown_entities, workflow.ifc_units)
        entity_best_guess_dict.update(entity_class_dict)
        valids, invalids = self.accept_valids(entity_class_dict, force=True)
        instance_lst.extend(valids)
        unknown_entities.extend(invalids)

        self.logger.info("Found %d relevant elements", len(instance_lst))
        self.logger.info("Found %d ifc_entities that could not be "
                         "identified and transformed into a python element.",
                         len(unknown_entities))

        # Identification of remaining entities by user
        entity_class_dict, unknown_entities = yield from self.set_class_by_user(
            unknown_entities, workflow.relevant_elements, entity_best_guess_dict)
        entity_best_guess_dict.update(entity_class_dict)
        invalids = []
        for element_cls, ifc_entities in entity_class_dict.items():
            for ifc_entity in ifc_entities:
                try:
                    item = self.factory.create(element_cls, ifc_entity)
                    instance_lst.append(item)
                except Exception as ex:
                    invalids.append(ifc_entity)
        if invalids:
            self.logger.info("Removed %d entities with no class set",
                             len(invalids))

        self.logger.info("Created %d elements", len(instance_lst))
        instances = {inst.guid: inst for inst in instance_lst}
        return instances, self.factory.finder

    # todo rename to "create_valids"
    def accept_valids(self, entities_dict, warn=True, force=False) -> \
            Tuple[List[ProductBased], List[Any]]:
        """Instantiate ifc_entities using given element class.
        Resulting instances are validated (if not force).
        Results are two lists, one with valid elements and one with
        remaining entities."""
        valid, invalid = [], []
        layersets_all = []
        constituents_all = []
        materials_all = []
        layers_all = []
        blacklist = [
            'IfcMaterialLayerSet',
            'IfcMaterialLayer',
            'IfcMaterial',
            'IfcMaterialConstituentSet',
            'IfcMaterialConstituent',
            'IfcMaterialProfile',
            'IfcMaterialProfileSet',
        ]

        for entity, ifc_type_or_element_cls in entities_dict.items():
            try:
                if isinstance(ifc_type_or_element_cls, str):
                    if ifc_type_or_element_cls in blacklist:
                        continue
                    element = self.factory(
                        entity, ifc_type=ifc_type_or_element_cls,
                        use_dummy=False)
                else:
                    # todo if class is implemented instead of string we need to
                    #  check against blacklist of classes
                    element = self.factory.create(
                        ifc_type_or_element_cls, entity)
            except LookupError:
                invalid.append(entity)
                continue

            if hasattr(element.ifc, 'HasAssociations'):
                for association in element.ifc.HasAssociations:
                    if association.is_a("IfcRelAssociatesMaterial"):
                        ifc_mat_rel_object = association.RelatingMaterial
                        # Layers
                        ifc_layerset_entity = None
                        if ifc_mat_rel_object.is_a('IfcMaterialLayerSetUsage'):
                            ifc_layerset_entity = ifc_mat_rel_object.ForLayerSet
                        elif ifc_mat_rel_object.is_a('IfcMaterialLayerSet'):
                            ifc_layerset_entity = ifc_mat_rel_object
                        if ifc_layerset_entity:
                            # check if layerset already exists
                            is_existing = False
                            for layerset in layersets_all:
                                if ifc_layerset_entity == layerset.ifc:
                                    is_existing = True
                                    break
                            if not is_existing:
                                # create otherwise
                                layerset = self.factory(
                                    ifc_layerset_entity,
                                    ifc_type='IfcMaterialLayerSet',
                                    use_dummy=False)
                                layersets_all.append(layerset)
                                valid.append(layerset)
                            layerset.parents.append(element)
                            element.layerset = layerset
                            for ifc_layer_entity in ifc_layerset_entity.MaterialLayers:
                                is_existing = False
                                for layer in layers_all:
                                    if ifc_layer_entity == layer.ifc:
                                        is_existing = True
                                        break
                                if not is_existing:
                                    layer = self.factory(
                                        ifc_layer_entity,
                                        ifc_type='IfcMaterialLayer',
                                        use_dummy=False)
                                    layers_all.append(layer)
                                    valid.append(layer)
                                layer.to_layerset.append(layerset)
                                layerset.layers.append(layer)
                                ifc_material_entity = ifc_layer_entity.Material
                                # check if material already exists
                                is_existing = False
                                for material in materials_all:
                                    if ifc_material_entity == material.ifc:
                                        is_existing = True
                                        break
                                if not is_existing:
                                    material = self.factory(
                                        ifc_material_entity,
                                        ifc_type='IfcMaterial',
                                        use_dummy=False)
                                    materials_all.append(material)
                                    valid.append(material)
                                material.parents.append(layer)
                                layer.material = material

                        # Constituent sets
                        if ifc_mat_rel_object.is_a(
                                'IfcMaterialConstituentSet'):
                            for ifc_constituent in ifc_mat_rel_object.MaterialConstituents:
                                ifc_material_entity = ifc_constituent.Material
                                # check if material already exists

                                is_existing = False
                                for material in materials_all:
                                    if ifc_material_entity == material.ifc:
                                        is_existing = True
                                        break
                                if not is_existing:
                                    # create new material
                                    material = self.factory(
                                        ifc_material_entity,
                                        ifc_type='IfcMaterial',
                                        use_dummy=False)
                                    constituents_all.append(ifc_constituent)
                                fraction = ifc_constituent.Fraction
                                material.parents.append(element)
                                element.material_set[fraction] = material
                                materials_all.append(material)

                        # Profiles
                        # TODO maybe use in future
                        if ifc_mat_rel_object.is_a(
                                'IfcMaterialProfileSetUsage'):
                            pass
                        elif ifc_mat_rel_object.is_a(
                            'IfcMaterialProfileSet'):
                            pass
                        elif ifc_mat_rel_object.is_a(
                            'IfcMaterialProfile'):
                            pass

            if element.validate_creation():
                valid.append(element)
            elif force:
                valid.append(element)
                if warn:
                    self.logger.warning("Force accept invalid element %s %s",
                                        ifc_type_or_element_cls, element)
            else:
                if warn:
                    self.logger.warning("Validation failed for %s %s",
                                        ifc_type_or_element_cls, element)
                invalid.append(entity)

        return valid, invalid

    def filter_by_text(self, text_filter, ifc_entities, ifc_units: dict) \
            -> Generator[DecisionBunch, None,
                         Tuple[Dict[Any, Type[ProductBased]], List]]:
        """Generator method filtering ifc elements by given TextFilter.

        yields decision bunch for ambiguous results"""
        entities_dict, unknown_entities = text_filter.run(ifc_entities)
        answers = {}
        decisions = DecisionBunch()
        for entity, classes in entities_dict.items():
            sorted_classes = sorted(classes, key=lambda item: item.key)
            if len(sorted_classes) > 1:
                # choices
                choices = []
                for element_cls in sorted_classes:
                    # TODO: filter_for_text_fragments() already called in text_filter.run()
                    hints = f"Matches: '" + "', '".join(
                        element_cls.filter_for_text_fragments(
                            entity, ifc_units)) + "'"
                    choices.append([element_cls.key, hints])
                choices.append(["Other", "Other"])
                decisions.append(ListDecision(
                    f"Searching for text fragments in [Name: '{entity.Name}', "
                    f"Description: '{entity.Description}]' gave the following class hints. Please select best match.",
                    choices=choices,
                    key=entity,
                    global_key="TextFilter:%s.%s" % (entity.is_a(), entity.GlobalId),
                    allow_skip=True,
                    context=[entity.GlobalId]))
            elif len(sorted_classes) == 1:
                answers[entity] = sorted_classes[0].key
            # empty classes are covered below
        yield decisions
        answers.update(decisions.to_answer_dict())
        result_entity_dict = {}
        for ifc_entity, element_classes in entities_dict.items():
            element_key = answers.get(ifc_entity)
            element_cls = ProductBased.key_map.get(element_key)
            if element_cls:
                result_entity_dict[ifc_entity] = element_cls
            else:
                unknown_entities.append(ifc_entity)

        return result_entity_dict, unknown_entities

    def set_class_by_user(self, unknown_entities, possible_elements, best_guess_dict):
        """Ask user for every given ifc_entity to specify matching element class"""
        sorted_elements = sorted(possible_elements, key=lambda item: item.key)
        checksum = Decision.build_checksum([pe.key for pe in sorted_elements])  # assert same list of ifc_classes
        decisions = DecisionBunch()
        for ifc_entity in sorted(unknown_entities,
                                 key=lambda it: it.Name + it.GlobalId):
            best_guess_cls = best_guess_dict.get(ifc_entity)
            best_guess = best_guess_cls.key if best_guess_cls else None
            decisions.append(ListDecision(
                "Found unidentified Element of %s (Name: %s, Description: %s):" % (
                    ifc_entity.is_a(), ifc_entity.Name, ifc_entity.Description),
                choices=[ele.key for ele in sorted_elements],
                default=best_guess,
                key=ifc_entity,
                global_key="SetClass:%s.%s" % (ifc_entity.is_a(), ifc_entity.GlobalId),
                allow_skip=True,
                validate_checksum=checksum))
        yield decisions
        answers = decisions.to_answer_dict()
        result_entity_dict = {}
        ignore = []
        for ifc_entity, element_key in answers.items():

            if element_key is None:
                ignore.append(ifc_entity)
            else:
                element_cls = ProductBased.key_map[element_key]
                lst = result_entity_dict.setdefault(element_cls, [])
                lst.append(ifc_entity)

        return result_entity_dict, ignore

    def get_ifc_types(self, relevant_elements: List[Type[ProductBased]]) \
            -> Set[str]:
        """Extract used ifc types from list of elements."""
        relevant_ifc_types = []
        for ele in relevant_elements:
            relevant_ifc_types.extend(ele.ifc_types.keys())
        return set(relevant_ifc_types)

    def create_valid_material_related(self, entities_dict, ifc, warn=True,
                                      force=False):
        """

        Args:
            entities_dict:

        Returns:

        """
        valid, invalid = [], []
        for entity, ifc_type_or_element_cls in entities_dict.items():
            try:
                if isinstance(ifc_type_or_element_cls, str):
                    element = self.factory(
                        entity, ifc_type=ifc_type_or_element_cls,
                        use_dummy=False)
                else:
                    element = self.factory.create(
                        ifc_type_or_element_cls, entity)
            except LookupError:
                invalid.append(entity)
                continue


            if element.validate_creation():
                valid.append(element)
            elif force:
                valid.append(element)
                if warn:
                    self.logger.warning("Force accept invalid element %s %s",
                                        ifc_type_or_element_cls, element)
            else:
                if warn:
                    self.logger.warning("Validation failed for %s %s",
                                        ifc_type_or_element_cls, element)
                invalid.append(entity)
        return valid, invalid


class CheckIfc(ITask):
    """
    Check an IFC file, for a number of conditions (missing information,
    incorrect information, etc) that could lead on future tasks to fatal errors.
    """
    reads = ('ifc',)
    touches = ('errors',)

    def __init__(self):
        super().__init__()
        self.error_summary_sub_inst = {}
        self.error_summary_inst = {}
        self.error_summary_prop = {}
        self.sub_inst = []
        self.id_list = []
        self.instances = []
        self.ps_summary = {}
        self.ifc_units = {}
        self.sub_inst_cls = None
        self.plugin = None

    def run(self, workflow: Workflow, ifc) -> [dict, dict]:
        """
        Analyzes sub_instances and instances of an IFC file for the validation
        functions and export the errors found as .json and .html files.

        Args:
            workflow: Workflow used on task
            ifc: IFC file translated with ifcopenshell

        Returns:
            error_summary_sub_inst: summary of errors related to sub_instances
            error_summary_inst: summary of errors related to instances
        """
        self.ps_summary = self._get_class_property_sets(self.plugin)
        self.ifc_units = workflow.ifc_units
        self.sub_inst = ifc.by_type(self.sub_inst_cls)
        self.instances = self.get_relevant_instances(ifc)
        self.id_list = [e.GlobalId for e in ifc.by_type("IfcRoot")]
        self.error_summary_sub_inst = self.check_inst(
            self.validate_sub_inst, self.sub_inst)
        self.error_summary_inst = self.check_inst(
            self.validate_instances, self.instances)
        instance_errors = sum(len(errors) for errors in
                              self.error_summary_inst.values())
        quality_logger = logging.getLogger('bim2sim.QualityReport')
        quality_logger.warning('%d errors were found on %d instances' %
                            (instance_errors, len(self.error_summary_inst)))
        sub_inst_errors = sum(len(errors) for errors in list(
            self.error_summary_sub_inst.values()))
        quality_logger.warning('%d errors were found on %d sub_instances' %
                            (sub_inst_errors, len(self.error_summary_sub_inst)))
        self._write_errors_to_json(self.plugin)
        self._write_errors_to_html_table(self.plugin)
        return [self.error_summary_sub_inst, self.error_summary_inst],

    @staticmethod
    def _get_ifc_type_classes(plugin):
        """
        Gets all the classes of a plugin, that represent an IFCProduct,
        and organize them on a dictionary for each ifc_type
        Args:
            plugin: plugin used in the check task (bps or hvac)

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
            if plugin_class.ifc_types:
                for ifc_type in plugin_class.ifc_types.keys():
                    cls_summary[ifc_type] = plugin_class
        return cls_summary

    @classmethod
    def _get_class_property_sets(cls, plugin):
        """
        Gets all property sets and properties required for bim2sim for all
        classes of a plugin, that represent an IFCProduct, and organize them on
        a dictionary for each ifc_type
        Args:
            plugin: plugin used in the check task (bps or hvac)

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

    def get_relevant_instances(self, ifc):
        """
        Gets all relevant ifc instances based on the plugin's classes that
        represent an IFCProduct

        Args:
            ifc: IFC file translated with ifcopenshell

        Returns:
            ifc_instances: list of IFC instance (Products)

        """
        relevant_ifc_types = list(self.ps_summary.keys())
        ifc_instances = []
        for ifc_type in relevant_ifc_types:
            ifc_instances.extend(ifc.by_type(ifc_type))
        return ifc_instances

    @staticmethod
    def check_inst(validation_function, instances: list):
        """
        Uses sb_validation/ports/instances functions in order to check each
        one and adds error to dictionary if object has errors.
        Args:
            validation_function: function that compiles all the validations
                to be performed on the object (sb/port/instance)
            instances: list containing all objects to be evaluates

        Returns:
            summary: summarized dictionary of errors, where the key is the
                GUID + the ifc_type

        """
        summary = {}
        for inst in instances:
            error = validation_function(inst)
            if len(error) > 0:
                if hasattr(inst, 'GlobalId'):
                    key = inst.GlobalId + ' ' + inst.is_a()
                else:
                    key = inst.is_a()
                summary.update({key: error})
        return summary

    def validate_sub_inst(self, sub_inst) -> list:
        raise NotImplementedError

    def validate_instances(self, inst) -> list:
        raise NotImplementedError

    @staticmethod
    def apply_validation_function(fct, err_name: str, error: list):
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

    def _write_errors_to_json(self, plugin):
        """
        Function to write the resulting list of errors to a .json file as a
        summary.

        Args:
            plugin: plugin used in the check task (bps or hvac)

        """
        plugin_name = plugin.__name__.split('.')[-1].upper()
        with open(str(self.paths.log) +
                  '\ifc_%s_sub_inst_error_summary.json' % plugin_name,
                  'w+') as fp:
            json.dump(self.error_summary_sub_inst, fp, indent="\t")
        with open(str(self.paths.log) +
                  '\ifc_%s_inst_error_summary.json' % plugin_name,
                  'w+') as fp:
            json.dump(self.error_summary_inst, fp, indent="\t")

    @staticmethod
    def _categorize_errors(error_dict):
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

    # general check functions
    @staticmethod
    def _check_unique(inst, id_list):
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

    def _check_inst_properties(self, inst):
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
    def _check_inst_representation(inst):
        """
        Check that an instance has a correct geometric representation.

        Args:
            inst: IFC instance

        Returns:
            True: if check succeeds
            False: if check fails
        """
        return inst.Representation is not None

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
            filename=os.path.join(path_templates, "summary_template"),
            lookup=lookup)
        return templates

    def _write_errors_to_html_table(self, plugin):
        """
        Writes all errors in the html templates in a summarized way

        Args:
            plugin: plugin used in the check task (bps or hvac)

        """
        templates = self.get_html_templates()
        plugin_name = plugin.__name__.split('.')[-1].upper()
        summary_inst = self._categorize_errors(self.error_summary_inst)
        summary_sbs = self._categorize_errors(self.error_summary_sub_inst)
        summary_props = self._categorize_errors(self.error_summary_prop)
        all_errors = {**summary_inst['per_type'], **summary_sbs['per_type']}

        with open(str(self.paths.log) +
                  '\%s_error_summary_inst.html' % plugin_name, 'w+') as \
                out_file:
            out_file.write(templates["inst_template"].render_unicode(
                task=self,
                summary_inst=summary_inst,
                summary_sbs=summary_sbs,
                all_errors=all_errors))
            out_file.close()
        with open(str(self.paths.log) +
                  '\%s_error_summary_prop.html' % plugin_name, 'w+') as \
                out_file:
            out_file.write(templates["prop_template"].render_unicode(
                task=self,
                summary_props=summary_props))
            out_file.close()
        with open(str(self.paths.log) +
                  '\%s_error_summary.html' % plugin_name, 'w+') as out_file:
            out_file.write(templates["summary_template"].render_unicode(
                task=self,
                plugin_name=plugin_name,
                summary_inst=summary_inst,
                summary_sbs=summary_sbs,
                summary_props=summary_props))
            out_file.close()
