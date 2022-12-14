"""
Common logging tools for all parts of the project.
"""

import logging
import sys

from . import util


class LoggerLazyStatic:
    @staticmethod
    def inst_once(func):
        def wrapper(self, *args, **kwargs):
            if self.inner is None:
                self.inner = LoggerFactory.get_logger(
                    *self.inst_args, **self.inst_kwargs
                )
            func(self, self.inner, *args, **kwargs)

        return wrapper

    def __init__(self, *args, **kwargs):
        self.inst_args = args
        self.inst_kwargs = kwargs
        self.inner = None

    @inst_once
    def debug(self, inst, *args, **kwargs):
        inst.debug(*args, **kwargs)

    @inst_once
    def info(self, inst, *args, **kwargs):
        print(inst)
        inst.info(*args, **kwargs)

    @inst_once
    def warning(self, inst, *args, **kwargs):
        inst.warning(*args, **kwargs)

    @inst_once
    def error(self, inst, *args, **kwargs):
        inst.error(*args, **kwargs)

    @inst_once
    def critical(self, inst, *args, **kwargs):
        inst.critical(*args, **kwargs)


class LoggerFactory:
    """
    Factory class for logger instances that will be each be configured
    accoriding to a preliminary factory configuration.
    """

    verbose = False
    logfile = None
    debug = False
    testing = False

    @classmethod
    def configure_logger(cls, verbose, logfile, debug):
        """
        Configure the LoggerFactory class.

        All future logger instances returned by get_logger will reflect this
        configuration, until called again.

        Params:
            verbose: Whether to send log output to stdout too.
            logfile: Path to logfile where log should be writte. File is appended to.
            debug: Whether to enable debug messages.
        """

        cls.verbose = verbose
        cls.logfile = logfile
        cls.debug = debug

    @classmethod
    def configure_test_logger(cls):
        """
        Configure the LoggerFactory for testing.

        All future logger instances will print nothing to files.
        """

        cls.logfile = "TEST_LOGFILE"
        cls.testing = True

    @classmethod
    def get_logger(cls, prefix):
        """
        Return a logger instance that will log using the specified prefix.

        This logger instance will be configured according to the current
        LoggerFactory class configuration.
        """

        if cls.logfile is None:
            util.exit_critical_bare(
                "LoggerFactory not configured with logfile prior to usage!"
            )

        logger = logging.getLogger(prefix)
        logger.setLevel(logging.DEBUG if cls.debug else logging.INFO)

        # Don't add any handlers to logger if configured for testing.
        if cls.testing:
            return logger

        logfile_handler = logging.FileHandler(cls.logfile)
        logfile_handler.setLevel(logging.DEBUG)

        logfile_format = logging.Formatter(
            "%(name)s -> %(levelname)s - %(asctime)s: %(message)s"
        )
        logfile_handler.setFormatter(logfile_format)

        if cls.verbose:
            stdout_handler = logging.StreamHandler(sys.stdout)
            logfile_handler.setLevel(logging.DEBUG)
            stdout_handler.setFormatter(logfile_format)
            logger.addHandler(stdout_handler)

        logger.addHandler(logfile_handler)
        return logger
