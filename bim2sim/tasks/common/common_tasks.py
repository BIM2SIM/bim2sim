from __future__ import annotations

import inspect
import json
import logging
import os
import warnings
from typing import Tuple, List, Any, Type, Set, Dict, Generator, TYPE_CHECKING

import pandas as pd
from mako.lookup import TemplateLookup
from mako.template import Template
from string_grouper import group_similar_strings
from ifcopenshell import file

from bim2sim.kernel.decision import Decision, ListDecision, DecisionBunch
from bim2sim.kernel.filter import TypeFilter, TextFilter
from bim2sim.kernel import attribute, IFCDomainError
from bim2sim.utilities import ifc2python
from bim2sim.elements.base_elements import Factory, ProductBased, Material
from bim2sim.utilities.ifc2python import get_property_sets
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import all_subclasses
from bim2sim.utilities.types import IFCDomain
from bim2sim.kernel.ifc_file import IfcFileClass
from bim2sim.tasks.base import Playground

from bim2sim.elements import bps_elements as bps
from bim2sim.elements import hvac_elements as hvac
from bim2sim.utilities.ifc2python import get_layers_ifc
from ifcopenshell.entity_instance import entity_instance

from bim2sim.utilities.ifc2python import get_ports

if TYPE_CHECKING:
    from pathlib import Path


class Reset(ITask):
    """Reset all progress"""

    touches = '__reset__'
    single_use = False

    @classmethod
    def requirements_met(cls, state, history):
        return bool(state)

    def run(self, sim_settings):
        return {}


class Quit(ITask):
    """Quit interactive tasks"""

    final = True
    single_use = False


class LoadIFC(ITask):
    """Load all IFC files from PROJECT.ifc_base path.

    This tasks reads the IFC files of one or multiple domains inside bim2sim.

    Returns:
        ifc: list of one or multiple IfcFileClass instances
    """
    touches = ('ifc_files', )

    def run(self):
        self.logger.info("Loading IFC files")
        base_path = self.paths.ifc_base
        ifc_files = yield from self.load_ifc_files(base_path)
        return ifc_files,

    def load_ifc_files(self, base_path: Path):
        """Load all ifc files in given base_path or a specific file in this path

        Loads the ifc files inside the different domain folders in the base
         path, and initializes the bim2sim ifc file classes.

         Args:
            base_path: Pathlib path that holds the different domain folders,
              which hold the ifc files.
        """
        if not base_path.is_dir():
            raise AssertionError(f"Given base_path {base_path} is not a"
                                 f" directory. Please provide a directory.")
        ifc_files = []
        for total_ifc_path in base_path.glob("**/*.ifc"):
            ifc_domain = total_ifc_path.parent.name
            reset_guids = self.playground.sim_settings.reset_guids
            ifc_domain = IFCDomain[ifc_domain]
            ifc_file_cls = IfcFileClass(
                total_ifc_path,
                ifc_domain=ifc_domain,
                reset_guids=reset_guids)
            yield from ifc_file_cls.initialize_finder(self.paths.finder)
            ifc_files.append(ifc_file_cls)
            self.logger.info(f"Loaded {total_ifc_path.name} for Domain "
                             f"{ifc_domain.name}")
        if not ifc_files:
            self.logger.error("No ifc found in project folder.")
            raise AssertionError("No ifc found. Check '%s'" % base_path)
        self.logger.info(f"Loaded {len(ifc_files)} IFC-files.")
        return ifc_files


