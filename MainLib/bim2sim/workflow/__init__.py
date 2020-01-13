"""Package containing classes for high level workflow"""

import os
import logging
import json


class Workflow():
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
