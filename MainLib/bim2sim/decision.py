"""Package holding decision system"""

import logging
import enum
import json


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


class FrontEnd:
    """Basic FrontEnd for decision solving"""

    def __init__(self):
        self.logger = logging.getLogger(__name__ + '.DecisonFrontend')

    def solve(self, decision):
        raise NotImplementedError

    def solve_collection(self, collection):
        raise NotImplementedError

    def get_question(self, decision):
        return decision.question

    def get_body(self, decision):
        return decision.get_body()

    def get_options(self, decision):
        return decision.get_options()

    def parse(self, decision, raw_answer):
        return decision.parse_input(raw_answer)

    def validate(self, decision, value):
        return decision.validate(value)


class ConsoleFrontEnd(FrontEnd):

    @staticmethod
    def get_input_txt(decision):
        txt = 'Enter value: '
        if isinstance(decision, CollectionDecision):
            txt = 'Enter key: '

        return txt

    @staticmethod
    def get_options_txt(options):
        return "Additional commands: %s" % (", ".join(options))

    @staticmethod
    def get_body_txt(body):
        len_labels = max(len(str(item[2])) for item in body)
        header_str = "  {key:3s}  {label:%ds}  {value:s}" % (len_labels)
        format_str = "\n  {key:3s}  {label:%ds}  {value:s}" % (len_labels)
        body_txt = header_str.format(key="key", label="label", value="value")

        for key, value, label in body:
            body_txt += format_str.format(key=str(key), label=str(label), value=str(value))

        return body_txt

    @staticmethod
    def collection_progress(collection):
        total = len(collection)
        for i, decision in enumerate(collection):
            yield decision, "[Decision {}/{}]".format(i + 1, total)

    def solve(self, decision):
        return self.user_input(decision)

    def solve_collection(self, collection):

        skip_all = False
        extra_options = []
        if all([d.allow_skip for d in collection]):
            extra_options.append(Decision.SKIPALL)

        for decision, progress in self.collection_progress(collection):
            if skip_all and decision.allow_skip:
                decision.skip()
            else:
                if skip_all:
                    self.logger.info("Decision can not be skipped")
                try:
                    decision.value = self.user_input(decision, extra_options=extra_options, progress=progress)
                except DecisionSkip:
                    decision.skip()
                except DecisionSkipAll:
                    skip_all = True
                    self.logger.info("Skipping remaining decisions")
                except DecisionCancle as ex:
                    self.logger.info("Canceling decisions")
                    raise

    # TODO: based on decision type
    # TODO: merge from element_filter_by_text
    def user_input(self, decision, extra_options=None, progress=''):

        question = self.get_question(decision)
        options = self.get_options(decision)
        if extra_options:
            options = options + extra_options
        options_txt = self.get_options_txt(options)
        body = self.get_body(decision)
        input_txt = self.get_input_txt(decision)
        if progress:
            progress += ' '

        print(progress, end='')
        print(question)
        print(options_txt)
        if body:
            print(self.get_body_txt(body))

        max_attempts = 10
        attempt = 0
        while True:
            raw_value = input(input_txt)
            if raw_value.lower() == Decision.SKIP.lower() and Decision.SKIP in options:
                raise DecisionSkip
                # decision.skip()
                # return None
            if raw_value.lower() == Decision.SKIPALL.lower() and Decision.SKIPALL in options:
                decision.skip()
                raise DecisionSkipAll
            if raw_value.lower() == Decision.CANCEL.lower() and Decision.CANCEL in options:
                raise DecisionCancle

            value = self.parse(decision, raw_value)
            if self.validate(decision, value):
                break
            else:
                if attempt <= max_attempts:
                    if attempt == max_attempts:
                        print("Last try before auto Cancel!")
                    print("'%s' is no valid input! Try again." % raw_value)
                else:
                    raise DecisionCancle("Too many invalid attempts. Canceling input.")
            attempt += 1

        return value


