""""""

import logging

class Workflow():
    """"""
    saveable = False
    verbose_description = ""

    def __init__(self):
        if not self.__class__.verbose_description:
            self.__class__.verbose_description = self.__class__.__doc__
        self.logger = logging.getLogger("%s.%s"%(__name__, self.__class__.__name__))

    @staticmethod
    def log(func):
        """Decorator for logging of entering and leaving method"""
        def wrapper(*args, **kwargs):
            self = args[0]
            self.logger.info("Started %s ...", self.__class__.__name__)
            if self.verbose_description:
                self.logger.info(self.__class__.verbose_description)
            res = func(*args, **kwargs)
            self.logger.info("Done %s."%(self.__class__.__name__))
            return res
        return wrapper

    def run(self, *args, **kwargs):
        raise NotImplementedError

    def save(self):
        raise NotImplementedError

    def reload(self):
        raise NotImplementedError
