"""Package holding decision system"""

import logging
import enum
import json

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

    def __init__(self, question: str, check_func, 
                 output: dict = None, dict_key: str = None, global_key: str = None, allow_skip = False):

        self.status = Status.open

        self.question = question
        self.check_func = check_func
        
        self.output = output
        self.dict_key = dict_key
        self.global_key = global_key

        self.allow_skip = allow_skip
        self.collect = False
        if not output is None:
            assert dict_key, "If output dict is given a dict_key is also needed."
            self.collect = True

        self.inner_load()

        if not self.status == Status.loadeddone:
            self.value = self._inner_decide(self.collect)

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

        logger = logging.getLogger(__name__)
        skip_all = False
        for decision in cls.collection:
            if skip_all:
                decision.skip()
            else:
                try:
                    decision.decide()
                except DecisionSkipAll as ex:
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
                reuse = BoolDecision(question=msg).value
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

    def inner_load(self):
        """Loads decision with matching global_key.

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

    def inner_save(self):
        """Make decision saveable by Decision.save()"""

        if self.status == Status.loadeddone:
            self.logger.debug("Not saving loaded decision")
            return

        if self.global_key:
            assert not self.global_key in Decision.stored_decisions, \
                "Decision id '%s' is not unique!"%(self.global_key)
            assert self.status in [Status.done, Status.loadeddone, Status.saveddone], \
                "Decision not made. There is nothing to store."
            Decision.stored_decisions[self.global_key] = self.value
            self.status = Status.saveddone
            self.logger.info("Stored decision '%s' with value: %s", self.global_key, self.value)

    def _inner_decide(self, collect):
        """Trys to find a dicison on given input and returns value"""

        self.status = Status.open

        if self.global_key:
            self.logger.warning("Recieved None or invalid value for '%s'", self.global_key)

        if collect:
            Decision.collection.append(self)
            self.logger.debug("Added decision for later processing.")
        else:
            # instant user input
            options = [Decision.CANCLE]
            if self.allow_skip:
                options.append(Decision.SKIP)
            result = self.user_input(options)
            self.status = Status.done
            return result

    def decide(self):
        """Decide by user input"""

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

        if not self.collect:
            return #Nothing to post to
        assert not self.status == Status.open
        self.output[self.dict_key] = self.value
        if not self.status == Status.skipped:
            self.inner_save()

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
        while True:
            raw_value = input("%s: "%(self.question))
            if raw_value == Decision.SKIP and Decision.SKIP in options:
                self.skip()
                return value
            if raw_value == Decision.SKIPALL and Decision.SKIPALL in options:
                self.skip()
                raise DecisionSkipAll
            if raw_value == Decision.CANCLE and Decision.CANCLE in options:
                raise DecisionCancle

            value = self.parse_input(raw_value)
            if self.check(value):
                break
            else:
                print("'%s' is no valid input! Try again."%(raw_value))
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

class BoolDecision(Decision):
    """Accepts input convertable as bool"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, check_func=self.check_bool, **kwargs)

    @staticmethod
    def check_bool(value):
        if value is True or value is False:
            return True
        else:
            return False

    def parse_input(self, raw_input):
        """Convert input to bool"""

        inp = raw_input.lower()
        if inp in ["y", "yes", "ja", "j", "1"]:
            return True
        if inp in ["n", "no", "nein", "n", "0"]:
            return False
        return None

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
