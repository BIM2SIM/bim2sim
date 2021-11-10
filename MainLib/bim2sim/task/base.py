import inspect
import logging
from typing import Generator, Tuple

from bim2sim.decision import DecisionBunch


class TaskFailed(Exception):
    pass


class ITask:
    """Interactive Task"""

    reads: Tuple[str] = tuple()
    touches: Tuple[str] = tuple()
    final = False
    single_use = True

    def __init__(self):
        self.name = self.__class__.__name__
        self.logger = logging.getLogger("%s.%s" % (__name__, self.name))
        self.paths = None
        self.made_decisions = DecisionBunch()

    def run(self, workflow, **kwargs):
        """Run task."""
        raise NotImplementedError

    @classmethod
    def requirements_met(cls, state, history):
        if cls.single_use:
            for task in history:
                if task.__class__ is cls:
                    return False
        # uses_ok = cls not in history if cls.single_use else True
        return all((r in state for r in cls.reads))

    def __repr__(self):
        return "<Task (%s)>" % self.name


class Playground:
    """Playground for executing ITasks"""

    def __init__(self, workflow, paths):
        self.paths = paths
        self.state = {}
        self.workflow = workflow
        self.history = []
        self.logger = logging.getLogger("Playground")
        self.made_decisions = DecisionBunch()

    @staticmethod
    def all_tasks():
        """Returns list of all tasks"""
        return [task for task in ITask.__subclasses__()]  # TODO: from workflow?

    def available_tasks(self):
        """Returns list of available tasks"""
        return [task for task in self.all_tasks() if task.requirements_met(self.state, self.history)]

    def run_task(self, task: ITask) -> Generator[DecisionBunch, None, None]:
        """Generator executing task with arguments specified in task.reads."""
        if not task.requirements_met(self.state, self.history):
            raise AssertionError("%s requirements not met." % task)

        self.logger.info("Starting Task '%s'", task)
        read_state = {k: self.state[k] for k in task.reads}
        try:
            task.paths = self.paths
            task.made_decisions = self.made_decisions
            if inspect.isgeneratorfunction(task.run):
                result = yield from task.run(self.workflow, **read_state)
            else:
                # no decisions
                result = task.run(self.workflow, **read_state)
        except Exception as ex:
            self.logger.exception("Task '%s' failed!", task)
            raise TaskFailed(str(task))
        else:
            self.logger.info("Successfully finished Task '%s'", task)

        if task.touches == '__reset__':
            # special case
            self.state.clear()
            self.history.clear()
        else:
            # normal case
            n_res = len(result) if result is not None else 0
            if len(task.touches) != n_res:
                raise TaskFailed("Mismatch in '%s' result. Required items: %d (%s)" % (task, n_res, task.touches))

            # assign results to state
            if n_res:
                for key, sub_state in zip(task.touches, result):
                    self.state[key] = sub_state

        self.history.append(task)
        self.logger.info("%s done", task)
