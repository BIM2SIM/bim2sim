"""DecisionHandlers prepare decisions to allow easy answering.

DecisionHandlers are designed to handle DecisionBunch yielding generators.

Example:
    >>> def de_gen():
    ...     decision = StringDecision("Whats your name?")
    ...     yield DecisionBunch([decision])
    ...     print(decision.value)

    >>> handler = DebugDecisionHandler(["R2D2"])

    >>> # version 1: no further interaction needed
    >>> handler.handle(de_gen())
    "R2D2"

    >>> # version 2: iterate over decisions and answers and apply them on your own
    >>> for decision, answer in handler.decision_answer_mapping(de_gen()):
    ...     decision.value = answer
    "R2D2"

"""
import logging
from abc import ABCMeta
from typing import Iterable, Generator, Any

from bim2sim.kernel.decision import BoolDecision, RealDecision, ListDecision, \
    StringDecision, \
    GuidDecision, DecisionBunch


# TODO: contextmanager (shutdown) or how to make sure shutdown is called?
class DecisionHandler(metaclass=ABCMeta):
    """Basic DecisionHandler for decision solving"""

    def __init__(self):
        self.logger = logging.getLogger(__name__ + '.DecisionHandler')
        self.return_value = None

    def handle(self, decision_gen: Generator[DecisionBunch, None, Any], saved_decisions: dict = None):
        """Run the generator and apply answers to occurring decisions."""
        for decision, answer in self.decision_answer_mapping(decision_gen):
            decision.value = answer
        return self.return_value

    def get_answers_for_bunch(self, bunch: DecisionBunch) -> list:
        """Collect and return answers for given decision bunch."""
        raise NotImplementedError

    def decision_answer_mapping(
            self, decision_generator: Generator[DecisionBunch, None, None]):
        """
        Generator method yielding tuples of decision and answer.

        the return value of decision_generator can be
        obtained from self.return_value
        """
        # We preserve the return value of the generator
        # by using next and StopIteration instead of just iterating
        try:
            while True:
                decision_bunch = next(decision_generator)
                answer_bunch = self.get_answers_for_bunch(decision_bunch)
                yield from zip(decision_bunch, answer_bunch)
        except StopIteration as generator_return:
            self.return_value = generator_return.value

    def get_question(self, decision):
        return decision.get_question()

    def get_body(self, decision):
        return decision.get_body()

    def get_options(self, decision):
        return decision.get_options()

    def validate(self, decision, value):
        return decision.validate(value)

    def shutdown(self, success):
        """Shut down handler"""
        pass

    def parse(self, decision, raw_answer):
        if isinstance(decision, BoolDecision):
            return self.parse_bool_input(raw_answer)
        elif isinstance(decision, RealDecision):
            return self.parse_real_input(raw_answer, decision.unit)
        elif isinstance(decision, ListDecision):
            return self.parse_list_input(raw_answer, decision.items)
        elif isinstance(decision, StringDecision):
            return self.parse_string_input(raw_answer)
        elif isinstance(decision, GuidDecision):
            return self.parse_guid_input(raw_answer)

    @staticmethod
    def parse_real_input(raw_input, unit=None):
        """Convert input to float"""
        if not isinstance(raw_input, float):
            raise NotImplementedError("Parsing real not implemented.")
        try:
            if unit:
                value = raw_input * unit
            else:
                value = raw_input
        except:
            raise NotImplementedError("Parsing real not implemented.")
        return value

    @staticmethod
    def parse_bool_input(raw_input):
        """Convert input to bool"""
        if not isinstance(raw_input, bool):
            raise NotImplementedError("Parsing bool not implemented.")
        return raw_input

    @staticmethod
    def parse_list_input(raw_input, items):
        try:
            raw_value = items[raw_input]
        except Exception:
            raise NotImplementedError("Parsing list index not implemented.")
        return raw_value

    @staticmethod
    def parse_string_input(raw_input):
        try:
            raw_value = str(raw_input)
        except Exception:
            raise NotImplementedError("Parsing string not implemented.")
        return raw_value

    @staticmethod
    def parse_guid_input(raw_input):
        try:
            raw_value = str(raw_input)
        except Exception:
            raise NotImplementedError("Parsing guid not implemented.")
        return raw_value


class DebugDecisionHandler(DecisionHandler):
    """Simply use a predefined list of values as answers."""

    def __init__(self, answers: Iterable):
        super().__init__()
        # turn answers into a generator
        self.answers = (ans for ans in answers)
        self.unused_answers = tuple()

    def get_answers_for_bunch(self, bunch: DecisionBunch) -> list:
        answers = []
        try:
            for decision in bunch:
                answers.append(next(self.answers))
        except StopIteration:
            raise AssertionError(f"Not enough answers provided. First decision with no answer: {decision}")
        return answers

    def decision_answer_mapping(self, *args, **kwargs):
        yield from super().decision_answer_mapping(*args, **kwargs)
        self.unused_answers = tuple(self.answers)
        if self.unused_answers:
            self.logger.warning(f"Following answers were not used: "
                                f"{', '.join(map(str, self.unused_answers))}")
