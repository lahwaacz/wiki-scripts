import argparse
import configparser
import json
import logging
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Self

import ws.logging

logger = logging.getLogger(__name__)

__all__ = [
    "ConfigurableObject",
    "ConfigParser",
    "argtype_bool",
    "argtype_config",
    "argtype_dirname_must_exist",
    "argtype_existing_dir",
    "getArgParser",
    "object_from_argparser",
]

PROJECT_NAME = "wiki-scripts"
CONFIG_DIR = os.getenv("XDG_CONFIG_HOME", os.path.expanduser("~/.config/"))
CONFIG_DIR = os.path.join(CONFIG_DIR, PROJECT_NAME)
DEFAULT_CONF = "default"


class ConfigurableObject(ABC):
    @classmethod
    @abstractmethod
    def set_argparser(cls: type[Self], argparser: argparse.ArgumentParser) -> None:
        """
        Abstract method to add arguments for constructing an instance to an
        :py:class:`argparse.ArgumentParser`.
        """
        ...

    @classmethod
    @abstractmethod
    def from_argparser(cls: type[Self], args: argparse.Namespace) -> Self:
        """
        Abstract factory method to create an instance from
        :py:class:`argparse.Namespace`.
        """
        ...


class ConfigParser(configparser.ConfigParser):
    """
    Drop-in replacement for :py:class:`configparser.Configparser`.
    """

    def __init__(self, configfile: str | Path, **kwargs: Any):
        kwargs.setdefault("interpolation", configparser.ExtendedInterpolation())
        super().__init__(**kwargs)
        assert configfile is not None
        self.configfile = configfile

    def fetch_section(
        self, section: str | None = None, to_list: bool = True
    ) -> dict[str, str | list[str]] | list[str]:
        """
        Fetches a specific section from a config file.

        :param str section: section name for fetching.
        :param bool to_list: defines the format of the returned value (see below).
        :returns:
            The data from the fetched config file section. The format is
            a list of strings if ``to_list=True`` (default value) and
            a dictionary otherwise.
        """
        with open(self.configfile) as f:
            self.read_file(f)

        if section is None:
            section, _ = os.path.splitext(os.path.basename(sys.argv[0]))
        if not self.has_section(section):
            section = configparser.DEFAULTSECT

        option_dict: dict[str, str | list[str]] = {}
        for key, value_str in self.items(section):
            if len(key) == 1:
                msg = f"short options are not allowed in a config file: '{key}'"
                raise argparse.ArgumentTypeError(msg)
            value_str = value_str.strip()
            if value_str.startswith("["):
                option_dict[key] = [str(item) for item in json.loads(value_str)]
            else:
                option_dict[key] = value_str

        if to_list is True:
            option_list = []
            for key, value in option_dict.items():
                option_list.append("--" + key)
                if isinstance(value, list):
                    option_list.extend(value)
                else:
                    option_list.append(value)
            return option_list
        return option_dict

    @staticmethod
    def set_argparser(argparser: argparse.ArgumentParser) -> None:
        group = argparser.add_mutually_exclusive_group()
        group.add_argument(
            "-c",
            "--config",
            type=argtype_config,
            metavar="PATH_OR_NAME",
            default=DEFAULT_CONF,
            help=f"path to the config file, or a base file name for config files looked up as {CONFIG_DIR}/<name>.conf (default: %(default)s)",
        )
        group.add_argument(
            "--no-config",
            dest="config",
            const=None,
            action="store_const",
            help="do not read any config file",
        )


# strict string to bool conversion
def argtype_bool(string: str) -> bool:
    string = string.lower()
    true_values = {"yes", "true", "on", "1"}
    false_values = {"no", "false", "off", "0"}
    if string in true_values:
        return True
    elif string in false_values:
        return False
    else:
        raise argparse.ArgumentTypeError(
            f"value '{string}' cannot be converted to boolean"
        )


def argtype_config(string: str | Path) -> str | None:
    """
    Compute config filepath and check its existence.
    """
    dirname = os.path.dirname(string)
    name, ext = os.path.splitext(os.path.basename(string))

    # configuration name was specified
    if not dirname and ext != ".conf":
        path = os.path.join(CONFIG_DIR, str(string) + ".conf")
    # relative or absolute path was specified
    else:
        if ext != ".conf":
            raise argparse.ArgumentTypeError(
                f"config filename must end with '.conf' suffix: '{string}'"
            )
        path = os.path.abspath(os.path.expanduser(string))

    if not os.path.exists(path):
        if os.path.islink(path):
            raise argparse.ArgumentTypeError(f"symbolic link is broken: '{path}'")
        elif string == DEFAULT_CONF:
            return None
        else:
            raise argparse.ArgumentTypeError(f"file does not exist: '{path}'")
    return path