class ExternalFrontEnd(FrontEnd):

    def __iter__(self):
        raise StopIteration


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

    frontend = ConsoleFrontEnd()
    logger = logging.getLogger(__name__)

    def __init__(self, question: str, validate_func=None,
                 output: dict = None, output_key: str = None, global_key: str = None,
                 allow_skip=False, allow_load=False, allow_save=False,
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
        self._value = None

        self.question = question
        self.validate_func = validate_func

        self.output = output
        self.output_key = output_key
        self.global_key = global_key

        self.allow_skip = allow_skip
        self.allow_save = allow_save
        self.allow_load = allow_load

        self.collect = collect

        if global_key and global_key in self.global_keys():
            self.discard()
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
        Decision.all.remove(self)
        self.reset()

    @classmethod
    def global_keys(cls):
        """Global key generator"""
        for decision in cls.all:
            if decision.global_key:
                yield decision.global_key

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

        self.value = self.frontend.solve(self)

        # self.status = Status.done
        # self._post()
        return self.value

    @classmethod
    def decide_collected(cls, collection=None):
        """Solve all stored decisions"""

        logger = logging.getLogger(__name__)

        _collection = collection or cls.collection()
        _collection = [d for d in _collection if d.status == Status.open]

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
            # assert self.global_key not in Decision.stored_decisions or self.allow_overwrite, \
            #     "Decision id '%s' is not unique!"%(self.global_key)
            assert self.status != Status.open, \
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

    def get_options(self):
        options = [Decision.CANCEL]
        if self.allow_skip:
            options.append(Decision.SKIP)

        return options

    def get_body(self):
        """Returns list of tuples representing items of CollectionDecision else None"""
        return None

    def parse_input(self, raw_input: str):
        """Convert input to desired type"""
        return raw_input

    def __repr__(self):
        return '<%s (<%s> Q: "%s" A: %s)>' % (self.__class__.__name__, self.status, self.question, self.value)


class RealDecision(Decision):
    """Accepts input of type real"""

    def parse_input(self, raw_input):
        """Convert input to float"""

        try:
            value = float(raw_input)
        except:
            value = None
        return value

    def _validate(self, value):
        return isinstance(value, float)


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

    def parse_input(self, raw_input):
        """Convert input to bool"""

        inp = raw_input.lower()
        if inp in BoolDecision.POSITIVES:
            return True
        if inp in BoolDecision.NEGATIVES:
            return False
        return None


class CollectionDecision(Decision):
    """Base class for chice bases Decisions"""

    def __init__(self, *args, choices, **kwargs):
        """"""
        self.choices = choices
        super().__init__(*args, **kwargs)


class ListDecision(CollectionDecision):
    """Accepts index of list element as input.

    Choices is a list of either
      - values, str(value) is used for label
      - tuples of (value, label)"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, validate_func=None, **kwargs)

    def parse_input(self, raw_input):
        raw_value = None
        try:
            index = int(raw_input)
            raw_value = self.choices[index]
        except Exception:
            pass

        return raw_value

    def validate(self, value):
        return value in self.choices

    def get_body(self):
        body = []
        for i, item in enumerate(self.choices):
            if isinstance(item, (list, tuple)) and len(item) == 2:
                # label provided
                body.append((i, *item))
            else:
                # no label provided
                body.append((i, item, str(item)))
        return body


# class DictDecision(CollectionDecision):
#     """Accepts index of dict element as input"""
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.choices = OrderedDict(self.choices)
#
#     def from_index(self, index):
#         return list(self.choices.values())[index]
#
#     def option_txt(self, options):
#         len_keys = max([len(str(key)) for key in self.choices.keys()])
#         header_str = "  {id:2s}  {key:%ds}  {value:s}"%(len_keys)
#         format_str = "\n {id:3d}  {key:%ds}  {value:s}"%(len_keys)
#         options_txt = header_str.format(id="id", key="key", value="value")
#         for i, (k, v) in enumerate(self.choices.items()):
#             options_txt += format_str.format(id=i, key=str(k), value=str(v))
#         return options_txt
