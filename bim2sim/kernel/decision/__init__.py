"""Decision system.

This package contains:
    - class Decision (and child classes) for representing decisions
    - class DecisionBunch for handling collections of Decision elements
    - class DecisionHandler to handle decisions
    - functions save() and load() to save to file system
"""

import enum
import hashlib
import json
import logging
from collections import Counter
from typing import Iterable, Callable, List, Dict, Any, Tuple, Union

import pint

from bim2sim.elements.mapping.units import ureg
# todo remove version? what is this used for?
__VERSION__ = '0.1'
logger = logging.getLogger(__name__)


class DecisionException(Exception):
    """Base Exception for Decisions"""


class DecisionSkip(DecisionException):
    """Exception raised on skipping Decision"""


class DecisionSkipAll(DecisionException):
    """Exception raised on skipping all Decisions"""


class DecisionCancel(DecisionException):
    """Exception raised on canceling Decisions"""


class PendingDecisionError(DecisionException):
    """Exception for unsolved Decisions"""


class Status(enum.Enum):
    """Enum for status of Decision"""
    pending = 1  # decision not yet made
    ok = 2  # decision made
    skipped = 5  # decision was skipped
    error = 6  # invalid answer


def convert_0_to_0_1(data):
    converted_data = {
        'version': '0.1',
        'checksum_ifc': None,
        'decisions': {decision: {'value': value} for decision, value in data.items()}
    }
    return converted_data


def convert(from_version, to_version, data):
    """convert stored decisions to new version"""
    if from_version == '0' and to_version == '0.1':
        return convert_0_to_0_1(data)


