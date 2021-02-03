import logging
import time
import json
from threading import Thread, Lock
import atexit

import rpyc
from rpyc.utils.server import OneShotServer, ThreadedServer

from ..decision import DecisionException, BoolDecision, RealDecision, ListDecision
from .frontend import FrontEnd


logger = logging.getLogger('bim2sim.communication')
lock = Lock()


class DecisionService(rpyc.Service):

    def __init__(self, answer_func, parse_func):
        super().__init__()
        self.project_id = None
        self.decisions = None
        self.answers = {}
        self._parse = parse_func
        self._answer = answer_func
        self.callback = None
        self.done = False

    def on_connect(self, conn):
        # code that runs when a connection is created
        # (to init the service, if needed)
        logger.info('connection opened')
        pass

    def on_disconnect(self, conn):
        # code that runs after the connection has already closed
        # (to finalize the service, if needed)
        logger.warning("Connection lost. Shutting down.")
        # exit(2)

    def exposed_set_callback(self, func):
        self.callback = func
        logger.info("Callback set")
        self.callback('Callback set')

    def notify_error(self):
        if self.callback:
            self.callback(error=True)

    def notify_finished(self):
        if self.callback:
            self.callback(finished=True)

    @staticmethod
    def reduced(decisions):
        return json.dumps(decisions)

    def exposed_get_decisions(self):
        if self.decisions:
            return self.reduced(self.decisions)
        return 'still working'

    def exposed_answers_done(self):
        """Continue calculation. Returns True if all answers are accepted, False otherwise"""
        with lock:
            if len(self.answers) == len(self.decisions):
                self.done = True
                self.decisions = None
                logger.info("Answers accepted")
                return True
            else:
                logger.info("Answers rejected")
                print(self.decisions)
                print(self.answers)
                return False

    def exposed_answer(self, key, value):
        logger.debug("Received answer %r for decision %s", value, key)
        # print("currend decisions: ", self.decisions)

        try:
            parsed = self._parse(key, value)
        except NotImplementedError:
            logger.error("Failed to parse %r for decision %s", value, key)
            return None
        # print("parsed: %r" % parsed)

        valid = self._answer(key, parsed)
        if valid:
            with lock:
                self.answers[key] = parsed
        # print("currend answers: ", self.answers)
        return valid

    def set_decisions(self, decisions):
        with lock:
            if self.decisions is None:
                self.answers.clear()
                self.decisions = decisions
                self.done = False
                print("Thread received %d decisions" % len(decisions))
            else:
                raise AssertionError("Can't send new decisions while working on old ones")

    def clear(self):
        """clear state of decisions and answers"""
        self.decisions = None
        self.answers.clear()


class CommunicationThread(Thread):

    def __init__(self, service, port=18861, *args, **kwargs):
        super().__init__(*args, **kwargs)
        config = {
            "allow_public_attrs": True,
        }
        # self.server = OneShotServer(service, port=port, protocol_config=config)
        self.server = ThreadedServer(service, port=port, protocol_config=config)

    def run(self) -> None:
        self.server.start()

    def join(self, *args, **kwargs):
        logger.warning("Shutting down frontend communication.")
        self.server.close()
        super().join(*args, **kwargs)


class ExternalFrontEnd(FrontEnd):

    def __init__(self, port=18861):
        super().__init__()

        self.id_gen = self._get_id_gen()
        self.pending = {}

        self.service = DecisionService(self.validate_single_answer, self.parse_answer)
        self.thread = CommunicationThread(self.service, port)

        atexit.register(self.shutdown)

        self.thread.start()

    def parse_answer(self, key, raw_value):
        """parse answer for decision key"""
        decision = self.pending.get(key, None)
        if decision is None:
            return None
        value = self.parse(decision, raw_value)
        return value

    def validate_single_answer(self, key, value):
        """validate answer. Returns True/False or None for invalid keys"""
        decision = self.pending.get(key, None)
        if decision is None:
            return None
        valid = self.validate(decision, value)
        return valid

    def check_answer(self, answer):
        self.logger.info(self.pending)
        for key, raw_value in answer.copy().items():
            decision = self.pending.get(key)
            if not decision:
                self.logger.warning("Removed unknown answer (%s) for key %s", answer[key], key)
                del answer[key]
                continue

            value = raw_value  # already parsed
            if self.validate(decision, value):
                decision.value = value
                del answer[key]
                del self.pending[key]

        if answer:
            self.logger.warning("Unused/invalid answers: %s", answer)
        return answer

    def solve(self, decision):
        return self.solve_collection([decision])

    def solve_collection(self, collection):
        if self.pending:
            raise AssertionError("Solve pending decisions first!")

        for decision in collection:
            self.pending[next(self.id_gen)] = decision

        for loop in range(10):
            answer = self.send()
            self.check_answer(answer)
            if not self.pending:
                break
        else:
            raise DecisionException("Failed to solve decisions after %d retries", loop + 1)
        self.accept()
        return

    @staticmethod
    def _get_id_gen():
        i = 0
        while True:
            i += 1
            yield i

    @staticmethod
    def decision_kind(decision):
        """returns king of decision"""
        if isinstance(decision, BoolDecision):
            return 'bool'
        elif isinstance(decision, RealDecision):
            return 'numeric'
        elif isinstance(decision, ListDecision):
            return 'list'
        else:
            return 'unknown'

    def to_dict(self, key, decision):

        data = dict(
            id=key,
            question=decision.question,
            options=self.get_options(decision),
            body=json.dumps(self.get_body(decision)),
            kind=self.decision_kind(decision),
            related=list(decision.related or []),
            context=list(decision.context or [])
        )

        return data

    def send(self):

        data = {}
        for key, decision in self.pending.items():
            data[key] = self.to_dict(key, decision)

        self.service.set_decisions(data)

        # print("Wait for answers", end='')
        while not self.service.done:
            # wait until all decisions are solved
            # print('.', end='')
            time.sleep(0.2)
            # check for errors on worker Thread
            if not self.thread.is_alive():
                self.logger.error("CommunicationThread died. Terminating ...")
                exit(-1)

        if not len(self.service.answers) >= len(self.pending):
            raise AssertionError("Not enough answers provided")

        return self.service.answers.copy()

    def accept(self):
        """Accept answers from thread and reset it"""
        self.logger.info("Answer accepted")
        self.service.clear()

    def shutdown(self, success):
        self.logger.info("Shutting down external Frontend")
        if success:
            self.service.notify_finished()
        else:
            self.service.notify_error()
        self.thread.join(.5)
