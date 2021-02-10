
import os
import logging
import json

from bim2sim.kernel import ifc2python


class TaskFailed(Exception): pass


class Task:
    """Base class for single Workload blocks"""
    saveable = False

    def __init__(self):
        self.name = self.__class__.__name__
        self.logger = logging.getLogger("%s.%s"%(__name__, self.name))

    def __repr__(self):
        return "<Workflow (%s)>"%(self.name)

    @staticmethod
    def log(func):
        """Decorator for logging of entering and leaving method"""
        def wrapper(*args, **kwargs):
            self = args[0]
            self.logger.info("Started %s ...", self.name)
            res = func(*args, **kwargs)
            self.logger.info("Done %s."%(self.name))
            return res
        return wrapper

    def run(self, task, *args, **kwargs):
        """Run job"""
        raise NotImplementedError

    def serialize(self):
        """Returns state of this Workflow instance as string"""
        raise NotImplementedError("%s has not implemented serialize()"%(self.name))

    def deserialize(self, data):
        """Sets state of this Workflow instance from data string"""
        raise NotImplementedError("%s has not implemented deserialize()"%(self.name))

    def get_arg_hash(self):
        """Returns hash value of arguments.

        Userd to compare for equality of arguments on saving and loading."""
        raise NotImplementedError("%s has not implemented get_arg_hash()"%(self.name))

    def save(self, path):
        """Saves state of this Workflow instance to filesystem"""
        if not self.__class__.saveable:
            self.logger.debug("Workflow %s is not saveable", self.name)
            return False
        arg_hash = self.get_arg_hash()
        data = self.serialize()
        with open(os.path.join(path, self.name + '.json'), 'w') as file:
            json.dump(dict(hash=arg_hash, data=data), file, indent=2)
        return True

    def load(self, path):
        """Sets state of this Workflow instance from filesystem"""
        if not self.__class__.saveable:
            self.logger.debug("Workflow %s is not load/saveable", self.name)
            return False
        arg_hash = self.get_arg_hash()
        try:
            with open(os.path.join(path, self.name + '.json'), 'r') as file:
                content = json.load(file)
        except IOError as ex:
            self.logger.error("Failed to load (%s)", ex)
            return False
        except json.JSONDecodeError as ex:
            self.logger.error("Failed to decode (%s)", ex)
            return False
        if arg_hash != content.get('hash'):
            return False
        data = content.get('data')
        self.deserialize(data)
        return True


class ITask(Task):
    """Interactive Task"""

    reads = tuple()
    touches = tuple()
    final = False
    single_use = True

    def run(self, workflow, **kwargs):
        pass

    @classmethod
    def requirements_met(cls, state, history):
        if cls.single_use:
            for task in history:
                if task.__class__ is cls:
                    return False
        # uses_ok = cls not in history if cls.single_use else True
        return all((r in state for r in cls.reads))


class Playground:
    """Playground for executing ITasks"""

    def __init__(self, workflow=None):
        self.state = {}
        self.workflow = workflow
        self.history = []
        self.logger = logging.getLogger("Playground")

    @staticmethod
    def all_tasks():
        """Returns list of all tasks"""
        return [task for task in ITask.__subclasses__()]  # TODO: from workflow?

    def available_tasks(self):
        """Returns list of available tasks"""
        return [task for task in self.all_tasks() if task.requirements_met(self.state, self.history)]

    def run_task(self, task):
        """Execute task with arguments specified in task.reads"""
        if not task.requirements_met(self.state, self.history):
            raise AssertionError("%s requirements not met." % task)

        read_state = {k: self.state[k] for k in task.reads}
        try:
            result = task.run(self.workflow, **read_state)
        except Exception as ex:
            self.logger.exception("Task '%s' failed!", task)
            raise TaskFailed(str(task))

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