class Decision:
    """A question and a value which should be set to answer the question.

    Args:
        question: The question asked to the user
        console_identifier: Additional information to identify related in
            console
        validate_func: callable to validate the users input
        key: key is used by DecisionBunch to create answer dict
        global_key: unique key to identify decision. Required for saving
        allow_skip: set to True to allow skipping the decision and user None as
            value
        validate_checksum: if provided, loaded decisions are only valid if
            checksum matches
        related: iterable of GUIDs this decision is related to (frontend)
        context: iterable of GUIDs for additional context to this decision
            (frontend)
        default: default answer
        group: group of decisions this decision belongs to
        representative_global_keys: list of global keys of elements that this
         decision also has the answer for

    Example:
        >>> decision = Decision("How much is the fish?", allow_skip=True)

        # the following is usually done by child classes. Here it's a hack to make plain Decisions work
        >>> decision._validate = lambda value: True

        >>> decision.value  # will raise ValueError
        Traceback (most recent call last):
        ValueError: Can't get value from invalid decision.
        >>> decision.value = 10  # ok
        >>> decision.value
        10
        >>> decision.freeze()  # decision cant be changed afterwards
        >>> decision.value = 12  # value cant be changed, will raise AssertionError
        Traceback (most recent call last):
        AssertionError: Can't change value of frozen decision
        >>> decision.freeze(False)  # unfreeze decision
        >>> decision.reset()  # reset to initial state
        >>> decision.skip()  # set value to None, only works if allow_skip flag set
    """

    SKIP = "skip"
    SKIPALL = "skip all"
    CANCEL = "cancel"
    options = [SKIP, SKIPALL, CANCEL]

    def __init__(self, question: str, console_identifier: str = None,
                 validate_func: Callable = None,
                 key: str = None, global_key: str = None,
                 allow_skip=False, validate_checksum=None,
                 related: List[str] = None, context: List[str] = None,
                 default=None, group: str = None,
                 representative_global_keys: list = None):

        self.status = Status.pending
        self._frozen = False
        self._value = None

        self.question = question
        self.console_identifier = console_identifier
        self.validate_func = validate_func
        self.default = None
        if default is not None:
            if self.validate(default):
                self.default = default
            else:
                logger.warning("Invalid default value (%s) for %s: %s",
                               default, self.__class__.__name__, self.question)

        self.key = key
        self.global_key = global_key

        self.allow_skip = allow_skip
        self.allow_save_load = bool(global_key)

        self.validate_checksum = validate_checksum

        self.related = related
        self.context = context

        self.group = group
        self.representative_global_keys = representative_global_keys

    @property
    def value(self):
        """Answer value of decision.

        Raises:
            ValueError: On accessing the value before it is set or by setting an invalid value
            AssertionError: By changing a frozen Decision
        """
        if self.valid():
            return self._value
        else:
            raise ValueError("Can't get value from invalid decision.")

    @value.setter
    def value(self, value):
        if self._frozen:
            raise AssertionError("Can't change value of frozen decision")
        # if self.status != Status.pending:
        #     raise ValueError("Decision is not pending. Call reset() first.")
        _value = self.convert(value)
        if _value is None:
            self.skip()
        elif self.validate(_value):
            self._value = _value
            self.status = Status.ok
        else:
            raise ValueError("Invalid value: %r for %s" % (value, self.question))

    def reset(self):
        """Reset the Decision to it's initial state.

        Raises:
            AssertionError: if Decision is frozen
        """
        if self._frozen:
            raise AssertionError("Can't change frozen decision")
        self.status = Status.pending
        self._value = None

    def freeze(self, freeze=True):
        """Freeze this Decision to prevent further manipulation.

        Args:
            freeze: the freeze state

        Raises:
            AssertionError: If the Decision is currently pending
        """
        if self.status == Status.pending and freeze:
            raise AssertionError(
                "Can't freeze pending decision. Set valid value first.")
        self._frozen = freeze

    def skip(self):
        """Set value to None und mark as solved."""
        if not self.allow_skip:
            raise DecisionException("This Decision can not be skipped.")
        if self._frozen:
            raise DecisionException("Can't change frozen decision.")
        if self.status != Status.pending:
            raise DecisionException(
                "This Decision is not pending. Call reset() first.")
        self._value = None
        self.status = Status.skipped

    @staticmethod
    def build_checksum(item):
        """Create checksum for item."""
        return hashlib.md5(json.dumps(item, sort_keys=True)
                           .encode('utf-8')).hexdigest()

    def convert(self, value):
        """Convert value to inner type."""
        return value

    def _validate(self, value):
        raise NotImplementedError("Implement method _validate!")

    def validate(self, value) -> bool:
        """Checks value with validate_func and returns truth value."""
        _value = self.convert(value)
        basic_valid = self._validate(_value)

        if self.validate_func:
            if type(self.validate_func) is not list:
                self.validate_func = [self.validate_func]
            check_list = []
            for fnc in self.validate_func:
                try:
                    check_list.append(bool(fnc(_value)))
                except:
                    check_list.append(False)
            external_valid = all(check_list)
        else:
            external_valid = True

        return basic_valid and external_valid

    def valid(self) -> bool:
        """Check if Decision is valid."""
        return self.status == Status.ok \
               or (self.status == Status.skipped and self.allow_skip)

    def reset_from_deserialized(self, kwargs):
        """Reset decision from its serialized form."""
        value = kwargs['value']
        checksum = kwargs.get('checksum')
        if value is None:
            return
        valid = False
        if self.validate_func:
            if type(self.validate_func) is not list:
                self.validate_func = [self.validate_func]
            check_list = []
            for fnc in self.validate_func:
                check_list.append(bool(fnc(value)))
            valid = all(check_list)
        if (not self.validate_func) or valid:
            if checksum == self.validate_checksum:
                self.value = self.deserialize_value(value)
                self.status = Status.ok
                logger.info("Loaded decision '%s' with value: %s", self.global_key, value)
            else:
                logger.warning("Checksum mismatch for loaded decision '%s", self.global_key)
        else:
            logger.warning("Check for loaded decision '%s' failed. Loaded value: %s",
                           self.global_key, value)

    def serialize_value(self):
        """Return JSON serializable value."""
        return {'value': self.value}

    def deserialize_value(self, value):
        """rebuild value from json deserialized object"""
        return value

    def get_serializable(self):
        """Returns json serializable object representing state of decision"""
        kwargs = self.serialize_value()
        if self.validate_checksum:
            kwargs['checksum'] = self.validate_checksum
        return kwargs

    def get_options(self):
        """Get all available options."""
        options = [Decision.CANCEL]
        if self.allow_skip:
            options.append(Decision.SKIP)

        return options

    def get_question(self) -> str:
        """Get the question."""
        return self.question

    def get_body(self):
        """Returns list of tuples representing items of CollectionDecision else None"""
        return None

    def __repr__(self):
        value = str(self.value) if self.status == Status.ok else '???'
        return '<%s (<%s> Q: "%s" A: %s)>' % (
            self.__class__.__name__, self.status, self.question, value)


