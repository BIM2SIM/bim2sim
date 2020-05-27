import logging
import time
import json

import rpyc
from rpyc.utils.server import OneShotServer

from .frontend import FrontEnd


class DecisionService(rpyc.Service):

    def __init__(self):
        super().__init__()
        self.project_id = None

    def on_connect(self, conn):
        # code that runs when a connection is created
        # (to init the service, if needed)
        print('connection opened')
        pass

    def on_disconnect(self, conn):
        # code that runs after the connection has already closed
        # (to finalize the service, if needed)
        print(self.logs)
        print("Connection lost. Shutting down.")
        exit(2)

    def exposed_log(self, message):
        self.logs.append(message)
        print("Recieved log: ", message)

    def exposed_set_project(self, project_id):
        self.project_id = project_id

    def exposed_iter_decisions(self, n=5):
        for i in range(n):
            time.sleep(1)
            yield i

    def exposed_answer(self, id, value):
        print(id, value)



class ExternalFrontEnd(FrontEnd):

    def __init__(self):
        super().__init__()

        self.id_gen = self._get_id_gen()
        self.pending = {}

        self.server = OneShotServer(DecisionService, port=18861)
        # self.connection = rpyc.connect('localhost', 18861)
        # self.connection.root.log("Connected!")

    def __iter__(self):
        raise StopIteration

    def check_answer(self, answer):

        for key, raw_value in answer.copy().items():
            decision = self.pending.get(key)
            if not decision:
                self.logger.warning("Removed unknown answer (%s) for key %s", answer[key], key)
                del answer[key]
                continue

            value = self.parse(decision, raw_value)
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
            remaining = self.check_answer(answer)
            if not remaining:
                break
        else:
            raise DecisionException("Failed to solve decisions after %d retries", loop + 1)
        return

    @staticmethod
    def _get_id_gen():
        i = 0
        while True:
            i += 1
            yield i

    def to_dict(self, key, decision):

        data = dict(
            id=key,
            question=decision.question,
            options=self.get_options(decision),
            body=json.dumps(self.get_body(decision)),
        )

        return data

    def send(self):
        data = []
        for key, decision in self.pending.items():
            data.append(self.to_dict(key, decision))

        # TODO: request to UI
        serialized = json.dumps(data, indent=2)
        print(serialized)
        # fake data
        # answer = {item['id']: '1' for item in data}
        raw_answer = self.connection.root.new_decision(data)
        answer = json.loads(raw_answer)
        print(answer)
        return answer

