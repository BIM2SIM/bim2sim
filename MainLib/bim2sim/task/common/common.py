import os
from typing import Tuple, List, Any, Type, Set, Dict, Generator

from bim2sim.decision import Decision, ListDecision, DecisionBunch
from bim2sim.filter import TypeFilter, TextFilter

from bim2sim.kernel import ifc2python
from bim2sim.kernel.element import Factory, ProductBased
from bim2sim.task.base import ITask
from bim2sim.kernel.units import ifcunits, ureg, ifc_pint_unitmap, parse_ifc
from ifcopenshell.file import file


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

        ifcunits.update(**self.get_ifcunits(ifc))

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
    """Create internal elements from ifc."""

    reads = ('ifc',)
    touches = ('instances', 'finder')

    def run(self, workflow, ifc):
        self.logger.info("Creates elements of relevant ifc types")

        default_ifc_types = {'IfcBuildingElementProxy', 'IfcUnitaryEquipment'}
        relevant_ifc_types = self.get_ifc_types(workflow.relevant_elements)
        relevant_ifc_types.update(default_ifc_types)

        self.factory = Factory(workflow.relevant_elements, self.paths.finder)
        for app in ifc.by_type('IfcApplication'):
            for decision in self.factory.finder.check_tool_template(app.ApplicationFullName):
                yield DecisionBunch([decision])
        # Filtering:
        #  filter returns dict of entities: suggested class and list of unknown
        #  accept_valids returns created elements and lst of invalids

        instance_lst = []
        entity_best_guess_dict = {}
        # filter by type
        type_filter = TypeFilter(relevant_ifc_types)
        entity_type_dict, unknown_entities = type_filter.run(ifc)
        # entity_class_dict = {entity: self.factory.get_element(ifc_type)
        #                      for entity, ifc_type in entity_type_dict.items()}
        # entity_best_guess_dict.update(entity_type_dict)
        valids, invalids = self.accept_valids(entity_type_dict)
        instance_lst.extend(valids)
        unknown_entities.extend(invalids)

        # filter by text
        text_filter = TextFilter(workflow.relevant_elements, ['Description'])
        entity_class_dict, unknown_entities = yield from self.filter_by_text(
            text_filter, unknown_entities)
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

    def accept_valids(self, entities_dict, warn=True, force=False) -> \
            Tuple[List[ProductBased], List[Any]]:
        """Instantiate ifc_entities using given element class.
        Resulting instances are validated (if not force).
        Results are two lists, one with valid elements and one with
        remaining entities."""
        valid, invalid = [], []
        for entity, ifc_type_or_element_cls in entities_dict.items():
            try:
                if isinstance(ifc_type_or_element_cls, str):
                    element = self.factory(
                        entity, ifc_type=ifc_type_or_element_cls, use_dummy=False)
                else:
                    element = self.factory.create(ifc_type_or_element_cls, entity)
            except LookupError:
                invalid.append(entity)
                continue

            if element.validate():
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
                element.discard()

        return valid, invalid

    def filter_by_text(self, text_filter, ifc_entities) \
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
                        element_cls.filter_for_text_fragments(entity)) + "'"
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