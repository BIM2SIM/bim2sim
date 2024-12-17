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

#
# def default_logging_setup(
#         verbose=False,
#         prj_log_path: Path = None,
#         thread_name=None
# ):
#     """Setup for logging module
#
#     This creates the following:
#     * the general logger with name bim2sim as default logger
#     * the file output file bim2sim.log where the logs are stored
#     * the logger quality_logger which stores all information about the quality
#     of existing information of the BIM model
#     """
#     general_logger = logging.getLogger('bim2sim')
#     handlers = []
#
#     if verbose:
#         general_log_stream_handler = logging.StreamHandler()
#         general_log_stream_handler.setFormatter(dev_formatter)
#         general_log_stream_handler.addFilter(AudienceFilter(audience=None))
#         if thread_name:
#             general_log_stream_handler.addFilter(ThreadLogFilter(thread_name))
#         general_logger.addHandler(general_log_stream_handler)
#         handlers.append(general_log_stream_handler)
#
#     if prj_log_path is not None:
#         handlers = add_file_handler(
#             prj_log_path, handlers, thread_name, general_logger)
#
#     quality_logger = logging.getLogger('bim2sim.QualityReport')
#     quality_logger.propagate = False
#     quality_handler = logging.FileHandler(
#         Path(prj_log_path / "IFCQualityReport.log"))
#     quality_handler.addFilter(ThreadLogFilter(thread_name))
#     quality_handler.setFormatter(quality_formatter)
#     quality_logger.addHandler(quality_handler)
#     handlers.append(quality_handler)
#
#     general_logger.setLevel(logging.DEBUG if verbose else logging.INFO)
#     return handlers


class BufferedHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self.buffer = []

    def emit(self, record):
        self.buffer.append(record)

    def flush_buffer(self, file_handler):
        for record in self.buffer:
            file_handler.emit(record)
        self.buffer.clear()


def initial_logging_setup():
    general_logger = logging.getLogger('bim2sim')
    general_logger.setLevel(logging.INFO)
    general_log_stream_handler = logging.StreamHandler()
    general_log_stream_handler.setFormatter(dev_formatter)
    # TODO do we make this only available for users?
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
    """Setup for logging module
    # TODO
    This creates the following:
    * the general logger with name bim2sim as default logger
    * the file output file bim2sim.log where the logs are stored
    * the logger quality_logger which stores all information about the quality
    of existing information of the BIM model
    """
    # get general_logger from initial_logging_setup
    general_logger = logging.getLogger('bim2sim')

    # TODO do we deal with verbose?

    # general_logger.setLevel(logging.DEBUG if verbose else logging.INFO)
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

    # TODO maybe add a user_handler as well based on set_user_logging_handler
    # from project.py

    # set thread log filter
    thread_log_filter = ThreadLogFilter(prj.thread_name)
    for handler in handlers:
        handler.addFilter(thread_log_filter)

    return handlers, [thread_log_filter]


# def add_file_handlers(
#         prj_log_path: Path,
#         handlers: List,
#         thread_name: str,
#         general_logger: logging.Logger):
#     """Adds a file handler to the logger with specific filters and formatting.
#
#     This function creates and configures a file handler for logging, adding it
#      to the specified logger. This is used as with project FoderStructure
#      initialization we already want logging but don't have a project directory
#      and therefore no place to store the log file
#
#     Args:
#         prj_log_path: Path object representing the directory where log file
#          will be created.
#         handlers: List of existing handlers to which the new handler will
#          be appended.
#         thread_name: Optional thread name for thread-specific filtering.
#          If None, no thread filter will be applied.
#         general_logger: Logger instance to which the file handler will be
#          added.
#
#     Returns:
#         List[logging.Handler]: Updated list of handlers including the newly
#          added file handler.
#     """
#     log_name = "bim2sim.log"
#     general_log_path = prj_log_path / log_name
#     general_log_file_handler = logging.FileHandler(general_log_path)
#     general_log_file_handler.setFormatter(dev_formatter)
#     general_log_file_handler.addFilter(AudienceFilter(audience=None))
#     if thread_name:
#         general_log_file_handler.addFilter(ThreadLogFilter(thread_name))
#     general_logger.addHandler(general_log_file_handler)
#     handlers.append(general_log_file_handler)
#     return handlers



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
