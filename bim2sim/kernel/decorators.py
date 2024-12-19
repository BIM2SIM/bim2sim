
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
