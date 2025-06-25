import logging
from pathlib import Path
from typing import List, Tuple

# from bim2sim.project import Project

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


class BufferedHandler(logging.Handler):
    """Handler to buffer messages and don't loose them."""
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self.buffer = []

    def emit(self, record):
        self.buffer.append(record)

    def flush_buffer(self, file_handler):
        for record in self.buffer:
            file_handler.emit(record)
        self.buffer.clear()


def initial_logging_setup(level=logging.DEBUG):
    """Initial setup before project folder exists.

    This is the first of the two-step logging setup. It makes sure that logging
    messages before project folder creation are still prompted to stream
    handler and saved to BufferHandler to get complete log files later.
    """
    general_logger = logging.getLogger('bim2sim', )
    general_logger.setLevel(level)
    general_log_stream_handler = logging.StreamHandler()
    general_log_stream_handler.setFormatter(dev_formatter)
    # general_log_stream_handler.addFilter(AudienceFilter(USER))
    general_logger.addHandler(general_log_stream_handler)

    # buffered handler to maintain messages that are logged before project
    # folder and therefore storage place for file handler exists
    buffered_handler = BufferedHandler()
    general_logger.addHandler(buffered_handler)

    return general_logger


def project_logging_setup(
        prj=None,
) -> Tuple[List[logging.Handler],  List[ThreadLogFilter]]:
    """Setup project logging

    This is the second step of the two-step logging setup. After project folder
    creation this step adds completes the setup and adds the filder handlers
    that store the logs.

    This creates the following:
    * the file output file bim2sim.log where the logs are stored
    * the logger quality_logger which stores all information about the quality
    of existing information of the BIM model. This logger is only on file to
    keep the logs cleaner
    """
    # get general_logger from initial_logging_setup
    general_logger = logging.getLogger('bim2sim')

    prj_log_path = prj.paths.log

    # get existing stream handler and buffer handler from initial_logging_setup
    handlers = []
    general_log_stream_handler = None
    buffered_handler = None
    for handler in general_logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            general_log_stream_handler = handler
            handlers.append(general_log_stream_handler)
        if isinstance(handler, BufferedHandler):
            buffered_handler = handler
            handlers.append(buffered_handler)

    # add file handler for general log and flush logs from buffer log to keep
    # all log messages between FolderStructure creation and project init
    general_log_file_handler = logging.FileHandler(
        prj_log_path / 'bim2sim.log')
    general_log_file_handler.setFormatter(dev_formatter)
    general_log_file_handler.addFilter(AudienceFilter(audience=None))
    general_logger.addHandler(general_log_file_handler)
    if buffered_handler:
        buffered_handler.flush_buffer(general_log_file_handler)
    handlers.append(general_log_file_handler)

    # add quality logger with stream and file handler
    quality_logger = logging.getLogger('bim2sim.QualityReport')
    # do not propagate messages to main bim2sim logger to keep logs cleaner
    quality_logger.propagate = False
    quality_handler = logging.FileHandler(
        Path(prj_log_path / "IFCQualityReport.log"))
    quality_handler.setFormatter(quality_formatter)
    quality_logger.addHandler(quality_handler)
    handlers.append(quality_handler)

    # set thread log filter
    thread_log_filter = ThreadLogFilter(prj.thread_name)
    for handler in handlers:
        handler.addFilter(thread_log_filter)

    return handlers, [thread_log_filter]


def teardown_loggers():
    """Closes and removes all handlers from loggers in the 'bim2sim' hierarchy.

    Iterates through all existing loggers and cleans up those that start
    with 'bim2sim'.
    For each matching logger, all handlers are properly closed and removed.
    Errors during file handler closure (e.g., due to already deleted l
    og files) are silently ignored.

    """
    # Get all loggers from logging manager hierarchy
    logger_dict = logging.Logger.manager.loggerDict

    # Iterate through all loggers that start with 'bim2sim'
    for logger_name, logger_instance in logger_dict.items():
        if isinstance(logger_instance,
                      logging.Logger) and logger_name.startswith('bim2sim'):
            for handler in logger_instance.handlers[:]:
                try:
                    handler.close()
                except (PermissionError, FileNotFoundError):
                    pass
                logger_instance.removeHandler(handler)


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