# path to existing directory
def argtype_existing_dir(string: str | Path) -> str:
    string = os.path.abspath(os.path.expanduser(string))
    if not os.path.isdir(string):
        raise argparse.ArgumentTypeError(f"directory '{string}' does not exist")
    return string


# any path, the dirname part must exist (e.g. path to a file that will be created in the future)
def argtype_dirname_must_exist(string: str | Path) -> str:
    string = os.path.abspath(os.path.expanduser(string))
    dirname, _ = os.path.split(string)
    if not os.path.isdir(dirname):
        raise argparse.ArgumentTypeError(f"directory '{dirname}' does not exist")
    return string


def getArgParser(**kwargs: Any) -> argparse.ArgumentParser:
    """
    Create an instance of :py:class:`argparse.ArgumentParser` and set the global
    arguments (e.g. for logging).

    :param kwargs: passed to :py:class:`argparse.ArgumentParser()` constructor.
    :returns: an instance of :py:class:`argparse.ArgumentParser`.
    """
    kwargs.setdefault("usage", "%(prog)s [options]")
    kwargs.setdefault("formatter_class", argparse.RawDescriptionHelpFormatter)
    kwargs.setdefault("allow_abbrev", False)
    msg = (
        "\n\nArgs that start with '--' (e.g., --log-level) can also be set in a config file (specified via -c)."
        " If an arg is specified in more than one place, then commandline values override config file values"
        " which override defaults."
    )
    kwargs["description"] = kwargs.get("description", "") + msg

    # create the main parser and add global arguments
    ap = argparse.ArgumentParser(**kwargs)
    ConfigParser.set_argparser(ap)
    ws.logging.set_argparser(ap)

    return ap


def parse_args(
    argparser: argparse.ArgumentParser, section: str | None = None
) -> argparse.Namespace:
    """
    Parses arguments given on the command line as well as in the config file.

    Additionally, logging interface is set up using the :py:mod:`ws.logging`
    module.

    :param argparser:
        An instance of :py:class:`argparse.ArgumentParser`. It **must** be
        created by calling the :py:func:`getArgParser` function, otherwise this
        function may access undefined arguments.
    :param str section:
        The name of the subsection to be read from the configuration file
        (usually the name of the script). By default ``sys.argv[0]`` is taken.
    :returns:
        an instance of :py:class:`argparse.Namespace` with the parsed arguments.
    """
    # parser for '--config' and '--no-config' options
    conf_ap = argparse.ArgumentParser(add_help=False)
    ConfigParser.set_argparser(conf_ap)

    cli_args = sys.argv[1:]
    config_args: list[str] = []
    args = argparse.Namespace()

    conf_ap.parse_known_args(cli_args, namespace=args)

    # read the config file and fetch the script-related section
    if args.config is not None:
        cfp = ConfigParser(args.config)
        config_args += cfp.fetch_section(section)

    # parsing
    _, remainder = argparser.parse_known_args(config_args + cli_args, namespace=args)
    unrecogn_cli_args = []
    for item in remainder:
        if item.startswith("-") and item in cli_args:
            unrecogn_cli_args.append(item)
    if unrecogn_cli_args:
        argparser.error(f"unrecognized arguments: {' '.join(unrecogn_cli_args)}")

    # set up logging
    ws.logging.init(args)
    logger.debug(f"Parsed arguments:\n{args}")

    return args


def object_from_argparser[
    T: ConfigurableObject
](cls: type[T], section: str | None = None, **kwargs: Any) -> T:
    """
    Create an instance of ``cls`` using its :py:meth:`cls.from_argparser()`
    factory and an instance of :py:class:`argparse.ArgumentParser`.

    :param cls: the class to instantiate
    :param str section: passed to :py:func:`parse_args`
    :param kwargs: passed to :py:func:`getArgParser`
    :returns: an instance of :py:class:`cls`
    """
    ap = getArgParser(**kwargs)
    cls.set_argparser(ap)
    args = parse_args(ap, section)
    return cls.from_argparser(args)
