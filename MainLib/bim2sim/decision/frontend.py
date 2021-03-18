import logging

from ..decision import BoolDecision, RealDecision, ListDecision, StringDecision, GuidDecision


class FrontEnd:
    """Basic FrontEnd for decision solving"""

    def __init__(self):
        self.logger = logging.getLogger(__name__ + '.DecisonFrontend')

    def solve(self, decision):
        raise NotImplementedError

    def solve_collection(self, collection):
        raise NotImplementedError

    def get_question(self, decision):
        return decision.get_question()

    def get_body(self, decision):
        return decision.get_body()

    def get_options(self, decision):
        return decision.get_options()

    def validate(self, decision, value):
        return decision.validate(value)

    def shutdown(self, success):
        """Shut down frontend"""
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
            raw_value = set(raw_input)
        except Exception:
            raise NotImplementedError("Parsing guid not implemented.")
        return raw_value