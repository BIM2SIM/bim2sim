import ifcopenshell
import uuid
import logging
import enum
import json
from collections import OrderedDict

class DecisionException(Exception):
    """Base Exception for Decisions"""
class DecisionSkipAll(DecisionException):
    """Exception raised on skipping all Decisions"""
class DecisionCancle(DecisionException):
    """Exception raised on canceling Decisions"""
class PendingDecisionError(DecisionException):
    """Exception for unsolved Decisions"""


class Status(enum.Enum):
    """Enum for status of Decision"""
    open = 1  # decision not yet made
    done = 2  # decision made
    loadeddone = 3  # previous made decision loaded
    saveddone = 4  # decision made and saved
    skipped = 5  # decision was skipped


class Decision:
    """Class for handling decisions and user interaction

    To make a single Decision call decision.decide() on an instance
    Decisions can be collected and decided in an bunch. Call Decision.decide_collected()
    Decisions with a global_key can be saved. Call Decision.save(<path>) to save all saveable decisions
    Decisions can be loaded. Call Decision.load(<path>) to load them internally.
    On instantiating a decision with a global_key matching a loaded key it gets the loaded value assigned
    """

    all = []  # all decision instances
    stored_decisions = {}  # Decisions ready to save
    _logger = None

    SKIP = "skip"
    SKIPALL = "skip all"
    CANCEL = "cancel"
    options = [SKIP, SKIPALL, CANCEL]

    def __init__(self, question: str, validate_func,
                 output: dict = None, output_key: str = None, global_key: str = None,
                 allow_skip=False, allow_load=False, allow_save=False, allow_overwrite=False,
                 collect=False, quick_decide=False):
        """
        :param question: The question asked to thu user
        :param validate_func: callable to validate the users input
        :param output: dictionary to store output_key:value in
        :param output_key: key for output
        :param global_key: unique key to identify decision. Required for saving
        :param allow_skip: set to True to allow skipping the decision and user None as value
        :param allow_load: allows loading value from previus made decision with same global_key (Has no effect when global_key is not provided)
        :param allow_save: allows saving decisions value and global_key for later reuse (Has no effect when global_key is not provided)
        :param collect: add decision to collection for later processing. (output and output_key needs to be provided)
        :param quick_decide: calls decide() within __init__()

        :raises: :class:'AttributeError'::
        """
        self.status = Status.open
        self.value = None

        self.question = question
        self.validate_func = validate_func

        self.output = output
        self.output_key = output_key
        self.global_key = global_key

        self.allow_skip = allow_skip
        self.allow_save = allow_save
        self.allow_load = allow_load
        self.allow_overwrite = allow_overwrite

        self.collect = collect

        if self.allow_load:
            self._inner_load()

        if quick_decide and not self.status == Status.loadeddone:
            self.decide()
            #self.value = self._inner_decide(self.collect)

        if self.status in [Status.done, Status.loadeddone]:
            self._post()
        elif self.collect:
            if not (isinstance(self.output, dict) and self.output_key):
                raise AttributeError(
                    "Can not collect Decision if output dict or output_key is missing.")

        Decision.all.append(self)

    def discard(self):
        """Remove decision from traced decisions (Decision.all)"""
        Decision.all.remove(self)

    @classmethod
    def filtered(cls, active=True):
        if active:
            for d in cls.all:
                if d.status == Status.open:
                    yield d
        else:
            for d in cls.all:
                if d.status != Status.open:
                    yield d

    @classmethod
    def collection(cls):
        return [d for d in cls.filtered() if d.collect]

    @property
    def logger(self):
        """logger instance"""
        if not Decision._logger:
            Decision._logger = logging.getLogger(__name__)
        return Decision._logger

    def validate(self, value):
        """Checks value with validate_func and returns truth value"""

        res = False
        try:
            res = bool(self.validate_func(value))
        except:
            pass
        return res

    @classmethod
    def decide_collected(cls, collection=None):
        """Solve all stored decisions"""

        logger = logging.getLogger(__name__)
        skip_all = False

        _collection = collection or cls.collection()

        for decision in _collection:
            if skip_all and decision.allow_skip:
                decision.skip()
            else:
                if decision.status != Status.open:
                    logger.debug("Decision not open -> continue (%s)", decision)
                    continue
                if skip_all:
                    logger.info("Decision can not be skipped")
                try:
                    decision.decide(collected=True)
                except DecisionSkipAll:
                    skip_all = True
                    logger.info("Skipping remaining decisions")
                except DecisionCancle as ex:
                    logger.info("Canceling decisions")
                    raise

    @classmethod
    def load(cls, path):
        """Load previously solved Decisions from file system"""

        logger = logging.getLogger(__name__)
        try:
            with open(path, "r") as file:
                data = json.load(file)
        except IOError as ex:
            logger.info("Unable to load decisions. (%s)", ex)
        else:
            if data:
                msg = "Found %d previous made decisions. Continue using them?"%(len(data))
                reuse = BoolDecision(question=msg).decide()
                if reuse:
                    cls.stored_decisions = data
                    logger.info("Loaded decisions.")

    @classmethod
    def save(cls, path):
        """Save solved Decisions to file system"""

        logger = logging.getLogger(__name__)
        with open(path, "w") as file:
            json.dump(cls.stored_decisions, file, indent=2)
        logger.info("Saved %d decisions.", len(cls.stored_decisions))

    @classmethod
    def summary(cls):
        """Returns summary string"""

        txt = "%d open decisions" % (len(list(cls.filtered(active=True))))
        txt += ""
        return txt

    def _inner_load(self):
        """Loads decision with matching global_key.

        Decision.load() first."""

        if self.global_key:
            value = Decision.stored_decisions.get(self.global_key)
            if value is None:
                return
            if (not self.validate_func) or self.validate_func(value):
                self.value = value
                self.status = Status.loadeddone
                self.logger.info("Loaded decision '%s' with value: %s", self.global_key, value)
            else:
                self.logger.warning("Check for loaded decision '%s' failed. Loaded value: %s",
                                    self.global_key, value)

    def _inner_save(self):
        """Make decision saveable by Decision.save()"""

        if self.status == Status.loadeddone:
            self.logger.debug("Not saving loaded decision")
            return

        if self.global_key:
            assert self.global_key not in Decision.stored_decisions or self.allow_overwrite, \
                "Decision id '%s' is not unique!"%(self.global_key)
            assert self.status in [Status.done, Status.loadeddone, Status.saveddone], \
                "Decision not made. There is nothing to store."
            Decision.stored_decisions[self.global_key] = self.value
            self.status = Status.saveddone
            self.logger.info("Stored decision '%s' with value: %s", self.global_key, self.value)

    def _post(self):
        """Write result to output dict"""
        if self.status == Status.open:
            return
        if not self.status == Status.skipped and self.allow_save:
            self._inner_save()
        if self.collect:
            self.output[self.output_key] = self.value

    def decide(self, collected=False):
        """Decide by user input
        reuses loaded decision if available

        :returns: value of decision"""

        if self.status == Status.loadeddone:
            return self.value

        if self.status != Status.open:
            raise AssertionError("Cannot call decide() for Decision with status != open")

        options = [Decision.CANCEL]
        if self.allow_skip:
            options.append(Decision.SKIP)
            if collected:
                options.append(Decision.SKIPALL)
        self.value = self.user_input(options)
        self.status = Status.done
        self._post()
        return self.value

    def skip(self):
        """Accept None as value und mark as solved"""
        if not self.allow_skip:
            raise DecisionException("This Decision can not be skipped.")
        self.value = None
        self.status = Status.skipped
        self._post()

    def parse_input(self, raw_input: str):
        """Convert input to desired type"""

        return raw_input

    def user_input(self, options):
        """Ask user for decision"""

        value = None
        msg = "Enter value"
        if options:
            msg += " or one of the following commands: %s"%(", ".join(options))
        print(msg)
        max_attempts = 10
        attempt = 0
        while True:
            raw_value = input("%s: "%(self.question))
            if raw_value == Decision.SKIP and Decision.SKIP in options:
                self.skip()
                return None
            if raw_value == Decision.SKIPALL and Decision.SKIPALL in options:
                self.skip()
                raise DecisionSkipAll
            if raw_value == Decision.CANCEL and Decision.CANCEL in options:
                raise DecisionCancle

            value = self.parse_input(raw_value)
            if self.validate(value):
                break
            else:
                if attempt <= max_attempts:
                    if attempt == max_attempts:
                        print("Last try before auto Cancel!")
                    print("'%s' is no valid input! Try again."%(raw_value))
                    value = None
                else:
                    raise DecisionCancle("Too many invalid attempts. Canceling input.")
            attempt += 1
        return value

    def __repr__(self):
        return "<%s (%s = %s)>"%(self.__class__.__name__, self.question, self.value)


