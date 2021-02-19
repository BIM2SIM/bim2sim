"""Package holding decision system"""

import logging
import enum
import json
import hashlib
from contextlib import contextmanager

import pint

from bim2sim.kernel.units import ureg


__VERSION__ = '0.1'


class DecisionException(Exception):
    """Base Exception for Decisions"""
class DecisionSkip(DecisionException):
    """Exception raised on skipping Decision"""
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

    _debug_answer = None
    _debug_mode = False
    _debug_validate = False

    frontend = None
    logger = logging.getLogger(__name__)

    def __init__(self, question: str, validate_func=None,
                 output: dict = None, output_key: str = None, global_key: str = None,
                 allow_skip=False, allow_load=None, allow_save=False,
                 collect=False, quick_decide=False,
                 validate_checksum=None, related=None, context=None):
        """
        :param question: The question asked to the user
        :param validate_func: callable to validate the users input
        :param output: dictionary to store output_key:value in
        :param output_key: key for output
        :param global_key: unique key to identify decision. Required for saving
        :param allow_skip: set to True to allow skipping the decision and user None as value
        :param allow_load: allows loading value from previous made decision with same global_key (Has no effect when global_key is not provided)
        :param allow_save: allows saving decisions value and global_key for later reuse (Has no effect when global_key is not provided)
        :param collect: add decision to collection for later processing. (output and output_key needs to be provided)
        :param quick_decide: calls decide() within __init__()
        :param validate_checksum: if provided, loaded decisions are only valid if checksum matches
        :param related: iterable of GUIDs this decision is related to (frontend)
        :param context: iterable of GUIDs for additional context to this decision (frontend)

        :raises: :class:'AttributeError'::
        """
        self.status = Status.open
        self._value = None

        self.question = question
        self.validate_func = validate_func

        self.output = output
        self.output_key = output_key
        self.global_key = global_key

        self.allow_skip = allow_skip
        self.allow_save = allow_save
        self.allow_load = allow_save if allow_load is None else allow_load

        self.collect = collect
        self.validate_checksum = validate_checksum

        self.related = related
        self.context = context

        if (allow_load or allow_save) and not global_key:
            raise AssertionError("Require global_key to enable save / load.")

        if global_key and global_key in self.global_keys():
            #self.discard()
            raise KeyError("Decision with key %s already exists!" % global_key)

        if self.allow_load:
            self._inner_load()

        if quick_decide and not self.status == Status.loadeddone:
            self.decide()

        if self.collect and not (isinstance(self.output, dict) and self.output_key):
            raise AttributeError("Can not collect Decision if output dict or output_key is missing.")

        Decision.all.append(self)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if self.status != Status.open:
            raise ValueError("Decision is not open. Call reset() first.")
        if self.validate(value):
            self._value = value
            self.status = Status.done
            self._post()
        else:
            raise ValueError("Invalid value: %r" % value)

    def reset(self):
        self.status = Status.open
        self._value = None
        if self.output_key in self.output:
            del self.output[self.output_key]
        if self.output_key in Decision.stored_decisions:
            del Decision.stored_decisions[self.global_key]

    def skip(self):
        """Accept None as value und mark as solved"""
        if not self.allow_skip:
            raise DecisionException("This Decision can not be skipped.")
        if self.status != Status.open:
            raise DecisionException("This Decision is not open. Call reset() first.")
        self._value = None
        self.status = Status.skipped
        self._post()

    def discard(self):
        """Remove decision from traced decisions (Decision.all)"""
        try:
            Decision.all.remove(self)
        except ValueError:
            # not in list
            pass
        self.reset()

    @classmethod
    def reset_decisions(cls):
        """Reset state of Decision class."""
        cls.stored_decisions.clear()
        cls.all.clear()

    @classmethod
    def global_keys(cls):
        """Global key generator"""
        for decision in cls.all:
            if decision.global_key:
                yield decision.global_key

    @staticmethod
    def build_checksum(item):
        return hashlib.md5(json.dumps(item, sort_keys=True).encode('utf-8')).hexdigest()

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

    @classmethod
    def set_frontend(cls, frontend):
        cls.frontend = frontend

    @classmethod
    def enable_debug(cls, answer, validate=False):
        """Enabled debug mode. All decisions are answered with answer"""
        cls._debug_mode = True
        cls._debug_answer = answer
        cls._debug_validate = validate

    @classmethod
    def disable_debug(cls):
        """Disable debug mode"""
        cls._debug_answer = None
        cls._debug_mode = False
        cls._debug_validate = False

    @classmethod
    @contextmanager
    def debug_answer(cls, answer, validate=False):
        """Contextmanager enabling debug mode temporarily with given answer"""
        cls.enable_debug(answer, validate)
        yield
        cls.disable_debug()

    def get_debug_answer(self):
        return self._debug_answer

    def _validate(self, value):
        raise NotImplementedError("Implement method _validate!")

    def validate(self, value):
        """Checks value with validate_func and returns truth value"""

        basic_valid = self._validate(value)

        if self.validate_func:
            try:
                external_valid = bool(self.validate_func(value))
            except:
                external_valid = False
        else:
            external_valid = True

        return basic_valid and external_valid

    def decide(self):
        """Decide by user input
        reuses loaded decision if available

        :returns: value of decision"""

        if self.status == Status.loadeddone:
            return self.value

        if self.status != Status.open:
            raise AssertionError("Cannot call decide() for Decision with status != open")

        if self._debug_mode:
            if self._debug_validate:
                self.value = self.get_debug_answer()
            else:
                self._value = self.get_debug_answer()
                self.status = Status.done
                self._post()
        else:
            self.frontend.solve(self)

        # self.status = Status.done
        # self._post()
        return self.value

    @classmethod
    def decide_collected(cls, collection=None):
        """Solve all stored decisions"""

        logger = logging.getLogger(__name__)

        _collection = collection or cls.collection()
        _collection = [d for d in _collection if d.status == Status.open]

        if cls._debug_mode:
            # debug
            for decision in _collection:
                if cls._debug_validate:
                    decision.value = cls._debug_answer
                else:
                    decision._value = cls._debug_answer
                    decision.status = Status.done
                    decision._post()
        else:
            # normal
            try:
                cls.frontend.solve_collection(_collection)
            except DecisionSkipAll:
                logger.info("Skipping remaining decisions")
                for decision in _collection:
                    if decision.status == Status.open:
                        decision.skip()
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
            return
        version = data.get('version', '0')
        if version != __VERSION__:
            try:
                data = convert(version, __VERSION__, data)
                logger.info("Converted stored decisions from version '%s' to '%s'", version, __VERSION__)
            except:
                logger.error("Decision conversion from %s to %s failed")
                return
        decisions = data.get('decisions')

        if decisions:
            msg = "Found %d previous made decisions. Continue using them?"%(len(decisions))
            reuse = BoolDecision(question=msg).decide()
            if reuse:
                cls.stored_decisions.clear()
                cls.stored_decisions.update(**decisions)
                logger.info("Loaded decisions.")

    @classmethod
    def save(cls, path):
        """Save solved Decisions to file system"""

        logger = logging.getLogger(__name__)

        decisions = {key: kwargs for key, kwargs in cls.stored_decisions.items()}
        data = {
            'version': __VERSION__,
            'checksum_ifc': None,
            'decisions': decisions,
        }
        with open(path, "w") as file:
            json.dump(data, file, indent=2)
        logger.info("Saved %d decisions.", len(cls.stored_decisions))

    @classmethod
    def summary(cls):
        """Returns summary string"""

        txt = "%d open decisions" % (len(list(cls.filtered(active=True))))
        txt += ""
        return txt

    def reset_from_deserialized(self, kwargs):
        """"""
        value = kwargs['value']
        checksum = kwargs.get('checksum')
        if value is None:
            return
        if (not self.validate_func) or self.validate_func(value):
            if checksum == self.validate_checksum:
                self.value = value
                self.status = Status.loadeddone
                self.logger.info("Loaded decision '%s' with value: %s", self.global_key, value)
            else:
                self.logger.warning("Checksum mismatch for loaded decision '%s", self.global_key)
        else:
            self.logger.warning("Check for loaded decision '%s' failed. Loaded value: %s",
                                self.global_key, value)

    def _inner_load(self):
        """Loads decision with matching global_key.

        Decision.load() first."""

        if self.global_key:
            kwargs = Decision.stored_decisions.get(self.global_key, None)
            if kwargs is not None:
                self.reset_from_deserialized(kwargs)

    def serialize_value(self):
        return {'value': self.value}

    def get_serializable(self):
        """Returns json serializable object representing state of decision"""
        kwargs = self.serialize_value()
        if self.validate_checksum:
            kwargs['checksum'] = self.validate_checksum
        return kwargs

    def _inner_save(self):
        """Make decision saveable by Decision.save()"""

        if self.status == Status.loadeddone:
            self.logger.debug("Not saving loaded decision")
            return

        if self.global_key:
            # assert self.global_key not in Decision.stored_decisions or self.allow_overwrite, \
            #     "Decision id '%s' is not unique!"%(self.global_key)
            assert self.status != Status.open, \
                "Decision not made. There is nothing to store."
            kwargs = self.get_serializable()

            Decision.stored_decisions[self.global_key] = kwargs
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

    def get_options(self):
        options = [Decision.CANCEL]
        if self.allow_skip:
            options.append(Decision.SKIP)

        return options

    def get_question(self):
        return self.question

    def get_body(self):
        """Returns list of tuples representing items of CollectionDecision else None"""
        return None

    def __repr__(self):
        return '<%s (<%s> Q: "%s" A: %s)>' % (self.__class__.__name__, self.status, self.question, self.value)


class RealDecision(Decision):
    """Accepts input of type real"""

    def __init__(self, *args, unit=None, **kwargs):
        """"""
        self.unit = unit if unit else ureg.dimensionless
        super().__init__(*args, **kwargs)

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
        return self._debug_answer * self.unit

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

    Choices is a list of either
      - values, str(value) is used for label
      - tuples of (value, label)"""

    def __init__(self, *args, choices, **kwargs):
        if not choices:
            raise AttributeError("choices must hold at least one item")
        if hasattr(choices[0], '__len__') and len(choices[0]) == 2:
            self.items = [choice[0] for choice in choices]
            self.labels = [str(choice[1]) for choice in choices]
        else:
            self.items = choices
            # self.labels = [str(choice) for choice in self.items]

        super().__init__(*args, validate_func=None, **kwargs)

        if len(self.items) == 1:
            if not self.status != Status.open:
                # auto decide
                self.value = self.items[0]

    @property
    def choices(self):
        if hasattr(self, 'labels'):
            return zip(self.items, self.labels)
        else:
            return self.items

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
