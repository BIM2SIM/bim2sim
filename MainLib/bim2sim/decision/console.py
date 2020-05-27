from ..decision import Decision, BoolDecision, RealDecision, ListDecision
from ..decision import DecisionCancle, DecisionSkip, DecisionSkipAll, PendingDecisionError, DecisionException
from .frontend import FrontEnd


class ConsoleFrontEnd(FrontEnd):

    @staticmethod
    def get_input_txt(decision):
        txt = 'Enter value: '
        if isinstance(decision, ListDecision):
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
        try:
            decision.value = self.user_input(decision)
        except DecisionSkip:
            decision.skip()
        except DecisionCancle as ex:
            self.logger.info("Canceling decisions")
            raise
        return

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

    def parse(self, decision, raw_answer):
        if isinstance(decision, BoolDecision):
            return self.parse_bool_input(raw_answer)
        elif isinstance(decision, RealDecision):
            return self.parse_real_input(raw_answer, decision.unit)
        elif isinstance(decision, ListDecision):
            return self.parse_list_input(raw_answer, decision.items)

    @staticmethod
    def parse_real_input(raw_input, unit=None):
        """Convert input to float"""

        try:
            if unit:
                value = float(raw_input) * unit
            else:
                value = float(raw_input)
        except:
            value = None
        return value

    @staticmethod
    def parse_bool_input(raw_input):
        """Convert input to bool"""

        inp = raw_input.lower()
        if inp in BoolDecision.POSITIVES:
            return True
        if inp in BoolDecision.NEGATIVES:
            return False
        return None

    @staticmethod
    def parse_list_input(raw_input, items):
        raw_value = None
        try:
            index = int(raw_input)
            raw_value = items[index]
        except Exception:
            pass

        return raw_value