class CreateElements(ITask):
    """Create internal elements from IFC."""

    reads = ('ifc_files',)
    touches = ('instances', 'ifc_files')

    def __init__(self, playground):
        super().__init__(playground)
        self.factory = None
        self.source_tools = []
        self.layersets_all = []
        self.materials_all = []
        self.layers_all = []

    def run(self, ifc_files: [IfcFileClass]):
        self.logger.info("Creates elements of relevant ifc types")
        default_ifc_types = {'IfcBuildingElementProxy', 'IfcUnitaryEquipment'}
        # Todo maybe move this into IfcFileClass instead simulation settings
        relevant_elements = self.playground.sim_settings.relevant_elements
        relevant_ifc_types = self.get_ifc_types(relevant_elements)
        relevant_ifc_types.update(default_ifc_types)

        instances = {}
        for ifc_file in ifc_files:
            self.factory = Factory(
                relevant_elements,
                ifc_file.ifc_units,
                ifc_file.domain,
                ifc_file.finder)

            # Filtering:
            #  filter returns dict of entities: suggested class and list of unknown
            #  accept_valids returns created elements and lst of invalids

            instance_lst = []
            entity_best_guess_dict = {}
            # filter by type
            type_filter = TypeFilter(relevant_ifc_types)
            entity_type_dict, unknown_entities = type_filter.run(ifc_file.file)

            # create valid elements
            valids, invalids = self.create_with_validation(entity_type_dict)
            instance_lst.extend(valids)
            unknown_entities.extend(invalids)

            # filter by text
            text_filter = TextFilter(
                relevant_elements,
                ifc_file.ifc_units,
                ['Description'])
            entity_class_dict, unknown_entities = yield from self.filter_by_text(
                text_filter, unknown_entities, ifc_file.ifc_units)
            entity_best_guess_dict.update(entity_class_dict)
            valids, invalids = self.create_with_validation(
                entity_class_dict, force=True)
            instance_lst.extend(valids)
            unknown_entities.extend(invalids)

            self.logger.info("Found %d relevant elements", len(instance_lst))
            self.logger.info("Found %d ifc_entities that could not be "
                             "identified and transformed into a python element.",
                             len(unknown_entities))

            # identification of remaining entities by user
            entity_class_dict, unknown_entities = yield from self.set_class_by_user(
                unknown_entities,
                self.playground.sim_settings,
                entity_best_guess_dict)
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

            self.logger.info(f"Created {len(instance_lst)} bim2sim instances "
                             f"based on IFC file {ifc_file.ifc_file_name}")
            instances.update({inst.guid: inst for inst in instance_lst})
        if not instances:
            self.logger.error("No bim2sim elements could be created based on "
                              "the IFC files.")
            raise AssertionError("No bim2sim elements could be created, program"
                                 "will be finished as no further process is "
                                 "possible.")
        self.logger.info(f"Created {len(instances)} bim2sim instances in "
                         f"total for all IFC files.")
        return instances, ifc_files

    def create_with_validation(self, entities_dict, warn=True, force=False) -> \
            Tuple[List[ProductBased], List[Any]]:
        """Instantiate ifc_entities using given element class.

        The given ifc entities are used to create bim2sim instances via factory
        method. After the creation the associated layers and material are
        created (see create_layers_and_materials).
        All created instances (including material and layers) are checked
        against the provided conditions and classified into valid and invalid.

        Args:
            entities_dict: dict with ifc entities
            warn: boolean to warn if something condition fail
            force: boolean if conditions should be ignored

        Returns:
            valid: list of all valid items that fulfill the conditions
            invalid: list of all instances that do not fulfill the conditions

        """
        valid, invalid = [], []
        blacklist = [
            'IfcMaterialLayerSet',
            'IfcMaterialLayer',
            'IfcMaterial',
            'IfcMaterialConstituentSet',
            'IfcMaterialConstituent',
            'IfcMaterialProfile',
            'IfcMaterialProfileSet',
        ]

        blacklist_classes = [
            bps.LayerSet, bps.Layer, Material
        ]

        for entity, ifc_type_or_element_cls in entities_dict.items():
            try:
                if isinstance(ifc_type_or_element_cls, str):
                    if ifc_type_or_element_cls in blacklist:
                        continue
                    try:
                        element = self.factory(
                            entity, ifc_type=ifc_type_or_element_cls,
                            use_dummy=False)
                    except IFCDomainError:
                        continue
                else:
                    if ifc_type_or_element_cls in blacklist_classes:
                        continue
                    element = self.factory.create(
                        ifc_type_or_element_cls, entity)
            except LookupError:
                invalid.append(entity)
                continue

            self.create_layers_and_materials(element)
            valid += self.layersets_all + self.layers_all + self.materials_all

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

        return list(set(valid)), list(set(invalid))

    def create_layers_and_materials(self, element):
        """Create all layers and materials associated with the given element.

        Layers and materials are no IfcProducts and have no GUID.
        They are always associated to IfcProducts. To create the association
        between Product and layer or material we create layers and materials
        directly when creating the corresponding element and not directly based
        on their IFC type in the normal creation process.
        For more information how materials work in IFC have a look at

            `wiki.osarch.org`_.
              _wiki.osarch.org: https://wiki.osarch.org/index.php?title=IFC_-_
              Industry_Foundation_Classes/IFC_materials

        Args:
            element: the already created bim2sim instance
        """
        quality_logger = logging.getLogger(
            'bim2sim.QualityReport')
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
                        self.create_layersets(element, ifc_layerset_entity)

                    # Constituent sets
                    if ifc_mat_rel_object.is_a(
                            'IfcMaterialConstituentSet'):
                        ifc_material_constituents =\
                            ifc_mat_rel_object.MaterialConstituents
                        self.create_constituent(
                            element, ifc_material_constituents, quality_logger)

                    # Direct Material
                    if ifc_mat_rel_object.is_a('IfcMaterial'):
                        ifc_material_entity = ifc_mat_rel_object
                        material = self.create_material(ifc_material_entity)
                        element.material = material
                        material.parents.append(element)

                    # TODO maybe use in future
                    # Profiles
                    if ifc_mat_rel_object.is_a(
                            'IfcMaterialProfileSetUsage'):
                        pass
                    elif ifc_mat_rel_object.is_a(
                            'IfcMaterialProfileSet'):
                        pass
                    elif ifc_mat_rel_object.is_a(
                            'IfcMaterialProfile'):
                        pass

    def create_layersets(self, element, ifc_layerset_entity):
        """Instantiate the layerset and its layers and materials and link to
         element.

        Layersets in IFC are used to describe the layer structure of e.g. walls.

        Args:
            element: bim2sim instance
            ifc_layerset_entity: ifc entity of layerset
        """
        for layerset in self.layersets_all:
            if ifc_layerset_entity == layerset.ifc:
                break
        else:
            layerset = self.factory(
                ifc_layerset_entity,
                ifc_type='IfcMaterialLayerSet',
                use_dummy=False)
            self.layersets_all.append(layerset)

            for ifc_layer_entity in ifc_layerset_entity.MaterialLayers:
                layer = self.factory(
                    ifc_layer_entity,
                    ifc_type='IfcMaterialLayer',
                    use_dummy=False)
                self.layers_all.append(layer)
                layer.to_layerset.append(layerset)
                layerset.layers.append(layer)
                ifc_material_entity = ifc_layer_entity.Material
                material = self.create_material(ifc_material_entity)
                layer.material = material
                material.parents.append(layer)
        # add layerset to element and vice versa
        element.layerset = layerset
        layerset.parents.append(element)

    def create_constituent(
            self, element, ifc_material_constituents, quality_logger):
        """Instantiate the constituent set  and its  materials and link to
         element.

        Constituent sets in IFC are used to describe the e.g. windows which
        consist out of different materials (glass, frame etc.) or mixtures like
        concrete (sand, cement etc.).

        Args:
            element: bim2sim instance
            ifc_material_constituents: ifc entity of layerset
            quality_logger: instance of bim2sim quality logger
        """
        for ifc_constituent in ifc_material_constituents:
            ifc_material_entity = ifc_constituent.Material

            material = self.create_material(ifc_material_entity)
            fraction = ifc_constituent.Fraction
            # todo if every element of the constituent has a geometric
            #  representation we could use them to get the volume of the
            #  different sub constituents and create fractions from it
            if not fraction:
                quality_logger.warning(
                    f"{element} has a "
                    f"IfcMaterialConstituentSet but no"
                    f" information to fraction is provided")
                n = len(element.material_set)
                fraction = 'unknown_' + str(n)
            element.material_set[fraction] = material
            material.parents.append(element)

    def create_material(self, ifc_material_entity):
        """As materials are unique in IFC we only want to have on material
        instance per material."""
        for material in self.materials_all:
            if ifc_material_entity == material.ifc:
                break
        else:
            material = self.factory(
                ifc_material_entity,
                ifc_type='IfcMaterial',
                use_dummy=False)
            self.materials_all.append(material)
        return material

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
                    # TODO: filter_for_text_fragments()
                    #  already called in text_filter.run()
                    hints = f"Matches: '" + "', '".join(
                        element_cls.filter_for_text_fragments(
                            entity, ifc_units)) + "'"
                    choices.append([element_cls.key, hints])
                choices.append(["Other", "Other"])
                decisions.append(ListDecision(
                    question=f"Searching for text fragments in '{entity.Name}',"
                    f" gave the following class hints. "
                    f"Please select best match.",
                    console_identifier=f"Name: '{entity.Name}', "
                                       f"Description: '{entity.Description}'",
                    choices=choices,
                    key=entity,
                    related=[entity.GlobalId],
                    global_key="TextFilter:%s.%s" % (
                        entity.is_a(), entity.GlobalId),
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

    def set_class_by_user(
            self,
            unknown_entities: list,
            sim_settings: base_settings,
            best_guess_dict: dict):
        """Ask user for every given ifc_entity to specify matching element
        class.

        This function allows to define unknown classes based on user feedback.
        To reduce the number of decisions we implemented fuzzy search. If and
        how fuzzy search is used can be set the workflow settings
        group_unidentified and fuzzy_threshold. See group_similar_entities
        for more information.

        Args:
            unknown_entities: list of unknown entities
            sim_settings: workflow: Workflow used on tasks
            best_guess_dict: dict that holds the best guesses for every element
        """

        def group_similar_entities(
            search_type: str = 'fuzzy',
            fuzzy_threshold: float = 0.7) -> dict:
            """Group unknown entities to reduce number of decisions.

            IFC elements are often not correctly specified, or have uncertain
            specifications like "USERDEFINED" as predefined type. For some IFC
            files this would lead to a very high amount of decisions to identify
            elements. To reduce this function groups similar elements based on:
                - same name (exact)
                - similar name (fuzzy search)

            Args:
                search_type: str which is either 'fuzzy' or 'name'
                fuzzy_threshold: float that sets the threshold for fuzzy search.
                    A low threshold means a small similarity is required for
                    grouping

            Returns:
                representatives: A dict with a string of the representing ifc
                element type as key (e.g. 'IfcPipeFitting') and a list of all
                represented ifc elements.
            """
            entities_by_type = {}
            for entity in unknown_entities:
                entity_type = entity.is_a()
                if entity_type not in entities_by_type:
                    entities_by_type[entity_type] = [entity]
                else:
                    entities_by_type[entity_type].append(entity)

            representatives = {}
            for entity_type, entities in entities_by_type.items():
                representatives[entity_type] = {}

                # group based on similarity in string of "Name" of IFC element
                if search_type == 'fuzzy':
                    # use names of entities for grouping
                    entity_names = [entity.Name for entity in entities]
                    name_series = pd.Series(data=entity_names)
                    res = group_similar_strings(
                        name_series, min_similarity=fuzzy_threshold)
                    for i, entity in enumerate(entities):
                        # get representative element based on similar strings df
                        repres = entities[res.iloc[i].group_rep_index]
                        if not repres in representatives[entity_type]:
                            representatives[entity_type][repres] = [entity]
                        else:
                            representatives[entity_type][repres].append(entity)

                    self.logger.info(
                        f"Grouping the unidentified elements with fuzzy search "
                        f"based on their Name (Threshold = {fuzzy_threshold})"
                        f" reduced the number of unknown "
                        f"entities from {len(entities_by_type[entity_type])} "
                        f"elements of IFC type {entity_type} "
                        f"to {len(representatives[entity_type])} elements.")
                # just group based on exact same string in "Name" of IFC element
                elif search_type == 'name':
                    for entity in entities:
                        # find if a key entity with same Name exists already
                        repr_entity = None
                        for repr in representatives[entity_type].keys():
                            if repr.Name == entity.Name:
                                repr_entity = repr
                                break

                        if not repr_entity:
                            representatives[entity_type][entity] = [entity]
                        else:
                            representatives[entity_type][repr_entity].append(entity)
                    self.logger.info(
                        f"Grouping the unidentified elements by their Name "
                        f"reduced the number of unknown entities from"
                        f" {len(entities_by_type[entity_type])} "
                        f"elements of IFC type {entity_type} "
                        f"to {len(representatives[entity_type])} elements.")
                else:
                    raise NotImplementedError('Only fuzzy and name grouping are'
                                              'implemented for now.')

            return representatives

        possible_elements = sim_settings.relevant_elements
        sorted_elements = sorted(possible_elements, key=lambda item: item.key)

        result_entity_dict = {}
        ignore = []

        representatives = group_similar_entities(
            sim_settings.group_unidentified, sim_settings.fuzzy_threshold)

        for ifc_type, repr_entities in sorted(representatives.items()):
            decisions = DecisionBunch()
            for ifc_entity, represented in repr_entities.items():
                # assert same list of ifc_files
                checksum = Decision.build_checksum(
                    [pe.key for pe in sorted_elements])

                best_guess_cls = best_guess_dict.get(ifc_entity)
                best_guess = best_guess_cls.key if best_guess_cls else None
                context = []
                for port in ifc2python.get_ports(ifc_entity):
                    connected_ports = ifc2python.get_ports_connections(port)
                    con_ports_guid = [con.GlobalId for con in connected_ports]
                    parents = []
                    for con_port in connected_ports:
                        parents.extend(ifc2python.get_ports_parent(con_port))
                    parents_guid = [par.GlobalId for par in parents]
                    context.append(port.GlobalId)
                    context.extend(con_ports_guid + parents_guid)

                decisions.append(ListDecision(
                    question="Found unidentified Element of %s" % (
                        ifc_entity.is_a()),
                    console_identifier="Name: %s, Description: %s, GUID: %s, "
                                       "Predefined Type: %s"
                    % (ifc_entity.Name, ifc_entity.Description,
                        ifc_entity.GlobalId, ifc_entity.PredefinedType),
                    choices=[ele.key for ele in sorted_elements],
                    related=[ifc_entity.GlobalId],
                    context=context,
                    default=best_guess,
                    key=ifc_entity,
                    global_key="SetClass:%s.%s" % (
                        ifc_entity.is_a(), ifc_entity.GlobalId),
                    allow_skip=True,
                    validate_checksum=checksum))
            self.logger.info(f"Found {len(decisions)} "
                             f"unidentified Elements of IFC type {ifc_type} "
                             f"to check by user")
            yield decisions

            answers = decisions.to_answer_dict()

            for ifc_entity, element_key in answers.items():
                represented_entities = representatives[ifc_type][ifc_entity]
                if element_key is None:
                    # todo check
                    # ignore.append(ifc_entity)
                    ignore.extend(represented_entities)
                else:
                    element_cls = ProductBased.key_map[element_key]
                    lst = result_entity_dict.setdefault(element_cls, [])
                    # lst.append(ifc_entity)
                    lst.extend(represented_entities)

        return result_entity_dict, ignore

    def get_ifc_types(self, relevant_elements: List[Type[ProductBased]]) \
            -> Set[str]:
        """Extract used ifc types from list of elements."""
        relevant_ifc_types = []
        for ele in relevant_elements:
            relevant_ifc_types.extend(ele.ifc_types.keys())
        return set(relevant_ifc_types)


class CheckIfc(ITask):
    """
    Check an IFC file, for a number of conditions (missing information,
    incorrect information, etc) that could lead on future tasks to fatal errors.
    """
    reads = ('ifc_files',)

    def __init__(self, playground: Playground):
        super().__init__(playground)
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

    def run(self, ifc_files: [IfcFileClass]) -> [dict, dict]:
        """
        Analyzes sub_instances and instances of an IFC file for the validation
        functions and export the errors found as .json and .html files.

        Args:
            ifc_files: bim2sim IfcFileClass holding the ifcopenshell ifc
                instance

        Returns:
            error_summary_sub_inst: summary of errors related to sub_instances
            error_summary_inst: summary of errors related to instances
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
            self.instances = self.get_relevant_instances(ifc_file.file)
            self.id_list = [e.GlobalId for e in ifc_file.file.by_type("IfcRoot")]
            self.check_critical_errors(ifc_file.file, self.id_list)
            self.error_summary_sub_inst = self.check_inst(
                self.validate_sub_inst, self.sub_inst)
            self.error_summary_inst = self.check_inst(
                self.validate_instances, self.instances)
            instance_errors = sum(len(errors) for errors in
                                  self.error_summary_inst.values())
            quality_logger = logging.getLogger('bim2sim.QualityReport')
            quality_logger.warning(
                '%d errors were found on %d instances' %
                (instance_errors, len(self.error_summary_inst)))
            sub_inst_errors = sum(len(errors) for errors in list(
                self.error_summary_sub_inst.values()))
            quality_logger.warning(
                '%d errors were found on %d sub_instances' % (
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

    @staticmethod
    def check_critical_uniqueness(id_list):
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

        Only files containing instances of type 'IfcRelSpaceBoundary' are
        valid for bim2sim.

        Raises:
            TypeError: if loaded file does not contain IfcRelSpaceBoundaries
        """
        if len(self.sub_inst) == 0:
            raise TypeError(
                f"Loaded IFC file does not contain instances of type "
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

    def validate_sub_inst(self, bound) -> list:
        """
        Validation function for a space boundary that compiles all validation
        functions.

        Args:
            bound: ifc space boundary entity

        Returns:
            error: list of errors found in the ifc space boundaries
        """
        error = []
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

    def validate_instances(self, inst) -> list:
        """
        Validation function for an instance that compiles all instance
        validation functions.

        Args:
            inst:IFC instance being checked

        Returns:
            error: list of instances error

        """
        error = []
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
    def _check_level(bound):
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
    def _check_description(bound):
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
    def _check_rel_space(bound):
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
    def _check_rel_building_elem(bound):
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
    def _check_conn_geom(bound):
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
    def _check_phys_virt_bound(bound):
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
    def _check_int_ext_bound(bound):
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
    def _check_on_relating_elem(bound):
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
    def _check_on_related_elem(bound):
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
    def _check_basis_surface(bound):
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
    def _check_inner_boundaries(bound):
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
    def _check_outer_boundary_composite(bound):
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
    def _check_segments(bound):
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
    def _check_segments_poly(cls, bound):
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
    def _check_segments_poly_coord(cls, bound):
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
    def _check_outer_boundary_poly(cls, bound):
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
    def _check_outer_boundary_poly_coord(bound):
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
    def _check_plane_position(bound):
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
    def _check_location(bound):
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
    def _check_axis(bound):
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
    def _check_refdirection(bound):
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
    def _check_location_coord(cls, bound):
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
    def _check_axis_dir_ratios(cls, bound):
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
    def _check_refdirection_dir_ratios(cls, bound):
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
    def _check_poly_points(polyline):
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
    def _check_coords(points):
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
    def _check_dir_ratios(dir_ratios):
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
    def _check_poly_points_coord(cls, polyline):
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
    def _check_inst_sb(inst):
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
    def _check_inst_materials(inst):
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
    def _check_inst_contained_in_structure(inst):
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
    def _check_inst_representation(inst):
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
        error = []
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

    def validate_instances(self, inst: entity_instance) -> list:
        """
        Validation function for an instance that compiles all instance validation functions.

        Args:
            inst: IFC instance being checked

        Returns:
            error: list of instances error

        """
        error = []
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

    # instances check
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