class BoolDecision(Decision):
    """Accepts input convertable as bool"""

    POSITIVES = ("y", "yes", "ja", "j", "1")
    NEGATIVES = ("n", "no", "nein", "n", "0")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, validate_func=self.validate_bool, **kwargs)

    @staticmethod
    def validate_bool(value):
        """validates if value is acceptable as bool"""
        return value is True or value is False

    def parse_input(self, raw_input):
        """Convert input to bool"""

        inp = raw_input.lower()
        if inp in BoolDecision.POSITIVES:
            return True
        if inp in BoolDecision.NEGATIVES:
            return False
        return None


class CollectionDecision(Decision):
    """Base class for choose bases Decisions"""

    def __init__(self, *args, choices, **kwargs):
        self.choices = choices
        super().__init__(*args, validate_func=lambda x:not x is None, **kwargs)

    def validate_index(self, value):
        """validates if value is valid index"""
        return isinstance(value, int) and value in range(len(self.choices))

    def parse_input(self, raw_input):
        try:
            index = int(raw_input)
            return index
        except Exception:
            try:
                for c in self.choices:
                    if c[0] == raw_input:
                        index = self.choices.index(c)
                        return index
                else:
                    raise Exception('Choice not in Choices!')
            except Exception:
                return None

    def from_index(self, index):
        return

    def option_txt(self, options, number=5):
        return str(self.choices[:min(len(self.choices), number)])

    def user_input(self, options):
        print(self.question)
        print(self.option_txt(options))
        value = None
        while True:
            raw_value = input("Select option id for '%s':"%(self.global_key))

            try:
                if str(raw_value) == "Show All":
                    print(self.option_txt(options, number=len(self.choices)))
                    continue
                elif raw_value == Decision.SKIP and Decision.SKIP in options:
                    self.skip()
                    return None
            except Exception as Ex:
                print(Ex)

            index = self.parse_input(raw_value)
            if not self.validate_index(index):
                print("Enter valid index! Try again.")
                continue
            value = self.from_index(index)
            if value is not None and self.validate(value):
                break
            else:
                print("Value '%s' does not match conditions! Try again."%(raw_value))
        return value


