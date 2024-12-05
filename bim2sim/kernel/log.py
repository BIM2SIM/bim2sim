import logging
from pathlib import Path

USER = 'user'

user = {'audience': USER}


# TODO: check log calls
# TODO: fix errors exposed by log messages


class AudienceFilter(logging.Filter):
    def __init__(self, audience, name=''):
        super().__init__(name)
        self.audience = audience

    def filter(self, record: logging.LogRecord) -> bool:
        audience = getattr(record, 'audience', None)
        return audience == self.audience


class ThreadLogFilter(logging.Filter):
    """This filter only show log entries for specified thread name."""

    def __init__(self, thread_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.thread_name = thread_name

    def filter(self, record):
        return record.threadName == self.thread_name


def get_user_logger(name):
    return logging.LoggerAdapter(logging.getLogger(name), user)


def default_logging_setup(verbose=False, prj_log_path: Path = None):
    """Setup for logging module

    This creates the following:
    * the general logger with name bim2sim as default logger
    * the file output file bim2sim.log where the logs are stored
    * the logger quality_logger which stores all information about the quality
    of existing information of the BIM model
    """
    general_logger = logging.getLogger('bim2sim')

    log_filter = AudienceFilter(audience=None)

    if verbose:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(dev_formatter)
        stream_handler.addFilter(log_filter)
        general_logger.addHandler(stream_handler)

    log_name = "bim2sim.log"
    if prj_log_path is not None:
        general_log_path = prj_log_path / log_name
    else:
        general_log_path = log_name
    general_log_handler = logging.FileHandler(general_log_path)
    general_log_handler.setFormatter(dev_formatter)
    general_log_handler.addFilter(log_filter)
    general_logger.addHandler(general_log_handler)

    quality_logger = logging.getLogger('bim2sim.QualityReport')
    quality_logger.propagate = False

    general_logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    general_logger.debug("Default logging setup done.")


class CustomFormatter(logging.Formatter):
    """Custom logging design based on
    https://stackoverflow.com/questions/384076/how-can-i-color-python
    -logging-output"""

    def __init__(self, fmt):
        super().__init__()
        self._fmt = fmt

    def format(self, record):
        grey = "\x1b[37;20m"
        green = "\x1b[32;20m"
        yellow = "\x1b[33;20m"
        red = "\x1b[31;20m"
        bold_red = "\x1b[31;1m"
        reset = "\x1b[0m"
        # format = "[%(levelname)s] %(name)s: %(message)s"

        FORMATS = {
            logging.DEBUG: grey + self._fmt + reset,
            logging.INFO: green + self._fmt + reset,
            logging.WARNING: yellow + self._fmt + reset,
            logging.ERROR: red + self._fmt + reset,
            logging.CRITICAL: bold_red + self._fmt + reset
        }
        log_fmt = FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


quality_formatter = CustomFormatter('[QUALITY-%(levelname)s] %(name)s:'
                                    ' %(message)s')
user_formatter = CustomFormatter('[USER-%(levelname)s]:'
                                 ' %(message)s')
dev_formatter = CustomFormatter('[DEV-%(levelname)s] -'
                                ' %(asctime)s  %(name)s.%(funcName)s:'
                                ' %(message)s')
