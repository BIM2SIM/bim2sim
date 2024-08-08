from __future__ import annotations

import logging
from typing import Tuple, List, Any, Generator, Dict, Type, Set
import copy

from bim2sim.elements import bps_elements as bps
from bim2sim.elements.base_elements import Factory, ProductBased, Material
from bim2sim.elements.mapping import ifc2python
from bim2sim.elements.mapping.filter import TypeFilter, TextFilter
from bim2sim.kernel import IFCDomainError
from bim2sim.kernel.decision import DecisionBunch, ListDecision, Decision
from bim2sim.kernel.ifc_file import IfcFileClass
from bim2sim.sim_settings import BaseSimSettings
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import group_by_levenshtein
from bim2sim.utilities.types import LOD


class CreateElementsOnIfcTypes(ITask):
    """Create bim2sim elements based on information of IFC types."""

    reads = ('ifc_files',)
    touches = ('elements', '_initial_elements', 'ifc_files')

    def __init__(self, playground):
        super().__init__(playground)
        self.factory = None
        self.source_tools = []
        self.layersets_all = []
        self.materials_all = []
        self.layers_all = []

    def run(self, ifc_files: [IfcFileClass]):
        """This task creates the bim2sim elements based on the ifc data.

        For each ifc file a factory instance is created. The factory instance
        allows the easy creation of bim2sim elements based on ifc elements.
        As we might not want to create bim2sim elements for every existing ifc
        element, we use the concept of relevant_elements which are taken from
        the sim_setting relevant_elements. This way the user can describe which
        bim2sim elements are relevant for the respective simulation and only
        the fitting ifc elements are taken into account.
        During the creation of the bim2sim elements validations are performed,
        to make sure that the resulting bim2sim elements hold valid
        information.

        Args:
            ifc_files: list of ifc files in bim2sim structured format
        Returns:
            elements: bim2sim elements created based on ifc data
            ifc_files: list of ifc files in bim2sim structured format
        """
        self.logger.info("Creates elements of relevant ifc types")
        default_ifc_types = {'IfcBuildingElementProxy', 'IfcUnitaryEquipment'}
        # Todo maybe move this into IfcFileClass instead simulation settings
        relevant_elements = self.playground.sim_settings.relevant_elements
        relevant_ifc_types = self.get_ifc_types(relevant_elements)
        relevant_ifc_types.update(default_ifc_types)

        elements = {}
        for ifc_file in ifc_files:
            self.factory = Factory(
                relevant_elements,
                ifc_file.ifc_units,
                ifc_file.domain,
                ifc_file.finder)

            # Filtering:
            #  filter returns dict of entities: suggested class and list of unknown
            #  accept_valids returns created elements and lst of invalids

            element_lst = []
            entity_best_guess_dict = {}
            # filter by type
            type_filter = TypeFilter(relevant_ifc_types)
            entity_type_dict, unknown_entities = type_filter.run(ifc_file.file)

            # create valid elements
            valids, invalids = self.create_with_validation(entity_type_dict)
            element_lst.extend(valids)
            unknown_entities.extend(invalids)

            # filter by text
            text_filter = TextFilter(
                relevant_elements,
                ifc_file.ifc_units,
                ['Description'])
            entity_class_dict, unknown_entities = yield from self.filter_by_text(
                text_filter, unknown_entities, ifc_file.ifc_units)
            entity_best_guess_dict.update(entity_class_dict)
            # TODO why do we run this two times, once without and once with
            #  force=True
            valids, invalids = self.create_with_validation(
                entity_class_dict, force=True)
            element_lst.extend(valids)
            unknown_entities.extend(invalids)

            self.logger.info("Found %d relevant elements", len(element_lst))
            self.logger.info("Found %d ifc_entities that could not be "
                             "identified and therefore not converted into a"
                             " bim2sim element.",
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
                        element_lst.append(item)
                    except Exception as ex:
                        invalids.append(ifc_entity)
            if invalids:
                self.logger.info("Removed %d entities with no class set",
                                 len(invalids))

            self.logger.info(f"Created {len(element_lst)} bim2sim elements "
                             f"based on IFC file {ifc_file.ifc_file_name}")
            elements.update({inst.guid: inst for inst in element_lst})
        if not elements:
            self.logger.error("No bim2sim elements could be created based on "
                              "the IFC files.")
            raise AssertionError("No bim2sim elements could be created, program"
                                 "will be terminated as no further process is "
                                 "possible.")
        self.logger.info(f"Created {len(elements)} bim2sim elements in "
                         f"total for all IFC files.")
        # sort elements for easier handling
        elements = dict(sorted(elements.items()))
        # store copy of elements to preserve for alter operations
        _initial_elements = copy.copy(elements)
        return elements, _initial_elements, ifc_files

    def create_with_validation(self, entities_dict, warn=True, force=False) -> \
            Tuple[List[ProductBased], List[Any]]:
        """Instantiate ifc_entities using given element class.

        The given ifc entities are used to create bim2sim elements via factory
        method. After the creation the associated layers and material are
        created (see create_layers_and_materials).
        All created elements (including material and layers) are checked
        against the provided conditions and classified into valid and invalid.

        Args:
            entities_dict: dict with ifc entities
            warn: boolean to warn if something condition fail
            force: boolean if conditions should be ignored

        Returns:
            valid: list of all valid items that fulfill the conditions
            invalid: list of all elements that do not fulfill the conditions

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
            # TODO #676
            plugin_name = self.playground.project.plugin_cls.name
            if plugin_name.lower() in ['energyplus', 'comfort', 'teaser']:
                if not self.playground.sim_settings.use_construction_templates:
                    # raise NotImplementedError(
                    #     "Only use_construction_templates = True LOD.low is currently supported.")
                    self.create_layers_and_materials(element)
                    valid += (
                            self.layersets_all
                            + self.layers_all +
                            self.materials_all
                    )

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
            element: the already created bim2sim element
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
            element: bim2sim element
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
            element: bim2sim element
            ifc_material_constituents: ifc entity of layerset
            quality_logger: element of bim2sim quality logger
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
                    global_key="TextFilter:%s.%s.%s" % (
                        entity.is_a(), entity.GlobalId, entity.Name), # maybe add the name of the entitiy?
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
            sim_settings: BaseSimSettings,
            best_guess_dict: dict):
        """Ask user for every given ifc_entity to specify matching element
        class.

        This function allows to define unknown classes based on user feedback.
        To reduce the number of decisions we implemented fuzzy search. If and
        how fuzzy search is used can be set the sim_settings
        group_unidentified and fuzzy_threshold. See group_similar_entities()
        for more information.

        Args:
            unknown_entities: list of unknown entities
            sim_settings: sim_settings used for this project
            best_guess_dict: dict that holds the best guesses for every element
        """

        def group_similar_entities(
            search_type: str = 'fuzzy',
            fuzzy_threshold: float = 0.7) -> dict:
            """Group unknown entities to reduce number of decisions.

            IFC elements are often not correctly specified, or have uncertain
            specifications like "USERDEFINED" as predefined type. For some IFC
            files this would lead to a very high amount of decisions to identify
            elements. To reduce those decisions, this function groups similar
            elements based on:
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
                if len(entities) == 1:
                    representatives.setdefault(entity_type,
                                               {entities[0]: entities})
                    continue
                # group based on similarity in string of "Name" of IFC element
                if search_type == 'fuzzy':
                    # use names of entities for grouping
                    representatives[entity_type] = group_by_levenshtein(
                        entities, similarity_score=fuzzy_threshold)
                    self.logger.info(
                        f"Grouping the unidentified elements with fuzzy search "
                        f"based on their Name (Threshold = {fuzzy_threshold})"
                        f" reduced the number of unknown "
                        f"entities from {len(entities_by_type[entity_type])} "
                        f"elements of IFC type {entity_type} "
                        f"to {len(representatives[entity_type])} elements.")
                # just group based on exact same string in "Name" of IFC element
                elif search_type == 'name':
                    representatives[entity_type] = {}
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
                    global_key="SetClass:%s.%s.%s" % (
                        ifc_entity.is_a(), ifc_entity.GlobalId, ifc_entity.Name), # same as before
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