class ListDecision(CollectionDecision):
    """Accepts index of list element as input"""

    def from_index(self, index):
        return self.choices[index]

    def option_txt(self, options, number=5):
        len_keys = len(self.choices)
        header_str = "  {id:2s}  {key:%ds}  " % len_keys
        format_str = "\n {id:3d}  {key:%ds}  " % len_keys
        options_txt = header_str.format(id="id", key="key")
        for i in range(min(len(self.choices), number)):
            # options_txt += format_str.format(id=i, key=str(self.choices[i][0]), value=str(self.choices[i][1]))
            options_txt += format_str.format(id=i, key=str(self.choices[i]))
        if len(self.choices) > number:
            for i in range(3):
                options_txt += "\n                     ."
            options_txt += "\n Type 'Show All' to display all %d options" % len(self.choices)
        return options_txt


class DictDecision(CollectionDecision):
    """Accepts index of dict element as input"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.choices = OrderedDict(self.choices)

    def from_index(self, index):
        return list(self.choices.values())[index]

    def option_txt(self, options):
        len_keys = max([len(str(key)) for key in self.choices.keys()])
        header_str = "  {id:2s}  {key:%ds}  {value:s}"%(len_keys)
        format_str = "\n {id:3d}  {key:%ds}  {value:s}"%(len_keys)
        options_txt = header_str.format(id="id", key="key", value="value")
        for i, (k, v) in enumerate(self.choices.items()):
            options_txt += format_str.format(id=i, key=str(k), value=str(v))
        return options_txt


def get_all_property_sets(element):
    sets = {'Property_Sets': {},
            'Quantity_Sets': {}}

    for p_set in element.IsDefinedBy:
        if hasattr(p_set, 'RelatingPropertyDefinition'):
            name = p_set.RelatingPropertyDefinition.Name
            props = []
            if hasattr(p_set.RelatingPropertyDefinition, 'HasProperties'):
                for p in p_set.RelatingPropertyDefinition.HasProperties:
                    props.append(p.Name)
                sets['Property_Sets'][name] = props
            elif hasattr(p_set.RelatingPropertyDefinition, 'Quantities'):
                for p in p_set.RelatingPropertyDefinition.Quantities:
                    props.append(p.Name)
                sets['Quantity_Sets'][name] = props
    return sets


def get_property(element, property_set, property_name):
    data = None
    for PropertySet in element.IsDefinedBy:
        if PropertySet.RelatingPropertyDefinition.Name == property_set:
            if hasattr(PropertySet.RelatingPropertyDefinition, 'HasProperties'):
                for Property in PropertySet.RelatingPropertyDefinition.HasProperties:
                    if Property.Name == property_name:
                        data = Property
                        break
            if hasattr(PropertySet.RelatingPropertyDefinition, 'Quantities'):
                for Property in PropertySet.RelatingPropertyDefinition.Quantities:
                    if Property.Name == property_name:
                        data = Property
                        break

    return data


def get_set(element, property_set):
    data = None
    for PropertySet in element.IsDefinedBy:
        if PropertySet.RelatingPropertyDefinition.Name == property_set:
            data = PropertySet.RelatingPropertyDefinition

    return data


def ifc_instance_overwriter(ifc_file):
    """modifies the IfcProperty of a selected Instance, and creates a new ifc file with those changes"""
    ifc_switcher = {bool: 'IfcBoolean',
                    str: 'IfcText',
                    float: 'IfcReal',
                    int: 'IfcInteger'}
    quantity_switcher = {'Volume': ifc_file.createIfcQuantityVolume,
                         'Area': ifc_file.createIfcQuantityArea,
                         'Length': ifc_file.createIfcQuantityLength}

    owner_history = ifc_file.by_type("IfcOwnerHistory")[0]

    options_by = ["by_guid", "by_type"]
    by_decision = ListDecision("Select the method to search for an element:",
                               global_key='Instance finder',
                               choices=options_by,
                               allow_skip=False,
                               allow_load=True)
    by = by_decision.decide()
    value = str(input("Insert value for the %s Method:" % by))

    finder = getattr(ifc_file, by)
    try:
        element = finder(value)
    except RuntimeError:
        element = None

    if type(element) is list:
        elements_options = {i.Name: i.GlobalId for i in element}
        element_decision = DictDecision("Select the element to change:",
                                        global_key='Element GUID',
                                        choices=elements_options,
                                        allow_skip=False,
                                        allow_load=True)
        element = ifc_file.by_guid(element_decision.decide())

    if element is not None:
        property_set = str(input("Insert name for the property set"))
        property_name = str(input("Insert name for the property"))
        property_value = input("Insert value for the property")
        if property_value.lower() in ['false', 'no']:
            property_value = False
        elif property_value.lower() in ['true', 'yes']:
            property_value = True

        sets = get_all_property_sets(element)

        # quantity set overwrite
        if property_set in sets['Quantity_Sets']:
            try:
                property_value = float(property_value)
                # property overwrite:
                if property_name in sets['Quantity_Sets'][property_set]:
                    property_to_edit = get_property(element, property_set, property_name)
                    for attr, p_value in vars(property_to_edit).items():
                        if attr.endswith('Value'):
                            attr_to_edit = attr
                            break
                    setattr(property_to_edit, attr_to_edit, property_value)

                # new property
                else:
                    set_to_edit = get_set(element, property_set)
                    quantity_function = ifc_file.createIfcQuantityLength
                    for dimension in quantity_switcher:
                        if dimension in property_name:
                            quantity_function = quantity_switcher.get(dimension, ifc_file.createIfcQuantityLength)
                        new_quantity = quantity_function(property_name, None, None, property_value)
                        edited_quantities_set = list(set_to_edit.Quantities)
                        edited_quantities_set.append(new_quantity)
                        set_to_edit.Quantities = tuple(edited_quantities_set)
            except ValueError:
                pass
        # property set overwrite
        elif property_set in sets['Property_Sets']:
            # property overwrite:
            if property_name in sets['Property_Sets'][property_set]:
                property_to_edit = get_property(element, property_set, property_name)
                type_value_in_ifc = type(property_to_edit.NominalValue.wrappedValue)
                try:
                    property_value = type_value_in_ifc(property_value)
                    property_to_edit.NominalValue.wrappedValue = property_value
                except ValueError:  # double, boolean, etc error
                    pass
            # new property
            else:
                set_to_edit = get_set(element, property_set)
                new_property = ifc_file.createIfcPropertySingleValue(
                    property_name, None, ifc_file.create_entity('IfcText', property_value),
                    None)
                edited_properties_set = list(set_to_edit.HasProperties)
                edited_properties_set.append(new_property)
                set_to_edit.HasProperties = tuple(edited_properties_set)
        #new property set, new property
        else:
            new_property = ifc_file.createIfcPropertySingleValue(
                property_name, None, ifc_file.create_entity('IfcText', property_value),
                None)
            new_properties_set = ifc_file.createIfcPropertySet(create_guid(), owner_history,
                                                               property_set, None, [new_property])
            ifc_file.createIfcRelDefinesByProperties(create_guid(), owner_history, None, None,
                                                     [element], new_properties_set)


def create_guid():
    return ifcopenshell.guid.compress(uuid.uuid1().hex)


def get_source_tool(instance):
    source_tool = None
    if hasattr(instance, 'source_tool'):
        if instance.source_tool.startswith('Autodesk'):
            source_tool = 'Autodesk Revit 2019 (DEU)'
        elif instance.source_tool.startswith('ARCHICAD'):
            source_tool = 'ARCHICAD-64'
        else:
            instance.logger.warning('No source tool for the ifc file found')
    return source_tool


def ifc_overwriter_tool(ifc_path):
    ifc_file = ifcopenshell.open(ifc_path)
    decision_bool = BoolDecision("Do you want to add changes to the ifc file %s" % ifc_path,
                                 allow_save=True,
                                 allow_load=True)
    use = decision_bool.decide()

    if use is True:
        ifc_instance_overwriter(ifc_file)
        s_continue = True
        while s_continue is not False:
            continue_bool = BoolDecision("Do you want to continue changing instances",
                                         allow_save=True,
                                         allow_load=True)
            s_continue = continue_bool.decide()

            if s_continue is True:
                ifc_instance_overwriter(ifc_file)

        ifc_file.write(ifc_path[:-4]+'_modified.ifc')


ifc_overwriter_tool("AC20-FZK-Haus.ifc")
