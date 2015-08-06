#! /usr/bin/env python3

# TODO:
#   global docstring
#       document how the ws module uses logging - Logger names, verbosity levels etc.
#       document how scripts should use the ws.logging submodule
#   make default options configurable (depends on issue #3)

import logging

def setTerminalLogging(level=logging.INFO):
    # create console handler and set level
    handler = logging.StreamHandler()
    handler.setLevel(level)

    # create formatter
    try:
        import colorlog
        formatter = colorlog.ColoredFormatter(
            "{log_color}{levelname}{reset:8} {message_log_color}{message}",
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
    logger.setLevel(level)

    return logger
