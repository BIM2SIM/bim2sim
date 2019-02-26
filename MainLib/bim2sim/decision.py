"""Package holding decision system"""

import logging
import enum

class DecisionException(Exception):
    """Base Exception for Decisions"""
class DecisionSkipAll(DecisionException):
    """Exception raised on skipping all Decisions"""
class DecisionCancle(DecisionException):
    """Exception raised on canceling Decisions"""

class Status(enum.Enum):
    """Enum for status of Decision"""
    open = 1
    done = 2
    loadeddone = 3
    saveddone = 4
    skipped = 5

class Decision():
    """Class for handling decisions and user interaction"""

    collection = []
    stored_decisions = {}
    _logger = None

    SKIP = "skip"
    SKIPALL = "skip all"
    CANCLE = "cancle"
    options = [SKIP, SKIPALL, CANCLE]

    def __init__(self, output: dict, dict_key: str, question: str, given_value,
                 check_func=None, global_key: str = None, collect=False):
        self.status = Status.open
        self.output = output
        self.global_key = global_key
        self.dict_key = dict_key
        self.question = question
        self.check_func = check_func

        self.load()

        if not self.status == Status.loadeddone:
            self.value = self._inner_decide(given_value, collect)

        if self.status in [Status.done, Status.loadeddone]:
            self.post()

    @property
    def logger(self):
        """logger instance"""
        if not Decision._logger:
            Decision._logger = logging.getLogger(__name__)
        return Decision._logger

    def check(self, value):
        """Checks value with check_func and returns truth value"""

        res = False
        try:
            res = bool(self.check_func(value))
        except:
            pass
        return res

    @classmethod
    def decide_stored(cls):
        """Solve all stored decisions"""

        skip_all = False
        for decision in cls.collection:
            if skip_all:
                decision.skip()
            else:
                try:
                    decision.decide()
                except DecisionSkipAll as ex:
                    skip_all = True
                except DecisionCancle as ex:
                    logger = cls.logger.__get__(None)
                    logger.info("Canceling decisions")
                    raise

    @classmethod
    def load(cls):
        pass

    @classmethod
    def save(cls):
        pass

    def load(self):
        """Loads decision with maching global_key.

        Decision.load() first."""

        if self.global_key:
            value = Decision.stored_decisions.get(self.global_key)
            if value is None:
                return
            if (not self.check_func) or self.check_func(value):
                self.value = value
                self.status = Status.loadeddone
                self.logger.info("Loaded decision '%s' with value: %s", self.global_key, value)
            else:
                self.logger.warning("Check for loaded decision '%s' failed. Loaded value: %s",
                                    self.global_key, value)

    def save(self):
        """Make decision saveable by Decision.save()"""

        if self.global_key:
            assert not self.global_key in Decision.stored_decisions, \
                "Decision id '%s' is not unique!"%(self.global_key)
            assert self.status in [Status.done, Status.loadeddone, Status.saveddone], \
                "Decision not made. There is nothing to store."
            Decision.stored_decisions[self.global_key] = self.value
            self.status = Status.saveddone
            self.logger.info("Stored decision '%s' with value: %s", self.global_key, self.value)

    def _inner_decide(self, given_value, collect):
        """Trys to find a dicison on given input and returns value"""

        result = given_value
        valid = self.check(result)
        if not valid:
            self.status = Status.open
            self.logger.warning("Recieved invalid value (%s) for '%s'", result, self.global_key)

        if not self.status in [Status.done, Status.loadeddone]:
            if collect:
                Decision.collection.append(self)
                self.logger.debug("Added decision for later processing.")
            else:
                # instant user input
                result = self.user_input([Decision.SKIP])
                self.status = Status.done

        return result

    def decide(self):
        """decide by user input"""
        self.value = self.user_input(Decision.options)
        self.status = Status.done
        self.post()

    def skip(self):
        """Accept None as value und mark as solved"""
        self.status = Status.skipped
        self.post()

    @classmethod
    def summary(cls):
        """Returns summary string"""
        txt = "%d open decisions"%(len(cls.collection))
        txt += ""
        return txt

    def post(self):
        """Write result to output dict"""
        assert not self.status == Status.open
        self.output[self.dict_key] = self.value
        if not self.status == Status.skipped:
            self.save()

    def parse_input(self, raw_input: str):
        """Convert input to desired type"""
        return raw_input

    def user_input(self, options):
        """Ask user for decision"""

        value = None
        print("Enter value or one of the following commands: %s"%(options))
        while True:
            raw_value = input("%s: "%(self.question))
            if raw_value == Decision.SKIP:
                self.skip()
                return value
            if raw_value == Decision.SKIPALL:
                self.skip()
                raise DecisionSkipAll
            if raw_value == Decision.CANCLE:
                raise DecisionCancle

            value = self.parse_input(raw_value)
            if self.check(value):
                break
            else:
                print("Value '%s' does not match conditions! Try again."%(raw_value))
        return value

    def __repr__(self):
        return "<%s (%s = %s)>"%(self.__class__.__name__, self.question, self.value)

class RealDecision(Decision):
    """Accepts input of type real"""

    def parse_input(self, raw_input):
        """Convert input to float"""
        try:
            value = float(raw_input)
        except:
            value = None
        return value

#class ListDecision(Decision):

#    def __init__(self, *args, choices:list, **kwargs):
#        self.chioces = choices
#        super().__init__(*args, getter=None, **kwargs)

#    def parse_input(self, raw_input):
#        try:
#            index = int(raw_input)
#            return self.chioces[index]
#        except:
#            return None

#    def user_input(self):
#        options = "  id  item"
#        for i in range(len(self.chioces)):
#            options += "\n{id:4d}  {item:s}".format(id=i, item=self.chioces[i])
#        print(options)
#        value = None
#        while True:
#            raw_value = input("Select id for '%s':"%(self.dict_key))
#            value = self.parse_input(raw_value)
#            if self.check(value):
#                break
#            else:
#                print("Value '%s' does not match conditions! Try again."%(raw_value))
#        return value
