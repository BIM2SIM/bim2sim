"""Module containing the ITask base class an Playground to execute ITasks.

All Tasks should inherit from ITask
"""
from __future__ import annotations

import inspect
import logging
from typing import Generator, Tuple, List, Type, TYPE_CHECKING

from bim2sim.kernel import log
from bim2sim.kernel.decision import DecisionBunch

if TYPE_CHECKING:
    from bim2sim import Project


class TaskFailed(Exception):
    pass


class ITask:
    """Baseclass for interactive Tasks.

    Args:
        reads: names of the arguments the run() method requires. The arguments
         are outputs from previous tasks
        touches: names that are assigned to the return value tuple of method
         run()
        final: flag that indicates termination of project run after this tasks
        single_user: flag that indicates if this tasks can be run multiple times
         in same Playground


    """

    reads: Tuple[str] = tuple()
    touches: Tuple[str] = tuple()
    final = False
    single_use = True

    def __init__(self, playground):
        self.name = self.__class__.__name__
        self.logger = log.get_user_logger("%s.%s" % (__name__, self.name))
        self.paths = None
        self.prj_name = None
        self.playground = playground

    def run(self, **kwargs):
        """Run tasks."""
        raise NotImplementedError

    @classmethod
    def requirements_met(cls, state, history) -> bool:
        """Check if all requirements for this tasks are met.

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

    def __init__(self, project: Project):
        self.project = project
        self.sim_settings = project.plugin_cls.sim_settings()
        # Note: Add and set attribute manually (temporary workaround)
        # Overwrites dymola_simulation_pydantic pydantic attribute
        # project.plugin_cls.sim_settings().dymola_simulation_pydantic.value
        setattr(self.sim_settings, project.plugin_cls.sim_settings().dymola_simulation_pydantic.name,
                False)

        self.sim_settings.update_from_config(config=project.config)
        self.state = {}
        self.history = []
        self.elements = {}
        self.elements_updated = False
        self.graph = None
        self.graph_updated = False
        self.logger = logging.getLogger("bim2sim.Playground")

    @staticmethod
    def all_tasks() -> List[Type[ITask]]:
        """Returns list of all tasks"""
        return [task for task in ITask.__subclasses__()]  # TODO: from workflow?

    def available_tasks(self) -> List[Type[ITask]]:
        """Returns list of available tasks"""
        return [task for task in self.all_tasks() if task.requirements_met(self.state, self.history)]

    def run_task(self, task: ITask) -> Generator[DecisionBunch, None, None]:
        """Generator executing tasks with arguments specified in tasks.reads."""
        if not task.requirements_met(self.state, self.history):
            raise AssertionError("%s requirements not met." % task)

        self.logger.info("Starting Task '%s'", task)
        read_state = {k: self.state[k] for k in task.reads}
        try:
            task.paths = self.project.paths
            task.prj_name = self.project.name
            if inspect.isgeneratorfunction(task.run):
                result = yield from task.run(**read_state)
            else:
                # no decisions
                result = task.run(**read_state)
        except Exception as ex:
            self.logger.exception("Task '%s' failed!", task)
            raise TaskFailed(str(task))
        else:
            self.logger.info("Successfully finished Task '%s'", task)

        # update elements in playground based on tasks results
        if 'elements' in task.touches:
            indices = [i for i in range(len(task.touches)) if
                       'element' in task.touches[i]]
            if len(indices) > 1:
                self.logger.info("Found more than one element entry in touches"
                                 ", using the last one to update elements")
                index = indices[-1]
            else:
                index = indices[0]
            self.elements = result[index]
            self.elements_updated = True
            self.logger.info("Updated elements based on tasks results.")

        if 'graph' in task.touches:
            indices = [i for i in range(len(task.touches)) if
                       'graph' in task.touches[i]]
            if len(indices) > 1:
                self.logger.info("Found more than one graph entry in touches"
                                 ", using the last one to update elements")
                index = indices[-1]
            else:
                index = indices[0]
            self.graph = result[index]
            self.graph_updated = True
            self.logger.info("Updated graph based on tasks results.")

        if task.touches == '__reset__':
            # special case
            self.state.clear()
            self.history.clear()
        else:
            # normal case
            n_res = len(result) if result is not None else 0
            if len(task.touches) != n_res:
                raise TaskFailed("Mismatch in '%s' result. Required items: %d (%s). Please make sure that required"
                                 " inputs (reads) are created in previous tasks." % (task, n_res, task.touches))

            # assign results to state
            if n_res:
                for key, sub_state in zip(task.touches, result):
                    self.state[key] = sub_state

        self.history.append(task)
        self.logger.info("%s done", task)

    def update_elements(self, elements):
        """Updates the elements of the current run.

        This only has to be done if you want to update elements manually,
        if a tasks touches elements, they will be updated automatically after
        the tasks is finished.
        """
        self.elements = elements
        self.elements_updated = True
        self.logger.info("Updated elements based on tasks results.")

    def update_graph(self, graph):
        """Updates the graph of the current run.

        This only has to be done if you want to update graph manually,
        if a tasks touches graph, they will be updated automatically after
        the tasks is finished.
        """
        self.graph = graph
        self.graph_updated = True
        self.logger.info("Updated graph based on tasks results.")
