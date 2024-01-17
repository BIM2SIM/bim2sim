
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
