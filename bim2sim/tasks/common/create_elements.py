from __future__ import annotations

import collections
import logging
from typing import Tuple, List, Any, Generator, Dict, Type, Set
import copy

from bim2sim.elements import bps_elements as bps
from bim2sim.elements.base_elements import Factory, ProductBased, Material, Element
from bim2sim.elements.mapping import ifc2python
from bim2sim.elements.mapping.filter import TypeFilter, TextFilter
from bim2sim.kernel import IFCDomainError
from bim2sim.kernel.decision import DecisionBunch, ListDecision, Decision
from bim2sim.kernel.ifc_file import IfcFileClass
from bim2sim.sim_settings import BaseSimSettings
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import group_by_levenshtein
from bim2sim.utilities.types import LOD
from bim2sim.tasks.base import Playground
from ifcopenshell import file, entity_instance


class CreateElementsOnIfcTypes(ITask):
    """Create bim2sim elements based on information of IFC types."""

    reads = ('ifc_files',)
    touches = ('elements', '_initial_elements', 'ifc_files')

    def __init__(self, playground: Playground):
        super().__init__(playground)
        self.factory = None
        self.source_tools: list = []
        self.layersets_all: list = []
        self.materials_all: list = []
        self.layers_all: list = []

    def run(self, ifc_files: [IfcFileClass]) -> (
            Tuple)[Dict[Any, Element], Dict[Any, Element], List[IfcFileClass]]:
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

        The element creation process follows a three-stage classification
        approach:

        1. **Validation-Based Classification**:
           * Elements are initially processed based on relevant element
           types and IFC classifications
           * Each element undergoes validation against predefined criteria
           * Valid elements are immediately added to the "valids" collection
           * Elements failing validation are placed in "unknown_entities"
           for further processing

        2. **Pattern Matching Classification**:
           * For unidentified elements in "unknown_entities", a text
           analysis is performed
           * The system examines IFC descriptions and compares them against
           regular expression patterns defined in element classes
           * Results are handled based on match confidence:
             - Single match: Element is automatically moved to "valids"
             - Multiple matches: User decision is requested to determine the
             correct classification
             - No matches: Element remains in "unknown_entities" for final
             classification stage

        3. **User-Assisted Classification**:
           * Remaining unidentified elements are processed through the
           set_class_by_user function
           * To optimize user experience, similar elements are intelligently
           grouped using one of these strategies:
             - Exact name matching: Groups elements with identical names
             - Name and description matching: Groups elements with identical
             names and descriptions
             - Fuzzy matching: Groups elements with similar names based on a
             configurable similarity threshold
           * This grouping significantly reduces the number of required user
           decisions
           * User decisions determine the final classification of each
           element or group

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

        elements: dict = {}
        for ifc_file in ifc_files:
            self.factory = Factory(
                relevant_elements,
                ifc_file.ifc_units,
                ifc_file.domain,
                ifc_file.finder)

            # Filtering:
            #  filter returns dict of entities: suggested class and list of
            #  unknown accept_valids returns created elements and lst of
            #  invalids

            element_lst: list = []
            entity_best_guess_dict: dict = {}
            # filter by type
            type_filter = TypeFilter(relevant_ifc_types)
            entity_type_dict, unknown_entities = type_filter.run(ifc_file.file)

            # create valid elements
            # First elements are created with validation, by checking
            # conditions and number of ports if they fit expectations, those
            # who don't fit expectations are added to invalids list
            valids, invalids = self.create_with_validation(entity_type_dict)
            element_lst.extend(valids)
            unknown_entities.extend(invalids)

            # filter by text
            # invalids from before are checked with text filter on their IFC
            # Description to identify them
            text_filter = TextFilter(
                relevant_elements,
                ifc_file.ifc_units,
                ['Description'])
            entity_class_dict, unknown_entities = yield from (
                self.filter_by_text(
                    text_filter, unknown_entities, ifc_file.ifc_units))
            entity_best_guess_dict.update(entity_class_dict)

            # Now we use the result of previous text filter to create the
            # elements that could be identified by text filter
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
            # those are elements that failed initial validation and could not
            # be identified by text filter
            entity_class_dict, unknown_entities = yield from (
                self.set_class_by_user(
                    unknown_entities,
                    self.playground.sim_settings,
                    entity_best_guess_dict)
            )
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

    def create_with_validation(self, entities_dict: dict, warn=True, force=False) -> \
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
            if plugin_name in ['EnergyPlus', 'Comfort', 'Teaser']:
                if (self.playground.sim_settings.layers_and_materials
                        is not LOD.low):
                    raise NotImplementedError(
                        "Only layers_and_materials using LOD.low is currently supported.")
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

    def create_layers_and_materials(self, element: Element):
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

    def create_layersets(self, element: Element, ifc_layerset_entity: entity_instance):
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
            self, element: Element, ifc_material_constituents: entity_instance, quality_logger: Element): # Error durch mypy: Element has no attribute Layerset
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

    def create_material(self, ifc_material_entity: entity_instance):
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

    def filter_by_text(self, text_filter: TextFilter, ifc_entities: entity_instance, ifc_units: dict) \
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
                        entity.is_a(), entity.GlobalId, entity.Name),
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
            # Sort unknown entities by GlobalId for determinism
            unknown_entities_sorted = sorted(unknown_entities,
                                             key=lambda e: e.GlobalId)

            entities_by_type = {}
            for entity in unknown_entities_sorted:
                entity_type = entity.is_a()
                if entity_type not in entities_by_type:
                    entities_by_type[entity_type] = [entity]
                else:
                    entities_by_type[entity_type].append(entity)

            representatives = {}
            for entity_type, entities in sorted(entities_by_type.items()):
                if len(entities) == 1:
                    # Use OrderedDict for stable iteration
                    entity_dict = collections.OrderedDict()
                    entity_dict[entities[0]] = entities
                    representatives[entity_type] = entity_dict
                    continue

                # group based on similarity in string of "Name" of IFC element
                if search_type == 'fuzzy':
                    # Modify group_by_levenshtein to ensure stable sorting
                    grouped = group_by_levenshtein(
                        entities, similarity_score=fuzzy_threshold)

                    # Convert result to a stable structure
                    stable_grouped = collections.OrderedDict()
                    for key, group in sorted(grouped.items(),
                                             key=lambda x: x[0].GlobalId):
                        # Sort the group itself
                        stable_grouped[key] = sorted(group,
                                                     key=lambda e: e.GlobalId)

                    representatives[entity_type] = stable_grouped

                    self.logger.info(
                        f"Grouping the unidentified elements with fuzzy search "
                        f"based on their Name (Threshold = {fuzzy_threshold})"
                        f" reduced the number of unknown "
                        f"entities from {len(entities_by_type[entity_type])} "
                        f"elements of IFC type {entity_type} "
                        f"to {len(representatives[entity_type])} elements.")

                # just group based on exact same string in "Name" of IFC element
                elif search_type == 'name':
                    # Use OrderedDict for stable iteration
                    name_groups = collections.defaultdict(list)

                    # Group by name, but keep the sorting
                    for entity in entities:
                        name_groups[entity.Name].append(entity)

                    # Create the stable representatives dictionary
                    stable_grouped = collections.OrderedDict()
                    for name, group in sorted(name_groups.items()):
                        # Sort the group by GlobalId and choose the first element as representative
                        sorted_group = sorted(group, key=lambda e: e.GlobalId)
                        stable_grouped[sorted_group[0]] = sorted_group

                    representatives[entity_type] = stable_grouped

                    self.logger.info(
                        f"Grouping the unidentified elements by their Name "
                        f"reduced the number of unknown entities from"
                        f" {len(entities_by_type[entity_type])} "
                        f"elements of IFC type {entity_type} "
                        f"to {len(representatives[entity_type])} elements.")
                elif search_type == 'name_and_description':
                    # Use OrderedDict for stable iteration
                    name_desc_groups = collections.defaultdict(list)

                    # Group by name AND description, but keep the sorting
                    for entity in entities:
                        # Create a composite key combining Name and Description
                        composite_key = (entity.Name, entity.Description)
                        name_desc_groups[composite_key].append(entity)

                    # Create the stable representatives dictionary
                    stable_grouped = collections.OrderedDict()
                    for (name, desc), group in sorted(
                            name_desc_groups.items()):
                        # Sort the group by GlobalId and choose the first element as representative
                        sorted_group = sorted(group, key=lambda e: e.GlobalId)
                        stable_grouped[sorted_group[0]] = sorted_group

                    representatives[entity_type] = stable_grouped

                    self.logger.info(
                        f"Grouping the unidentified elements by their Name and Description "
                        f"reduced the number of unknown entities from"
                        f" {len(entities_by_type[entity_type])} "
                        f"elements of IFC type {entity_type} "
                        f"to {len(representatives[entity_type])} elements.")
                else:
                    raise NotImplementedError(
                        'Only fuzzy and name grouping are'
                        'implemented for now.')

            return representatives

        possible_elements = sim_settings.relevant_elements
        sorted_elements = sorted(possible_elements, key=lambda item: item.key)

        result_entity_dict = {}
        ignore = []

        representatives = group_similar_entities(
            sim_settings.group_unidentified, sim_settings.fuzzy_threshold)

        # Sort the outer loop by IFC type
        # Create a single decision bunch for all entities
        all_decisions = DecisionBunch()
        # Store associations between decisions and their representatives
        decision_associations = {}  # Maps (decision -> (ifc_type, ifc_entity))

        # Sort the outer loop by IFC type
        for ifc_type, repr_entities in sorted(representatives.items()):
            # Sort the inner loop by GlobalId for determinism
            for ifc_entity, represented in sorted(repr_entities.items(),
                                                  key=lambda x: x[0].GlobalId):
                # assert same list of ifc_files
                checksum = Decision.build_checksum(
                    [pe.key for pe in sorted_elements])

                best_guess_cls = best_guess_dict.get(ifc_entity)
                best_guess = best_guess_cls.key if best_guess_cls else None

                # Sort ports and related elements
                context = []
                for port in sorted(ifc2python.get_ports(ifc_entity),
                                   key=lambda p: p.GlobalId):
                    connected_ports = sorted(
                        ifc2python.get_ports_connections(port),
                        key=lambda p: p.GlobalId)
                    con_ports_guid = [con.GlobalId for con in connected_ports]
                    parents = []
                    for con_port in sorted(connected_ports,
                                           key=lambda p: p.GlobalId):
                        port_parents = sorted(
                            ifc2python.get_ports_parent(con_port),
                            key=lambda p: p.GlobalId)
                        parents.extend(port_parents)
                    parents_guid = [par.GlobalId for par in parents]
                    context.append(port.GlobalId)
                    context.extend(sorted(con_ports_guid + parents_guid))

                # Sort the represented elements
                representative_global_keys = []
                for represent in sorted(repr_entities[ifc_entity],
                                        key=lambda e: e.GlobalId):
                    representative_global_keys.append(
                        "SetClass:%s.%s.%s" % (
                            represent.is_a(), represent.GlobalId,
                            represent.Name
                        )
                    )

                decision = ListDecision(
                    question="Found unidentified Element of Ifc Type: %s" % (
                        ifc_entity.is_a()),
                    console_identifier="Name: %s, Description: %s, GUID: %s, "
                                       "Predefined Type: %s"
                                       % (
                                           ifc_entity.Name,
                                           ifc_entity.Description,
                                           ifc_entity.GlobalId,
                                           ifc_entity.PredefinedType),
                    choices=[ele.key for ele in sorted_elements],
                    related=[ifc_entity.GlobalId],
                    context=sorted(context),  # Sort the context
                    default=best_guess,
                    key=ifc_entity,
                    global_key="SetClass:%s.%s.%s" % (
                        ifc_entity.is_a(), ifc_entity.GlobalId, ifc_entity.Name
                    ),
                    representative_global_keys=sorted(
                        representative_global_keys),  # Sort the keys
                    allow_skip=True,
                    validate_checksum=checksum)

                # Add decision to the bunch
                all_decisions.append(decision)

                # Store association between decision and its representatives
                decision_associations[ifc_entity] = (ifc_type, ifc_entity)

        self.logger.info(
            f"Found {len(all_decisions)} unidentified Elements to check by user")

        # Yield the single big bunch of decisions
        yield all_decisions

        # Process all answers at once
        answers = all_decisions.to_answer_dict()

        for ifc_entity, element_key in sorted(answers.items(),
                                              key=lambda x: x[0].GlobalId):
            # Get the associated ifc_type and representative entity
            ifc_type, _ = decision_associations[ifc_entity]
            represented_entities = representatives[ifc_type][ifc_entity]

            if element_key is None:
                ignore.extend(
                    sorted(represented_entities, key=lambda e: e.GlobalId))
            else:
                element_cls = ProductBased.key_map[element_key]
                lst = result_entity_dict.setdefault(element_cls, [])
                lst.extend(
                    sorted(represented_entities, key=lambda e: e.GlobalId))

        return result_entity_dict, ignore

    @staticmethod
    def get_ifc_types(relevant_elements: List[Type[ProductBased]]) \
            -> Set[str]:
        """Extract used ifc types from list of elements."""
        relevant_ifc_types = []
        for ele in relevant_elements:
            relevant_ifc_types.extend(ele.ifc_types.keys())
        return set(relevant_ifc_types)