class RealDecision(Decision):
    """Accepts input of type real.

    Args:
        unit: the unit of the Decisions value
    """

    def __init__(self, *args, unit: pint.Quantity = None, **kwargs):
        self.unit = unit if unit else ureg.dimensionless
        default = kwargs.get('default')
        if default is not None and not isinstance(default, pint.Quantity):
            kwargs['default'] = default * self.unit
        super().__init__(*args, **kwargs)

    def convert(self, value):
        if not isinstance(value, pint.Quantity):
            try:
                return value * self.unit
            except:
                pass
        return value

    def _validate(self, value):
        if isinstance(value, pint.Quantity):
            try:
                float(value.m)
            except:
                pass
            else:
                return True
        return False

    def get_question(self):
        return "{} in [{}]".format(self.question, self.unit)

    def get_body(self):
        return {'unit': str(self.unit)}

    def get_debug_answer(self):
        answer = super().get_debug_answer()
        if isinstance(answer, pint.Quantity):
            return answer.to(self.unit)
        return answer * self.unit

    def serialize_value(self):
        kwargs = {
            'value': self.value.magnitude,
            'unit': str(self.value.units)
        }
        return kwargs

    def reset_from_deserialized(self, kwargs):
        kwargs['value'] = kwargs['value'] * ureg[kwargs.pop('unit', str(self.unit))]
        super().reset_from_deserialized(kwargs)


class BoolDecision(Decision):
    """Accepts input convertable as bool"""

    POSITIVES = ("y", "yes", "ja", "j", "1")
    NEGATIVES = ("n", "no", "nein", "n", "0")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, validate_func=None, **kwargs)

    @staticmethod
    def _validate(value):
        """validates if value is acceptable as bool"""
        return value is True or value is False


class ListDecision(Decision):
    """Accepts index of list element as input.

    Args:
        choices: a list of values where str(value) is used for labels or a list of (value, label) tuples
        live_search:

    """

    def __init__(self, *args, choices:List[Union[Any, Tuple[Any, str]]], live_search=False, **kwargs):
        if not choices:
            raise AttributeError("choices must hold at least one item")
        if hasattr(choices[0], '__len__') and len(choices[0]) == 2:
            self.items = [choice[0] for choice in choices]
            self.labels = [str(choice[1]) for choice in choices]
        else:
            self.items = choices
            # self.labels = [str(choice) for choice in self.items]

        self.live_search = live_search
        super().__init__(*args, validate_func=None, **kwargs)

        if len(self.items) == 1:
            if not self.status != Status.pending:
                # set only item as default
                if self.default is None:
                    self.default = self.items[0]

    @property
    def choices(self):
        """Available choices for the Decision."""
        if hasattr(self, 'labels'):
            return zip(self.items, self.labels)
        else:
            return self.items

    def _validate(self, value):
        pass  # _validate not required. see validate

    def validate(self, value):
        return value in self.items

    def get_body(self):
        body = []
        for i, item in enumerate(self.choices):
            if isinstance(item, (list, tuple)) and len(item) == 2:
                # label provided
                body.append((i, *item))
            else:
                # no label provided
                body.append((i, item, ' '))
        return body


