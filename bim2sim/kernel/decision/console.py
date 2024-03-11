"""Decision handling via console."""

import re

from bim2sim.kernel.decision import Decision, BoolDecision, ListDecision, \
    DecisionBunch
from bim2sim.kernel.decision import DecisionCancel, DecisionSkip, DecisionSkipAll
from bim2sim.kernel.decision.decisionhandler import DecisionHandler


class ConsoleDecisionHandler(DecisionHandler):
    """DecisionHandler to user with an interactive console."""

    @staticmethod
    def get_input_txt(decision):
        txt = 'Enter value: '
        if isinstance(decision, ListDecision):
            if not decision.live_search:
                txt = 'Enter key: '
            else:
                txt = 'Enter key or search words: '

        return txt

    @staticmethod
    def get_default_txt(decision):
        if decision.default is not None:
            return f"default={decision.default} (leave blank to use default)"
        else:
            return ''

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
            body_txt += format_str.format(key=str(key), label=str(label),
                                          value=str(value))

        return body_txt

    @staticmethod
    def collection_progress(collection):
        total = len(collection)
        for i, decision in enumerate(collection):
            yield decision, "[Decision {}/{}]".format(i + 1, total)

    def get_answers_for_bunch(self, bunch: DecisionBunch) -> list:
        answers = []
        if not bunch:
            return answers

        skip_all = False
        extra_options = []
        if all([d.allow_skip for d in bunch]):
            extra_options.append(Decision.SKIPALL)

        for decision, progress in self.collection_progress(bunch):
            answer = None
            if skip_all and decision.allow_skip:
                # decision.skip()
                pass
            else:
                if skip_all:
                    self.logger.info("Decision can not be skipped")
                try:
                    answer = self.user_input(decision,
                                             extra_options=extra_options,
                                             progress=progress)
                except DecisionSkip:
                    # decision.skip()
                    pass
                except DecisionSkipAll:
                    skip_all = True
                    self.logger.info("Skipping remaining decisions")
                except DecisionCancel as ex:
                    self.logger.info("Canceling decisions")
                    raise
            answers.append(answer)
        return answers

    # TODO: based on decision type
    # TODO: merge from element_filter_by_text
    def user_input(self, decision, extra_options=None, progress=''):

        question = self.get_question(decision)
        identifier = decision.console_identifier
        options = self.get_options(decision)
        if extra_options:
            options = options + extra_options
        options_txt = self.get_options_txt(options)
        default = self.get_default_txt(decision)
        body = self.get_body(decision) if isinstance(decision, ListDecision) \
            else None
        input_txt = self.get_input_txt(decision)
        if progress:
            progress += ' '

        print(progress, end='')
        print(question)
        if identifier:
            print(identifier)
        if isinstance(decision, ListDecision) and decision.live_search:
            print("enter 'reset' to start search again")
            print("enter 'back' to return to last search")
        print(options_txt + ' ' + default)
        if body:
            print(self.get_body_txt(body))

        max_attempts = 10
        attempt = 0

        if isinstance(decision, ListDecision) and decision.live_search:
            value = self.user_input_live(decision, input_txt, options)
        else:
            while True:
                raw_value = input(input_txt)
                if raw_value.lower() == Decision.SKIP.lower() and Decision.SKIP in options:
                    raise DecisionSkip
                    # decision.skip()
                    # return None
                if raw_value.lower() == Decision.SKIPALL.lower() and Decision.SKIPALL in options:
                    # decision.skip()
                    raise DecisionSkipAll
                if raw_value.lower() == Decision.CANCEL.lower() and Decision.CANCEL in options:
                    raise DecisionCancel

                if not raw_value and decision.default is not None:
                    return decision.default

                value = self.parse(decision, raw_value)
                if self.validate(decision, value):
                    break
                else:
                    if attempt <= max_attempts:
                        if attempt == max_attempts:
                            print("Last try before auto Cancel!")
                        print(
                            f"'{raw_value}' (interpreted as {value}) is no valid input! Try again.")
                    else:
                        raise DecisionCancel(
                            "Too many invalid attempts. Canceling input.")
                attempt += 1

        return value

    def user_input_live(self, decision, input_txt, options):
        last_searches = []

        max_attempts = 10
        attempt = 0

        original_options = list(decision.items)
        new_options = decision.items
        while True:
            searches = ' + '.join([i[0] for i in last_searches]) + ' +' \
                if len(last_searches) > 0 else ''
            raw_value = input(input_txt + searches)

            if raw_value.lower() == Decision.SKIP.lower() and Decision.SKIP in options:
                raise DecisionSkip
            if raw_value.lower() == Decision.SKIPALL.lower() and Decision.SKIPALL in options:
                raise DecisionSkipAll
            if raw_value.lower() == Decision.CANCEL.lower() and Decision.CANCEL in options:
                raise DecisionCancel

            value = self.parse(decision, raw_value)
            if value:
                if self.validate(decision, value):
                    break
                else:
                    if attempt <= max_attempts:
                        if attempt == max_attempts:
                            print("Last try before auto Cancel!")
                        print(
                            f"'{raw_value}' (interpreted as {value}) is no valid input! Try again.")
                    else:
                        raise DecisionCancel(
                            "Too many invalid attempts. Canceling input.")
                attempt += 1
            else:
                if raw_value.lower() == 'none':  # cancel search option
                    break
                elif raw_value.lower() == 'back' and len(last_searches) > 1:
                    del last_searches[-1]
                    new_options = last_searches[-1][1]
                elif raw_value.lower() == 'reset' or \
                        (raw_value.lower() == 'back' and len(
                            last_searches) <= 1):
                    last_searches = []
                    new_options = original_options
                else:
                    new_options = self.get_matches_list(raw_value, new_options)
                    if len(new_options) == 1:
                        value = new_options[0]
                        break
                    elif len(new_options) == 0:
                        print('No options found for %s' % raw_value)
                        if len(last_searches) == 0:
                            new_options = original_options
                        else:
                            new_options = last_searches[-1][1]
                    else:
                        last_searches.append([raw_value, new_options])
                decision.items = new_options
                options_txt = self.get_options_txt(options)
                default = self.get_default_txt(decision)
                body = decision.get_body()
                body_txt = self.get_body_txt(body)
                print(decision.question)
                print(options_txt + ' ' + default)
                print(body_txt)

        return value

    @staticmethod
    def get_matches_list(search_words: str, search_list: list) -> list:
        """get patterns for a search name, and get afterwards the related
        elements from list that matches the search"""

        search_ref = []
        if search_words in search_list:
            return [search_words]

        if type(search_words) is str:
            pattern_search = search_words.split()

            for i in pattern_search:
                search_ref.append(re.compile('(.*?)%s' % i,
                                             flags=re.IGNORECASE))

        search_options = []
        for ref in search_ref:
            for mat in search_list:
                if ref.match(mat):
                    if mat not in search_options:
                        search_options.append(mat)

        return search_options

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

    @staticmethod
    def parse_string_input(raw_input):
        raw_value = None
        try:
            raw_value = str(raw_input)
        except Exception:
            pass
        return raw_value

    @staticmethod
    def parse_guid_input(raw_input):
        raw_value = None
        try:
            parts = str(raw_input).replace(',', ' ').split(' ')
            raw_value = {guid for guid in parts if guid}
        except Exception:
            pass
        return raw_value
