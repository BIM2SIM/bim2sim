import logging


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
