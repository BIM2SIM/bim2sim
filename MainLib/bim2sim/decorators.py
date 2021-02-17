
import logging


def log(name):
    """Decorator for logging of entering and leaving method"""
    logger = logging.getLogger(__name__)
    def log_decorator(func):
        def wrapper(*args, **kwargs):
            logger.info("Started %s ...", name)
            func(*args, **kwargs)
            logger.info("Done %s.", name)
        return wrapper
    return log_decorator


class cached_property(property):
    def __init__(self, func, name=None, doc=None):
        self.__name__ = name or func.__name__
        self.__module__ = func.__module__
        self.__doc__ = doc or func.__doc__
        self.func = func

    def __set__(self, obj, value):
        obj.__dict__[self.__name__] = value

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        value = obj.__dict__.get(self.__name__, None)
        if value is None:
            value = self.func(obj)
            obj.__dict__[self.__name__] = value
        return value


if __name__ == "__main__":

    class Test():

        @cached_property
        def a(self):
            print("calc ...")
            return 42

        @cached_property
        def b(self):
            print("calc2 ...")
            return [1,2,3]


    t = Test()
    print(t.a)
    print(t.a)
    print(t.b)
    print(t.b)
