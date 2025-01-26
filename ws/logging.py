#! /usr/bin/env python3

# TODO:
#   global docstring
#       document how the ws module uses logging - Logger names, verbosity levels etc.
#       document how scripts should use the ws.logging submodule
#   check if stdout is actually attached to terminal

import collections
import logging

__all__ = ["setTerminalLogging", "set_argparser", "init"]

LOG_LEVELS = collections.OrderedDict((
    ("debug", logging.DEBUG),
    ("info", logging.INFO),
    ("warning", logging.WARNING),
    ("error", logging.ERROR),
    ("critical", logging.CRITICAL),
))

def setTerminalLogging():
    # create console handler and set level
    handler = logging.StreamHandler()

    # create formatter
    try:
        import colorlog
        # TODO: make this configurable
        formatter = colorlog.ColoredFormatter(
            "{log_color}{levelname:8}{reset} {message_log_color}{message}",
            datefmt=None,
            reset=True,
            log_colors={
                "DEBUG":    "cyan",
                "INFO":     "green",
                "WARNING":  "yellow",
                "ERROR":    "bold_red",
                "CRITICAL": "bold_red",
            },
            secondary_log_colors={
                "message": {
                    "ERROR":    "bold_white",
                    "CRITICAL": "bold_white",
                },
            },
            style='{'
        )
    except ImportError:
        formatter = logging.Formatter("{levelname:8} {message}", style="{")
    handler.setFormatter(formatter)

    # add the handler to the root logger
    logger = logging.getLogger()
    logger.addHandler(handler)

    return logger

def set_argparser(argparser):
    """
    Add arguments for configuring global logging values to an instance of
    :py:class:`argparse.ArgumentParser`.

    This function is called internally from the :py:mod:`ws.config` module.

    :param argparser: an instance of :py:class:`argparse.ArgumentParser`
    """
    argparser.add_argument("--log-level", action="store", choices=LOG_LEVELS.keys(), default="info",
            help="the verbosity level for terminal logging (default: %(default)s)")
    argparser.add_argument("-d", "--debug", action="store_const", const="debug", dest="log_level",
            help="shortcut for '--log-level debug'")
    argparser.add_argument("-q", "--quiet", action="store_const", const="warning", dest="log_level",
            help="shortcut for '--log-level warning'")
    # TODO: --log-file

def init(args):
    """
    Initialize the :py:mod:`logging` module with the arguments parsed by
    :py:class:`argparse.ArgumentParser`.

    This function is called internally from the :py:mod:`ws.config` module.

    :param args:
        an instance of :py:class:`argparse.Namespace`. It is expected that
        :py:func:`set_argparser()` was called prior to parsing the arguments.
    """
    logger = logging.getLogger()
    logger.setLevel(LOG_LEVELS[args.log_level])

    # reset alembic logger to its default level
    alembic_logger = logging.getLogger("alembic")
    alembic_logger.setLevel(logging.WARNING)

    setTerminalLogging()
