"""Module containing the ITask base class an Playground to execute ITasks.

All Tasks should inherit from ITask
"""

import inspect
import logging
from typing import Generator, Tuple, List, Type

from bim2sim import log
from bim2sim.decision import DecisionBunch


class TaskFailed(Exception):
    pass


class ITask:
    """Baseclass for interactive Tasks.

    Args:
        reads: names of the arguments the run() method requires. The arguments
         are outputs from previous tasks
        touches: names that are assigned to the return value tuple of method
         run()
        final: flag that indicates termination of project run after this task
        single_user: flag that indicates if this task can be run multiple times
         in same Playground
    """

    reads: Tuple[str] = tuple()
    touches: Tuple[str] = tuple()
    final = False
    single_use = True

    def __init__(self):
        self.name = self.__class__.__name__
        self.logger = log.get_user_logger("%s.%s" % (__name__, self.name))
        self.paths = None
        self.prj_name = None

    def run(self, workflow, **kwargs):
        """Run task."""
        raise NotImplementedError

    @classmethod
    def requirements_met(cls, state, history) -> bool:
        """Check if all requirements for this task are met.

        Args:
            state: state of playground
            history: history of playground
        """
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

    def __init__(self, workflow, paths, prj_name):
        self.paths = paths
        self.prj_name = prj_name
        self.state = {}
        self.workflow = workflow
        self.history = []
        self.instances = {}
        self.instances_updated = False
        self.logger = logging.getLogger("bim2sim.Playground")

    @staticmethod
    def all_tasks() -> List[Type[ITask]]:
        """Returns list of all tasks"""
        return [task for task in ITask.__subclasses__()]  # TODO: from workflow?

    def available_tasks(self) -> List[Type[ITask]]:
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
            task.prj_name = self.prj_name
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

        # update instances in playground based on task results
        if 'instances' in task.touches:
            indices = [i for i in range(len(task.touches)) if 'instance' in task.touches[i]]
            if len(indices) > 1:
                self.logger.info("Found more than one instance entry in touches"
                                 ", using the last one to update instances")
                index = indices[-1]
            else:
                index = indices[0]
            self.instances = result[index]
            self.instances_updated = True
            self.logger.info("Updated instances based on task results.")
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
