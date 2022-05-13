import logging

IFC_QUALITY = 'qs'
USER = 'user'

ifc_quality = {'audience': IFC_QUALITY}
user = {'audience': USER}

quality_formatter = logging.Formatter('QS|[%(levelname)s] %(name)s: %(message)s')
user_formatter = logging.Formatter('user|[%(levelname)s] %(name)s: %(message)s')
dev_formatter = logging.Formatter('dev|[%(levelname)s] %(name)s: %(message)s')

# TODO: docu how to log bim2sim. eg. logging in django -> rotatingFileHandler for dev
# TODO: no general file logging outside projects (docu how)
# TODO: User feedback stream
# TODO: check log calls
# TODO: formatter: dev: time etc.
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


def get_quality_logger(name):
    return logging.LoggerAdapter(logging.getLogger(name), ifc_quality)


def get_user_logger(name):
    return logging.LoggerAdapter(logging.getLogger(name), user)


def logging_setup(verbose=False):
    """Setup for logging module"""
    logger = logging.getLogger('bim2sim')
    default_logger_setup(logger, verbose)
    quality_logger_setup()

    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # silence matplotlib
    # matlog = logging.getLogger('matplotlib')
    # matlog.level = logging.INFO

    logger.debug("Logging setup done.")


def default_logger_setup(logger, verbose):
    log_filter = AudienceFilter(audience=None)

    if verbose:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(dev_formatter)
        stream_handler.addFilter(log_filter)
        logger.addHandler(stream_handler)

    file_handler = logging.FileHandler("bim2sim.log")
    file_handler.setFormatter(dev_formatter)
    file_handler.addFilter(log_filter)
    logger.addHandler(file_handler)


def quality_logger_setup():
    quality_logger = logging.getLogger('bim2sim.QualityReport')
    quality_logger.propagate = False


if __name__ == '__main__':
    logging_setup()

    logger = logging.getLogger(__name__)
    qs_logger = get_quality_logger('bim2sim.QualityReport')

    logger.debug('bla')
    qs_logger.debug('qs bla')
    logger.info('info')
    qs_logger.info('qs info')
    logger.warning('warn')
    qs_logger.warning('qs warn')
    logger.error('error')
    qs_logger.error('qs error')