class StringDecision(Decision):
    """Accepts string input"""

    def __init__(self, *args, min_length=1, **kwargs):
        self.min_length = min_length
        super().__init__(*args, **kwargs)

    def _validate(self, value):
        return isinstance(value, str) and len(value) >= self.min_length


class GuidDecision(Decision):
    """Accepts GUID(s) as input. Value is a set of GUID(s)"""

    def __init__(self, *args, multi=False, **kwargs):
        self.multi = multi
        super().__init__(*args, **kwargs)

    def _validate(self, value):
        if isinstance(value, set) and value:
            if not self.multi and len(value) != 1:
                return False
            return all(isinstance(guid, str) and len(guid) == 22 for guid in value)
        return False

    def serialize_value(self):
        return {'value': list(self.value)}

    def deserialize_value(self, value):
        return set(value)


class DecisionBunch(list):
    """Collection of decisions."""

    def __init__(self, decisions: Iterable[Decision] = ()):
        super().__init__(decisions)

    def valid(self) -> bool:
        """Check status of all decisions."""
        return all(decision.status in (Status.ok, Status.skipped)
                   for decision in self)

    def to_answer_dict(self) -> Dict[Any, Decision]:
        """Create dict from DecisionBunch using decision.key."""
        return {decision.key: decision.value for decision in self}

    def to_serializable(self) -> dict:
        """Create JSON serializable dict of decisions."""
        decisions = {decision.global_key: decision.get_serializable()
                     for decision in self}
        return decisions

    def validate_global_keys(self):
        """Check if all global keys are unique.

        :raises: AssertionError on bad keys."""
        # mapping = {decision.global_key: decision for decision in self}
        count = Counter(item.global_key for item in self if item.global_key)
        duplicates = {decision for (decision, v) in count.items() if v > 1}

        if duplicates:
            raise AssertionError("Following global keys are not unique: %s",
                                 duplicates)

    def get_reduced_bunch(self, criteria: str = 'key'):
        """Reduces the decisions to one decision per unique key.

        To reduce the number of decisions in some cases the same answer can be
        used for multiple decisions. This method allows to reduce the number
        of decisions based on a given criteria.

        Args:
            criteria: criteria based on which the decisions should be reduced.
                Possible are 'key' and 'question'.
        Returns:
            unique_decisions: A DecisionBunch with only unique decisions based
                on criteria
        """
        pos_criteria = ['key', 'question']
        if criteria not in pos_criteria:
            raise NotImplementedError(f'Pick one of these valid options:'
                                      f' {pos_criteria}')
        unique_decisions = DecisionBunch()
        doubled_decisions = DecisionBunch()
        existing_criteria = []
        for decision in self:
            cur_key = getattr(decision, criteria)
            if cur_key not in existing_criteria:
                unique_decisions.append(decision)
                existing_criteria.append(cur_key)
            else:
                doubled_decisions.append(decision)

        return unique_decisions, doubled_decisions


def save(bunch: DecisionBunch, path):
    """Save solved Decisions to file system"""

    decisions = bunch.to_serializable()
    data = {
        'version': __VERSION__,
        'checksum_ifc': None,
        'decisions': decisions,
    }
    with open(path, "w") as file:
        json.dump(data, file, indent=2)
    logger.info("Saved %d decisions.", len(bunch))


def load(path) -> Dict[str, Any]:
    """Load previously solved Decisions from file system."""

    try:
        with open(path, "r") as file:
            data = json.load(file)
    except IOError as ex:
        logger.info(f"Unable to load decisions. "
                    f"No Existing decisions found at {ex.filename}")
        return {}
    version = data.get('version', '0')
    if version != __VERSION__:
        try:
            data = convert(version, __VERSION__, data)
            logger.info("Converted stored decisions from version '%s' to '%s'", version, __VERSION__)
        except:
            logger.error("Decision conversion from %s to %s failed")
            return {}
    decisions = data.get('decisions')
    logger.info("Found %d previous made decisions.", len(decisions or []))
    return decisions
