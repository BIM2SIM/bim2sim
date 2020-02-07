"""Managing related"""
import os
import logging
from abc import ABCMeta, abstractmethod

from bim2sim.project import PROJECT, get_config
from bim2sim.decision import Decision, ListDecision
from bim2sim.task.base import Playground


class BIM2SIMManager:
    """Base class of overall bim2sim managing instance"""
    __metaclass__ = ABCMeta

    def __init__(self, workflow):
        self.logger = logging.getLogger(__name__)

        assert PROJECT.is_project_folder(), "PROJECT ist not set correctly!"

        if not os.path.samefile(PROJECT.root, os.getcwd()):
            self.logger.info("Changing working directory to '%s'", PROJECT.root)
            os.chdir(PROJECT.root)
        # self.init_project()
        self.config = get_config()

        # self.workflow = workflow
        self.playground = Playground(workflow)

        Decision.load(PROJECT.decisions)

        self.logger.info("BIM2SIMManager '%s' initialized", self.__class__.__name__)

    def init_project(self):
        """Check project folder and create it if necessary"""
        if not PROJECT.is_project_folder():
            self.logger.info("Creating project folder in '%s'", PROJECT.root)
            PROJECT.create_project_folder()
        else:
            PROJECT.complete_project_folder()

    @abstractmethod
    def run(self):
        """Run the manager"""

    def run_interactive(self):
        """Run manager in interactive mode"""
        while True:
            tasks_classes = {task.__name__: task for task in self.playground.available_tasks()}
            choices = [(name, task.__doc__) for name, task in tasks_classes.items()]
            task_name = ListDecision("What shall we do?", choices=choices).decide()  # TODO savable decision
            task_class = tasks_classes[task_name[0]]
            self.playground.run_task(task_class())
            if task_class.final:
                break

    def run_decision_generator(self):
        self.run()

    def __repr__(self):
        return "<%s>"%(self.__class__.__name__)

    def read_config(self):
        """Read config file"""
        self.config = get_config()

    def save_config(self):
        """Write config file"""
        with open(PROJECT.config, "w") as file:
            self.config.write(file)
