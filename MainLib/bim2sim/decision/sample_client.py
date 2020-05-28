import time
import rpyc

config = {
    'sync_request_timeout': None  # No timeout
}
conn = rpyc.connect('localhost', 18861, config=config)
# conn._config['sync_request_timeout'] = None  # No timeout
conn.root.set_project(3)


def answer_gen(answers=None):
    _answers = answers or [1, False, "y"]
    i = 0
    while True:
        yield _answers[i]
        i += 1
        if i >= len(_answers):
            i = 0


for bunch in conn.root.iter_decisions():
    print(bunch)

    answer = answer_gen()
    for key in bunch:
        decision = bunch[key]
        valid = False
        while not valid:
            time.sleep(1)
            valid = conn.root.answer(key, next(answer))
            print("key: %s valid: %s" % (key, valid))

